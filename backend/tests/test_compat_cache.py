"""Compat render cache + gzip (app/compat/cache.py): repeated 1 s dashboard refreshes reuse the rendered
body, and every kind of write the reads depend on invalidates it."""

from __future__ import annotations

import concurrent.futures
import gzip
import sqlite3
import threading
import time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from sqlalchemy import text

from app.compat import cache, mappers, spending_index
from app.compat import schemas as S
from app.config import Settings
from app.core.clock import FrozenClock, SequentialIdFactory
from app.db.models import ImportBatch, PlanningPeriod
from app.main import create_app
from app.schemas.forecasts import ForecastResult, TeamProjection
from app.seed.northstar import seed
from app.services import people as people_svc

API = "/compat/api"
IMPORTER = {"X-Actor-Id": "imp-1", "X-Actor-Role": "importer"}
ANALYST = {"X-Actor-Id": "fa-1", "X-Actor-Role": "finance_analyst"}
EXTRA = ("record_id,occurred_at,source_account,provider,cost_category,value_kind,amount,unit\n"
         "{key},2026-10-18T00:00:00Z,ws-research,openai,direct_api,simulated,{amount},USD\n")


@pytest.fixture
def c(seeded) -> TestClient:
    with TestClient(seeded) as client:
        yield client


def stats(client) -> tuple[int, int]:
    store = cache.cache_for(client.app.state)
    return store.hits, store.misses


def total(rows) -> Decimal:
    return sum((Decimal(str(r["amount"])) for r in rows), Decimal("0"))


def add_person(client, person_id: str) -> None:
    """An ORM write in its own session, as the people loader does (no compat route writes people)."""
    s = client.app.state.session_factory()
    try:
        people_svc.create_people(s, [{"id": person_id, "team": "product", "name": "New Person"}],
                                 clock=client.app.state.clock)
        s.commit()
    finally:
        s.close()


def import_row(c, key: str, amount: str) -> None:
    r = c.post("/api/imports", data={"source_kind": "northstar_billing"},
               files={"file": (f"{key}.csv", EXTRA.format(key=key, amount=amount).encode(), "text/csv")},
               headers=IMPORTER)
    assert r.status_code in (200, 201), r.text


def index(client) -> spending_index.SpendingIndex:
    return spending_index.index_for(client.app.state)


def full_body(client, **filters) -> bytes:
    """What a from-scratch build renders now (a fresh index: one full rebuild)."""
    s = client.app.state.session_factory()
    try:
        period = s.query(PlanningPeriod).one()
        return spending_index.SpendingIndex().body(s, period.id, **filters).raw
    finally:
        s.close()


def test_repeated_spending_reads_hit_the_cache_with_identical_bodies(c):
    first = c.get(f"{API}/spending")
    idx = index(c)
    builds = (idx.full_builds, idx.incremental_updates)
    second = c.get(f"{API}/spending")
    assert second.content == first.content
    assert (idx.full_builds, idx.incremental_updates) == builds == (1, 0)
    TypeAdapter(list[S.SpendingRecord]).validate_python(second.json())
    # A filtered query is served from the same index (no rebuild).
    rows = c.get(f"{API}/spending?teamId=product").json()
    assert rows and {r["teamId"] for r in rows} == {"product"}
    assert (idx.full_builds, idx.incremental_updates) == (1, 0)


def test_spending_matches_the_uncached_build_byte_for_byte(c):
    """The rendered body equals the old full path: mappers.spending over every record, rendered once."""
    s = c.app.state.session_factory()
    try:
        records = spending_index.spend_rows(s, s.query(PlanningPeriod).one().id)
        labels = {b.id: (b.source_label or b.filename or b.source_kind) for b in s.query(ImportBatch)}
    finally:
        s.close()
    expected = cache.render(list[S.SpendingRecord], mappers.spending(records, batch_labels=labels))
    assert c.get(f"{API}/spending", headers={"Accept-Encoding": "identity"}).content == expected


def test_live_imports_update_spending_incrementally(c):
    """An append (live feed) re-maps only the touched rows; the result equals a full rebuild, filters too."""
    c.get(f"{API}/spending")
    idx = index(c)
    import_row(c, "live-a", "1.25")   # an existing row (research, Oct 18, openai) changes
    body = c.get(f"{API}/spending", headers={"Accept-Encoding": "identity"}).content
    assert (idx.full_builds, idx.incremental_updates) == (1, 1)
    assert body == full_body(c)
    r = c.post("/api/imports", data={"source_kind": "northstar_billing"},
               files={"file": ("new.csv", ("record_id,occurred_at,source_account,provider,cost_category,value_kind,"
                                           "amount,unit\nlive-b,2026-10-19T00:00:00Z,ws-research,newprov,direct_api,"
                                           "simulated,2.00,USD\n").encode(), "text/csv")},
               headers=IMPORTER)
    assert r.status_code in (200, 201), r.text  # a brand-new row key (new provider) is inserted in order
    body = c.get(f"{API}/spending", headers={"Accept-Encoding": "identity"}).content
    assert idx.full_builds == 1 and idx.incremental_updates == 2
    assert body == full_body(c) and b"newprov" in body
    q = "?teamId=research&from=2026-10-18&to=2026-10-19"
    assert c.get(f"{API}/spending{q}", headers={"Accept-Encoding": "identity"}).content == \
        full_body(c, team_id="research", date_from="2026-10-18", date_to="2026-10-19")


def test_in_place_change_rebuilds_spending_fully(c):
    c.get(f"{API}/spending")
    idx = index(c)
    r = c.put("/api/team-mappings", json={"source_kind": "northstar_billing", "source_account": "ws-research",
                                          "team_id": "product", "effective_from": "2026-01-01"}, headers=ANALYST)
    assert r.status_code == 200, r.text
    body = c.get(f"{API}/spending", headers={"Accept-Encoding": "identity"}).content
    assert idx.full_builds == 2 and body == full_body(c)


def test_concurrent_misses_build_once():
    """Single-flight: concurrent callers on one missing key wait for one build and share its value."""
    store = cache.ResponseCache()
    started, release = threading.Event(), threading.Event()
    calls = []

    def build():
        calls.append(1)
        started.set()
        release.wait(5)
        return "body"

    results = []
    threads = [threading.Thread(target=lambda: results.append(store.get_or_build("k", build))) for _ in range(4)]
    for t in threads:
        t.start()
    started.wait(5)
    time.sleep(0.05)
    release.set()
    for t in threads:
        t.join(5)
    assert results == ["body"] * 4 and len(calls) == 1 and store.builds == 1


def test_concurrent_spending_requests_share_one_update(c):
    c.get(f"{API}/spending")
    idx = index(c)
    import_row(c, "live-c", "3.00")
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        bodies = list(pool.map(lambda _: c.get(f"{API}/spending").content, range(4)))
    assert len(set(bodies)) == 1 and idx.incremental_updates == 1 and idx.full_builds == 1


def test_table_generation_tracks_in_place_writes_not_appends(c):
    before = cache.table_generation("usage_records")
    import_row(c, "live-d", "1.00")
    assert cache.table_generation("usage_records") == before  # an append
    s = c.app.state.session_factory()
    try:
        s.execute(text("UPDATE usage_records SET amount = amount WHERE 0"))
        s.commit()
    finally:
        s.close()
    assert cache.table_generation("usage_records") != before


def test_new_usage_import_invalidates_spending(c):
    before = total(c.get(f"{API}/spending").json())
    c.get(f"{API}/spending")
    import_row(c, "live-1", "123.45")
    assert total(c.get(f"{API}/spending").json()) == before + Decimal("123.45")
    import_row(c, "live-2", "10.00")  # each live-feed import shows on the next refresh
    assert total(c.get(f"{API}/spending").json()) == before + Decimal("133.45")


def test_idempotent_reimport_keeps_the_cache(c):
    import_row(c, "live-1", "5.00")
    body = c.get(f"{API}/spending").content
    import_row(c, "live-1", "5.00")  # same record key: nothing new
    assert c.get(f"{API}/spending").content == body


def test_in_place_remap_invalidates_spending(c):
    """A mapping change updates usage rows in place (no new rowid): the write generation catches it."""
    before = {r["teamId"] for r in c.get(f"{API}/spending").json()}
    assert "research" in before
    r = c.put("/api/team-mappings", json={"source_kind": "northstar_billing", "source_account": "ws-research",
                                          "team_id": "product", "effective_from": "2026-01-01"}, headers=ANALYST)
    assert r.status_code == 200, r.text
    assert r.json()["reattributed_records"] > 0
    after = {r["teamId"] for r in c.get(f"{API}/spending").json()}
    assert "research" not in after


def test_rows_appended_by_another_process_invalidate_spending(c, settings):
    """A writer outside this process (a loader on the same file) fires no SQLAlchemy event; the latest
    usage rowid in the data stamp still moves."""
    body = c.get(f"{API}/spending").json()
    con = sqlite3.connect(settings.db_path)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(usage_records)")]
        row = dict(zip(cols, con.execute(
            "SELECT * FROM usage_records WHERE cost_category = 'direct_api' AND amount IS NOT NULL LIMIT 1").fetchone()))
        row.update(id="ur_external", source_record_key="external-1", amount="1.00")
        con.execute(f"INSERT INTO usage_records ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                    [row[k] for k in cols])
        con.commit()
    finally:
        con.close()
    assert total(c.get(f"{API}/spending").json()) == total(body) + Decimal("1.00")


def test_people_cache_invalidates_on_person_writes(c):
    people = c.get(f"{API}/people").json()
    h0, _ = stats(c)
    assert c.get(f"{API}/people").json() == people and stats(c)[0] == h0 + 1
    rolled_back = c.app.state.session_factory()  # a flushed-then-rolled-back write leaves nothing stale
    try:
        people_svc.create_people(rolled_back, [{"id": "zz-gone", "team": "product", "name": "Gone"}],
                                 clock=c.app.state.clock)
        rolled_back.rollback()
    finally:
        rolled_back.close()
    assert "zz-gone" not in {p["id"] for p in c.get(f"{API}/people").json()}
    add_person(c, "zz-new")
    assert "zz-new" in {p["id"] for p in c.get(f"{API}/people").json()}


def test_gzip_when_accepted_plain_otherwise(c):
    plain = c.get(f"{API}/spending", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers
    # httpx decodes transparently; read the raw stream to see the wire form.
    with c.stream("GET", f"{API}/spending", headers={"Accept-Encoding": "gzip"}) as r:
        raw = b"".join(r.iter_raw())
        assert r.headers["content-encoding"] == "gzip"
    assert len(raw) < len(plain.content) and gzip.decompress(raw) == plain.content
    # Uncached routes are compressed by the middleware.
    with c.stream("GET", f"{API}/documents", headers={"Accept-Encoding": "gzip"}) as r:
        assert r.headers.get("content-encoding") == "gzip"


def test_budgets_are_the_allocations(c):
    rows = TypeAdapter(list[S.Budget]).validate_python(c.get(f"{API}/budgets").json())
    assert {b.teamId: b.allocated for b in rows} == {"engineering": 60000, "product": 80000, "research": 60000}
    assert {b.version for b in rows} == {"1"}


# ---- forecast mapping cache -------------------------------------------------------------------


class FixedProvider:
    """Returns the same result object until told otherwise, like a provider that caches its results."""

    name = "fixed"

    def __init__(self) -> None:
        self.set(Decimal("1000.00"))

    def set(self, amount: Decimal) -> None:
        self.amount, self.result = amount, None

    def get_forecast(self, period_id, team_ids):
        if self.result is None or self.result.target_period != period_id:
            self.result = ForecastResult(
                provider=self.name, availability="available", target_period=period_id, method_label="fixed test",
                projections=[TeamProjection(team=t, amount=self.amount) for t in team_ids])
        return self.result


@pytest.fixture
def fc(tmp_path, clock):
    provider = FixedProvider()
    app = create_app(Settings(db_path=tmp_path / "f.db"), clock=clock, id_factory=SequentialIdFactory(),
                     forecast_provider=provider)
    s = app.state.session_factory()
    try:
        assert seed(s, clock=app.state.clock, ids=app.state.id_factory)
    finally:
        s.close()
    with TestClient(app) as client:
        yield client, provider


def test_forecast_mapping_is_reused_until_the_provider_result_changes(fc):
    c, provider = fc
    first = c.get(f"{API}/forecasts")
    assert {f["projected"] for f in first.json() if "personId" not in f} == {1000}
    h0, m0 = stats(c)
    assert c.get(f"{API}/forecasts").content == first.content and stats(c) == (h0 + 1, m0)
    provider.set(Decimal("2000.00"))
    teams = [f for f in c.get(f"{API}/forecasts").json() if "personId" not in f]
    assert {f["projected"] for f in teams} == {2000}
    TypeAdapter(list[S.Forecast]).validate_python(c.get(f"{API}/forecasts").json())


def test_forecast_cache_sees_people_changes(fc):
    c, _ = fc
    ids = {f.get("personId") for f in c.get(f"{API}/forecasts").json()}
    add_person(c, "zz-new")
    assert "zz-new" in {f.get("personId") for f in c.get(f"{API}/forecasts").json()} - ids

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
from app.db.models import ImportBatch, PlanningPeriod
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
    with c.app.state.session_factory() as session:
        before = cache.table_generation(session, "usage_records")
    import_row(c, "live-d", "1.00")
    with c.app.state.session_factory() as session:
        assert cache.table_generation(session, "usage_records") == before
        session.execute(text("UPDATE usage_records SET amount = amount WHERE rowid=(SELECT MIN(rowid) FROM usage_records)"))
        session.commit()
    with c.app.state.session_factory() as session:
        assert cache.table_generation(session, "usage_records") != before


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


def test_external_update_delete_and_batch_label_changes_invalidate(c, settings):
    before = total(c.get(f"{API}/spending").json())
    idx = index(c)
    with sqlite3.connect(settings.db_path) as con:
        row_id, old_amount, batch_id = con.execute(
            "SELECT id,amount,import_batch_id FROM usage_records WHERE cost_category='direct_api' AND amount IS NOT NULL LIMIT 1"
        ).fetchone()
        con.execute("UPDATE usage_records SET amount=? WHERE id=?", (str(Decimal(old_amount) + Decimal('0.01')), row_id))
    assert total(c.get(f"{API}/spending").json()) == before + Decimal('0.01')
    assert idx.full_builds == 2
    with sqlite3.connect(settings.db_path) as con:
        con.execute("UPDATE import_batches SET source_label=? WHERE id=?", ('Corrected source label', batch_id))
    rows = c.get(f"{API}/spending").json()
    assert any('Corrected source label' in r['source'] for r in rows)
    assert idx.full_builds == 3
    with sqlite3.connect(settings.db_path) as con:
        con.execute("DELETE FROM usage_records WHERE id=?", (row_id,))
    assert total(c.get(f"{API}/spending").json()) == before - Decimal(old_amount)
    assert idx.full_builds == 4


def test_uncommitted_and_rolled_back_edits_never_poison_cached_response(c, settings):
    original = c.get(f"{API}/spending").content
    con = sqlite3.connect(settings.db_path)
    try:
        con.execute("UPDATE usage_records SET amount='0.00' WHERE counts_toward_spend=1")
        assert c.get(f"{API}/spending").content == original
        con.rollback()
    finally:
        con.close()
    assert c.get(f"{API}/spending").content == original
    assert index(c).full_builds == 1


def test_incremental_index_retains_models_provenance_tokens_notional_and_unknown_identity(c, settings):
    c.get(f"{API}/spending")
    with sqlite3.connect(settings.db_path) as con:
        columns = [r[1] for r in con.execute('PRAGMA table_info(usage_records)')]
        base = dict(zip(columns, con.execute("SELECT * FROM usage_records WHERE cost_category='direct_api' AND amount IS NOT NULL LIMIT 1").fetchone()))
        changes = [
            {'model': 'model-a', 'value_kind': 'measured', 'amount': '0.25', 'input_tokens': 100, 'cached_input_tokens': 60, 'output_tokens': 40, 'reasoning_tokens': 10},
            {'model': 'model-a', 'value_kind': 'measured', 'amount': '0.75', 'input_tokens': None, 'output_tokens': 0},
            {'model': 'model-b', 'value_kind': 'measured', 'amount': '-0.10', 'input_tokens': 90, 'output_tokens': 10},
            {'model': 'model-a', 'value_kind': 'estimated', 'amount': '0.05', 'input_tokens': 90, 'output_tokens': 10},
            {'model': None, 'team_id': None, 'person_id': None, 'cost_category': 'unpriced_usage', 'counts_toward_spend': 0,
             'amount': None, 'value_kind': 'measured', 'input_tokens': 900, 'output_tokens': 100},
            {'model': 'model-a', 'cost_category': 'included_usage', 'counts_toward_spend': 0, 'amount': None,
             'value_kind': 'measured', 'notional_value': '4.25'},
            {'model': 'model-a', 'cost_category': 'included_usage', 'counts_toward_spend': 0, 'amount': None,
             'value_kind': 'measured', 'notional_value': None},
        ]
        for number, change in enumerate(changes):
            row = {**base, 'id': f'index-proof-{number}', 'source_record_key': f'index-proof-{number}',
                   'provider': 'index-proof', 'input_tokens': None, 'cached_input_tokens': None,
                   'output_tokens': None, 'reasoning_tokens': None, **change}
            con.execute(f"INSERT INTO usage_records ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                        [row[key] for key in columns])
    response = c.get(f"{API}/spending", headers={'Accept-Encoding': 'identity'})
    assert index(c).incremental_updates == 1 and index(c).full_builds == 1
    assert response.content == full_body(c)
    rows = [r for r in response.json() if r['provider'] == 'index-proof']
    assert len(rows) == 5
    billed = {(r['model'], r['provenance']): r for r in rows if r['component'] == 'api'}
    assert billed['model-a', 'measured']['amount'] == 1
    assert billed['model-a', 'measured'].get('tokens') is None
    assert billed['model-a', 'measured']['outputTokens'] == 40
    assert billed['model-b', 'measured']['amount'] == -0.1
    assert billed['model-a', 'estimate']['amount'] == 0.05
    unpriced = next(r for r in rows if r['component'] == 'unpriced_usage')
    assert unpriced['amount'] == 0 and unpriced['tokens'] == 1000
    assert unpriced['teamId'] == 'unattributed' and unpriced['complete'] is False
    assert 'model' not in unpriced and 'personId' not in unpriced
    included = next(r for r in rows if r['component'] == 'included_usage')
    assert included['amount'] == 0 and included.get('includedUsageNotional') is None


def test_atomic_reset_reinstalls_revision_tracking_and_clears_old_index(c):
    from app.seed.northstar import reset_database
    before = c.get(f"{API}/spending").content
    import_row(c, 'before-reset', '123.45')
    assert c.get(f"{API}/spending").content != before
    state = c.app.state
    reset_database(state.engine, state.session_factory, clock=state.clock, ids=state.id_factory,
                   forecast_store=state.forecast_service.store, settings=state.settings, forecast_provider=state.forecast_provider)
    assert c.get(f"{API}/spending").content == before
    import_row(c, 'after-reset', '1.00')
    assert c.get(f"{API}/spending").content == full_body(c)


def test_external_replace_invalidates_old_group_even_without_recursive_triggers(c, settings):
    c.get(f"{API}/spending")
    with sqlite3.connect(settings.db_path) as con:
        assert con.execute('PRAGMA recursive_triggers').fetchone()[0] == 0
        columns = [r[1] for r in con.execute('PRAGMA table_info(usage_records)')]
        row = dict(zip(columns, con.execute("SELECT * FROM usage_records WHERE cost_category='direct_api' AND amount IS NOT NULL LIMIT 1").fetchone()))
        row.update(amount='0.01', model='replacement-model', value_kind='measured')
        con.execute(f"INSERT OR REPLACE INTO usage_records ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                    [row[key] for key in columns])
    assert c.get(f"{API}/spending", headers={'Accept-Encoding': 'identity'}).content == full_body(c)
    assert index(c).full_builds == 2


def test_external_replaced_batch_label_rebuilds_unchanged_usage(c, settings):
    c.get(f"{API}/spending")
    with sqlite3.connect(settings.db_path) as con:
        columns = [r[1] for r in con.execute('PRAGMA table_info(import_batches)')]
        row = dict(zip(columns, con.execute('SELECT * FROM import_batches LIMIT 1').fetchone()))
        row['source_label'] = 'Replacement source label'
        con.execute(f"INSERT OR REPLACE INTO import_batches ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                    [row[key] for key in columns])
    response = c.get(f"{API}/spending", headers={'Accept-Encoding': 'identity'})
    assert response.content == full_body(c)
    assert any('Replacement source label' in r['source'] for r in response.json())

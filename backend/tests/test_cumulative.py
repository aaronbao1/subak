"""Acceptance check 2: repeated cumulative telemetry must not masquerade as new usage."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.db import models as m
from app.services.imports import StreamState, to_deltas
from app.services.parsers.base import ParsedRecord
from reference_data import codex_lines, seed_reference, upload, usage

ACCT = "codex-research-laptops"


@pytest.fixture(autouse=True)
def _ref(session):
    seed_reference(session)


def codex(client, text, **kw):
    return upload(client, text, source_kind="codex_sessions", filename=kw.pop("filename", "rollout.jsonl"),
                  source_account=kw.pop("source_account", ACCT), **kw)


def totals(session, field="input_tokens"):
    session.expire_all()
    col = getattr(m.UsageRecord, field)
    return session.scalar(select(func.coalesce(func.sum(col), 0)))


def test_repeated_cumulative_snapshot_yields_zero_delta(client, session):
    text = codex_lines("s1", [
        ("2026-10-02T10:00:00Z", usage(100, 40, 10)),
        ("2026-10-02T10:00:05Z", usage(100, 40, 10)),  # re-emitted unchanged
        ("2026-10-02T10:00:09Z", usage(100, 40, 10)),
        ("2026-10-02T10:05:00Z", usage(250, 90, 30, 5)),
    ])
    body = codex(client, text).json()
    assert body["status"] == "imported"
    assert body["record_count"] == 2
    assert body["stats"]["repeated_snapshots_skipped"] == 2
    assert totals(session) == 250
    assert totals(session, "output_tokens") == 30
    assert totals(session, "reasoning_tokens") == 5


def test_monotonic_counters_sum_to_final_value(client, session):
    snaps = [(f"2026-10-03T10:{i:02d}:00Z", usage(100 * (i + 1), 10 * i, 7 * (i + 1))) for i in range(6)]
    codex(client, codex_lines("s2", snaps))
    assert totals(session) == 600
    assert totals(session, "cached_input_tokens") == 50
    assert totals(session, "output_tokens") == 42
    recs = session.scalars(select(m.UsageRecord).order_by(m.UsageRecord.occurred_at)).all()
    assert [r.input_tokens for r in recs] == [100] * 6
    assert recs[-1].cumulative_snapshot["input_tokens"] == 600  # raw counter kept for audit


def test_counter_decrease_flagged_as_reset_and_partial_coverage(client, session):
    text = codex_lines("s3", [
        ("2026-10-04T10:00:00Z", usage(500, 0, 50)),
        ("2026-10-04T11:00:00Z", usage(80, 0, 8)),  # decreased -> reset
        ("2026-10-04T12:00:00Z", usage(120, 0, 12)),
    ])
    body = codex(client, text).json()
    assert body["stats"]["counter_resets"] == 1
    assert any(w["code"] == "counter_reset" for w in body["warnings"])
    assert totals(session) == 500 + 80 + 40
    reset = session.scalars(select(m.UsageRecord).where(m.UsageRecord.counter_reset.is_(True))).one()
    assert reset.input_tokens == 80
    cov = client.get("/api/coverage").json()
    research = next(t for t in cov["teams"] if t["team"] == "research")
    assert research["status"] == "partial" and research["counter_resets"] == 1
    assert cov["company"]["status"] == "partial"


def test_reimport_same_session_file_is_duplicate(client, session):
    text = codex_lines("s4", [("2026-10-05T10:00:00Z", usage(10, 0, 1))])
    codex(client, text)
    r = codex(client, text)
    assert r.status_code == 200 and r.json()["status"] == "duplicate"
    assert totals(session) == 10


def test_growing_session_file_reimport_adds_only_new_usage(client, session):
    """A live session file re-exported later (different bytes, same prefix) adds only the delta."""
    early = [("2026-10-06T10:00:00Z", usage(100, 0, 10)), ("2026-10-06T10:10:00Z", usage(300, 0, 20))]
    later = early + [("2026-10-06T10:20:00Z", usage(450, 0, 25))]
    codex(client, codex_lines("s5", early))
    body = codex(client, codex_lines("s5", later)).json()
    assert body["record_count"] == 1
    assert body["stats"]["repeated_snapshots_skipped"] == 2
    assert totals(session) == 450
    new = session.scalars(select(m.UsageRecord).order_by(m.UsageRecord.occurred_at.desc())).first()
    assert new.input_tokens == 150 and new.counter_reset is False


def test_continuation_file_uses_stored_baseline(client, session):
    codex(client, codex_lines("s6", [("2026-10-07T10:00:00Z", usage(1000, 0, 100))]))
    codex(client, codex_lines("s6", [("2026-10-07T11:00:00Z", usage(1200, 0, 130))]), filename="part2.jsonl")
    assert totals(session) == 1200
    assert totals(session, "output_tokens") == 130


def test_out_of_order_snapshot_is_skipped_not_double_counted(client, session):
    codex(client, codex_lines("s7", [("2026-10-08T12:00:00Z", usage(500, 0, 50))]))
    body = codex(client, codex_lines("s7", [("2026-10-08T11:00:00Z", usage(200, 0, 20))])).json()
    assert body["record_count"] == 0
    assert body["stats"]["out_of_order_skipped"] == 1
    assert totals(session) == 500


def test_tokens_are_measured_unpriced_never_spend(client, session):
    codex(client, codex_lines("s8", [("2026-10-09T10:00:00Z", usage(10, 0, 1))]))
    rec = session.scalars(select(m.UsageRecord)).one()
    assert rec.value_kind == "measured"
    assert rec.cost_category == "unpriced_usage"
    assert rec.amount is None and rec.counts_toward_spend is False
    assert rec.team_id == "research"
    assert rec.model == "gpt-5-codex" and rec.stream_key == "codex:s8"


def test_codex_without_source_account_is_unattributed(client, session):
    body = upload(client, codex_lines("s9", [("2026-10-09T10:00:00Z", usage(10, 0, 1))]),
                  source_kind="codex_sessions", filename="r.jsonl").json()
    assert body["unmapped_record_count"] == 1
    assert session.scalars(select(m.UsageRecord)).one().team_id is None


def test_codex_null_info_truncated_line_and_missing_session(client, session):
    text = codex_lines("s10", [("2026-10-09T10:00:00Z", None), ("2026-10-09T10:01:00Z", usage(10, 0, 1))])
    orphan = codex_lines("zz", [("2026-10-09T09:00:00Z", usage(5, 0, 1))], meta_first=False)
    body = codex(client, orphan + text + '{"timestamp": "2026-10-09T10:0').json()
    assert body["record_count"] == 1
    assert body["stats"]["token_events_without_usage"] == 1
    codes = {w["code"] for w in body["warnings"]}
    assert {"truncated_last_line", "token_count_without_session"} <= codes


def test_codex_file_without_token_events_fails(client):
    r = codex(client, '{"timestamp":"2026-10-09T10:00:00Z","type":"session_meta","payload":{"id":"x"}}\n')
    assert r.status_code == 422
    assert r.json()["error"]["details"]["batch"]["errors"][0]["code"] == "no_records"


def test_two_sessions_in_one_upload_are_separate_streams(client, session):
    text = codex_lines("a", [("2026-10-10T10:00:00Z", usage(100, 0, 1))]) + \
        codex_lines("b", [("2026-10-10T10:00:00Z", usage(100, 0, 1))])
    body = codex(client, text).json()
    assert body["record_count"] == 2
    assert totals(session) == 200


def _rec(ts_min: int, i: int, stream="s") -> ParsedRecord:
    return ParsedRecord(
        row=ts_min, occurred_at=datetime(2026, 10, 1, 0, ts_min, tzinfo=timezone.utc),
        cost_category="unpriced_usage", value_kind=None, stream_key=stream,
        cumulative={"input_tokens": i, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0},
    )


def test_to_deltas_unit_ordering_and_prior_baseline():
    out, stats = to_deltas([_rec(3, 30), _rec(1, 10), _rec(2, 10), _rec(4, 45)],
                           {"s": StreamState(last_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                                             last_counter={"input_tokens": 5})})
    assert [r.tokens["input_tokens"] for r, _ in out] == [5, 20, 15]
    assert stats.repeated_snapshots == 1 and stats.counter_resets == 0

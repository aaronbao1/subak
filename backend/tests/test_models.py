from datetime import date, datetime, timezone

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db import models as m
from app.main import create_app

T0 = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)

EXPECTED_TABLES = {
    "planning_periods", "teams", "team_mappings", "import_batches", "usage_records",
    "budget_envelopes", "budget_allocations", "budget_snapshots", "proposals", "decisions",
    "decision_events", "corpus_documents", "context_signals", "signal_citations",
    "forecast_snapshots", "agent_runs", "agent_run_steps",
}


def _base(session):
    session.add(m.PlanningPeriod(id="2026-P1", label="Northstar planning period",
                                 starts_on=date(2026, 10, 1), ends_on=date(2026, 12, 31)))
    session.add_all([m.Team(id=t, name=t.title()) for t in ("research", "product", "engineering")])
    batch = m.ImportBatch(source_kind="northstar_billing", content_hash="h1", status="imported",
                          imported_by="importer-1", value_kind_default="simulated")
    session.add(batch)
    session.flush()
    return batch


def _usage(batch, **kw):
    data = dict(import_batch_id=batch.id, source_kind="northstar_billing", source_record_key="r1",
                period_id="2026-P1", occurred_at=T0, value_kind="simulated",
                cost_category="direct_api", counts_toward_spend=True, amount="100.00")
    data.update(kw)
    return m.UsageRecord(**data)


def test_all_design_tables_created(app):
    assert EXPECTED_TABLES <= set(inspect(app.state.engine).get_table_names())


def test_foreign_keys_enforced(session):
    session.add(m.BudgetAllocation(envelope_id="missing", team_id="research", amount="1.00"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unattributed_is_not_a_team_row(session):
    session.add(m.Team(id="unattributed", name="Unattributed"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_usage_record_key_unique_per_source(session):
    batch = _base(session)
    session.add(_usage(batch))
    session.flush()
    session.add(_usage(batch))
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("category", ["included_usage", "unpriced_usage"])
def test_included_or_unpriced_usage_cannot_count_toward_spend(session, category):
    batch = _base(session)
    session.add(_usage(batch, cost_category=category, counts_toward_spend=True))
    with pytest.raises(IntegrityError):
        session.flush()


def test_billable_category_must_count_toward_spend(session):
    batch = _base(session)
    session.add(_usage(batch, cost_category="billable_overage", counts_toward_spend=False))
    with pytest.raises(IntegrityError):
        session.flush()


def test_derive_counts_toward_spend():
    assert m.UsageRecord.derive_counts_toward_spend("included_usage") is False
    assert m.UsageRecord.derive_counts_toward_spend("unpriced_usage") is False
    for c in ("subscription_fee", "billable_overage", "direct_api"):
        assert m.UsageRecord.derive_counts_toward_spend(c) is True


def test_negative_token_delta_rejected(session):
    batch = _base(session)
    session.add(_usage(batch, input_tokens=-5))
    with pytest.raises(IntegrityError):
        session.flush()


def test_identical_import_hash_only_once_while_duplicates_allowed(session):
    batch = _base(session)
    session.add(m.ImportBatch(source_kind="northstar_billing", content_hash="h1", status="duplicate",
                              duplicate_of_batch_id=batch.id, imported_by="i", value_kind_default="simulated"))
    session.flush()  # duplicate-status rows do not collide
    session.add(m.ImportBatch(source_kind="northstar_billing", content_hash="h1", status="imported",
                              imported_by="i", value_kind_default="simulated"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unknown_enum_value_rejected(session):
    _base(session)
    session.add(m.Proposal(period_id="2026-P1", unit="USD", action_type="mixed", base_version=1,
                           envelope_increase="0.00", lines=[], before={}, after={}, rationale="x",
                           created_by_actor="a", created_by_role="droid_agent", origin="droid_run"))
    with pytest.raises(IntegrityError):
        session.flush()


def _proposal(session):
    _base(session)
    p = m.Proposal(period_id="2026-P1", unit="USD", action_type="transfer", base_version=1,
                   envelope_increase="0.00", lines=[], before={}, after={}, rationale="r",
                   created_by_actor="droid-1", created_by_role="droid_agent", origin="droid_run")
    session.add(p)
    session.flush()
    return p


def _decision(p, **kw):
    data = dict(proposal_id=p.id, outcome="approved_applied", actor_id="fin-1", actor_role="finance_approver",
                rationale="ok", idempotency_key="k1", request_fingerprint="f", from_version=1, to_version=2,
                before={}, after={}, decided_at=T0)
    data.update(kw)
    return m.Decision(**data)


@pytest.mark.parametrize(
    "kw",
    [
        {"rationale": "   "},
        {"to_version": 3},
        {"outcome": "rejected", "to_version": 2},
        {"outcome": "approved_applied", "to_version": None},
    ],
)
def test_decision_invariants(session, kw):
    p = _proposal(session)
    session.add(_decision(p, **kw))
    with pytest.raises(IntegrityError):
        session.flush()


def test_one_decision_per_proposal(session):
    p = _proposal(session)
    session.add(_decision(p))
    session.flush()
    session.add(_decision(p, idempotency_key="k2"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_naive_datetime_rejected_and_aware_returned(session):
    _base(session)
    session.add(m.ForecastSnapshot(period_id="2026-P1", provider="placeholder", availability="available",
                                   payload={}, fetched_at=datetime(2026, 10, 24, 12, 0)))
    with pytest.raises(Exception):
        session.flush()
    session.rollback()
    _base(session)
    snap = m.ForecastSnapshot(period_id="2026-P1", provider="placeholder", availability="available",
                              payload={}, fetched_at=T0)
    session.add(snap)
    session.commit()
    session.expire_all()
    got = session.get(m.ForecastSnapshot, snap.id)
    assert got.fetched_at == T0 and got.fetched_at.tzinfo is not None


def test_data_persists_across_app_restart(db_path):
    s = Settings(db_path=db_path)
    app1 = create_app(s)
    with app1.state.session_factory() as sess:
        sess.add(m.Team(id="research", name="Research"))
        sess.commit()
    app1.state.engine.dispose()

    app2 = create_app(s)
    with app2.state.session_factory() as sess:
        assert sess.scalars(select(m.Team.id)).all() == ["research"]
    app2.state.engine.dispose()

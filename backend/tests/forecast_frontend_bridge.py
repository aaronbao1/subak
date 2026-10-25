"""Line-delimited test transport for the real frontend client and FastAPI app.

This replaces only the TCP transport. Requests still traverse TestClient,
FastAPI validation, SQLite, the worker, numerical engine and Droid toolbox.
It does not install test routes in the product or substitute API responses.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import sys
from tempfile import TemporaryDirectory
import traceback

from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.clock import FrozenClock, SequentialIdFactory
from app.forecasting.demo import create_demo_app, observed_inputs
from app.forecasting.directory import snapshot_people
from app.forecasting.fixtures import northstar_evidence, northstar_spending_records
from app.db.models import Person, UsageRecord
from app.seed.northstar import seed
from app.seed.interpret import interpret_at_seed
from app.services.imports import run_import


def import_coherent_observed_actuals(app, snapshot, clock):
    """Test-only native directory and ledger with the forecast fixture's identities.

    Synthetic emails are explicit fixture identifiers; none are inferred contacts.
    Source observations have total tokens without a native input/output split, so
    this cost import intentionally leaves token categories unknown.
    """
    with app.state.session_factory() as session:
        for person in snapshot_people(snapshot):
            if session.get(Person, person.id) is None:
                person.email = f"{person.id}@forecast-fixture.invalid"
                person.created_at = clock.now()
                session.add(person)
        session.commit()
    rows = []
    for row in northstar_spending_records(snapshot):
        rows.append({
            "record_id": row["id"], "occurred_at": row["date"] + "T00:00:00Z",
            "source_account": "ws-" + row["teamId"], "cost_category": "direct_api",
            "value_kind": "simulated", "amount": str(Decimal(str(row["amount"])).quantize(Decimal(".01"))),
            "unit": "USD", "provider": "Northstar synthetic fixture", "model": "classic",
            **({"user_email": f"{row['personId']}@forecast-fixture.invalid"} if row.get("personId") else {}),
        })
    return import_fixture_rows(app, rows, clock, "coherent-observed-actuals.json")


def import_fixture_rows(app, rows, clock, filename):
    with app.state.session_factory() as session:
        result = run_import(session, source_kind="northstar_billing", raw=json.dumps(rows).encode(),
                            filename=filename, actor_id="fixture", clock=clock, ids=app.state.id_factory,
                            value_kind_default="simulated")
        if result.batch.status not in {"imported", "duplicate"}:
            raise RuntimeError(result.batch.error_details)
        session.commit()
        return {"status": result.batch.status, "id": result.batch.id}


def validate_posted_fixture_week(snapshot, records, start, end):
    """Attest this synthetic ledger only after every source charge is accounted for.

    Generic repository records do not establish completeness. The independent
    fixture's explicit complete source manifest does, after exact ID, attribution,
    and posted-money agreement. Informational/unpriced rows do not add dollars.
    """
    ledger_snapshot = deepcopy(snapshot)
    ledger_snapshot['period_start'], ledger_snapshot['period_end'] = start, end
    expected = {row['id']: row for row in northstar_spending_records(ledger_snapshot)}
    days = {(date.fromisoformat(start) + timedelta(days=i)).isoformat()
            for i in range((date.fromisoformat(end) - date.fromisoformat(start)).days)}
    assert len(days) == 7 and {row['date'] for row in expected.values()} == days
    assert all(row['complete'] is True for row in expected.values())
    charges = [row for row in records if row['counts_toward_spend']]
    assert len(charges) == len(expected) and {row['source_record_key'] for row in charges} == set(expected)
    for row in charges:
        source = expected[row['source_record_key']]
        assert row['source_kind'] == 'northstar_billing' and row['cost_category'] == 'direct_api'
        assert row['value_kind'] == 'simulated' and row['unit'] == 'USD'
        assert row['team_id'] == (None if source['teamId'] == 'unattributed' else source['teamId'])
        assert row['person_id'] == source.get('personId')
        assert str(row['occurred_at'])[:10] == source['date']
        assert Decimal(str(row['amount'])) == Decimal(str(source['amount'])).quantize(Decimal('.01'))
    return charges


def posted_fixture_week(app, snapshot, start, end, clock):
    with app.state.session_factory() as session:
        rows = session.scalars(select(UsageRecord).where(
            UsageRecord.occurred_at >= datetime.fromisoformat(start).replace(tzinfo=timezone.utc),
            UsageRecord.occurred_at < datetime.fromisoformat(end).replace(tzinfo=timezone.utc),
            UsageRecord.created_at <= clock.now()))
        records = [{field: getattr(row, field) for field in ('source_record_key', 'source_kind', 'cost_category',
                    'value_kind', 'unit', 'team_id', 'person_id', 'occurred_at', 'amount', 'counts_toward_spend')}
                   for row in rows]
    return validate_posted_fixture_week(snapshot, records, start, end)


def posted_fixture_value(target, records):
    def scoped(row):
        kind, ident = target['scope_type'], target['scope_id']
        if kind == 'company': return True
        if kind == 'team': return row['team_id'] == ident
        if kind == 'person': return row['person_id'] == ident
        if kind == 'shared' and ident == 'shared': return row['team_id'] is None and row['person_id'] is None
        if kind == 'shared' and ident == 'people_unallocated': return row['team_id'] is not None and row['person_id'] is None
        if kind == 'shared' and ident == 'teams_unallocated': return row['team_id'] is None and row['person_id'] is not None
        raise ValueError(f'Unknown posted fixture scope {kind}/{ident}')
    return sum((Decimal(str(row['amount'])) for row in records if scoped(row)), Decimal('0.00'))


def import_synthetic_token_examples(app, clock):
    """Independent synthetic telemetry examples; no dollar-to-token estimation."""
    common = {"occurred_at": "2026-10-24T12:00:00Z", "source_account": "ws-research",
              "user_email": "maya@forecast-fixture.invalid", "model": "example-model",
              "cost_category": "unpriced_usage", "value_kind": "simulated", "unit": "USD"}
    return import_fixture_rows(app, [
        {**common, "record_id": "token-example-a", "provider": "Synthetic provider A",
         "input_tokens": 100, "output_tokens": 20, "cached_input_tokens": 80, "reasoning_tokens": 10},
        {**common, "record_id": "token-example-b", "provider": "Synthetic provider B",
         "input_tokens": 200, "output_tokens": 30, "cached_input_tokens": 150, "reasoning_tokens": 15},
        {**common, "record_id": "token-example-zero", "provider": "Synthetic provider A",
         "occurred_at": "2026-10-25T12:00:00Z", "input_tokens": 0, "output_tokens": 0,
         "cached_input_tokens": 0, "reasoning_tokens": 0},
    ], clock, "explicit-synthetic-token-examples.json")


def interpret_fixture_corpus(app, clock):
    result = interpret_at_seed(app.state.session_factory, settings=app.state.settings, clock=clock,
                               ids=app.state.id_factory, mode="fake", forecast_provider=app.state.forecast_provider)
    if not result.succeeded:
        raise RuntimeError(result.error)


def mature_company_week(app, clock, run_id):
    """Attest only independent complete source observations after the target ends."""
    service = app.state.forecast_service
    target = next(record['payload'] for record in service.store.input_records(clock.now().isoformat(), kinds='issued_targets')
                  if record['payload']['run_id'] == run_id and record['payload']['scope_type'] == 'company'
                  and record['payload']['aggregation'] == 'weekly' and record['payload']['lead_days'] == 0)
    assert target['end'] <= clock.now().date().isoformat()
    snapshot = observed_inputs(now=clock.now().isoformat())
    rows = [r for r in snapshot['observations'] if target['start'] <= r['date'] < target['end']]
    assert len({r['date'] for r in rows}) == 7 and all(r['complete'] and r['mature'] for r in rows)
    actual = posted_fixture_value(target, posted_fixture_week(app, snapshot, target['start'], target['end'], clock))
    result = service.ingest_outcome({**{key: target[key] for key in ('quantity', 'unit', 'basis', 'timezone', 'scope_type', 'scope_id', 'start', 'end')},
        'target_id': target['target_id'], 'revision': 1, 'available_at': clock.now().isoformat(), 'mature_at': clock.now().isoformat(),
        'status': 'mature', 'value': float(actual), 'source_id': 'integration-independent-week:' + target['start'],
        'is_synthetic': True, 'complete': True, 'provenance': {'kind': 'observed', 'reference': 'northstar-complete-posted-ledger-cents-v1:' + target['start']}})
    return {'receipt': result, 'actual': str(actual), 'target_id': target['target_id'], 'prediction': target['prediction']}


def main():
    clock = FrozenClock(datetime(2026, 10, 26, tzinfo=timezone.utc))
    with TemporaryDirectory(prefix="forecast-frontend-") as directory:
        app = create_demo_app(directory, clock)
        app.state.id_factory = SequentialIdFactory()
        with app.state.session_factory() as session:
            seed(session, clock=clock, ids=app.state.id_factory, include_spend=False)
        import_coherent_observed_actuals(app, observed_inputs(now=clock.now().isoformat()), clock)
        interpret_fixture_corpus(app, clock)
        with TestClient(app) as client:
            for line in sys.stdin:
                message = json.loads(line)
                try:
                    if message["operation"] == "request":
                        response = client.request(message.get("method", "GET"), message["path"],
                                                  headers=message.get("headers"), content=message.get("body"))
                        result = {"status": response.status_code, "body": response.text,
                                  "headers": dict(response.headers)}
                    elif message["operation"] == "work":
                        result = app.state.forecast_worker.process_one(job_id=message.get("job_id"))
                    elif message["operation"] == "events":
                        result = northstar_evidence()
                    elif message["operation"] == "token_examples":
                        result = import_synthetic_token_examples(app, clock)
                    elif message["operation"] == "mature_company_week":
                        result = mature_company_week(app, clock, message["run_id"])
                    elif message["operation"] == "advance":
                        clock.advance(days=message["days"])
                        import_coherent_observed_actuals(app, observed_inputs(now=clock.now().isoformat()), clock)
                        result = clock.now().isoformat()
                    else:
                        raise ValueError("Unknown test transport operation")
                    output = {"id": message["id"], "result": result}
                except Exception:
                    output = {"id": message["id"], "error": traceback.format_exc()}
                print(json.dumps(output, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()

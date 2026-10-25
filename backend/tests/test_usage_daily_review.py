"""Independent daily-usage checks for missingness and historical scope identity."""

from app.db.models import Person
from test_usage_daily import daily, ledger  # Shared native-record fixture.


def test_person_transfer_does_not_reassign_historical_usage(ledger, client, session):
    ledger("before-transfer", amount="2.00", team="active", person="alice")
    session.get(Person, "alice").team_id = "inactive"
    session.commit()
    assert daily(client, scope_type="person", scope_id="alice")["buckets"][1]["recorded_spend"] == "2.00"
    assert daily(client, scope_type="team", scope_id="active")["buckets"][1]["recorded_spend"] == "2.00"
    assert daily(client, scope_type="team", scope_id="inactive")["buckets"][1]["recorded_spend"] is None


def test_mixed_paired_and_unpaired_tokens_retain_observation_denominators(ledger, client):
    ledger("paired", input_tokens=100, output_tokens=20, cached_input_tokens=80)
    ledger("input-only", input_tokens=10)
    ledger("charge-only", amount="1.00")
    bucket = daily(client)["buckets"][1]
    assert bucket["record_count"] == 3
    assert bucket["tokens"] == {"input_tokens": 110, "output_tokens": 20, "cached_input_tokens": 80,
                                 "reasoning_tokens": None, "total_tokens": None}
    assert bucket["token_observed_record_counts"] == {
        "input_tokens": 2, "output_tokens": 1, "cached_input_tokens": 1, "reasoning_tokens": 0, "total_tokens": 1,
    }


def test_known_nonbillable_zero_is_distinct_from_absent_provenance(ledger, client):
    ledger("unpriced", category="unpriced_usage", kind="measured", amount=None, input_tokens=10, output_tokens=0)
    bucket = daily(client)["buckets"][1]
    assert bucket["recorded_spend"] == "0.00"
    assert bucket["costs_by_value_kind"] == {"reported": None, "estimated": None, "measured": "0.00", "simulated": None}
    assert bucket["tokens"]["total_tokens"] == 10
    assert bucket["coverage"] == "partial"


def test_partial_included_notional_does_not_become_a_complete_known_value(ledger, client):
    ledger("known", category="included_usage", amount=None, notional="5.00")
    ledger("unknown", category="included_usage", amount=None)
    bucket = daily(client)["buckets"][1]
    assert bucket["included_usage_notional"] is None
    assert bucket["recorded_spend"] == "0.00"

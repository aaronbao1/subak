"""Usage detail survives the compatibility mapper without changing billable totals."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.compat.mappers import spending


def record(**changes):
    row = {
        "team": "research", "person": "analyst", "occurred_at": datetime(2026, 10, 18, tzinfo=timezone.utc),
        "provider": "openai", "model": "gpt-a", "cost_category": "direct_api", "value_kind": "reported",
        "amount": Decimal("3.25"), "counts_toward_spend": True, "unit": "USD", "counter_reset": False,
        "import_batch_id": "billing", "source_kind": "billing", "notional_value": None,
        "input_tokens": None, "cached_input_tokens": None, "output_tokens": None, "reasoning_tokens": None,
    }
    return {**row, **changes}


def mapped(*records):
    return spending(records, batch_labels={"billing": "Provider usage export"})


@pytest.mark.parametrize("native,expected", [
    ("reported", "reported_charge"), ("estimated", "estimate"),
    ("measured", "measured"), ("simulated", "simulated"),
])
def test_native_provenance_survives_for_billable_and_included_usage(native, expected):
    billable = mapped(record(value_kind=native))[0]
    included = mapped(record(value_kind=native, cost_category="included_usage", amount=None,
                             counts_toward_spend=False, notional_value=Decimal("9.75")))[0]
    assert billable["amount"] == 3.25
    assert billable["provenance"] == expected
    assert included["amount"] == 0
    assert included["provenance"] == expected
    assert included["includedUsageNotional"] == 9.75


def test_models_and_provenance_do_not_merge_or_share_ids():
    rows = mapped(record(), record(model="gpt-b"), record(value_kind="simulated"), record(amount=Decimal("1.75")))
    assert len(rows) == 3
    assert len({row["id"] for row in rows}) == 3
    assert {(row["model"], row["provenance"]): row["amount"] for row in rows} == {
        ("gpt-a", "reported_charge"): 5, ("gpt-b", "reported_charge"): 3.25, ("gpt-a", "simulated"): 3.25,
    }


def test_token_totals_do_not_double_count_cached_and_reasoning_subsets():
    row = mapped(
        record(input_tokens=100, cached_input_tokens=80, output_tokens=40, reasoning_tokens=30),
        record(input_tokens=10, cached_input_tokens=0, output_tokens=5, reasoning_tokens=0),
    )[0]
    assert {key: row[key] for key in ("tokens", "inputTokens", "cachedInputTokens", "outputTokens", "reasoningTokens")} == {
        "tokens": 155, "inputTokens": 110, "cachedInputTokens": 80, "outputTokens": 45, "reasoningTokens": 30,
    }


def test_partial_token_telemetry_stays_unknown_instead_of_becoming_a_complete_total():
    row = mapped(record(input_tokens=100, output_tokens=40), record(input_tokens=None, output_tokens=0))[0]
    assert row["inputTokens"] is None
    assert row["outputTokens"] == 40
    assert row["tokens"] is None
    assert row["cachedInputTokens"] is None
    assert row["reasoningTokens"] is None


def test_known_zero_tokens_remain_zero_and_missing_model_is_not_invented():
    row = mapped(record(model=None, input_tokens=0, cached_input_tokens=0, output_tokens=0, reasoning_tokens=0))[0]
    assert row.get("model") is None
    assert row["tokens"] == 0
    assert row["inputTokens"] == row["cachedInputTokens"] == row["outputTokens"] == row["reasoningTokens"] == 0


def test_unpriced_usage_retains_measured_tokens_without_adding_billable_dollars():
    rows = mapped(record(), record(cost_category="unpriced_usage", value_kind="measured", amount=None,
                                   counts_toward_spend=False, input_tokens=900, output_tokens=100))
    assert len(rows) == 2
    assert sum(row["amount"] for row in rows) == 3.25
    unpriced = next(row for row in rows if row["component"] == "unpriced_usage")
    assert unpriced["amount"] == 0
    assert unpriced["provenance"] == "measured"
    assert unpriced["tokens"] == 1000
    assert unpriced["complete"] is True


def test_partial_included_notional_stays_unknown():
    row = mapped(
        record(cost_category="included_usage", amount=None, counts_toward_spend=False, notional_value=Decimal("4.25")),
        record(cost_category="included_usage", amount=None, counts_toward_spend=False),
    )[0]
    assert row["includedUsageNotional"] is None
    assert "notional value $4.25" not in row["source"]
    assert row["amount"] == 0

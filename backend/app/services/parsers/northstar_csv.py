"""Northstar billing export (simulated). CSV or JSON with the same per-record fields.

Columns: record_id, occurred_at, source_account, cost_category, amount, [user_email, provider, model,
value_kind, unit, notional_value, input_tokens, cached_input_tokens, output_tokens, reasoning_tokens,
description].

Rules (master plan §2, backend plan "Major features"):
- Team attribution comes ONLY from team mappings. A `team` column is ignored with a warning.
- subscription_fee / billable_overage / direct_api require a non-negative amount.
- included_usage carries no charge (amount blank or 0); its list value goes in notional_value.
- unpriced_usage must not carry an amount: a token count is not a dollar cost.
- `user_email` (optional) names who used it. It is lowercased and only ever matched against the people
  directory at import time; it never decides the team.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.core.money import MoneyError, parse_money
from app.db.models import COST_CATEGORIES, VALUE_KINDS
from app.services.parsers.base import (
    TOKEN_FIELDS,
    FieldError,
    ParsedRecord,
    ParseIssue,
    ParseResult,
    parse_timestamp,
    parse_token_count,
)

SOURCE_KIND = "northstar_billing"
REQUIRED = ("record_id", "occurred_at", "source_account", "cost_category")
OPTIONAL = (
    "user_email", "amount", "provider", "model", "value_kind", "unit", "notional_value", "description", *TOKEN_FIELDS,
)
CHARGED = frozenset({"subscription_fee", "billable_overage", "direct_api"})
ATTRIBUTION_COLUMNS = frozenset({"team", "team_id", "owner"})
MAX_EMAIL = 320


def _email(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    text = text.lower()
    if "@" not in text or len(text) > MAX_EMAIL or any(c.isspace() for c in text):
        raise FieldError("invalid_user_email", f"user_email must be an email address of at most {MAX_EMAIL} characters")
    return text


def _money_or_none(value: Any, name: str) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return parse_money(value)
    except MoneyError as exc:
        raise FieldError(exc.code, f"{name}: {exc}") from exc


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def parse_row(raw: dict[str, Any], row: int) -> ParsedRecord:
    for col in REQUIRED:
        if _text(raw.get(col)) is None:
            raise FieldError(f"{col}_required", f"{col} is required")
    category = _text(raw["cost_category"])
    if category not in COST_CATEGORIES:
        raise FieldError("unknown_cost_category", f"cost_category must be one of {COST_CATEGORIES}")
    value_kind = _text(raw.get("value_kind"))
    if value_kind is not None and value_kind not in VALUE_KINDS:
        raise FieldError("unknown_value_kind", f"value_kind must be one of {VALUE_KINDS}")
    unit = _text(raw.get("unit")) or "USD"
    if unit != "USD":
        raise FieldError("unsupported_unit", f"only USD is supported, got {unit!r}")

    amount = _money_or_none(raw.get("amount"), "amount")
    notional = _money_or_none(raw.get("notional_value"), "notional_value")
    for name, val in (("amount", amount), ("notional_value", notional)):
        if val is not None and val < 0:
            raise FieldError("negative_amount", f"{name} must not be negative (credits/refunds are not supported)")

    if category in CHARGED and amount is None:
        raise FieldError("amount_required", f"{category} requires an amount")
    if category == "included_usage":
        if amount is not None and amount != 0:
            raise FieldError(
                "included_usage_with_charge",
                "included usage is covered by its subscription fee; put the list value in notional_value",
            )
        amount = None
    if category == "unpriced_usage" and amount is not None:
        raise FieldError("unpriced_usage_with_amount", "unpriced usage must not carry an amount")

    tokens = {f: parse_token_count(raw.get(f), f) for f in TOKEN_FIELDS}
    user_ref = _email(raw.get("user_email"))
    return ParsedRecord(
        row=row,
        source_record_key=_text(raw["record_id"]),
        occurred_at=parse_timestamp(_text(raw["occurred_at"])),
        source_account=_text(raw["source_account"]),
        cost_category=category,
        value_kind=value_kind,
        provider=_text(raw.get("provider")),
        model=_text(raw.get("model")),
        amount=amount,
        unit=unit,
        notional_value=notional,
        tokens=tokens,
        user_ref=user_ref,
    )


def _check_columns(columns: set[str], result: ParseResult) -> None:
    if columns & ATTRIBUTION_COLUMNS:
        result.warnings.append(ParseIssue(
            "team_column_ignored",
            f"column(s) {sorted(columns & ATTRIBUTION_COLUMNS)} ignored: team attribution comes only "
            "from explicit team mappings",
        ))
    unknown = columns - set(REQUIRED) - set(OPTIONAL) - ATTRIBUTION_COLUMNS
    if unknown:
        result.warnings.append(ParseIssue("unknown_columns_ignored", f"ignored columns: {sorted(unknown)}"))


def _collect(rows: list[tuple[int, dict[str, Any]]], result: ParseResult) -> None:
    seen: dict[str, ParsedRecord] = {}
    for row_no, raw in rows:
        try:
            rec = parse_row(raw, row_no)
        except FieldError as exc:
            result.errors.append(ParseIssue(exc.code, str(exc), row_no))
            continue
        prior = seen.get(rec.source_record_key)  # type: ignore[arg-type]
        if prior is not None:
            if prior.fingerprint() == rec.fingerprint():
                result.warnings.append(ParseIssue(
                    "duplicate_row_in_file", f"record_id {rec.source_record_key!r} repeated; counted once", row_no
                ))
                result.bump("duplicate_rows_in_file")
            else:
                result.errors.append(ParseIssue(
                    "conflicting_duplicate_record_id",
                    f"record_id {rec.source_record_key!r} appears with different values (row {prior.row})",
                    row_no,
                ))
            continue
        seen[rec.source_record_key] = rec  # type: ignore[index]
        result.records.append(rec)


def parse_csv(text: str) -> ParseResult:
    result = ParseResult()
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        result.errors.append(ParseIssue("empty_file", "no header row"))
        return result
    columns = {c.strip() for c in reader.fieldnames if c}
    missing = [c for c in REQUIRED if c not in columns]
    if missing:
        result.errors.append(ParseIssue("missing_columns", f"missing required columns: {missing}"))
        return result
    _check_columns(columns, result)
    rows = []
    for i, raw in enumerate(reader, start=2):  # row 1 is the header
        if None in raw:
            result.errors.append(ParseIssue("too_many_fields", "row has more fields than the header", i))
            continue
        clean = {(k or "").strip(): v for k, v in raw.items()}
        if all(not (v or "").strip() for v in clean.values()):
            continue  # blank line
        rows.append((i, clean))
    _collect(rows, result)
    if not result.records and not result.errors:
        result.errors.append(ParseIssue("no_records", "file contains no records"))
    return result


def parse_json(text: str) -> ParseResult:
    result = ParseResult()
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        result.errors.append(ParseIssue("invalid_json", f"invalid JSON: {exc.msg}", exc.lineno))
        return result
    records = doc.get("records") if isinstance(doc, dict) else doc
    if not isinstance(records, list):
        result.errors.append(ParseIssue("invalid_json", 'expected a list or {"records": [...]}'))
        return result
    rows = []
    columns: set[str] = set()
    for i, raw in enumerate(records, start=1):
        if not isinstance(raw, dict):
            result.errors.append(ParseIssue("invalid_record", "record must be an object", i))
            continue
        columns |= set(raw)
        # JSON floats for money are rejected (parse_money raises float_not_allowed).
        rows.append((i, raw))
    _check_columns(columns, result)
    _collect(rows, result)
    if not result.records and not result.errors:
        result.errors.append(ParseIssue("no_records", "file contains no records"))
    return result


def parse(text: str, filename: str | None) -> ParseResult:
    name = (filename or "").lower()
    if name.endswith(".json") or (not name.endswith(".csv") and text.lstrip()[:1] in ("[", "{")):
        return parse_json(text)
    return parse_csv(text)

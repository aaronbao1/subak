"""Codex CLI session telemetry (real local format, JSONL).

Relevant line shapes:
  {"timestamp": ..., "type": "session_meta", "payload": {"id": "<session uuid>", ...}}
  {"timestamp": ..., "type": "turn_context", "payload": {"model": "...", ...}}
  {"timestamp": ..., "type": "event_msg", "payload": {"type": "token_count",
      "info": {"total_token_usage": {"input_tokens", "cached_input_tokens", "output_tokens",
               "reasoning_output_tokens", "total_tokens"}, "last_token_usage": {...}} | null}}

`total_token_usage` is a CUMULATIVE counter per session and is frequently re-emitted unchanged.
The parser only reports cumulative observations; the pipeline turns them into deltas, so repeated
counters never masquerade as new usage. Tokens carry no price: cost_category `unpriced_usage`.
Nothing beyond session id, model, timestamps and token counters is read (no prompts, no paths).
"""

from __future__ import annotations

import json

from app.services.parsers.base import FieldError, ParsedRecord, ParseIssue, ParseResult, parse_timestamp

SOURCE_KIND = "codex_sessions"
COUNTER_MAP = {
    "input_tokens": "input_tokens",
    "cached_input_tokens": "cached_input_tokens",
    "output_tokens": "output_tokens",
    "reasoning_output_tokens": "reasoning_tokens",
}


def _counter(usage: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for src, dst in COUNTER_MAP.items():
        value = usage.get(src, 0)
        if value is None:
            value = 0
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise FieldError("invalid_token_count", f"{src} must be a non-negative integer")
        out[dst] = value
    return out


def parse(text: str, filename: str | None = None) -> ParseResult:
    result = ParseResult()
    session_id: str | None = None
    model: str | None = None
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            code = "truncated_last_line" if i == len(lines) else "invalid_json_line"
            result.warnings.append(ParseIssue(code, "line is not valid JSON; skipped", i))
            result.bump("invalid_lines")
            continue
        if not isinstance(obj, dict):
            continue
        kind = obj.get("type")
        payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
        if kind == "session_meta":
            sid = payload.get("id")
            if isinstance(sid, str) and sid.strip():
                if session_id is not None and sid != session_id:
                    model = None
                session_id = sid.strip()
            continue
        if kind == "turn_context":
            if isinstance(payload.get("model"), str):
                model = payload["model"]
            continue
        if kind != "event_msg" or payload.get("type") != "token_count":
            continue
        info = payload.get("info")
        if not isinstance(info, dict) or not isinstance(info.get("total_token_usage"), dict):
            result.bump("token_events_without_usage")
            continue
        if session_id is None:
            result.warnings.append(ParseIssue(
                "token_count_without_session",
                "token_count before any session_meta; the counter stream is unknown, skipped",
                i,
            ))
            result.bump("token_events_without_session")
            continue
        try:
            occurred_at = parse_timestamp(obj.get("timestamp"))
            counter = _counter(info["total_token_usage"])
        except FieldError as exc:
            result.errors.append(ParseIssue(exc.code, str(exc), i))
            continue
        result.records.append(ParsedRecord(
            row=i,
            occurred_at=occurred_at,
            cost_category="unpriced_usage",
            value_kind=None,
            provider="openai",
            model=model,
            stream_key=f"codex:{session_id}",
            cumulative=counter,
        ))
        result.bump("token_events")
    if not result.records and not result.errors:
        result.errors.append(ParseIssue("no_records", "no token_count events with usage were found"))
    return result

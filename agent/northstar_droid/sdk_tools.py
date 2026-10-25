"""Northstar tools exposed to the real Factory Droid as in-process SDK MCP tools.

`tool_functions(toolbox)` returns plain, fully type-annotated Python functions (the SDK derives each
tool's input schema from the annotations) that call the backend's scoped `BackendToolbox`, i.e. the
backend service layer in the same process. `build_mcp_server(toolbox)` wraps them with
`droid_sdk.mcp.tool` and serves them on the SDK's loopback, token-protected MCP server. The SDK is
imported only inside `build_mcp_server`, so this module imports fine without it.

Names and descriptions come from `app.agent.tools.TOOLS` (the same definitions the fake runner uses).
There is no apply / approve / decide tool (`rebase_proposal` only creates a new pending draft). Droid sees them as `northstar___<tool>` (the ids the runner
passes to `restrict_tools`).
"""

from __future__ import annotations

import json
from typing import Any, Callable

from app.agent.runner import ToolError
from app.agent.tools import TOOL_NAMES, TOOLS

SERVER_NAME = "northstar"
MAX_RESULT_CHARS = 60_000
# Live-verified (droid CLI 0.249.0, droid-sdk 0.5.0): SDK MCP tools are listed as `<server>___<tool>`
# (three underscores) and are reachable from Droid's code-mode `Script` tool as `tools.<server>.<tool>`.
TOOL_ID_SEPARATOR = "___"


def tool_id(name: str) -> str:
    return f"{SERVER_NAME}{TOOL_ID_SEPARATOR}{name}"


NORTHSTAR_TOOL_IDS: frozenset[str] = frozenset(tool_id(n) for n in TOOL_NAMES)


def _respond(fn: Callable[[], dict]) -> str:
    try:
        result = fn()
    except ToolError as exc:
        return json.dumps({"error": exc.as_dict()}, sort_keys=True)
    text = json.dumps(result, sort_keys=True)
    if len(text) > MAX_RESULT_CHARS:
        return json.dumps({"truncated": True, "note": "result too large; narrow the query",
                           "preview": text[:MAX_RESULT_CHARS]})
    return text


def tool_functions(toolbox: Any) -> list[tuple[str, str, Callable[..., str]]]:
    """(name, description, function) for every Northstar tool, bound to one run's toolbox."""

    def search_corpus(query: str = "", team: str | None = None, project: str | None = None,
                      include_superseded: bool = True) -> str:
        return _respond(lambda: toolbox.call("search_corpus", {"query": query, "team": team, "project": project,
                                                               "include_superseded": include_superseded}))

    def read_document(document_id: str) -> str:
        return _respond(lambda: toolbox.call("read_document", {"document_id": document_id}))

    def get_spend_summary() -> str:
        return _respond(lambda: toolbox.call("get_spend_summary", {}))

    def get_budgets() -> str:
        return _respond(lambda: toolbox.call("get_budgets", {}))

    def get_forecast() -> str:
        return _respond(lambda: toolbox.call("get_forecast", {}))

    def explain_forecast(run_id: str, scope_type: str = "company", scope_id: str | None = None,
                         driver_id: str | None = None) -> str:
        return _respond(lambda: toolbox.call("explain_forecast", {"run_id":run_id,"scope_type":scope_type,
                                                                  "scope_id":scope_id,"driver_id":driver_id}))

    def compare_forecasts(run_ids: list[str], scope_type: str = "company", scope_id: str | None = None) -> str:
        return _respond(lambda: toolbox.call("compare_forecasts", {"run_ids":run_ids,"scope_type":scope_type,"scope_id":scope_id}))

    def preview_forecast_scenario(run_id: str, drivers: list[dict[str, Any]], scope_type: str = "company",
                                  scope_id: str | None = None) -> str:
        return _respond(lambda: toolbox.call("preview_forecast_scenario", {"run_id":run_id,"drivers":drivers,
                                                                          "scope_type":scope_type,"scope_id":scope_id}))

    def request_forecast_refresh(idempotency_key: str) -> str:
        return _respond(lambda: toolbox.call("request_forecast_refresh", {"idempotency_key":idempotency_key}))

    def list_signals(status: str | None = None, team: str | None = None, include_company: bool = True) -> str:
        return _respond(lambda: toolbox.call("list_signals", {"status": status, "team": team,
                                                              "include_company": include_company}))

    def list_people(team: str | None = None) -> str:
        return _respond(lambda: toolbox.call("list_people", {"team": team}))

    def build_chart_spec(kind: str, team: str | None = None, metric: str | None = None) -> str:
        return _respond(lambda: toolbox.call("build_chart_spec", {"kind": kind, "team": team, "metric": metric}))

    def record_signal(summary: str, change_type: str, status: str, uncertainty: str,
                      citations: list[dict[str, Any]], team: str | None = None, project: str | None = None,
                      applies_from: str | None = None, applies_to: str | None = None,
                      supersedes_signal_id: str | None = None, scope: str = "team",
                      person_ids: list[str] | None = None, signal_kind: str | None = None,
                      title: str | None = None) -> str:
        signal = {"summary": summary, "change_type": change_type, "status": status, "uncertainty": uncertainty,
                  "citations": citations, "team": team, "project": project, "applies_from": applies_from,
                  "applies_to": applies_to, "supersedes_signal_id": supersedes_signal_id, "scope": scope,
                  "person_ids": person_ids or [], "signal_kind": signal_kind, "title": title}
        return _respond(lambda: toolbox.call("record_signal", {"signal": signal}))

    def draft_proposal(action_type: str, base_version: int, rationale: str, lines: list[dict[str, Any]],
                       envelope_increase: str | None = None,
                       evidence_refs: list[dict[str, Any]] | None = None) -> str:
        proposal: dict[str, Any] = {"action_type": action_type, "base_version": base_version,
                                    "rationale": rationale, "lines": lines, "evidence_refs": evidence_refs or []}
        if envelope_increase is not None:
            proposal["envelope_increase"] = envelope_increase
        return _respond(lambda: toolbox.call("draft_proposal", {"proposal": proposal}))

    def rebase_proposal(proposal_id: str, rationale: str | None = None) -> str:
        return _respond(lambda: toolbox.call("rebase_proposal", {"proposal_id": proposal_id, "rationale": rationale}))

    fns = {f.__name__: f for f in (search_corpus, read_document, get_spend_summary, get_budgets, get_forecast,
                                   list_signals, list_people, build_chart_spec, record_signal, draft_proposal, rebase_proposal,
                                   explain_forecast, compare_forecasts, preview_forecast_scenario, request_forecast_refresh)}
    return [(t.name, t.description, fns[t.name]) for t in TOOLS]


def build_mcp_server(toolbox: Any) -> Any:
    """Requires `droid-sdk[mcp]`. Raises ImportError if it is not installed."""
    from droid_sdk.mcp import create_sdk_mcp_server, tool  # lazy: optional dependency

    tools = [tool(name, description)(fn) for name, description, fn in tool_functions(toolbox)]
    return create_sdk_mcp_server(SERVER_NAME, tools)

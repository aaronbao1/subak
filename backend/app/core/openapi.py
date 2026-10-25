"""OpenAPI post-processing so the published spec matches what the API actually returns.

FastAPI on its own documents 422 as `HTTPValidationError` ({detail: [...]}) and knows nothing about the
domain errors or the alternate success codes. This module:

- adds the `ErrorBody` / `ErrorDetail` components (the `{"error": {code, message, details}}` envelope
  that `app/core/errors.py` returns for every 4xx/5xx) and removes `HTTPValidationError`;
- documents every error status a route can return, each with `ErrorBody` and the `code` values to
  branch on (generic rules: identity headers -> 401/403, path or `period` params -> 404);
- documents alternate success codes: 200 for an idempotent decision replay, a duplicate import or a
  duplicate document; 202 for a background agent run; and the SSE event payload schema.

`tests/test_contract.py` checks that every fixture's (method, path, status) is declared here.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.schemas.agent import AgentEventOut
from app.schemas.common import ErrorBody

REF = "#/components/schemas/{model}"
ERROR_REF = {"$ref": "#/components/schemas/ErrorBody"}

GENERIC_DESCRIPTIONS = {
    400: "Bad request",
    401: "Identity headers missing (`actor_required`)",
    403: "Not allowed",
    404: "Not found",
    409: "Conflict with the current state",
    413: "Payload too large",
    422: "Validation failed (`validation_failed` with `details.errors[]` or `details.reasons[]`)",
    429: "Too many concurrent requests",
    503: "Dependency unavailable",
}

# (method, path) -> {status: [error codes]}. Merged with the generic rules below.
ROUTE_ERRORS: dict[tuple[str, str], dict[int, list[str]]] = {
    ("post", "/api/proposals"): {
        409: ["stale_base_version"],
        422: ["validation_failed", "currency_mismatch", "unknown_team", "negative_allocation_result"],
    },
    ("post", "/api/proposals/{proposal_id}/decision"): {
        400: ["idempotency_key_required", "idempotency_key_invalid"],
        403: ["role_forbidden", "self_approval_forbidden"],
        404: ["proposal_not_found"],
        409: ["stale_proposal", "idempotency_key_reused", "proposal_not_pending", "proposal_no_longer_valid",
              "proposal_state_mismatch"],
        422: ["validation_failed"],
    },
    ("post", "/api/proposals/{proposal_id}/rebase"): {
        404: ["proposal_not_found"],
        409: ["proposal_not_stale", "proposal_not_pending", "stale_base_version"],
        422: ["validation_failed"],
    },
    ("post", "/api/proposals/{proposal_id}/revise"): {
        404: ["proposal_not_found"],
        409: ["proposal_not_pending", "stale_base_version"],
        422: ["validation_failed"],
    },
    ("get", "/api/proposals/{proposal_id}"): {404: ["proposal_not_found"]},
    ("get", "/api/decisions/{decision_id}"): {404: ["decision_not_found"]},
    ("post", "/api/imports"): {
        413: ["file_too_large"],
        422: ["import_failed", "unknown_source_kind", "unknown_value_kind", "source_account_not_allowed",
              "validation_failed"],
    },
    ("post", "/api/documents"): {
        409: ["already_superseded"],
        422: ["validation_failed", "version_predates_current", "supersedes_same_key", "supersedes_newer_document",
              "supersedes_target_not_found", "front_matter_required", "invalid_front_matter"],
    },
    ("post", "/api/signals"): {422: ["validation_failed", "citation_not_found", "signal_cites_superseded_only"]},
    ("patch", "/api/signals/{signal_id}"): {404: ["not_found"], 422: ["validation_failed"]},
    ("delete", "/api/signals/{signal_id}"): {404: ["not_found"], 409: ["signal_in_use"]},
    ("put", "/api/team-mappings"): {422: ["validation_failed", "unknown_team"]},
    ("post", "/api/agent/runs"): {
        422: ["validation_failed", "unknown_team", "non_positive_amount", "invalid_params", "unexpected_params"],
        429: ["runner_busy"],
        503: ["runner_unavailable"],
    },
    ("post", "/api/admin/reset"): {403: ["reset_disabled"]},
    ("post", "/api/forecasts/snapshots"): {404: ["unknown_period"]},
    ("get", "/api/charts/{kind}"): {404: ["unknown_chart_kind"], 422: ["unknown_metric", "unknown_team",
                                                                     "team_not_applicable"]},
}

# (method, path) -> {status: (description, component name)} for success codes besides the default one.
EXTRA_SUCCESS: dict[tuple[str, str], dict[int, tuple[str, str]]] = {
    ("post", "/api/proposals/{proposal_id}/decision"): {
        200: ("Idempotent replay: same Idempotency-Key and body; the stored decision with `replayed: true`. "
              "Nothing is applied twice.", "DecisionOut"),
    },
    ("post", "/api/imports"): {
        200: ("Duplicate file: identical bytes were already imported; `status: duplicate`, nothing added.",
              "ImportResult"),
    },
    ("post", "/api/documents"): {
        200: ("Duplicate: identical content and metadata already stored; `created: false`.",
              "DocumentIngestResult"),
    },
    ("post", "/api/agent/runs"): {
        202: ("Accepted (`wait=false`): the run continues in the background; follow its events.", "AgentRunOut"),
    },
}


def _error_response(status: int, codes: list[str] | None) -> dict:
    desc = GENERIC_DESCRIPTIONS.get(status, "Error")
    if codes:
        desc = f"{desc}. `error.code`: " + ", ".join(f"`{c}`" for c in codes)
    return {"description": desc, "content": {"application/json": {"schema": ERROR_REF}}}


def _add_components(schema: dict) -> None:
    comps = schema.setdefault("components", {}).setdefault("schemas", {})
    for model in (ErrorBody, AgentEventOut):
        js = model.model_json_schema(ref_template=REF)
        for name, sub in js.pop("$defs", {}).items():
            comps.setdefault(name, sub)
        comps[model.__name__] = js
    comps.pop("HTTPValidationError", None)
    comps.pop("ValidationError", None)


def patch_openapi(schema: dict) -> dict:
    _add_components(schema)
    for path, item in schema.get("paths", {}).items():
        for method, op in item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            responses: dict[str, Any] = op.setdefault("responses", {})
            params = op.get("parameters", [])
            names = {p.get("name", "").lower() for p in params}
            statuses: dict[int, list[str]] = {}
            if "x-actor-id" in names:
                statuses.setdefault(401, []).append("actor_required")
                statuses.setdefault(403, []).extend(["unknown_role", "role_forbidden"])
            if any(p.get("in") == "path" for p in params):
                statuses.setdefault(404, []).append("not_found")
            if "period" in names:
                statuses.setdefault(404, []).extend(["unknown_period", "no_budget", "no_periods"])
            if "422" in responses:
                statuses.setdefault(422, []).append("validation_failed")
            for status, codes in ROUTE_ERRORS.get((method, path), {}).items():
                statuses.setdefault(status, []).extend(codes)
            for status, codes in sorted(statuses.items()):
                unique = list(dict.fromkeys(codes))
                responses[str(status)] = _error_response(status, unique)
            for status, (desc, model) in EXTRA_SUCCESS.get((method, path), {}).items():
                responses[str(status)] = {
                    "description": desc,
                    "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{model}"}}},
                }
            if (method, path) == ("get", "/api/agent/runs/{run_id}/events"):
                responses["200"] = {
                    "description": "Server-Sent Events. Each event: `id: <seq>`, `event: <type>`, "
                                   "`data: <AgentEventOut as JSON>`; the stream ends after `run_finished`.",
                    "content": {"text/event-stream": {"schema": {"$ref": "#/components/schemas/AgentEventOut"}}},
                }
    return schema


def install_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, description=app.description,
                             routes=app.routes)
        app.openapi_schema = patch_openapi(schema)
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

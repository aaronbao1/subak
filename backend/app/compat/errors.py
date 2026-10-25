"""Compat error rendering: backend codes -> the plain-English `{"error": "..."}` the frontend shows verbatim.

The frontend's HttpDataClient reads `json.error` as a string and throws it as the message, so the
backend's `{"error": {"code", "message", "details"}}` would render as "[object Object]". Compat routes
answer `{"error": "<plain English>", "code": "<backend code>"}` instead. The global error handlers
for `/api/*` are unchanged.
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from app.core.errors import DomainError

ALREADY_APPLIED = "This proposal was already applied; it cannot be applied or rejected again."
ALREADY_REJECTED = "This proposal was already rejected."
STALE = ("The budget changed after this proposal was drafted, so it was not applied. Ask the assistant for a "
         "refreshed proposal, or dismiss this one.")
NOT_SEEDED = "The database is not seeded yet; run `python -m app.seed`."

MESSAGES: dict[str, str] = {
    "stale_proposal": STALE,
    "already_applied": ALREADY_APPLIED,
    "already_rejected": ALREADY_REJECTED,
    "self_approval_forbidden": "You asked for this change, so you cannot approve it. Another finance approver must decide.",
    "role_forbidden": "Your role cannot approve or reject proposals. Only a finance approver can.",
    "unknown_role": "Unknown demo role.",
    "actor_required": "Send both X-Actor-Id and X-Actor-Role, or neither.",
    "proposal_no_longer_valid": "This proposal no longer fits the current budget. Ask for a refreshed proposal.",
    "proposal_state_mismatch": "The saved budget differs from what this proposal was reviewed against. Ask for a refreshed proposal.",
    "idempotency_key_reused": "A different decision was already recorded for this proposal.",
    "proposal_not_found": "That proposal does not exist.",
    "not_seeded": NOT_SEEDED,
    "no_periods": "No planning period is configured yet. Seed the backend first (python -m app.seed).",
    "unknown_period": "Unknown planning period.",
    "no_budget": "No budget is configured for the current period. Seed the backend first (python -m app.seed).",
    "validation_failed": "The request was not valid.",
    "runner_unavailable": "The assistant is unavailable right now. Nothing was changed.",
    "runner_busy": "The assistant is busy. Try again in a moment.",
}


def plain_message(code: str, message: str, details: dict[str, Any] | None = None) -> str:
    details = details or {}
    if code == "proposal_not_pending":
        status = details.get("status")
        if status == "applied":
            return ALREADY_APPLIED
        if status == "rejected":
            return ALREADY_REJECTED
        if status == "stale":
            return STALE
        if status == "revised":
            return "This proposal was replaced by a revised one and can no longer be decided."
        return f"This proposal is {status or 'not pending'} and cannot be decided."
    if code == "validation_failed":
        reasons = details.get("reasons") or details.get("errors") or []
        texts = [str(r.get("message") or r.get("msg")) for r in reasons if isinstance(r, dict)
                 and (r.get("message") or r.get("msg"))]
        if texts:
            return "The request was not valid: " + "; ".join(texts[:3]) + "."
    return MESSAGES.get(code) or (message[:1].upper() + message[1:] if message else "Request failed.")


def error_response(status: int, code: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": plain_message(code, message, details), "code": code})


def from_domain(exc: DomainError) -> JSONResponse:
    return error_response(exc.status, exc.code, exc.message, exc.details)

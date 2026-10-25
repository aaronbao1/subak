"""Demo reset. Disabled unless BACKEND_ALLOW_RESET=1; drops all data and reseeds the Northstar example
(with the stand-in interpretation, so context signals labeled `droid_fake` exist again)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.errors import DomainError
from app.seed.northstar import reset_database

router = APIRouter(prefix="/api", tags=["admin"])


@router.post("/admin/reset")
def reset(request: Request) -> dict:
    state = request.app.state
    if not state.settings.allow_reset:
        raise DomainError("reset_disabled", 403, "reset is disabled; set BACKEND_ALLOW_RESET=1 to enable it")
    reset_database(state.engine, state.session_factory, clock=state.clock, ids=state.id_factory,
                   settings=state.settings, forecast_provider=state.forecast_provider)
    return {"status": "reset", "seeded": True}

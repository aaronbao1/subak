"""App factory: settings, DB, CORS, error envelope, routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.core.clock import Clock, IdFactory, SystemClock, UuidIdFactory
from app.core.errors import install_error_handlers
from app.core.openapi import install_openapi
from app.db.base import check_schema, create_all, make_engine, make_session_factory
from app.providers.forecast import ForecastProvider, provider_from_settings


def create_app(
    settings: Settings | None = None,
    *,
    clock: Clock | None = None,
    id_factory: IdFactory | None = None,
    forecast_provider: ForecastProvider | None = None,
    droid_runner: Any | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()

    engine = make_engine(settings.db_path)
    create_all(engine)
    check_schema(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(title="Northstar AI-spend backend", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.clock = clock or SystemClock()
    app.state.id_factory = id_factory or UuidIdFactory()
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.forecast_provider = forecast_provider or provider_from_settings(settings.forecast_provider)
    # Providers that read history themselves (ForecastingPackageProvider) get the session factory.
    if callable(getattr(app.state.forecast_provider, "bind", None)):
        app.state.forecast_provider.bind(app.state.session_factory, app.state.clock)
    # None: the runner is selected per run from settings (DROID_RUNNER), so a missing Factory key is a
    # visible 503 on the run, not a startup crash. Tests may inject a runner.
    app.state.droid_runner = droid_runner

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Idempotency-Key"],
    )
    install_error_handlers(app)

    health = APIRouter()

    @health.get("/health")
    def _health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(health)
    app.include_router(health, prefix="/api")

    from app.api import (
        routes_admin,
        routes_agent,
        routes_budget,
        routes_charts,
        routes_decisions,
        routes_documents,
        routes_forecasts,
        routes_imports,
        routes_meta,
        routes_people,
        routes_proposals,
        routes_signals,
        routes_spending,
        routes_teams,
    )

    for module in (
        routes_meta,
        routes_teams,
        routes_people,
        routes_imports,
        routes_spending,
        routes_budget,
        routes_forecasts,
        routes_charts,
        routes_documents,
        routes_signals,
        routes_proposals,
        routes_decisions,
        routes_agent,
        routes_admin,
    ):
        app.include_router(module.router)
    if settings.compat:
        from app.compat.router import router as compat_router

        # Kept out of openapi.json: the main contract and its --check stay unchanged.
        app.include_router(compat_router, include_in_schema=False)
    install_openapi(app)

    return app


def run() -> None:  # pragma: no cover - entry point
    import uvicorn

    settings = Settings.from_env()
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port)


if __name__ == "__main__":  # pragma: no cover
    run()

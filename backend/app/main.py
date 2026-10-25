"""App factory: settings, DB, CORS, error envelope, routers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.core.clock import Clock, IdFactory, SystemClock, UuidIdFactory
from app.core.errors import install_error_handlers
from app.core.openapi import install_openapi
from app.db.base import create_all, make_engine, make_session_factory
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

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        stop = asyncio.Event()
        task = None
        if settings.forecast_worker and settings.forecast_provider == "engine":
            task = asyncio.create_task(app.state.forecast_worker.run_forever(stop))
        try:
            yield
        finally:
            stop.set()
            if task is not None:
                await task
            engine.dispose()

    app = FastAPI(title="Northstar AI-spend backend", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.clock = clock or SystemClock()
    app.state.id_factory = id_factory or UuidIdFactory()
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    from app.forecasting.persistence import ForecastStore
    from app.forecasting.service import ForecastService
    from app.forecasting.worker import ForecastWorker
    from app.services.forecast_freshness import invalidate_dependent_proposals

    from app.forecasting.repository import capture_repository_inputs, repository_snapshot_factory
    forecast_store = ForecastStore(settings.db_path, on_input=invalidate_dependent_proposals)
    app.state.session_factory.configure(info={'forecast_store': forecast_store, 'forecast_clock': app.state.clock.now})
    # Capture preexisting repository state at actual initialization time. This
    # explicit write never backdates knowledge or runs on forecast read paths.
    with app.state.session_factory() as session:
        capture_repository_inputs(session, now=app.state.clock.now())
        session.commit()
    snapshot_factory = repository_snapshot_factory(app.state.session_factory, clock=app.state.clock.now, store=forecast_store)
    if settings.forecast_demo:
        from app.forecasting.fixtures import build_northstar_snapshot
        snapshot_factory = build_northstar_snapshot
    app.state.forecast_service = ForecastService(
        forecast_store,
        snapshot_factory=snapshot_factory, now=lambda: app.state.clock.now().isoformat(),
    )
    app.state.forecast_worker = ForecastWorker(app.state.forecast_service)
    app.state.forecast_provider = forecast_provider or provider_from_settings(
        settings.forecast_provider, forecast_service=app.state.forecast_service,
        session_factory=app.state.session_factory,
    )
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
        routes_proposals,
        routes_signals,
        routes_spending,
        routes_teams,
    )

    for module in (
        routes_meta,
        routes_teams,
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
    from app.forecasting.routes import router as forecasting_router
    app.include_router(forecasting_router)
    if settings.compat:
        app.include_router(forecasting_router, prefix="/compat", include_in_schema=False)
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

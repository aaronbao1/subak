"""App factory: settings, DB, CORS, error envelope, routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.core.clock import Clock, IdFactory, SystemClock, UuidIdFactory
from app.core.errors import install_error_handlers
from app.db.base import create_all, make_engine, make_session_factory


def create_app(
    settings: Settings | None = None,
    *,
    clock: Clock | None = None,
    id_factory: IdFactory | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()

    engine = make_engine(settings.db_path)
    create_all(engine)

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

    return app


def run() -> None:  # pragma: no cover - entry point
    import uvicorn

    settings = Settings.from_env()
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port)


if __name__ == "__main__":  # pragma: no cover
    run()

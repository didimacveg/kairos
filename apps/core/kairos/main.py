from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from kairos.api.v1.router import api_router
from kairos.config import get_settings
from kairos.core.bootstrap import build_core
from kairos.db.bootstrap import create_schema
from kairos.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.env)
    log = get_logger("kairos.main")
    await create_schema()
    app.state.core = build_core()
    log.info(
        "kairos.started",
        instance=settings.instance_name,
        egress_allowed=settings.allow_egress,
        chat_model=settings.chat_model,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="KAIROS Core",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.env == "development" else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "core", "kairos.local", "*.local"],
    )
    app.include_router(api_router)

    @app.middleware("http")
    async def security_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    return app


app = create_app()

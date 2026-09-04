from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

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

    # El informe diario corre en segundo plano durante toda la vida del
    # proceso. Se cancela limpiamente al apagar.
    from kairos.agents.briefing.scheduler import run_scheduler

    tarea = asyncio.create_task(run_scheduler(app.state.core))

    from kairos.agents.watch.scheduler import run_watcher

    vigilia = asyncio.create_task(run_watcher(app.state.core))

    from kairos.agents.agenda.scheduler import run_agenda

    agenda = asyncio.create_task(run_agenda(app.state.core))

    from kairos.agents.curiosidad.scheduler import run_curiosidad

    curiosidad = asyncio.create_task(run_curiosidad(app.state.core))

    from kairos.agents.tareas.scheduler import run_tareas

    cola = asyncio.create_task(run_tareas(app.state.core))

    from kairos.agents.consciencia.scheduler import run_consciencia

    consciencia = asyncio.create_task(run_consciencia(app.state.core))

    from kairos.agents.instintos.scheduler import run_instintos

    instintos = asyncio.create_task(run_instintos(app.state.core))

    from kairos.agents.juez.scheduler import run_juez

    juez = asyncio.create_task(run_juez(app.state.core))
    log.info(
        "kairos.started",
        instance=settings.instance_name,
        egress_allowed=settings.allow_egress,
        chat_model=settings.chat_model,
    )
    yield

    tarea.cancel()
    vigilia.cancel()
    agenda.cancel()
    curiosidad.cancel()
    cola.cancel()
    consciencia.cancel()
    instintos.cancel()
    juez.cancel()
    with suppress(asyncio.CancelledError):
        await tarea
    with suppress(asyncio.CancelledError):
        await vigilia


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
    # Tailscale Serve termina el TLS y reenvia a 127.0.0.1. Sin esto, el
    # nucleo cree que la peticion llego por HTTP y rechaza la cookie Secure.
    app.add_middleware(
        ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1", "localhost", "*"]
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "localhost", "127.0.0.1", "core", "kairos.local", "*.local",
            # Nombres de red privada (Tailscale). NO abre nada por si solo:
            # solo permite que las peticiones que YA llegan por la VPN no se
            # rechacen por el nombre del host.
            "*.ts.net", *settings.extra_hosts,
        ],
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

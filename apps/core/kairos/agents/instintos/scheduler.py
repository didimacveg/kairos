"""Bucle de aprendizaje.

Una vez al dia, de madrugada. No mas: los patrones de uso cambian por semanas,
no por horas, y recalcularlos cada rato gastaria CPU para llegar al mismo
resultado.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from kairos.agents.base import AgentRequest
from kairos.config import get_settings
from kairos.db.models import User
from kairos.db.session import get_session_factory
from kairos.logging import get_logger

log = get_logger("kairos.instintos.scheduler")

HORA_APRENDER = 4


async def run_instintos(core) -> None:  # type: ignore[no-untyped-def]
    settings = get_settings()
    if not settings.instintos_enabled:
        log.info("instintos.desactivados")
        return

    await asyncio.sleep(600)
    log.info("instintos.activos", hora=HORA_APRENDER)

    while True:
        try:
            ahora = datetime.now(ZoneInfo(settings.timezone))
            if ahora.hour == HORA_APRENDER:
                await _aprender(core)
                # Dormir una hora larga para no repetir dentro de la misma
                # ventana horaria.
                await asyncio.sleep(3900)
                continue
        except Exception as exc:  # noqa: BLE001
            log.warning("instintos.fallo", error=str(exc))
        await asyncio.sleep(900)


async def _aprender(core) -> None:  # type: ignore[no-untyped-def]
    async with get_session_factory()() as db:
        owner = (
            await db.execute(select(User).where(User.role == "owner").limit(1))
        ).scalar_one_or_none()
        if owner is None:
            return
        try:
            agente = core.registry.find("instintos.aprender")
        except KeyError:
            return
        r = await agente.handle(
            AgentRequest(capability="instintos.aprender", actor_id=owner.id), db=db
        )
        if r.ok:
            log.info("instintos.ciclo", nuevos=r.data.get("instintos", 0))

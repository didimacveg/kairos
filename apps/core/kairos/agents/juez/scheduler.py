"""Bucle de evaluacion. Una vez al dia, de madrugada.

Solo avisa si la calidad CAE. Un informe diario de "todo bien" se deja de
leer a la semana, y entonces tampoco se lee el dia que dice algo.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from kairos.agents.base import AgentRequest
from kairos.config import get_settings
from kairos.db.models import Briefing, User
from kairos.db.session import get_session_factory
from kairos.logging import get_logger

log = get_logger("kairos.juez.scheduler")

HORA = 5


async def run_juez(core) -> None:  # type: ignore[no-untyped-def]
    settings = get_settings()
    if not settings.juez_enabled:
        log.info("juez.desactivado")
        return

    await asyncio.sleep(720)
    log.info("juez.activo", hora=HORA)

    while True:
        try:
            if datetime.now(ZoneInfo(settings.timezone)).hour == HORA:
                await _evaluar(core)
                await asyncio.sleep(3900)
                continue
        except Exception as exc:  # noqa: BLE001
            log.warning("juez.fallo", error=str(exc))
        await asyncio.sleep(900)


async def _evaluar(core) -> None:  # type: ignore[no-untyped-def]
    async with get_session_factory()() as db:
        owner = (
            await db.execute(select(User).where(User.role == "owner").limit(1))
        ).scalar_one_or_none()
        if owner is None:
            return
        try:
            agente = core.registry.find("juez.evaluar")
        except KeyError:
            return

        r = await agente.handle(
            AgentRequest(capability="juez.evaluar", actor_id=owner.id), db=db
        )
        if not r.ok:
            return

        log.info("juez.ciclo", global_=r.data.get("global"))

        # Solo se avisa si algo va mal. Un "todo bien" diario se deja de leer.
        if not r.data.get("alerta"):
            return

        texto = (
            f"Mis respuestas de ayer puntuaron {r.data['global']}/10, "
            f"y lo peor fue {r.data['peor']}. {r.data.get('ejemplo', '')}"
        )
        db.add(Briefing(owner_id=owner.id, content=texto))
        await db.commit()

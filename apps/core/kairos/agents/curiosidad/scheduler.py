"""Bucle de la curiosidad.

Cada dos horas mira si hay algo que merezca contarte. Casi siempre la
respuesta sera que no, y eso es lo correcto: un asistente que encuentra algo
notable cada dos horas no esta juzgando, esta rellenando.

Cuando encuentra algo, dice la apertura en alto Y la deja escrita. Si no
estabas delante, la lees luego.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from kairos.agents.base import AgentRequest
from kairos.config import get_settings
from kairos.db.models import Briefing, User
from kairos.db.session import get_session_factory
from kairos.logging import get_logger

log = get_logger("kairos.curiosidad.scheduler")


async def run_curiosidad(core) -> None:  # type: ignore[no-untyped-def]
    settings = get_settings()
    if not settings.curiosidad_enabled:
        log.info("curiosidad.desactivada")
        return

    # Margen amplio al arrancar: nada mas encender el PC no es momento de
    # sacar temas.
    await asyncio.sleep(300)
    log.info("curiosidad.activa", cada_horas=settings.curiosidad_horas)

    while True:
        try:
            await _revisar(core)
        except Exception as exc:  # noqa: BLE001
            log.warning("curiosidad.fallo", error=str(exc))
        await asyncio.sleep(settings.curiosidad_horas * 3600)


async def _revisar(core) -> None:  # type: ignore[no-untyped-def]
    async with get_session_factory()() as db:
        owner = (
            await db.execute(select(User).where(User.role == "owner").limit(1))
        ).scalar_one_or_none()
        if owner is None:
            return

        try:
            agente = core.registry.find("curiosidad.revisar")
        except KeyError:
            return

        r = await agente.handle(
            AgentRequest(
                capability="curiosidad.revisar", actor_id=owner.id,
                payload={"owner": owner.username},
            ),
            db=db,
        )
        if not r.ok or not r.data.get("merece"):
            return

        apertura = r.data["apertura"]
        log.info("curiosidad.saca_tema", tema=r.data.get("tema"))

        # Se guarda antes de decirlo: si no estabas delante, queda escrito.
        db.add(Briefing(owner_id=owner.id, content=apertura))
        await db.commit()

        try:
            device = core.registry.find("device.say")
        except KeyError:
            return
        await device.handle(AgentRequest(
            capability="device.say", actor_id=owner.id,
            # Voz buena: es el momento en que KAIROS toma la iniciativa, y
            # suena distinto a una respuesta rutinaria a proposito.
            payload={"text": apertura, "motivo": "urgente"},
        ))

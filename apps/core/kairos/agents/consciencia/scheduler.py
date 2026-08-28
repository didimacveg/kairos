"""Bucle de la consciencia.

Cada 90 minutos mira si algo de lo que sabe, puesto en la linea del tiempo,
merece comentarse. Casi siempre no, y eso es correcto.

Por que 90 y no 20 como la vigilancia: las relaciones entre cosas cambian por
horas, no por minutos. Un examen que era el jueves sigue siendo el jueves
dentro de veinte minutos.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from kairos.agents.base import AgentRequest
from kairos.config import get_settings
from kairos.db.models import Briefing, User
from kairos.db.session import get_session_factory
from kairos.logging import get_logger

log = get_logger("kairos.consciencia.scheduler")


async def run_consciencia(core) -> None:  # type: ignore[no-untyped-def]
    settings = get_settings()
    if not settings.consciencia_enabled:
        log.info("consciencia.desactivada")
        return

    # Margen amplio: nada mas encender el PC no es momento de comentar nada.
    await asyncio.sleep(420)
    log.info("consciencia.activa", cada_minutos=settings.consciencia_minutos)

    while True:
        try:
            await _revisar(core)
        except Exception as exc:  # noqa: BLE001
            log.warning("consciencia.fallo", error=str(exc))
        await asyncio.sleep(settings.consciencia_minutos * 60)


async def _revisar(core) -> None:  # type: ignore[no-untyped-def]
    async with get_session_factory()() as db:
        owner = (
            await db.execute(select(User).where(User.role == "owner").limit(1))
        ).scalar_one_or_none()
        if owner is None:
            return

        try:
            agente = core.registry.find("consciencia.revisar")
        except KeyError:
            return

        r = await agente.handle(
            AgentRequest(
                capability="consciencia.revisar", actor_id=owner.id,
                payload={"owner": owner.username},
            ),
            db=db,
        )
        if not r.ok or not r.data.get("merece"):
            return

        observacion = r.data["observacion"]
        log.info("consciencia.dice", clave=r.data.get("clave"))

        # Se guarda antes de decirlo: si no esta delante, queda escrito.
        db.add(Briefing(owner_id=owner.id, content=observacion))
        await db.commit()

        try:
            device = core.registry.find("device.say")
        except KeyError:
            return
        await device.handle(AgentRequest(
            capability="device.say", actor_id=owner.id,
            payload={"text": observacion, "motivo": "urgente"},
        ))

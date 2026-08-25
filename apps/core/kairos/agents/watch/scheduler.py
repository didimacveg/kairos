"""Bucle de vigilancia.

Revisa cada N minutos y, si encuentra algo NUEVO, lo deja como aviso y lo dice
en alto si el puente esta disponible.

Por que un intervalo largo y no continuo: la vigilancia util no es la que mira
cada segundo, es la que avisa cuando algo lleva un rato mal. Un agente que se
cae y vuelve en treinta segundos no merece interrumpirte.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from kairos.agents.base import AgentRequest
from kairos.config import get_settings
from kairos.db.models import Briefing, User
from kairos.db.session import get_session_factory
from kairos.logging import get_logger

log = get_logger("kairos.watch.scheduler")


async def run_watcher(core) -> None:  # type: ignore[no-untyped-def]
    settings = get_settings()
    if not settings.watch_enabled:
        log.info("watch.desactivado")
        return

    # Margen al arrancar: durante el primer minuto medio sistema esta todavia
    # levantandose y avisaria de caidas que no existen.
    await asyncio.sleep(90)
    log.info("watch.activo", cada_minutos=settings.watch_interval_minutes)

    while True:
        try:
            await _revisar(core)
        except Exception as exc:  # noqa: BLE001
            log.warning("watch.fallo", error=str(exc))
        await asyncio.sleep(settings.watch_interval_minutes * 60)


async def _revisar(core) -> None:  # type: ignore[no-untyped-def]
    async with get_session_factory()() as db:
        owner = (
            await db.execute(select(User).where(User.role == "owner").limit(1))
        ).scalar_one_or_none()
        if owner is None:
            return

        try:
            agente = core.registry.find("watch.revisar")
        except KeyError:
            return

        resultado = await agente.handle(
            AgentRequest(capability="watch.revisar", actor_id=owner.id), db=db
        )
        if not resultado.ok:
            return

        hallazgos = resultado.data.get("hallazgos", [])
        if not hallazgos:
            return

        # El aviso lleva la pregunta si KAIROS propone algo. La respuesta
        # llega por el panel o por voz; nunca se ejecuta sin ella.
        # Lo urgente se dice aunque no lo hayas pedido; lo normal espera en
        # el panel. La diferencia importa: un sistema que interrumpe por todo
        # acaba silenciado, y entonces tampoco avisa de lo que si importaba.
        urgentes = [h for h in hallazgos if h.get("urgencia") == "alta"]

        texto = "\n".join(
            h["texto"] + (f"\n{h['propuesta']}" if h.get("propuesta") else "")
            for h in hallazgos
        )
        log.info("watch.aviso", cuantos=len(hallazgos))

        # Se guarda como aviso ANTES de intentar decirlo: si no estas delante,
        # el audio se pierde pero el texto espera.
        db.add(Briefing(owner_id=owner.id, content=texto))
        await db.commit()

        # Solo lo urgente se dice en alto. El resto queda como aviso escrito.
        if not urgentes:
            return

        try:
            device = core.registry.find("device.say")
        except KeyError:
            return
        await device.handle(AgentRequest(
            capability="device.say", actor_id=owner.id, payload={"text": texto, "motivo": "urgente"}
        ))

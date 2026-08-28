"""Bucle de la agenda: dispara los avisos y resuelve los abiertos.

Dos ritmos distintos a proposito:
  - Los avisos vencidos se comprueban cada minuto: llegar tarde a un aviso lo
    inutiliza.
  - Los abiertos se resuelven cada 30 minutos: buscar en la web cuesta, y una
    fecha que no se sabe ahora tampoco se sabra dentro de un minuto.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from kairos.agents.base import AgentRequest
from kairos.config import get_settings
from kairos.db.models import Reminder, User
from kairos.db.session import get_session_factory
from kairos.logging import get_logger

log = get_logger("kairos.agenda.scheduler")

RESOLVER_CADA_MIN = 30


async def run_agenda(core) -> None:  # type: ignore[no-untyped-def]
    if not get_settings().agenda_enabled:
        log.info("agenda.desactivada")
        return

    await asyncio.sleep(60)
    log.info("agenda.activa")
    ciclos = 0

    while True:
        try:
            await _disparar(core)
            if ciclos % RESOLVER_CADA_MIN == 0:
                await _resolver(core)
            # El correo se mira cada 5 min: mas seguido gasta cuota de la API
            # sin ganar nada, y menos hace que un aviso llegue tarde.
            if ciclos % 5 == 0:
                await _correo(core)
        except Exception as exc:  # noqa: BLE001
            log.warning("agenda.fallo", error=str(exc))
        ciclos += 1
        await asyncio.sleep(60)


async def _propietario(db):  # type: ignore[no-untyped-def]
    return (
        await db.execute(select(User).where(User.role == "owner").limit(1))
    ).scalar_one_or_none()


async def _disparar(core) -> None:  # type: ignore[no-untyped-def]
    async with get_session_factory()() as db:
        owner = await _propietario(db)
        if owner is None:
            return

        vencidos = (
            await db.execute(
                select(Reminder).where(
                    Reminder.owner_id == owner.id,
                    Reminder.status == "pendiente",
                    Reminder.kind == "fijo",
                    Reminder.due_at <= datetime.now(UTC),
                )
            )
        ).scalars().all()
        if not vencidos:
            return

        for fila in vencidos:
            # Se marca ANTES de intentar decirlo. Si el puente esta caido, el
            # aviso queda dado y no se repite en bucle cada minuto.
            fila.status = "avisado"
            fila.fired_at = datetime.now(UTC)
        await db.commit()

        texto = " ".join(f.message for f in vencidos)
        log.info("agenda.aviso", cuantos=len(vencidos))

        try:
            device = core.registry.find("device.say")
        except KeyError:
            return
        await device.handle(AgentRequest(
            capability="device.say", actor_id=owner.id, payload={"text": texto, "motivo": "recordatorio"}
        ))


async def _resolver(core) -> None:  # type: ignore[no-untyped-def]
    async with get_session_factory()() as db:
        owner = await _propietario(db)
        if owner is None:
            return
        try:
            agente = core.registry.find("agenda.resolver")
        except KeyError:
            return
        await agente.handle(
            AgentRequest(capability="agenda.resolver", actor_id=owner.id), db=db
        )


async def _correo(core) -> None:  # type: ignore[no-untyped-def]
    """Revisa los avisos de correo y los dice en alto."""
    from kairos.agents.google import auth, vigilante

    if not auth.configurado():
        return

    async with get_session_factory()() as db:
        owner = await _propietario(db)
        if owner is None:
            return
        avisos = await vigilante.revisar(db, owner.id)

    if not avisos:
        return

    texto = " ".join(avisos)
    log.info("agenda.correo", cuantos=len(avisos))
    try:
        device = core.registry.find("device.say")
    except KeyError:
        return
    await device.handle(AgentRequest(
        capability="device.say", actor_id=owner.id,
        payload={"text": texto, "motivo": "recordatorio"},
    ))

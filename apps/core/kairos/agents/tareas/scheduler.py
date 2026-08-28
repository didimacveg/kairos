"""Cola de tareas: coge la siguiente pendiente y la ejecuta.

UNA a la vez, a proposito. Dos tareas largas en paralelo compiten por el
mismo proveedor y las dos tardan el doble; ademas el coste se dispara sin que
nadie lo vea venir.

Mientras una tarea corre, la conversacion normal sigue funcionando: son
llamadas distintas al proveedor y no se bloquean entre si. Eso es lo que hace
util el segundo plano.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from kairos.agents.base import AgentRequest
from kairos.config import get_settings
from kairos.db.models import Task, User
from kairos.db.session import get_session_factory
from kairos.logging import get_logger

log = get_logger("kairos.tareas.scheduler")


async def run_tareas(core) -> None:  # type: ignore[no-untyped-def]
    if not get_settings().tareas_enabled:
        log.info("tareas.desactivadas")
        return

    await asyncio.sleep(45)
    log.info("tareas.activas")

    while True:
        try:
            await _siguiente(core)
        except Exception as exc:  # noqa: BLE001
            log.warning("tareas.fallo", error=str(exc))
        await asyncio.sleep(20)


async def _siguiente(core) -> None:  # type: ignore[no-untyped-def]
    fabrica = get_session_factory()
    async with fabrica() as db:
        # Si ya hay una en marcha, no se coge otra.
        activa = (
            await db.execute(
                select(Task).where(Task.status.in_(["planificando", "trabajando"])).limit(1)
            )
        ).scalar_one_or_none()
        if activa is not None:
            return

        pendiente = (
            await db.execute(
                select(Task).where(Task.status == "pendiente")
                .order_by(Task.created_at.asc()).limit(1)
            )
        ).scalar_one_or_none()
        if pendiente is None:
            return

        owner = (
            await db.execute(select(User).where(User.id == pendiente.owner_id))
        ).scalar_one_or_none()
        tarea_id = pendiente.id
        owner_id = pendiente.owner_id
        nombre = owner.username if owner else "Diego"

    try:
        agente = core.registry.find("tareas.ejecutar")
    except KeyError:
        return

    log.info("tareas.arranca", id=str(tarea_id))
    async with fabrica() as db:
        r = await agente.handle(
            AgentRequest(
                capability="tareas.ejecutar", actor_id=owner_id,
                payload={"id": str(tarea_id), "owner": nombre},
            ),
            db=db,
        )

    if not r.ok:
        log.warning("tareas.fallida", id=str(tarea_id), error=r.error)
        return

    # Avisar al terminar: el sentido de trabajar en segundo plano es no tener
    # que estar mirando.
    aviso = f"He terminado {r.data.get('titulo', 'el encargo')}. Lo tienes en el panel de encargos."
    try:
        device = core.registry.find("device.say")
    except KeyError:
        return
    await device.handle(AgentRequest(
        capability="device.say", actor_id=owner_id,
        payload={"text": aviso, "motivo": "recordatorio"},
    ))

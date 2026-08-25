"""Planificador del informe diario.

Un bucle asincrono que despierta cada minuto y comprueba si toca. Sin cron ni
librerias de scheduling: para una tarea al dia, un `while` con `sleep` es mas
facil de leer y de depurar que una dependencia mas.

Idempotencia: se guarda la fecha del ultimo informe. Si el contenedor se
reinicia a las 15:31, no se genera otro; si arranca a las 18:00 y hoy no se
genero ninguno, tampoco se genera con retraso — un informe de la manana leido
por la noche es peor que ninguno.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from kairos.agents.base import AgentRequest
from kairos.config import get_settings
from kairos.db.models import Briefing, User
from kairos.db.session import get_session_factory
from kairos.logging import get_logger

log = get_logger("kairos.briefing.scheduler")

# Margen: si el sistema estaba apagado a la hora exacta, se genera igualmente
# durante los siguientes minutos. Pasado eso, se salta el dia.
MARGEN_MINUTOS = 20


async def _ya_generado_hoy(hoy: date) -> bool:
    async with get_session_factory()() as db:
        result = await db.execute(select(Briefing).order_by(Briefing.created_at.desc()).limit(1))
        ultimo = result.scalar_one_or_none()
        if ultimo is None:
            return False
        return ultimo.created_at.astimezone().date() == hoy


async def run_scheduler(core) -> None:  # type: ignore[no-untyped-def]
    settings = get_settings()
    if not settings.briefing_enabled:
        log.info("briefing.desactivado")
        return

    tz = ZoneInfo(settings.timezone)
    hora, minuto = (int(x) for x in settings.briefing_time.split(":"))
    log.info("briefing.programado", hora=settings.briefing_time, zona=settings.timezone)

    while True:
        try:
            ahora_local = datetime.now(tz)
            objetivo = ahora_local.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            minutos_desde = (ahora_local - objetivo).total_seconds() / 60

            en_ventana = 0 <= minutos_desde <= MARGEN_MINUTOS
            dia_valido = settings.briefing_weekends or ahora_local.weekday() < 5

            if en_ventana and dia_valido and not await _ya_generado_hoy(ahora_local.date()):
                await _generar(core)
        except Exception as exc:  # noqa: BLE001
            # El planificador no puede morir: si falla un dia, mañana lo
            # vuelve a intentar.
            log.warning("briefing.fallo", error=str(exc))

        await asyncio.sleep(60)


async def _generar(core) -> None:  # type: ignore[no-untyped-def]
    async with get_session_factory()() as db:
        owner = (
            await db.execute(select(User).where(User.role == "owner").limit(1))
        ).scalar_one_or_none()
        if owner is None:
            return

        agente = core.registry.find("briefing.generate")
        resultado = await agente.handle(
            AgentRequest(
                capability="briefing.generate",
                actor_id=owner.id,
                payload={"owner": owner.username, "db": db},
            ),
            db=db,
        )
        if not resultado.ok:
            log.warning("briefing.no_generado", error=resultado.error)
            return

        log.info("briefing.generado", caracteres=len(resultado.data["content"]))

        # Contarlo en alto, si el puente esta disponible. Que no lo este no
        # invalida el informe: ya esta guardado y espera en la interfaz.
        try:
            device = core.registry.find("device.say")
        except KeyError:
            return
        hablado = await device.handle(
            AgentRequest(
                capability="device.say",
                actor_id=owner.id,
                payload={"text": resultado.data["content"], "motivo": "informe"},
            )
        )
        if not hablado.ok:
            log.info("briefing.sin_voz", motivo=hablado.error)

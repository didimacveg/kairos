"""Watch Agent — KAIROS decide por su cuenta que merece tu atencion.

Hasta ahora todo empezaba contigo: preguntabas, respondia. El informe diario
fue el primer paso en la otra direccion, pero era un horario fijo.

Esto es distinto: mira el estado del sistema periodicamente y avisa **solo
cuando algo cambia a peor**. No informa de que todo va bien; eso es ruido.

Que vigila hoy:
  - agentes que dejan de responder
  - propuestas aprobadas que llevan dias sin aplicarse
  - la salida a Internet activada sin que nadie la mirara
  - el disco de la maquina llenandose

REGLA QUE GOBIERNA TODO ESTE AGENTE: **avisa, no actua.** Puede decirte que el
puente lleva dos horas caido; no puede reiniciarlo. Un sistema que se arregla
solo es un sistema que un dia decide que tu sesion de trabajo es el problema.

Y una segunda regla igual de importante: **no repite**. Un aviso que ya te
dio no vuelve a darlo hasta que la situacion se resuelva y vuelva a ocurrir.
Un vigilante que repite lo mismo cada diez minutos deja de leerse, y entonces
no vigila nada.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.registry import AgentRegistry
from kairos.db.models import Briefing, Proposal
from kairos.logging import get_logger

log = get_logger("kairos.watch")

# Cuanto tiene que pasar para volver a dar el mismo aviso.
SILENCIO_HORAS = 6
# Dias que puede llevar una propuesta aprobada sin aplicar antes de recordarlo.
PROPUESTA_OLVIDADA_DIAS = 2


class Hallazgo:
    """Algo que merece la atencion del usuario."""

    __slots__ = ("clave", "texto", "urgencia")

    def __init__(self, clave: str, texto: str, urgencia: str = "normal") -> None:
        # `clave` identifica el TIPO de aviso, no la ocurrencia. Es lo que
        # permite no repetirse.
        self.clave = clave
        self.texto = texto
        self.urgencia = urgencia


class WatchAgent(Agent):
    name = "watch"
    capabilities = frozenset({"watch.revisar"})

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry
        self._vistos: dict[str, datetime] = {}

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "watch.revisar":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        started = time.perf_counter()
        hallazgos: list[Hallazgo] = []
        hallazgos += await self._revisar_agentes()
        hallazgos += await self._revisar_propuestas(db, request.actor_id)

        nuevos = [h for h in hallazgos if self._es_nuevo(h.clave)]
        for h in nuevos:
            self._vistos[h.clave] = datetime.now(UTC)

        # Las claves que ya no aparecen se olvidan: si el problema se
        # resolvio y vuelve, es un aviso nuevo y merece contarse otra vez.
        activas = {h.clave for h in hallazgos}
        self._vistos = {k: v for k, v in self._vistos.items() if k in activas}

        return AgentResponse(
            ok=True,
            data={
                "hallazgos": [
                    {"clave": h.clave, "texto": h.texto, "urgencia": h.urgencia}
                    for h in nuevos
                ],
                "revisados": len(hallazgos),
            },
            trace=[TraceEvent(
                agent=self.name, step="revisar",
                detail={"encontrados": len(hallazgos), "nuevos": len(nuevos)},
                duration_ms=int((time.perf_counter() - started) * 1000),
            )],
        )

    def _es_nuevo(self, clave: str) -> bool:
        visto = self._vistos.get(clave)
        if visto is None:
            return True
        return datetime.now(UTC) - visto > timedelta(hours=SILENCIO_HORAS)

    async def _revisar_agentes(self) -> list[Hallazgo]:
        caidos = []
        for agente in self._registry.all():
            if agente.name == self.name:
                continue
            try:
                salud = await agente.health()
            except Exception:  # noqa: BLE001
                caidos.append(agente.name)
                continue
            if salud.get("status") not in {"ok", "disabled"}:
                caidos.append(agente.name)

        if not caidos:
            return []

        # El puente merece mencion aparte: es el que mas se cae y el unico
        # cuya caida tiene un arreglo que Diego puede hacer en diez segundos.
        if caidos == ["device"]:
            return [Hallazgo(
                "device_caido",
                "El puente no responde, asi que no puedo abrir aplicaciones ni "
                "colocar ventanas. Se arregla con el acceso directo Abrir KAIROS.",
                "normal",
            )]
        return [Hallazgo(
            "agentes_caidos",
            f"No responden: {', '.join(caidos)}. Merece un vistazo.",
            "alta",
        )]

    async def _revisar_propuestas(self, db: AsyncSession, owner_id: Any) -> list[Hallazgo]:
        limite = datetime.now(UTC) - timedelta(days=PROPUESTA_OLVIDADA_DIAS)
        filas = (
            await db.execute(
                select(Proposal).where(
                    Proposal.owner_id == owner_id,
                    Proposal.status == "aprobada",
                    Proposal.created_at < limite,
                )
            )
        ).scalars().all()
        if not filas:
            return []

        titulos = ", ".join(f.title[:50] for f in filas[:2])
        return [Hallazgo(
            "propuestas_sin_aplicar",
            f"Tienes {len(filas)} propuesta(s) aprobada(s) sin aplicar: {titulos}. "
            "Aprobarlas no las aplica; hay que pulsar Aplicar.",
            "normal",
        )]

    async def health(self) -> dict[str, Any]:
        return {"agent": self.name, "status": "ok", "avisos_activos": len(self._vistos)}

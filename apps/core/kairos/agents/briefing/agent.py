"""Briefing Agent — KAIROS habla primero.

Hasta ahora KAIROS solo respondia. Esto invierte la iniciativa: a una hora
fijada prepara un resumen y lo cuenta, estes o no delante.

Dos decisiones de diseno:

1. **El informe se PERSISTE antes de contarse.** Si no estas en casa a las
   15:30, el audio se pierde pero el texto queda esperando en la interfaz.
   Un aviso que solo existe mientras suena no es un aviso, es ruido.

2. **Se genera con lo que KAIROS ya sabe**, no con integraciones nuevas: la
   fecha, el tiempo por busqueda web, su propio estado y lo que recuerda de
   ti. Cada integracion futura (tienda, redes, correo) anade una seccion sin
   tocar el resto.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.reasoning.agent import ahora
from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider
from kairos.agents.registry import AgentRegistry
from kairos.config import get_settings
from kairos.db.models import Briefing
from kairos.logging import get_logger

log = get_logger("kairos.briefing")

PROMPT = """Eres KAIROS. Preparas el informe diario para {owner}.

Reglas:
- Habla directamente a {owner}, en segunda persona.
- Empieza saludando segun la hora que sea, sin decir la fecha completa: el
  ya sabe en que dia vive.
- Se breve: entre 4 y 7 frases. Esto se va a ESCUCHAR, no leer, y un parrafo
  largo hablado se hace eterno.
- Nada de relleno, ni "espero que tengas un buen dia", ni listas con guiones.
- Menciona solo lo que aparezca en los datos. Si algo falta, omitelo en
  silencio: no digas "no tengo informacion sobre el tiempo".
- Si hay algo que recuerdas de el que venga a cuento hoy, mencionalo con
  naturalidad. Si no, no fuerces."""


class BriefingAgent(Agent):
    name = "briefing"
    capabilities = frozenset({"briefing.generate"})

    def __init__(self, provider: LLMProvider, registry: AgentRegistry) -> None:
        self._provider = provider
        self._registry = registry
        self._settings = get_settings()

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "briefing.generate":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        started = time.perf_counter()
        owner = request.payload.get("owner", "Diego")
        datos = await self._recopilar(request, owner)

        try:
            completion = await self._provider.complete([
                ChatTurn(role="system", content=PROMPT.format(owner=owner)),
                ChatTurn(role="user", content=datos),
            ])
            texto = completion.text.strip()
        except Exception as exc:  # noqa: BLE001
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")

        if not texto:
            return AgentResponse.failure("El informe salio vacio")

        informe = Briefing(owner_id=request.actor_id, content=texto)
        db.add(informe)
        await db.commit()
        await db.refresh(informe)

        return AgentResponse(
            ok=True,
            data={"id": str(informe.id), "content": texto},
            trace=[
                TraceEvent(
                    agent=self.name,
                    step="generate",
                    detail={"caracteres": len(texto), "modelo": completion.model},
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            ],
        )

    async def _recopilar(self, request: AgentRequest, owner: str) -> str:
        """Reune lo que KAIROS puede saber hoy sin integraciones externas."""
        settings = self._settings
        partes = [f"FECHA Y HORA: {ahora(settings.timezone)}"]

        # Tiempo, si la busqueda esta disponible.
        try:
            buscador = self._registry.find("search.web")
            resultado = await buscador.handle(
                AgentRequest(
                    capability="search.web",
                    actor_id=request.actor_id,
                    payload={"query": f"tiempo hoy {settings.briefing_city}", "limit": 3},
                )
            )
            if resultado.ok and resultado.data.get("results"):
                lineas = "\n".join(
                    f"- {r['title']}: {r['snippet'][:180]}"
                    for r in resultado.data["results"][:3]
                )
                partes.append(f"TIEMPO EN {settings.briefing_city.upper()}:\n{lineas}")
        except KeyError:
            pass

        # Estado del propio sistema: agentes vivos y por donde razona.
        salud = []
        for agente in self._registry.all():
            if agente.name == "briefing":
                continue
            try:
                salud.append(await agente.health())
            except Exception:  # noqa: BLE001
                salud.append({"agent": agente.name, "status": "error"})
        caidos = [s["agent"] for s in salud if s.get("status") not in {"ok", "disabled"}]
        partes.append(
            "ESTADO DE KAIROS: "
            + (f"todo en orden, {len(salud)} agentes activos."
               if not caidos else f"atencion, no responden: {', '.join(caidos)}.")
        )

        # Lo que recuerda de el.
        try:
            memoria = self._registry.find("memory.retrieve")
            recuerdos = await memoria.handle(
                AgentRequest(
                    capability="memory.retrieve",
                    actor_id=request.actor_id,
                    payload={"query": "planes, tareas pendientes, rutina, preferencias",
                             "top_k": 5, "min_similarity": 0.3},
                ),
                db=request.payload.get("db"),
            )
            hits = recuerdos.data.get("hits", []) if recuerdos.ok else []
            if hits:
                partes.append(
                    "LO QUE RECUERDAS DE EL:\n"
                    + "\n".join(f"- {h['content']}" for h in hits[:5])
                )
        except KeyError:
            pass

        return "\n\n".join(partes)

    async def health(self) -> dict[str, Any]:
        return {"agent": self.name, "status": "ok"}

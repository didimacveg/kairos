"""Reasoning Agent — genera respuestas a partir del contexto disponible.

Fase 1: una sola pasada al modelo. Sin herramientas, sin planificacion, sin
bucle. La estructura permite anadirlos en Fase 5 sin tocar la interfaz.
"""
from __future__ import annotations

import time
from typing import Any

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider
from kairos.config import get_settings

SYSTEM_PROMPT = """Eres KAIROS, el sistema personal de {owner}.
Funcionas integramente en su maquina: ningun dato de esta conversacion sale de ella.

Reglas:
- Responde en el idioma en que te hablen.
- Se conciso y concreto. Nada de relleno ni halagos.
- Usa el bloque MEMORIA con naturalidad: no lo menciones, no cites
  similitudes ni digas de donde sale la informacion. La trazabilidad
  la muestra la interfaz, no tu.
- Si no sabes algo, dilo. No inventes hechos sobre {owner}.
"""


class ReasoningAgent(Agent):
    name = "reasoning"
    capabilities = frozenset({"reasoning.respond"})

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self._settings = get_settings()

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "reasoning.respond":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        if not self._provider.local and not self._settings.allow_egress:
            return AgentResponse.failure(
                "Proveedor remoto bloqueado: KAIROS_ALLOW_EGRESS esta desactivado"
            )

        try:
            turns = self._build_turns(request.payload)
            started = time.perf_counter()
            completion = await self._provider.complete(turns)
            elapsed = int((time.perf_counter() - started) * 1000)
        except Exception as exc:  # noqa: BLE001
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")

        return AgentResponse(
            ok=True,
            data={
                "content": completion.text,
                "model": completion.model,
                "latency_ms": completion.latency_ms,
                "local": completion.local,
            },
            trace=[
                TraceEvent(
                    agent=self.name,
                    step="complete",
                    detail={
                        "model": completion.model,
                        "local": completion.local,
                        "turns": len(turns),
                    },
                    duration_ms=elapsed,
                )
            ],
        )

    def _build_turns(self, payload: dict[str, Any]) -> list[ChatTurn]:
        owner: str = payload.get("owner", "el propietario")
        memories: list[dict[str, Any]] = payload.get("memories", [])
        history: list[dict[str, str]] = payload.get("history", [])
        message: str = payload["message"]

        system = SYSTEM_PROMPT.format(owner=owner)
        if memories:
            lines = "\n".join(
                f"- ({m['similarity']:.2f}) {m['content']}" for m in memories
            )
            system += f"\n\nMEMORIA recuperada de conversaciones anteriores:\n{lines}\n"

        turns = [ChatTurn(role="system", content=system)]
        turns += [ChatTurn(role=h["role"], content=h["content"]) for h in history]
        turns.append(ChatTurn(role="user", content=message))
        return turns

    async def health(self) -> dict[str, Any]:
        return {
            "agent": self.name,
            "status": "ok" if await self._provider.available() else "unavailable",
            "provider": self._provider.name,
            "local": self._provider.local,
        }

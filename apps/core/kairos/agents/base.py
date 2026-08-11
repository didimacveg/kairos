"""Contrato de agente.

Un agente es un *bounded context*: posee su propio estado, expone capacidades
nombradas y no importa modulos internos de otro agente. Hoy todos viven en el
mismo proceso y se invocan por llamada directa a traves del registro. Cuando
un agente necesite correr en otra maquina (Vision en la Raspberry, Fase 3),
solo cambia el transporte: el contrato de abajo no se toca.

Fase 2A anade una segunda forma de responder: en flujo. No se ha metido dentro
de `handle` porque forzar a todo agente a devolver un generador complicaria a
los que solo tienen una respuesta (Vision devuelve una deteccion, no un
chorro de tokens). En su lugar hay un protocolo aparte, `StreamingAgent`, que
implementan solo los agentes cuya salida es incremental.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    """Paso observable del razonamiento del sistema.

    La traza no es logging: se devuelve al cliente. El usuario debe poder ver
    que hizo KAIROS para producir una respuesta sin leer los logs del servidor.
    """

    agent: str
    step: str
    detail: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = None
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentRequest(BaseModel):
    capability: str
    actor_id: uuid.UUID | None = None
    correlation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    trace: list[TraceEvent] = Field(default_factory=list)

    @classmethod
    def failure(cls, message: str, trace: list[TraceEvent] | None = None) -> AgentResponse:
        return cls(ok=False, error=message, trace=trace or [])


StreamEventType = Literal["token", "trace", "error", "end"]


class StreamEvent(BaseModel):
    """Fragmento de una respuesta incremental.

    `token` lleva texto; `trace` lleva un TraceEvent ya cerrado; `end` cierra
    el flujo con los metadatos finales; `error` lo aborta. Un flujo bien
    formado termina SIEMPRE en `end` o en `error`, nunca en silencio: el
    cliente necesita distinguir "ha terminado" de "se ha cortado la conexion".
    """

    type: StreamEventType
    text: str | None = None
    trace: TraceEvent | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class Agent(ABC):
    """Interfaz que implementa todo agente de KAIROS."""

    name: str
    capabilities: frozenset[str]

    @abstractmethod
    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        """Ejecuta una capacidad. Nunca lanza: devuelve AgentResponse.failure."""

    async def health(self) -> dict[str, Any]:
        return {"agent": self.name, "status": "unknown"}

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


@runtime_checkable
class StreamingAgent(Protocol):
    """Agente capaz de emitir su respuesta por partes.

    Es un Protocol y no una clase base para que un agente pueda adquirir la
    capacidad sin cambiar su jerarquia de herencia. `isinstance` funciona por
    el decorador runtime_checkable.
    """

    async def handle_stream(
        self, request: AgentRequest, **context: Any
    ) -> AsyncIterator[StreamEvent]: ...

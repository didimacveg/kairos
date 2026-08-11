from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatTurn:
    role: str  # system | user | assistant
    content: str


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    latency_ms: int
    local: bool


@dataclass(frozen=True)
class CompletionChunk:
    """Fragmento de generacion.

    `done=True` marca el ultimo fragmento y no lleva texto util: trae los
    metadatos que el proveedor solo conoce al terminar (modelo efectivo,
    latencia total).
    """

    text: str
    done: bool = False
    model: str | None = None
    latency_ms: int | None = None


class LLMProvider(ABC):
    """Proveedor de generacion de texto.

    `local` distingue lo que se ejecuta en esta maquina de lo que sale a
    Internet. El orquestador lo usa para marcar la traza y para bloquear
    salida cuando KAIROS_ALLOW_EGRESS esta desactivado.
    """

    name: str
    local: bool

    @abstractmethod
    async def complete(self, turns: list[ChatTurn], *, model: str | None = None) -> Completion: ...

    @abstractmethod
    def complete_stream(
        self, turns: list[ChatTurn], *, model: str | None = None
    ) -> AsyncIterator[CompletionChunk]:
        """Genera la respuesta por fragmentos.

        No es `async def`: devuelve directamente el generador asincrono, para
        que el llamante pueda hacer `async for` sin un await previo.
        """

    @abstractmethod
    async def embed(self, text: str, *, model: str | None = None) -> list[float]: ...

    @abstractmethod
    async def available(self) -> bool: ...

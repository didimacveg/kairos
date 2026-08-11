from __future__ import annotations

from abc import ABC, abstractmethod
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
    async def embed(self, text: str, *, model: str | None = None) -> list[float]: ...

    @abstractmethod
    async def available(self) -> bool: ...

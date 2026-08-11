from __future__ import annotations

import os

os.environ.setdefault("POSTGRES_USER", "kairos")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "kairos")
os.environ.setdefault("KAIROS_SESSION_SECRET", "x" * 48)

import pytest  # noqa: E402

from kairos.agents.reasoning.providers.base import ChatTurn, Completion, LLMProvider  # noqa: E402


class FakeProvider(LLMProvider):
    """Proveedor determinista para tests. No toca la red."""

    def __init__(self, *, local: bool = True, reply: str = "respuesta") -> None:
        self.name = "fake"
        self.local = local
        self._reply = reply
        self.last_turns: list[ChatTurn] = []

    async def complete(self, turns: list[ChatTurn], *, model: str | None = None) -> Completion:
        self.last_turns = turns
        return Completion(text=self._reply, model="fake-model", latency_ms=1, local=self.local)

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        # Embedding estable derivado del texto: suficiente para comprobar que
        # el pipeline pasa vectores del tamano correcto.
        seed = sum(ord(c) for c in text) or 1
        return [((seed * (i + 1)) % 97) / 97 for i in range(768)]

    async def available(self) -> bool:
        return True


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()

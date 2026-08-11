from __future__ import annotations

import os
from collections.abc import AsyncIterator

os.environ.setdefault("POSTGRES_USER", "kairos")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "kairos")
os.environ.setdefault("KAIROS_SESSION_SECRET", "x" * 48)

import pytest  # noqa: E402

from kairos.agents.reasoning.providers.base import (  # noqa: E402
    ChatTurn,
    Completion,
    CompletionChunk,
    LLMProvider,
)


class FakeProvider(LLMProvider):
    """Proveedor determinista para tests. No toca la red."""

    def __init__(
        self,
        *,
        local: bool = True,
        reply: str = "respuesta",
        chunks: list[str] | None = None,
        fail_at: int | None = None,
    ) -> None:
        self.name = "fake"
        self.local = local
        self._reply = reply
        self._chunks = chunks if chunks is not None else ["res", "pue", "sta"]
        self._fail_at = fail_at
        self.last_turns: list[ChatTurn] = []

    async def complete(self, turns: list[ChatTurn], *, model: str | None = None) -> Completion:
        self.last_turns = turns
        return Completion(text=self._reply, model="fake-model", latency_ms=1, local=self.local)

    async def complete_stream(
        self, turns: list[ChatTurn], *, model: str | None = None
    ) -> AsyncIterator[CompletionChunk]:
        self.last_turns = turns
        for index, piece in enumerate(self._chunks):
            if self._fail_at is not None and index == self._fail_at:
                raise RuntimeError("el proveedor se cayo a media generacion")
            yield CompletionChunk(text=piece)
        yield CompletionChunk(text="", done=True, model="fake-model", latency_ms=42)

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        seed = sum(ord(c) for c in text) or 1
        return [((seed * (i + 1)) % 97) / 97 for i in range(768)]

    async def available(self) -> bool:
        return True


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()

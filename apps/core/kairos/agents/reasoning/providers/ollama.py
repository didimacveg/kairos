from __future__ import annotations

import time

import httpx

from kairos.agents.reasoning.providers.base import ChatTurn, Completion, LLMProvider
from kairos.config import get_settings


class OllamaProvider(LLMProvider):
    """Proveedor local. Ruta por defecto de KAIROS."""

    name = "ollama"
    local = True

    def __init__(self, base_url: str | None = None, timeout: int | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.ollama_url).rstrip("/")
        self._timeout = timeout or settings.llm_timeout_seconds
        self._chat_model = settings.chat_model
        self._embedding_model = settings.embedding_model

    async def complete(self, turns: list[ChatTurn], *, model: str | None = None) -> Completion:
        target = model or self._chat_model
        payload = {
            "model": target,
            "messages": [{"role": t.role, "content": t.content} for t in turns],
            "stream": False,
            "options": {"temperature": 0.7, "num_ctx": 8192},
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()
        latency = int((time.perf_counter() - started) * 1000)
        return Completion(
            text=body["message"]["content"].strip(),
            model=target,
            latency_ms=latency,
            local=True,
        )

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        target = model or self._embedding_model
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/embeddings", json={"model": target, "prompt": text}
            )
            response.raise_for_status()
            body = response.json()
        return list(body["embedding"])

    async def available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

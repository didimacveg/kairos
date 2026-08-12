"""Proveedor remoto (Anthropic).

Rompe deliberadamente el "todo local" del proyecto, y por eso lleva tres
salvaguardas que no son opcionales:

1. **Interruptor central.** Si `KAIROS_ALLOW_EGRESS` esta desactivado, este
   proveedor ni se instancia. Tener la clave puesta no basta.
2. **`local = False`.** El orquestador marca la traza y la interfaz enciende
   el indicador de salida de datos. Nunca sale nada sin que se vea.
3. **Caida a local.** Si falla la red o la API, la peticion se reintenta con
   Ollama. KAIROS sigue funcionando con el router desenchufado: peor, pero
   funcionando. Esa era la regla fundacional y sigue en pie.

Lo que NO sale de casa: la memoria semantica, los embeddings, la auditoria y
el historial. Solo viaja el prompt del turno en curso.
"""
from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import httpx

from kairos.agents.reasoning.providers.base import (
    ChatTurn,
    Completion,
    CompletionChunk,
    LLMProvider,
)
from kairos.config import get_settings

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    local = False

    def __init__(self, api_key: str, model: str | None = None, timeout: int | None = None) -> None:
        settings = get_settings()
        self._key = api_key
        self._model = model or settings.cloud_model
        self._timeout = timeout or settings.llm_timeout_seconds
        self._max_tokens = settings.cloud_max_tokens

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

    def _payload(self, turns: list[ChatTurn], stream: bool) -> dict[str, object]:
        # La API de Anthropic separa el sistema del historial, a diferencia de
        # Ollama que lo mete como un turno mas.
        system = "\n\n".join(t.content for t in turns if t.role == "system")
        messages = [
            {"role": t.role, "content": t.content} for t in turns if t.role in {"user", "assistant"}
        ]
        return {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": messages,
            "stream": stream,
        }

    async def complete(self, turns: list[ChatTurn], *, model: str | None = None) -> Completion:
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                API_URL, headers=self._headers(), json=self._payload(turns, stream=False)
            )
            response.raise_for_status()
            body = response.json()
        text = "".join(
            block.get("text", "") for block in body.get("content", []) if block.get("type") == "text"
        )
        return Completion(
            text=text.strip(),
            model=body.get("model", self._model),
            latency_ms=int((time.perf_counter() - started) * 1000),
            local=False,
        )

    async def complete_stream(
        self, turns: list[ChatTurn], *, model: str | None = None
    ) -> AsyncIterator[CompletionChunk]:
        """Lee el flujo SSE de la API.

        Cada linea util empieza por `data: `. Se ignoran los eventos de control
        y las lineas malformadas: una anomalia no debe tumbar el flujo entero.
        """
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST", API_URL, headers=self._headers(), json=self._payload(turns, stream=True)
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    kind = event.get("type")
                    if kind == "content_block_delta":
                        text = (event.get("delta") or {}).get("text", "")
                        if text:
                            yield CompletionChunk(text=text)
                    elif kind == "message_stop":
                        yield CompletionChunk(
                            text="",
                            done=True,
                            model=self._model,
                            latency_ms=int((time.perf_counter() - started) * 1000),
                        )
                        return
                    elif kind == "error":
                        raise RuntimeError(str((event.get("error") or {}).get("message", "error")))

        yield CompletionChunk(
            text="", done=True, model=self._model,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        # Los embeddings se quedan SIEMPRE en casa. La memoria semantica es el
        # dato mas sensible del sistema y no viaja bajo ningun ajuste.
        raise NotImplementedError("Los embeddings se calculan siempre en local")

    async def available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.post(
                    API_URL,
                    headers=self._headers(),
                    json={
                        "model": self._model,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                )
                return response.status_code < 500
        except httpx.HTTPError:
            return False

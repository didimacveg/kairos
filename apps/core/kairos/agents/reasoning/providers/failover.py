"""Proveedor con caida a local.

Envuelve dos proveedores: uno preferido (normalmente remoto) y uno de
respaldo (siempre Ollama). Si el preferido falla — red caida, API sin cuota,
clave revocada — la peticion se reintenta con el respaldo de forma
transparente.

Esto es lo que mantiene viva la regla fundacional del proyecto: KAIROS nunca
depende de Internet para funcionar. Internet anade capacidad; su ausencia
degrada la calidad, no la disponibilidad.

Caso delicado: si el remoto falla A MEDIA generacion, ya se han emitido tokens
al cliente. Reintentar produciria una respuesta duplicada e incoherente, asi
que en ese caso NO se reintenta: se propaga el error. Solo se cae a local
cuando el fallo ocurre antes del primer token.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from kairos.agents.reasoning.providers.base import (
    ChatTurn,
    Completion,
    CompletionChunk,
    LLMProvider,
)
from kairos.logging import get_logger

log = get_logger("kairos.provider.failover")


class FailoverProvider(LLMProvider):
    def __init__(self, preferred: LLMProvider, fallback: LLMProvider) -> None:
        self._preferred = preferred
        self._fallback = fallback
        self.name = f"{preferred.name}->{fallback.name}"
        self.local = preferred.local

    @property
    def last_used_local(self) -> bool:
        return self.local

    async def complete(self, turns: list[ChatTurn], *, model: str | None = None) -> Completion:
        try:
            result = await self._preferred.complete(turns, model=model)
            self.local = self._preferred.local
            return result
        except Exception as exc:  # noqa: BLE001
            log.warning("provider.failover", provider=self._preferred.name, error=str(exc))
            result = await self._fallback.complete(turns, model=model)
            self.local = self._fallback.local
            return result

    async def complete_stream(
        self, turns: list[ChatTurn], *, model: str | None = None
    ) -> AsyncIterator[CompletionChunk]:
        emitted = False
        try:
            async for chunk in self._preferred.complete_stream(turns, model=model):
                emitted = emitted or bool(chunk.text)
                self.local = self._preferred.local
                yield chunk
            return
        except Exception as exc:  # noqa: BLE001
            if emitted:
                # Ya hay texto en pantalla: reintentar lo duplicaria.
                raise
            log.warning("provider.failover.stream", provider=self._preferred.name, error=str(exc))

        self.local = self._fallback.local
        async for chunk in self._fallback.complete_stream(turns, model=model):
            yield chunk

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        # Siempre local: la memoria semantica no sale de casa.
        return await self._fallback.embed(text, model=model)

    async def available(self) -> bool:
        return await self._fallback.available()

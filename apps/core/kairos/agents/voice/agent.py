"""Voice Agent — puente entre el nucleo y el servicio de transcripcion.

Capacidad:
  voice.transcribe   audio (bytes) -> texto

Este es el primer agente de KAIROS que NO ejecuta su trabajo en el proceso del
nucleo: delega en `kairos-voice`, un contenedor aparte con CUDA. Lo importante
es que el contrato es el mismo que el de Memory o Reasoning. Para el
orquestador no hay diferencia entre un agente local y uno remoto, que es
justo lo que se diseño en la Fase 1 pensando en la Fase 3.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.config import get_settings


class VoiceAgent(Agent):
    name = "voice"
    capabilities = frozenset({"voice.transcribe"})

    def __init__(self, base_url: str | None = None, timeout: int | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.voice_url).rstrip("/")
        self._timeout = timeout or settings.voice_timeout_seconds

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "voice.transcribe":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        audio: bytes = request.payload.get("audio", b"")
        if not audio:
            return AgentResponse.failure("No se recibio audio")

        filename: str = request.payload.get("filename", "audio.webm")
        content_type: str = request.payload.get("content_type", "audio/webm")
        started = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/transcribe",
                    files={"audio": (filename, audio, content_type)},
                )
                if response.status_code >= 400:
                    detail = response.json().get("detail", response.text)
                    return AgentResponse.failure(f"Servicio de voz: {detail}")
                body = response.json()
        except httpx.HTTPError as exc:
            return AgentResponse.failure(
                f"No se pudo contactar con el servicio de voz: {type(exc).__name__}"
            )

        elapsed = int((time.perf_counter() - started) * 1000)
        return AgentResponse(
            ok=True,
            data={
                "text": body["text"],
                "language": body["language"],
                "duration_s": body["duration_s"],
                "model": body["model"],
            },
            trace=[
                TraceEvent(
                    agent=self.name,
                    step="transcribe",
                    detail={
                        # Nunca el texto: la traza viaja al cliente y se
                        # registra. El contenido ya esta en el mensaje.
                        "audio_kb": round(len(audio) / 1024, 1),
                        "audio_s": body["duration_s"],
                        "chars": len(body["text"]),
                        "modelo": body["model"],
                        "idioma": body["language"],
                    },
                    duration_ms=elapsed,
                )
            ],
        )

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._base_url}/health")
                if response.status_code != 200:
                    return {"agent": self.name, "status": "unavailable"}
                body = response.json()
        except httpx.HTTPError:
            return {"agent": self.name, "status": "unavailable"}
        return {
            "agent": self.name,
            "status": body.get("status", "unknown"),
            "model": body.get("model"),
            "device": body.get("device"),
        }

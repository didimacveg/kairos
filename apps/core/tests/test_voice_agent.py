"""Tests del Voice Agent (Fase 2C).

No tocan la red ni cargan Whisper: verifican el contrato del agente frente a
un servicio simulado. Lo que importa aqui es que un servicio de voz caido no
tumbe el nucleo y que la traza no filtre el contenido transcrito.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from kairos.agents.base import AgentRequest
from kairos.agents.voice.agent import VoiceAgent


class FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler: Any) -> None:
        self._handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return self._handler(request)


def _agent_with(monkeypatch: pytest.MonkeyPatch, handler: Any) -> VoiceAgent:
    original = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = FakeTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    return VoiceAgent(base_url="http://voice:8100")


def _request(audio: bytes = b"fake-audio-bytes") -> AgentRequest:
    return AgentRequest(capability="voice.transcribe", payload={"audio": audio})


async def test_transcription_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "text": "  hola que tal  ",
                "language": "es",
                "duration_s": 2.4,
                "latency_ms": 300,
                "model": "medium",
                "segments": 1,
                "confidence": -0.3,
                "low_confidence": False,
                "no_speech": False,
            },
        )

    agent = _agent_with(monkeypatch, handler)
    result = await agent.handle(_request())

    assert result.ok
    assert result.data["text"] == "  hola que tal  "
    assert result.data["language"] == "es"


async def test_trace_never_contains_the_transcript(monkeypatch: pytest.MonkeyPatch) -> None:
    """La traza viaja al cliente y se audita: no debe llevar el contenido."""
    secreto = "mi contrasena del banco es azulejo"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "text": secreto,
                "language": "es",
                "duration_s": 3.0,
                "latency_ms": 100,
                "model": "medium",
                "segments": 1,
                "confidence": -0.3,
                "low_confidence": False,
                "no_speech": False,
            },
        )

    agent = _agent_with(monkeypatch, handler)
    result = await agent.handle(_request())

    serialized = str(result.trace[0].model_dump())
    assert secreto not in serialized
    assert "azulejo" not in serialized
    assert result.trace[0].detail["chars"] == len(secreto)


async def test_service_down_returns_failure_not_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    agent = _agent_with(monkeypatch, handler)
    result = await agent.handle(_request())

    assert not result.ok
    assert "servicio de voz" in (result.error or "").lower()


async def test_service_error_is_propagated_readably(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "No se pudo transcribir: formato invalido"})

    agent = _agent_with(monkeypatch, handler)
    result = await agent.handle(_request())

    assert not result.ok
    assert "formato invalido" in (result.error or "")


async def test_empty_audio_is_rejected_before_the_network() -> None:
    agent = VoiceAgent(base_url="http://voice:8100")
    result = await agent.handle(_request(audio=b""))
    assert not result.ok
    assert "audio" in (result.error or "").lower()


async def test_unsupported_capability() -> None:
    agent = VoiceAgent(base_url="http://voice:8100")
    result = await agent.handle(AgentRequest(capability="voice.speak"))
    assert not result.ok


async def test_health_reports_unavailable_when_service_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope")

    agent = _agent_with(monkeypatch, handler)
    assert (await agent.health())["status"] == "unavailable"

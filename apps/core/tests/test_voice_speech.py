"""Tests de sintesis y confianza (Fase 2D)."""
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


def _agent(monkeypatch: pytest.MonkeyPatch, handler: Any) -> VoiceAgent:
    original = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = FakeTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    return VoiceAgent(base_url="http://voice:8100")


def _transcription(**overrides: Any) -> dict[str, Any]:
    base = {
        "text": "hola que tal",
        "language": "es",
        "duration_s": 2.0,
        "latency_ms": 100,
        "model": "medium",
        "segments": 1,
        "confidence": -0.31,
        "low_confidence": False,
        "no_speech": False,
    }
    base.update(overrides)
    return base


async def test_speak_returns_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent(monkeypatch, lambda r: httpx.Response(200, content=b"RIFF....WAVE"))
    result = await agent.handle(
        AgentRequest(capability="voice.speak", payload={"text": "Hola Diego."})
    )
    assert result.ok
    assert result.data["audio"].startswith(b"RIFF")
    assert result.data["media_type"] == "audio/wav"


async def test_speak_rejects_empty_text_before_the_network() -> None:
    agent = VoiceAgent(base_url="http://voice:8100")
    result = await agent.handle(AgentRequest(capability="voice.speak", payload={"text": "   "}))
    assert not result.ok


async def test_speak_trace_carries_no_text(monkeypatch: pytest.MonkeyPatch) -> None:
    secreto = "la clave del router es girasol"
    agent = _agent(monkeypatch, lambda r: httpx.Response(200, content=b"RIFF"))
    result = await agent.handle(
        AgentRequest(capability="voice.speak", payload={"text": secreto})
    )
    assert secreto not in str(result.trace[0].model_dump())
    assert result.trace[0].detail["chars"] == len(secreto)


async def test_missing_voice_model_degrades_readably(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin modelo de Piper, KAIROS oye pero no habla. No debe caerse."""
    agent = _agent(
        monkeypatch,
        lambda r: httpx.Response(503, json={"detail": "Voz no disponible: falta el modelo"}),
    )
    result = await agent.handle(AgentRequest(capability="voice.speak", payload={"text": "hola"}))
    assert not result.ok
    assert "no disponible" in (result.error or "")


async def test_confidence_flows_through(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent(
        monkeypatch,
        lambda r: httpx.Response(200, json=_transcription(confidence=-1.4, low_confidence=True)),
    )
    result = await agent.handle(
        AgentRequest(capability="voice.transcribe", payload={"audio": b"xx"})
    )
    assert result.ok
    assert result.data["low_confidence"] is True
    assert result.trace[0].detail["dudosa"] is True


async def test_silence_is_reported_as_no_speech(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent(
        monkeypatch,
        lambda r: httpx.Response(200, json=_transcription(text="", no_speech=True, segments=0)),
    )
    result = await agent.handle(
        AgentRequest(capability="voice.transcribe", payload={"audio": b"xx"})
    )
    assert result.ok
    assert result.data["no_speech"] is True


async def test_agent_declares_both_capabilities() -> None:
    agent = VoiceAgent(base_url="http://voice:8100")
    assert agent.supports("voice.transcribe")
    assert agent.supports("voice.speak")

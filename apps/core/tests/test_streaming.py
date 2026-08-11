"""Tests de la ruta de streaming (Fase 2A).

Cubren lo que fallo en la Fase 1 por no estar cubierto: el troceado real, el
comportamiento ante un fallo a media generacion, y el formato SSE.
"""
from __future__ import annotations

import json

from kairos.agents.base import AgentRequest, StreamEvent
from kairos.agents.reasoning.agent import ReasoningAgent
from kairos.api.v1.routes_chat import _sse
from tests.conftest import FakeProvider


def _request() -> AgentRequest:
    return AgentRequest(
        capability="reasoning.respond_stream",
        payload={"message": "hola", "owner": "diego"},
    )


async def _collect(agent: ReasoningAgent, request: AgentRequest) -> list[StreamEvent]:
    return [event async for event in agent.handle_stream(request)]


async def test_stream_emits_tokens_then_trace() -> None:
    agent = ReasoningAgent(FakeProvider(chunks=["Hola", " ", "Diego"]))
    events = await _collect(agent, _request())

    tokens = [e.text for e in events if e.type == "token"]
    assert tokens == ["Hola", " ", "Diego"]
    assert "".join(tokens) == "Hola Diego"
    assert events[-1].type == "trace"
    assert events[-1].data["model"] == "fake-model"


async def test_stream_ends_with_terminal_event() -> None:
    """Un flujo nunca puede acabar en silencio: o trace final o error."""
    agent = ReasoningAgent(FakeProvider())
    events = await _collect(agent, _request())
    assert events[-1].type in {"trace", "error"}


async def test_provider_failure_becomes_error_event_not_exception() -> None:
    agent = ReasoningAgent(FakeProvider(chunks=["a", "b", "c"], fail_at=2))
    events = await _collect(agent, _request())

    assert [e.text for e in events if e.type == "token"] == ["a", "b"]
    assert events[-1].type == "error"
    assert "se cayo" in (events[-1].error or "")


async def test_unsupported_capability_yields_error() -> None:
    agent = ReasoningAgent(FakeProvider())
    events = await _collect(agent, AgentRequest(capability="reasoning.respond"))
    assert len(events) == 1
    assert events[0].type == "error"


async def test_remote_provider_blocked_in_stream(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from kairos.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("KAIROS_ALLOW_EGRESS", "false")
    agent = ReasoningAgent(FakeProvider(local=False))
    events = await _collect(agent, _request())
    assert events[0].type == "error"
    assert "EGRESS" in (events[0].error or "")
    get_settings.cache_clear()


async def test_memories_still_injected_in_stream() -> None:
    provider = FakeProvider()
    agent = ReasoningAgent(provider)
    request = AgentRequest(
        capability="reasoning.respond_stream",
        payload={
            "message": "que dije?",
            "owner": "diego",
            "memories": [{"content": "prefiero respuestas cortas", "similarity": 0.82}],
        },
    )
    await _collect(agent, request)
    system = provider.last_turns[0].content
    assert "MEMORIA" in system
    assert "prefiero respuestas cortas" in system


def test_sse_format_is_wire_correct() -> None:
    frame = _sse({"type": "token", "text": "hola"})
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n"), "SSE exige linea en blanco como delimitador"
    assert json.loads(frame[6:].strip())["text"] == "hola"


def test_sse_preserves_accents_and_newlines() -> None:
    frame = _sse({"type": "token", "text": "línea\ncon salto"})
    payload = json.loads(frame[len("data: ") :].strip())
    assert payload["text"] == "línea\ncon salto"
    assert frame.count("\n\n") == 1, "un salto real rompería el delimitador del protocolo"

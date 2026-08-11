from __future__ import annotations

from kairos.agents.base import AgentRequest
from kairos.agents.reasoning.agent import ReasoningAgent
from kairos.config import get_settings
from tests.conftest import FakeProvider


def _request(**payload: object) -> AgentRequest:
    return AgentRequest(capability="reasoning.respond", payload=payload)


async def test_respond_returns_completion(fake_provider: FakeProvider) -> None:
    agent = ReasoningAgent(fake_provider)
    result = await agent.handle(_request(message="hola", owner="diego"))
    assert result.ok
    assert result.data["content"] == "respuesta"
    assert result.data["local"] is True
    assert result.trace[0].agent == "reasoning"


async def test_memories_are_injected_into_system_prompt(fake_provider: FakeProvider) -> None:
    agent = ReasoningAgent(fake_provider)
    await agent.handle(
        _request(
            message="que dije?",
            owner="diego",
            memories=[{"content": "prefiero respuestas cortas", "similarity": 0.82}],
        )
    )
    system = fake_provider.last_turns[0].content
    assert "MEMORIA" in system
    assert "prefiero respuestas cortas" in system


async def test_remote_provider_is_blocked_when_egress_disabled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    get_settings.cache_clear()
    monkeypatch.setenv("KAIROS_ALLOW_EGRESS", "false")
    agent = ReasoningAgent(FakeProvider(local=False))
    result = await agent.handle(_request(message="hola"))
    assert not result.ok
    assert "EGRESS" in (result.error or "")
    get_settings.cache_clear()


async def test_unsupported_capability_fails_cleanly(fake_provider: FakeProvider) -> None:
    agent = ReasoningAgent(fake_provider)
    result = await agent.handle(AgentRequest(capability="vision.detect"))
    assert not result.ok

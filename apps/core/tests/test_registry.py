from __future__ import annotations

from typing import Any

import pytest

from kairos.agents.base import Agent, AgentRequest, AgentResponse
from kairos.agents.registry import AgentRegistry


class DummyAgent(Agent):
    def __init__(self, name: str, capabilities: set[str]) -> None:
        self.name = name
        self.capabilities = frozenset(capabilities)

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        return AgentResponse(ok=True, data={"echo": request.capability})


def test_register_and_lookup_by_capability() -> None:
    registry = AgentRegistry()
    registry.register(DummyAgent("vision", {"vision.detect"}))
    registry.register(DummyAgent("voice", {"voice.transcribe"}))
    assert registry.find("vision.detect").name == "vision"
    assert registry.names == ["vision", "voice"]


def test_duplicate_agent_is_rejected() -> None:
    registry = AgentRegistry()
    registry.register(DummyAgent("vision", {"vision.detect"}))
    with pytest.raises(ValueError):
        registry.register(DummyAgent("vision", {"otra.cosa"}))


def test_unknown_capability_raises() -> None:
    registry = AgentRegistry()
    with pytest.raises(KeyError):
        registry.find("no.existe")

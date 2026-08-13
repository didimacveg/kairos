"""Tests del Device Agent (Fase 4).

Lo que se verifica aqui no es que funcione: es que NO pueda hacer de mas.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from kairos.agents.base import AgentRequest
from kairos.agents.device.agent import DeviceAgent


class FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler: Any) -> None:
        self._handler = handler
        self.calls: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return self._handler(request)


def _agent(monkeypatch: pytest.MonkeyPatch, handler: Any) -> tuple[DeviceAgent, FakeTransport]:
    original = httpx.AsyncClient
    transport = FakeTransport(handler)

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    return DeviceAgent(base_url="http://host:8200", token="secreto"), transport


async def test_profile_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    agent, _ = _agent(
        monkeypatch,
        lambda r: httpx.Response(200, json={"ok": True, "profile": "casa", "results": ["Spotify abierta"]}),
    )
    result = await agent.handle(
        AgentRequest(capability="device.profile", payload={"name": "casa"})
    )
    assert result.ok
    assert result.data["profile"] == "casa"


async def test_close_requires_explicit_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin confirmacion NO se llega siquiera a la red."""
    agent, transport = _agent(monkeypatch, lambda r: httpx.Response(200, json={"ok": True}))
    result = await agent.handle(
        AgentRequest(capability="device.close", payload={"pattern": "Word"})
    )
    assert not result.ok
    assert "confirmacion" in (result.error or "")
    assert transport.calls == [], "no debe haber salido ninguna peticion"


async def test_unknown_capability_is_rejected() -> None:
    agent = DeviceAgent(base_url="http://host:8200", token="x")
    for capability in ("device.exec", "device.shell", "system.run"):
        result = await agent.handle(AgentRequest(capability=capability))
        assert not result.ok


async def test_bridge_rejects_bad_token_readably(monkeypatch: pytest.MonkeyPatch) -> None:
    agent, _ = _agent(monkeypatch, lambda r: httpx.Response(401))
    result = await agent.handle(
        AgentRequest(capability="device.profile", payload={"name": "casa"})
    )
    assert not result.ok
    assert "token" in (result.error or "").lower()


async def test_bridge_down_does_not_crash_the_core(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    agent, _ = _agent(monkeypatch, handler)
    result = await agent.handle(
        AgentRequest(capability="device.profile", payload={"name": "casa"})
    )
    assert not result.ok
    assert "puente" in (result.error or "").lower()


async def test_token_travels_in_every_request(monkeypatch: pytest.MonkeyPatch) -> None:
    agent, transport = _agent(monkeypatch, lambda r: httpx.Response(200, json={"ok": True}))
    await agent.handle(AgentRequest(capability="device.focus", payload={"pattern": "Spotify"}))
    assert transport.calls[0].headers["x-bridge-token"] == "secreto"


async def test_empty_profile_name_is_rejected() -> None:
    agent = DeviceAgent(base_url="http://host:8200", token="x")
    result = await agent.handle(AgentRequest(capability="device.profile", payload={"name": "  "}))
    assert not result.ok

"""Tests del aplicador (Fase 24).

Lo unico del sistema que escribe en el repositorio real. Los tests verifican
que no escriba cuando no debe.
"""
from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest

from kairos.agents.base import AgentRequest
from kairos.agents.warden.agent import WardenAgent


class T(httpx.AsyncBaseTransport):
    def __init__(self, h: Any) -> None:
        self.h = h
        self.calls: list[httpx.Request] = []

    async def handle_async_request(self, r: httpx.Request) -> httpx.Response:
        self.calls.append(r)
        return self.h(r)


def _agente(monkeypatch: pytest.MonkeyPatch, handler: Any) -> tuple[WardenAgent, T]:
    original = httpx.AsyncClient
    t = T(handler)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **k: original(*a, **{**k, "transport": t})
    )
    return WardenAgent(base_url="http://warden:8400", token="w4rd3n"), t


async def test_identificador_invalido_no_llega_a_la_red(monkeypatch: pytest.MonkeyPatch) -> None:
    agente, t = _agente(monkeypatch, lambda r: httpx.Response(200, json={"ok": True}))

    class DbFalsa:
        async def execute(self, *a: Any, **k: Any) -> Any:
            raise AssertionError("no deberia consultarse")

    r = await agente.handle(
        AgentRequest(capability="warden.aplicar", payload={"proposal_id": "no-soy-uuid"}),
        db=DbFalsa(),
    )
    assert not r.ok
    assert t.calls == []


async def test_sin_sesion_de_base_de_datos_falla_limpio() -> None:
    agente = WardenAgent(base_url="http://warden:8400", token="x")
    r = await agente.handle(
        AgentRequest(capability="warden.aplicar", payload={"proposal_id": str(uuid.uuid4())})
    )
    assert not r.ok
    assert "base de datos" in (r.error or "")


async def test_capacidad_desconocida_se_rechaza() -> None:
    agente = WardenAgent(base_url="http://warden:8400", token="x")
    for cap in ("warden.shell", "warden.push", "warden.borrar"):
        assert not (await agente.handle(AgentRequest(capability=cap))).ok


async def test_warden_caido_no_tumba_el_nucleo(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    agente, _ = _agente(monkeypatch, handler)
    salud = await agente.health()
    assert salud["status"] == "unavailable"

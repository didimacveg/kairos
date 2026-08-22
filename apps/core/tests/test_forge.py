"""Tests del banco de pruebas (Fase 21).

Verifican lo mismo de siempre: que no pueda hacer de mas.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from kairos.agents.base import AgentRequest
from kairos.agents.forge.agent import ForgeAgent


class T(httpx.AsyncBaseTransport):
    def __init__(self, h: Any) -> None:
        self.h = h
        self.calls: list[httpx.Request] = []

    async def handle_async_request(self, r: httpx.Request) -> httpx.Response:
        self.calls.append(r)
        return self.h(r)


def _agente(monkeypatch: pytest.MonkeyPatch, handler: Any) -> tuple[ForgeAgent, T]:
    original = httpx.AsyncClient
    t = T(handler)
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda *a, **k: original(*a, **{**k, "transport": t}),
    )
    return ForgeAgent(base_url="http://forge:8300", token="s3cr3t"), t


async def test_ensayo_verde(monkeypatch: pytest.MonkeyPatch) -> None:
    agente, _ = _agente(monkeypatch, lambda r: httpx.Response(200, json={
        "ok": True, "pasos": [{"paso": "tests", "ok": True, "salida": "70 passed"}],
        "diff": "--- a\n+++ b", "duracion_ms": 12000,
    }))
    r = await agente.handle(AgentRequest(
        capability="forge.ensayar", payload={"rama": "kairos/x", "parche": "diff"}))
    assert r.ok and r.data["ok"]
    assert r.trace[0].detail["resultado"] == "verde"


async def test_ensayo_rojo_dice_donde_fallo(monkeypatch: pytest.MonkeyPatch) -> None:
    agente, _ = _agente(monkeypatch, lambda r: httpx.Response(200, json={
        "ok": False,
        "pasos": [
            {"paso": "clonar", "ok": True, "salida": ""},
            {"paso": "aplicar parche", "ok": False, "salida": "patch does not apply"},
        ],
        "diff": "", "duracion_ms": 800,
    }))
    r = await agente.handle(AgentRequest(
        capability="forge.ensayar", payload={"rama": "kairos/x", "parche": "roto"}))
    assert r.ok
    assert r.data["ok"] is False
    assert "aplicar parche" in r.trace[0].detail["resultado"]


async def test_sin_parche_no_sale_peticion(monkeypatch: pytest.MonkeyPatch) -> None:
    agente, t = _agente(monkeypatch, lambda r: httpx.Response(200, json={"ok": True}))
    r = await agente.handle(AgentRequest(capability="forge.ensayar", payload={"rama": "x"}))
    assert not r.ok
    assert t.calls == []


async def test_capacidad_desconocida_se_rechaza() -> None:
    agente = ForgeAgent(base_url="http://forge:8300", token="x")
    for cap in ("forge.aplicar", "forge.shell", "forge.deploy"):
        assert not (await agente.handle(AgentRequest(capability=cap))).ok


async def test_token_viaja_en_la_peticion(monkeypatch: pytest.MonkeyPatch) -> None:
    agente, t = _agente(monkeypatch, lambda r: httpx.Response(200, json={"ok": True, "pasos": []}))
    await agente.handle(AgentRequest(
        capability="forge.ensayar", payload={"rama": "kairos/x", "parche": "d"}))
    assert t.calls[0].headers["x-forge-token"] == "s3cr3t"


async def test_forge_caido_no_tumba_el_nucleo(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    agente, _ = _agente(monkeypatch, handler)
    r = await agente.handle(AgentRequest(
        capability="forge.ensayar", payload={"rama": "kairos/x", "parche": "d"}))
    assert not r.ok
    assert "inalcanzable" in (r.error or "").lower()

"""Forge Agent — puente entre el nucleo y el banco de pruebas.

Capacidad:
  forge.ensayar   parche + rama -> resultado de los tests y diff efectivo

El nucleo NO ejecuta el codigo propuesto: se lo pasa al forge, que corre
aislado y sin red. Si el parche es hostil, lo peor que puede hacer es
destruirse a si mismo dentro de un contenedor efimero.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.config import get_settings


class ForgeAgent(Agent):
    name = "forge"
    capabilities = frozenset({"forge.ensayar"})

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        s = get_settings()
        self._base_url = (base_url or s.forge_url).rstrip("/")
        self._token = token if token is not None else s.forge_token
        # Un ensayo clona, parchea y corre la suite: minutos, no segundos.
        self._timeout = 420

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "forge.ensayar":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        parche = (request.payload.get("parche") or "").strip()
        rama = (request.payload.get("rama") or "").strip()
        if not parche or not rama:
            return AgentResponse.failure("Hacen falta rama y parche")

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.post(
                    f"{self._base_url}/ensayar",
                    json={"rama": rama, "parche": parche},
                    headers={"x-forge-token": self._token},
                )
                if r.status_code >= 400:
                    detalle = r.json().get("detail", r.text)
                    return AgentResponse.failure(f"Forge: {detalle}")
                body = r.json()
        except httpx.HTTPError as exc:
            return AgentResponse.failure(f"Forge inalcanzable: {type(exc).__name__}")

        fallo = next((p["paso"] for p in body.get("pasos", []) if not p["ok"]), None)
        return AgentResponse(
            ok=True,
            data=body,
            trace=[
                TraceEvent(
                    agent=self.name,
                    step="ensayar",
                    detail={
                        "rama": rama,
                        "resultado": "verde" if body.get("ok") else f"falla en {fallo}",
                        "lineas_parche": parche.count("\n") + 1,
                    },
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            ],
        )

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                r = await client.get(f"{self._base_url}/health")
                if r.status_code != 200:
                    return {"agent": self.name, "status": "unavailable"}
                return {"agent": self.name, "status": r.json().get("status", "ok")}
        except httpx.HTTPError:
            return {"agent": self.name, "status": "unavailable"}

"""Device Agent — puente entre el nucleo y el escritorio.

Capacidades:
  device.profile   ejecuta un perfil declarado (nombre, no comando)
  device.focus     trae una ventana al frente
  device.close     cierra una ventana (exige confirmacion explicita)
  device.status    que perfiles existen y como esta el escritorio

Punto clave del diseno: este agente NO puede ejecutar comandos. Solo puede
pedir al puente acciones POR NOMBRE, y el puente solo conoce las que Diego ha
declarado en su fichero de configuracion. Si el modelo alucina un perfil que
no existe, el puente responde "perfil no declarado" y no pasa nada.

Es la diferencia entre darle a un modelo de lenguaje una terminal y darle un
mando a distancia con botones fijos. Aqui es lo segundo, a proposito.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.config import get_settings


class DeviceAgent(Agent):
    name = "device"
    capabilities = frozenset(
        {"device.profile", "device.focus", "device.close", "device.status"}
    )

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.bridge_url).rstrip("/")
        self._token = token if token is not None else settings.bridge_token
        self._timeout = 60

    def _headers(self) -> dict[str, str]:
        return {"x-bridge-token": self._token}

    async def _call(self, path: str, payload: dict[str, Any]) -> tuple[bool, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}{path}", json=payload, headers=self._headers()
                )
                if response.status_code == 401:
                    return False, "El puente rechazo el token. Revisa KAIROS_BRIDGE_TOKEN."
                if response.status_code >= 400:
                    return False, f"El puente respondio {response.status_code}"
                return True, response.json()
        except httpx.HTTPError:
            return False, (
                "El puente no responde. ¿Esta corriendo bridge.py en Windows?"
            )

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        started = time.perf_counter()
        capability = request.capability

        if capability == "device.status":
            ok, body = await self._status()
        elif capability == "device.profile":
            name = (request.payload.get("name") or "").strip()
            if not name:
                return AgentResponse.failure("Falta el nombre del perfil")
            ok, body = await self._call("/profile", {"name": name})
        elif capability == "device.focus":
            pattern = (request.payload.get("pattern") or "").strip()
            if not pattern:
                return AgentResponse.failure("Falta la ventana")
            ok, body = await self._call("/focus", {"pattern": pattern})
        elif capability == "device.close":
            pattern = (request.payload.get("pattern") or "").strip()
            # La confirmacion tiene que venir del usuario, no del modelo.
            if not request.payload.get("confirm"):
                return AgentResponse.failure(
                    "Cerrar una ventana requiere confirmacion explicita del usuario"
                )
            ok, body = await self._call("/close", {"pattern": pattern, "confirm": True})
        else:
            return AgentResponse.failure(f"Capacidad no soportada: {capability}")

        if not ok:
            return AgentResponse.failure(str(body))

        return AgentResponse(
            ok=True,
            data=body if isinstance(body, dict) else {"result": body},
            trace=[
                TraceEvent(
                    agent=self.name,
                    step=capability.split(".", 1)[1],
                    detail={k: v for k, v in request.payload.items() if k != "confirm"},
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            ],
        )

    async def _status(self) -> tuple[bool, Any]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self._base_url}/health")
                if response.status_code != 200:
                    return False, f"El puente respondio {response.status_code}"
                return True, response.json()
        except httpx.HTTPError:
            return False, "El puente no responde"

    async def health(self) -> dict[str, Any]:
        ok, body = await self._status()
        if not ok:
            return {"agent": self.name, "status": "unavailable"}
        return {
            "agent": self.name,
            "status": "ok",
            "perfiles": body.get("perfiles", []),
            "monitores": len(body.get("escritorio", {}).get("monitores", [])),
        }

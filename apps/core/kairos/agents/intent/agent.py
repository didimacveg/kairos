"""Intent Agent — entiende lo que quieres decir, no lo que has dicho exacto.

El problema que resuelve: hasta ahora las ordenes se reconocian con
expresiones regulares. Funcionaba para "abre el perfil trabajo" y fallaba con
"entra en modo trabajo", "activa el rollo de estudiar" o "abre el... hmm...
modo estudio". Eso es un asistente por comandos, no un asistente.

La solucion NO es dejar que el modelo ejecute lo que le parezca. Es esta:

    el modelo NO emite ordenes; ELIGE una de una lista cerrada.

Recibe las acciones disponibles y los perfiles que existen, y devuelve JSON
con una accion de esa lista. Todo lo que no este en la lista se descarta al
validar, aqui, antes de salir del nucleo. Un modelo que alucine
"formatea_el_disco" recibe un rechazo silencioso: esa accion no existe.

Es la diferencia entre darle un teclado y darle un mando con botones fijos.
Sigue siendo un mando; solo que ahora entiende como se lo pides.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider

# Lista cerrada. Anadir una accion aqui es una decision de diseno consciente,
# no algo que el modelo pueda hacer por su cuenta.
ACTIONS = {
    "abrir_perfil": ["perfil"],
    "abrir_app": ["app"],
    "cerrar_perfil": ["perfil"],
    "cambiar_perfil": ["perfil", "perfil_anterior"],
    "poner_musica": ["consulta"],
    "pausar_musica": [],
    "reanudar_musica": [],
    "siguiente_cancion": [],
    "cancion_anterior": [],
    "subir_volumen": [],
    "bajar_volumen": [],
    "poner_volumen": ["porcentaje"],
    "que_suena": [],
    "conversar": [],
}

PROMPT = """Clasificas ordenes de voz para KAIROS, un asistente personal.

Acciones disponibles (NO puedes inventar otras):
{acciones}

Perfiles que existen (NO puedes inventar otros):
{perfiles}

Aplicaciones que existen (NO puedes inventar otras):
{apps}

Reglas:
- Devuelve SOLO un objeto JSON, sin texto alrededor ni ```.
- Formato: {{"accion": "...", "perfil": "...", "consulta": "...", "porcentaje": 0}}
- Incluye solo los campos que la accion necesite.
- El usuario habla por voz: habra titubeos ("abre el... hmm... modo estudio"),
  transcripciones imperfectas y sinonimos. Interpreta la INTENCION.
- "modo trabajo", "perfil de trabajo", "entra en trabajo", "ponme a trabajar"
  son todos abrir_perfil con perfil "trabajo".
- Para poner_musica, "consulta" es SOLO el nombre de la cancion o artista.
  Quita coletillas como "en spotify", "porfa", "va".
- Si no es una orden sino conversacion o una pregunta, devuelve
  {{"accion": "conversar"}}. Ante la duda, conversar: ejecutar algo que no se
  pidio es peor que no hacer nada.

Ejemplos:
"kairos entra en modo trabajo" -> {{"accion":"abrir_perfil","perfil":"trabajo"}}
"venga ponme el rollo de estudiar" -> {{"accion":"abrir_perfil","perfil":"estudio"}}
"quita el perfil de juego" -> {{"accion":"cerrar_perfil","perfil":"juego"}}
"sal de trabajo y entra en juego" -> {{"accion":"cambiar_perfil","perfil":"juego","perfil_anterior":"trabajo"}}
"reproduce safari de serrat en spotify" -> {{"accion":"poner_musica","consulta":"safari serrat"}}
"para la musica un momento" -> {{"accion":"pausar_musica"}}
"ponlo al cuarenta por ciento" -> {{"accion":"poner_volumen","porcentaje":40}}
"que cancion es esta" -> {{"accion":"que_suena"}}
"abre spotify" -> {{"accion":"abrir_app","app":"spotify"}}
"ponme youtube" -> {{"accion":"abrir_app","app":"youtube"}}
"lanza el visual studio" -> {{"accion":"abrir_app","app":"vscode"}}
"que tiempo hace manana" -> {{"accion":"conversar"}}"""


def parse_intent(
    raw: str, profiles: list[str], apps: list[str] | None = None
) -> dict[str, Any]:
    """Valida la salida del modelo contra la lista cerrada.

    Nunca lanza. Todo lo dudoso acaba en `conversar`, que no toca nada.
    """
    apps = apps or []
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return {"accion": "conversar"}
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {"accion": "conversar"}
    if not isinstance(parsed, dict):
        return {"accion": "conversar"}

    accion = parsed.get("accion")
    if accion not in ACTIONS:
        return {"accion": "conversar"}

    resultado: dict[str, Any] = {"accion": accion}

    if "app" in ACTIONS[accion]:
        app = str(parsed.get("app", "")).strip().lower()
        # Igual que los perfiles: una app inventada no llega al puente.
        if app not in apps:
            return {"accion": "conversar"}
        resultado["app"] = app

    if "perfil" in ACTIONS[accion]:
        perfil = str(parsed.get("perfil", "")).strip().lower()
        # Un perfil que no existe se rechaza aqui, no en el puente.
        if perfil not in profiles:
            return {"accion": "conversar"}
        resultado["perfil"] = perfil

    if "perfil_anterior" in ACTIONS[accion]:
        anterior = str(parsed.get("perfil_anterior", "")).strip().lower()
        if anterior in profiles:
            resultado["perfil_anterior"] = anterior

    if "consulta" in ACTIONS[accion]:
        consulta = str(parsed.get("consulta", "")).strip()
        consulta = re.sub(r"\b(en|por|con)\s+spotify\b", "", consulta, flags=re.I).strip()
        if not consulta or len(consulta) > 120:
            return {"accion": "conversar"}
        resultado["consulta"] = consulta

    if "porcentaje" in ACTIONS[accion]:
        try:
            resultado["porcentaje"] = max(0, min(100, int(parsed.get("porcentaje", 50))))
        except (TypeError, ValueError):
            resultado["porcentaje"] = 50

    return resultado


class IntentAgent(Agent):
    name = "intent"
    capabilities = frozenset({"intent.classify"})

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "intent.classify":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        text = (request.payload.get("text") or "").strip()
        if not text:
            return AgentResponse.failure("Sin texto que clasificar")

        profiles = [p.lower() for p in request.payload.get("profiles", [])]
        acciones = "\n".join(
            f"- {a}" + (f" (campos: {', '.join(c)})" if c else "") for a, c in ACTIONS.items()
        )
        apps = [a.lower() for a in request.payload.get("apps", [])]
        system = PROMPT.format(
            acciones=acciones,
            perfiles=", ".join(profiles) or "ninguno declarado",
            apps=", ".join(apps) or "ninguna declarada",
        )

        started = time.perf_counter()
        try:
            completion = await self._provider.complete(
                [ChatTurn(role="system", content=system), ChatTurn(role="user", content=text)]
            )
        except Exception as exc:  # noqa: BLE001
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")

        intent = parse_intent(completion.text, profiles, apps)
        return AgentResponse(
            ok=True,
            data=intent,
            trace=[
                TraceEvent(
                    agent=self.name,
                    step="classify",
                    detail={"accion": intent["accion"], "modelo": completion.model},
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            ],
        )

    async def health(self) -> dict[str, Any]:
        return {"agent": self.name, "status": "ok", "acciones": len(ACTIONS)}

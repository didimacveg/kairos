"""Extraccion de hechos memorizables a partir de un intercambio.

El problema que resuelve: hasta la Fase 2A, KAIROS indexaba literalmente cada
mensaje del usuario. Eso llenaba la memoria de preguntas ("¿cuando trabajo
mejor?"), de peticiones ("escribeme una historia sobre un farero") y de
duplicados exactos, que despues competian con los hechos reales en cada
recuperacion. Una peticion no es un hecho sobre el usuario.

La decision de que merece recordarse la toma el propio modelo local, con un
prompt estricto y salida JSON. Es una llamada extra al LLM por turno, pero se
ejecuta DESPUES de que el usuario ya tenga su respuesta, asi que no anade
latencia percibida.

Limitacion asumida: un modelo de 8B se equivoca. Por eso la salida se valida
con dureza (esquema, longitud, numero de hechos) y ante cualquier duda se
descarta el candidato. Preferimos perder un hecho que ensuciar la memoria:
un recuerdo falso contamina todas las busquedas futuras, uno ausente solo se
vuelve a mencionar.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider
from kairos.logging import get_logger

log = get_logger("kairos.memory.extractor")

MAX_FACTS_PER_TURN = 4
MAX_FACT_CHARS = 300
VALID_KINDS = {"semantic", "preference", "episodic"}

EXTRACTION_PROMPT = """Analizas un intercambio entre un usuario y su asistente personal.
Tu unica tarea es decidir que informacion DURADERA sobre el usuario merece guardarse.

Guarda SOLO:
- Hechos estables sobre el usuario (donde vive, que estudia, en que trabaja, que tiene).
- Preferencias declaradas (como quiere las respuestas, que le gusta, que evita).
- Decisiones o planes que el usuario afirma (no los que el asistente propone).

NO guardes NUNCA:
- Preguntas o peticiones del usuario. "Escribeme una historia" no es un hecho.
- Contenido generado por el asistente (historias, explicaciones, definiciones).
- Conocimiento general del mundo. La entropia no es un dato sobre el usuario.
- Estados pasajeros: que hora es, que tiempo hace, en que paso va ahora mismo.
- Saludos, agradecimientos, cortesias.

Reglas de formato:
- Escribe cada hecho en tercera persona, autocontenido, sin pronombres ambiguos.
- Un hecho por entrada. Nada de frases con varias afirmaciones.
- Anade "subject": un identificador corto en minusculas del TEMA del hecho
  (longitud_respuestas, horario_trabajo, ubicacion, estudios, tono).
  Dos hechos sobre el mismo tema deben llevar el MISMO subject, aunque digan
  cosas opuestas. Es lo que permite que un dato nuevo sustituya al viejo.
- Maximo {max_facts} hechos. Si no hay ninguno, devuelve una lista vacia.

Ejemplos:

USUARIO: prefiero respuestas cortas
ASISTENTE: Entendido.
[{{"content": "Prefiere respuestas cortas.", "kind": "preference", "subject": "longitud_respuestas"}}]

USUARIO: estudio primero de bachillerato y vivo en Madrid
ASISTENTE: Anotado.
[{{"content": "Estudia primero de bachillerato.", "kind": "semantic", "subject": "estudios"}}, {{"content": "Vive en Madrid.", "kind": "semantic", "subject": "ubicacion"}}]

USUARIO: no me gusta que uses emojis
ASISTENTE: De acuerdo.
[{{"content": "No quiere que se usen emojis.", "kind": "preference", "subject": "uso_emojis"}}]

USUARIO: que es un algoritmo
ASISTENTE: Un algoritmo es una secuencia de pasos.
[]

USUARIO: escribeme una historia sobre un farero
ASISTENTE: Habia una vez un faro...
[]

USUARIO: hola
ASISTENTE: Hola, en que puedo ayudarte.
[]

Fijate: "prefiero", "no me gusta", "odio", "siempre", "nunca" seguidos de algo
que el usuario afirma sobre si mismo SI son hechos guardables (kind preference).
Lo que descartas son preguntas y encargos de trabajo, no las declaraciones.

Responde EXCLUSIVAMENTE con un array JSON, sin texto antes ni despues:
[{{"content": "...", "kind": "semantic|preference|episodic", "subject": "tema_corto"}}]

Si no hay nada que guardar, responde exactamente: []"""


@dataclass(frozen=True)
class FactCandidate:
    content: str
    kind: str
    subject: str = ""


def _strip_fences(raw: str) -> str:
    """Quita los ``` que los modelos pequenos anaden pese a pedir JSON puro."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _first_json_array(text: str) -> str | None:
    """Localiza el primer array JSON del texto.

    Un modelo pequeno a veces antepone "Aqui tienes:" pese a la instruccion.
    Recortar por corchetes es mas robusto que rechazar la respuesta entera.
    """
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None
    return text[start : end + 1]


def parse_extraction(raw: str) -> list[FactCandidate]:
    """Convierte la salida cruda del modelo en candidatos validados.

    Toda anomalia se resuelve descartando. Esta funcion no lanza nunca.
    """
    text = _first_json_array(_strip_fences(raw))
    if text is None:
        return []

    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    candidates: list[FactCandidate] = []
    for entry in parsed[:MAX_FACTS_PER_TURN]:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content")
        kind = entry.get("kind", "semantic")
        if not isinstance(content, str) or not isinstance(kind, str):
            continue
        content = content.strip()
        if not content or len(content) > MAX_FACT_CHARS:
            continue
        # Una interrogacion es la senal mas fiable de que el modelo ha
        # guardado una pregunta pese a la instruccion explicita.
        if content.endswith("?") or content.startswith("¿"):
            continue
        if kind not in VALID_KINDS:
            kind = "semantic"
        subject = entry.get("subject", "")
        if not isinstance(subject, str):
            subject = ""
        subject = re.sub(r"[^a-z0-9_]", "", subject.strip().lower().replace(" ", "_"))[:48]
        candidates.append(FactCandidate(content=content, kind=kind, subject=subject))
    return candidates


class FactExtractor:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def extract(self, *, user_message: str, assistant_reply: str) -> list[FactCandidate]:
        exchange = (
            f"USUARIO: {user_message}\n\nASISTENTE: {assistant_reply[:2000]}"
        )
        turns = [
            ChatTurn(
                role="system",
                content=EXTRACTION_PROMPT.format(max_facts=MAX_FACTS_PER_TURN),
            ),
            ChatTurn(role="user", content=exchange),
        ]
        try:
            completion = await self._provider.complete(turns)
        except Exception as exc:  # noqa: BLE001
            log.warning("extraction.failed", error=str(exc))
            return []
        return parse_extraction(completion.text)

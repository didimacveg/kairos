"""Interpretacion de ordenes de voz: SOLO PATRONES INEQUIVOCOS.

Esta es la via rapida: 0 ms, sin red. Todo lo que no encaje aqui pasa al
clasificador de intencion del nucleo, que entiende lenguaje natural.

Leccion aprendida en uso real: "ponme el rollo ese de estudiar" encajaba con
el patron de musica y KAIROS puso una cancion en vez de abrir el perfil de
estudio. Un patron demasiado goloso hace algo INCORRECTO; uno que no encaja
solo cede el turno al modelo, que entiende mejor. Ante la duda, no encajar.

Por eso "pon X" ya no esta aqui: es la construccion mas ambigua del espanol.
Los perfiles y las ordenes de transporte, que si son inequivocas, se quedan.

Y nada de esto pasa por el modelo: un LLM puede alucinar "cierra el perfil
trabajo" a partir de una conversacion cualquiera; una expresion regular sobre
tu voz, no.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def normalize(text: str) -> str:
    """Sin acentos ni mayusculas: Whisper es inconsistente con ambos."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip(" .,!?¿¡")


OPEN = re.compile(
    r"\b(abre|abrir|ejecuta|ejecutar|activa|activar|lanza|inicia|entra en)\b"
    r".{0,20}?\b(perfil|modo)\b\s+(?:de\s+)?(?P<name>[a-z]+)"
)
CLOSE = re.compile(
    r"\b(cierra|cerrar|apaga|apagar|termina|desactiva|quita|sal de)\b"
    r".{0,20}?\b(perfil|modo)\b\s+(?:de\s+)?(?P<name>[a-z]+)"
)
SWITCH = re.compile(
    r"\b(cierra|sal de)\b.{0,20}?\b(perfil|modo)\b\s+(?:de\s+)?(?P<from>[a-z]+)"
    r".{0,25}?\b(abre|entra en)\b.{0,20}?\b(perfil|modo)\b\s+(?:de\s+)?(?P<to>[a-z]+)"
)

# Transporte: inequivoco porque exige el objeto explicito.
PAUSE = re.compile(
    r"\b(pausa|pausar|para|parar|deten|detener|silencia|quita)\b"
    r"\s+(la\s+|el\s+)?(musica|cancion|spotify|sonido)\b"
)
RESUME = re.compile(r"\b(reanuda|continua|quita la pausa)\b")
NEXT = re.compile(r"\b(siguiente|otra)\s+(cancion|tema)\b|\bpasa de cancion\b")
PREV = re.compile(r"\b(anterior|previa)\s+cancion\b|\bcancion anterior\b")
NOW = re.compile(r"\bque\b.{0,15}\b(suena|esta sonando|cancion es)\b")


@dataclass
class Command:
    kind: str  # open | close | switch | phrase | pause | resume | next
               # | prev | now | none
    name: str = ""
    other: str = ""


def parse(text: str, phrases: dict[str, str]) -> Command:
    """Traduce voz a una orden. `none` = que lo decida el modelo."""
    clean = normalize(text)

    # Las frases declaradas ganan: son las que tu has escrito.
    for phrase, profile in phrases.items():
        if normalize(phrase) in clean:
            return Command(kind="phrase", name=profile)

    if (m := SWITCH.search(clean)) is not None:
        return Command(kind="switch", name=m.group("to"), other=m.group("from"))
    if (m := CLOSE.search(clean)) is not None:
        return Command(kind="close", name=m.group("name"))
    if (m := OPEN.search(clean)) is not None:
        return Command(kind="open", name=m.group("name"))

    if NOW.search(clean):
        return Command(kind="now")
    if NEXT.search(clean):
        return Command(kind="next")
    if PREV.search(clean):
        return Command(kind="prev")
    if RESUME.search(clean):
        return Command(kind="resume")
    if PAUSE.search(clean):
        return Command(kind="pause")

    # "pon X" NO se resuelve aqui. Demasiado ambiguo: lo decide el modelo.
    return Command(kind="none")

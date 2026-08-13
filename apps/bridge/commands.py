"""Interpretacion de ordenes de voz sobre perfiles.

Deliberadamente NO usa el modelo de lenguaje. Son cuatro patrones fijos, y esa
es la garantia: un modelo puede alucinar "cierra el perfil trabajo" a partir
de una conversacion cualquiera; una expresion regular sobre tu voz, no.

Todo lo que no encaje con estos patrones se manda al nucleo como conversacion
normal, sin tocar el escritorio.
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
    r"\b(abre|abrir|ejecuta|ejecutar|activa|activar|lanza|pon|inicia)\b"
    r".{0,20}?\bperfil\b\s+(?:de\s+)?(?P<name>[a-z]+)"
)
CLOSE = re.compile(
    r"\b(cierra|cerrar|apaga|apagar|termina|desactiva|quita)\b"
    r".{0,20}?\bperfil\b\s+(?:de\s+)?(?P<name>[a-z]+)"
)
SWITCH = re.compile(
    r"\bcierra\b.{0,20}?\bperfil\b\s+(?:de\s+)?(?P<from>[a-z]+)"
    r".{0,20}?\babre\b.{0,20}?\bperfil\b\s+(?:de\s+)?(?P<to>[a-z]+)"
)


# --- musica ---------------------------------------------------------------
# Igual que los perfiles: patrones fijos, no el modelo. "Pausa la musica" no
# puede salir de una alucinacion.
PLAY = re.compile(
    r"\b(pon|ponme|reproduce|escuchar|suena|dale a)\b\s+(?P<query>.{2,80})"
)
# El objeto es OBLIGATORIO. Sin el, "para" —una de las palabras mas comunes
# del espanol— convertia media conversacion en una orden de pausa.
PAUSE = re.compile(
    r"\b(pausa|pausar|para|parar|deten|detener|silencia|quita)\b"
    r"\s+(la\s+|el\s+)?(musica|cancion|spotify|sonido)\b"
)
RESUME = re.compile(r"\b(reanuda|continua|sigue|quita la pausa)\b")
NEXT = re.compile(r"\b(siguiente|pasa|salta|otra)\b.{0,12}\bcancion\b|\bsiguiente cancion\b")
PREV = re.compile(r"\b(anterior|atras|vuelve)\b.{0,12}\bcancion\b")
VOLUME = re.compile(r"\bvolumen\b.{0,12}?(?P<pct>\d{1,3})|\b(sube|baja)\b.{0,12}\bvolumen\b")
NOW = re.compile(r"\bque\b.{0,12}\b(suena|esta sonando|cancion es)\b")


@dataclass
class Command:
    kind: str  # open | close | switch | phrase | play | pause | resume
               # | next | prev | volume | now | none
    name: str = ""
    other: str = ""


def parse(text: str, phrases: dict[str, str]) -> Command:
    """Traduce voz a una orden sobre perfiles. `none` = no es una orden."""
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

    # --- musica ---
    if NOW.search(clean):
        return Command(kind="now")
    if (m := VOLUME.search(clean)) is not None:
        pct = m.group("pct")
        if pct:
            return Command(kind="volume", name=pct)
        return Command(kind="volume", name="80" if "sube" in clean else "30")
    if NEXT.search(clean):
        return Command(kind="next")
    if PREV.search(clean):
        return Command(kind="prev")
    if RESUME.search(clean):
        return Command(kind="resume")
    if PAUSE.search(clean):
        return Command(kind="pause")
    if (m := PLAY.search(clean)) is not None:
        query = m.group("query").strip()
        # "pon el perfil trabajo" ya lo habria cogido OPEN; si llega aqui con
        # "perfil" dentro es ruido de transcripcion, no una cancion.
        if "perfil" not in query:
            return Command(kind="play", name=query)

    return Command(kind="none")

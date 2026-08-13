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


@dataclass
class Command:
    kind: str  # open | close | switch | phrase | none
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

    return Command(kind="none")

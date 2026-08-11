"""Auditoria y limpieza de la memoria acumulada.

Existe porque la Fase 1 y la 2A indexaron todo mensaje del usuario sin
filtrar. Al activar el curado, esa basura sigue ahi y sigue compitiendo en
cada recuperacion.

Regla de esta herramienta: NUNCA borra por su cuenta. Clasifica, ensena lo que
propone retirar, y solo actua si se le pasa `apply=True` desde la CLI. La
memoria es del usuario; una limpieza automatica que se equivoca es
indistinguible de una perdida de datos.

"Retirar" significa marcar `status='discarded'`, no DELETE. Reversible.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.db.models import MemoryItem

QUESTION_STARTERS = (
    "que ", "qué ", "quien ", "quién ", "como ", "cómo ", "cuando ", "cuándo ",
    "donde ", "dónde ", "por que", "por qué", "cual ", "cuál ", "cuanto ", "cuánto ",
)
REQUEST_STARTERS = (
    "escribe", "escribeme", "escríbeme", "cuentame", "cuéntame", "explica",
    "explicame", "explícame", "dame", "hazme", "haz ", "genera", "crea ",
    "dime", "resume", "traduce", "muestra", "lista ", "ayudame", "ayúdame",
)
GREETINGS = {"hola", "buenas", "adios", "adiós", "gracias", "vale", "ok", "despierta"}


@dataclass(frozen=True)
class Verdict:
    id: str
    content: str
    reason: str


def classify(content: str) -> str | None:
    """Devuelve el motivo por el que este recuerdo no deberia estar, o None."""
    text = content.strip().lower()
    if not text:
        return "vacio"
    if len(text) < 4 or text in GREETINGS:
        return "saludo o interjeccion"
    if text.startswith("¿") or text.endswith("?"):
        return "es una pregunta, no un hecho"
    if text.startswith(QUESTION_STARTERS):
        return "es una pregunta, no un hecho"
    if text.startswith(REQUEST_STARTERS):
        return "es una peticion, no un hecho"
    return None


async def review(db: AsyncSession, *, apply: bool = False) -> tuple[list[Verdict], int]:
    """Clasifica la memoria activa. Con apply=True marca los descartes."""
    rows = (
        await db.execute(select(MemoryItem).where(MemoryItem.status == "active"))
    ).scalars().all()

    verdicts = [
        Verdict(id=str(item.id), content=item.content, reason=reason)
        for item in rows
        if (reason := classify(item.content)) is not None
    ]

    if apply and verdicts:
        await db.execute(
            update(MemoryItem)
            .where(MemoryItem.id.in_([v.id for v in verdicts]))
            .values(status="discarded")
        )
        await db.commit()

    return verdicts, len(rows)

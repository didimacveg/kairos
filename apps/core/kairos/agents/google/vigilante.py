"""Avisos por remitente: "cuando me escriba X, avisame".

Se apoya en la agenda que ya existe. Un aviso de correo es un recordatorio
abierto mas: algo cuya fecha no se sabe todavia y hay que ir comprobando.

POR QUE NO ES UN AGENTE NUEVO: la agenda ya sabe resolver avisos abiertos,
persistirlos y dispararlos. Anadir un sistema paralelo para lo mismo seria
duplicar el problema de mantener dos.

LO QUE SE COMPRUEBA CADA VEZ: solo el correo LLEGADO DESDE LA ULTIMA REVISION.
Sin esa marca, cada ciclo encontraria los mismos correos y avisaria en bucle.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.google import gmail
from kairos.db.models import Reminder
from kairos.logging import get_logger

log = get_logger("kairos.google.vigilante")

# Cuanto atras se mira como maximo, aunque lleve dias sin revisarse. Mas de un
# dia y un arranque tras el fin de semana avisaria de veinte correos viejos.
VENTANA_MAX_HORAS = 24

_PIDE_AVISO_CORREO = re.compile(
    r"\b(avisame|avisa|dime|notificame)\b.{0,40}"
    r"\b(correo|email|mail|escriba|escribe|mande|manda)\b"
    r"|\bcuando\s+(me\s+)?(escriba|mande|llegue)\b",
    re.I,
)


def es_aviso_de_correo(texto: str) -> bool:
    """¿Es un aviso sobre correo y no sobre otra cosa?"""
    import unicodedata

    limpio = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )
    return bool(_PIDE_AVISO_CORREO.search(limpio))


def extraer_remitente(texto: str) -> str:
    """Saca de quien hay que avisar.

    Devuelve una consulta lista para Gmail: si hay un correo entero, `from:`;
    si es un nombre, se busca en remitente Y asunto, porque "el instituto"
    puede llegar de varias direcciones distintas.
    """
    correo = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", texto)
    if correo:
        return f"from:{correo.group(0)}"

    m = re.search(
        r"\b(?:escriba|escribe|mande|manda|llegue|de|desde)\s+"
        r"(?:un\s+correo\s+)?(?:de\s+|del\s+|la\s+|el\s+)?"
        r"(?P<quien>[\w\sáéíóúñÁÉÍÓÚÑ]{3,40}?)"
        r"(?:\s*[,.]|\s+avisa|\s*$)",
        texto, re.I,
    )
    if m:
        quien = m.group("quien").strip()
        if quien:
            return f"from:{quien} OR subject:{quien}"
    return ""


async def revisar(db: AsyncSession, owner_id: Any) -> list[str]:
    """Comprueba los avisos de correo activos. Devuelve los textos a decir."""
    filas = (
        await db.execute(
            select(Reminder).where(
                Reminder.owner_id == owner_id,
                Reminder.kind == "correo",
                Reminder.status == "pendiente",
            )
        )
    ).scalars().all()
    if not filas:
        return []

    avisos: list[str] = []
    ahora = datetime.now(timezone.utc)

    for fila in filas:
        # Solo lo llegado desde la ultima revision, con tope de un dia.
        desde = fila.last_attempt_at or (ahora - timedelta(hours=1))
        horas = max(1, min(VENTANA_MAX_HORAS, int((ahora - desde).total_seconds() / 3600) + 1))
        fila.last_attempt_at = ahora

        consulta = f"{fila.query} newer_than:{horas}h" if fila.query else ""
        if not consulta:
            continue

        correos = await gmail.buscar(consulta, limite=5)
        if not correos:
            continue

        # El aviso dice QUIEN y DE QUE, no el cuerpo: es lo que necesitas para
        # decidir si vale la pena mirarlo ahora.
        for c in correos[:2]:
            remitente = c["de"].split("<")[0].strip().strip('"') or c["de"]
            avisos.append(f"Correo de {remitente}. Asunto: {c['asunto']}.")
        log.info("vigilante.correo", encontrados=len(correos))

    await db.commit()
    return avisos

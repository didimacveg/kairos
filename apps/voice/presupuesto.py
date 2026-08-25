"""Presupuesto de caracteres de la voz buena.

El plan gratuito de ElevenLabs son 10.000 caracteres al mes: unos diez
minutos de audio. Con los informes diarios (≈500 caracteres) y las respuestas
de conversacion, se agota en tres o cuatro dias.

Este modulo hace dos cosas:

1. **Reparte por importancia.** No todo el audio merece la voz buena. El
   despertar, los avisos urgentes y lo que se va a grabar, si. "Son las tres
   y media" y las respuestas rutinarias, no.

2. **Cuenta y frena.** Lleva la cuenta de lo gastado en el mes y deja de
   usar ElevenLabs al llegar al limite, en vez de fallar con un 401 a mitad
   de una frase.

El estado vive en disco, no en memoria: un reinicio del contenedor no debe
regalar cuota que ya se gasto.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

RUTA = Path(os.getenv("KAIROS_TTS_PRESUPUESTO", "/var/lib/kairos/tts-presupuesto.json"))

# Se para un poco antes del limite real: quedarse sin cuota a mitad de una
# frase es peor que quedarse corto.
LIMITE_MES = int(os.getenv("KAIROS_ELEVENLABS_LIMITE", "9000"))

# Que se lleva la voz buena. Todo lo demas va por Deepgram.
IMPORTANTES = {
    "despertar",     # la secuencia de arranque
    "urgente",       # avisos de la vigilancia con urgencia alta
    "informe",       # el informe diario, que se escucha entero
    "recordatorio",  # los avisos de la agenda
}


def _estado() -> dict:
    if not RUTA.exists():
        return {"mes": "", "gastado": 0}
    try:
        return json.loads(RUTA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"mes": "", "gastado": 0}


def _guardar(estado: dict) -> None:
    try:
        RUTA.parent.mkdir(parents=True, exist_ok=True)
        RUTA.write_text(json.dumps(estado), encoding="utf-8")
    except OSError:
        # Si no se puede escribir, el contador se pierde al reiniciar. Es
        # peor que llevarlo, pero no justifica tumbar la sintesis.
        pass


def _mes_actual() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def gastado() -> int:
    e = _estado()
    return int(e.get("gastado", 0)) if e.get("mes") == _mes_actual() else 0


def restante() -> int:
    return max(0, LIMITE_MES - gastado())


def merece_voz_buena(texto: str, motivo: str = "") -> bool:
    """¿Este audio justifica gastar cuota de la voz buena?

    Dos condiciones: que el motivo este en la lista, y que quede cuota. Sin
    motivo declarado, se asume rutina — el reparto por defecto tiene que ser
    el barato, no el caro.
    """
    if motivo not in IMPORTANTES:
        return False
    return len(texto) <= restante()


def apuntar(caracteres: int) -> None:
    mes = _mes_actual()
    e = _estado()
    if e.get("mes") != mes:
        e = {"mes": mes, "gastado": 0}
    e["gastado"] = int(e.get("gastado", 0)) + caracteres
    _guardar(e)


def resumen() -> dict:
    g = gastado()
    return {
        "limite_mes": LIMITE_MES,
        "gastado": g,
        "restante": max(0, LIMITE_MES - g),
        "porcentaje": round(g / LIMITE_MES * 100, 1) if LIMITE_MES else 0,
        "motivos_con_voz_buena": sorted(IMPORTANTES),
    }

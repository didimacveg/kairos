"""Diagnostico del puente: microfono y conexion con el nucleo."""
from __future__ import annotations

import os
import sys
import time

CORE_URL = os.getenv("KAIROS_CORE_URL", "http://127.0.0.1:8000")

print("=" * 60)
print("1. DISPOSITIVOS DE AUDIO")
print("=" * 60)
try:
    import sounddevice as sd

    print(sd.query_devices())
    default_in = sd.default.device[0]
    print(f"\nEntrada por defecto: {default_in}")
    if default_in is None or default_in < 0:
        print("!! No hay microfono por defecto. Windows > Sonido > Entrada.")
except Exception as exc:  # noqa: BLE001
    print(f"!! sounddevice fallo: {exc}")
    sys.exit(1)

print()
print("=" * 60)
print("2. NIVEL DEL MICROFONO — habla durante 6 segundos")
print("=" * 60)
try:
    import numpy as np

    levels: list[float] = []

    def probe(indata, frames, t, status):  # type: ignore[no-untyped-def]
        samples = np.frombuffer(bytes(indata), dtype="int16").astype("float32")
        rms = float((samples**2).mean() ** 0.5) if samples.size else 0.0
        levels.append(rms)
        bars = "#" * min(50, int(rms / 40))
        print(f"\r  {rms:7.0f} |{bars:<50}|", end="")

    with sd.RawInputStream(samplerate=16000, blocksize=1600, dtype="int16",
                           channels=1, callback=probe):
        time.sleep(6)
    print()

    if levels:
        quiet = sorted(levels)[len(levels) // 10]
        loud = max(levels)
        print(f"\n  silencio ~{quiet:.0f}   pico ~{loud:.0f}")
        if loud < 300:
            print("  !! El microfono no capta. Revisa que sea el correcto y su volumen.")
        elif loud < quiet * 2.6:
            print("  !! Hay demasiado ruido de fondo: tu voz no destaca sobre el.")
        else:
            print(f"  OK. Umbral recomendado: {max(220, quiet * 2.6):.0f}")
except Exception as exc:  # noqa: BLE001
    print(f"!! fallo midiendo: {exc}")

print()
print("=" * 60)
print("3. CONEXION CON EL NUCLEO")
print("=" * 60)
try:
    import httpx

    r = httpx.get(f"{CORE_URL}/api/v1/health", timeout=10)
    print(f"  /health -> {r.status_code}")

    token = ""
    for name in (".bridge-secret",):
        if os.path.exists(name):
            token = open(name, encoding="utf-8").read().strip()
    r = httpx.post(
        f"{CORE_URL}/api/v1/voice/transcribe",
        files={"audio": ("x.wav", b"RIFF", "audio/wav")},
        headers={"x-bridge-token": token},
        timeout=20,
    )
    print(f"  /voice/transcribe -> {r.status_code}")
    if r.status_code == 401:
        print("  !! 401: el nucleo no acepta el token del puente.")
        print("     Falta aplicar el parche 5B en el nucleo y reiniciarlo.")
    elif r.status_code in (400, 422):
        print("  OK: autenticado (rechaza el audio falso, que es lo correcto).")
except Exception as exc:  # noqa: BLE001
    print(f"!! nucleo inalcanzable: {exc}")

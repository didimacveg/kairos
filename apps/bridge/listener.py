"""Escucha permanente con palabra de activacion.

Como funciona, y por que asi:

El micrófono está siempre abierto, pero **casi nunca se transcribe nada**. Un
detector de energía con umbral autocalibrado decide qué trozos de audio
contienen voz; solo esos se mandan a Whisper. En una habitación en silencio,
el coste de CPU en reposo es prácticamente cero.

Dos fases:

  1. ESPERA   — segmentos cortos (hasta 3 s). Se transcriben buscando la
                palabra de activación. Si no aparece, se descartan y no se
                guarda nada en ningún sitio.
  2. ESCUCHA  — tras oír "kairos", graba tu orden completa (hasta 12 s) y la
                manda al núcleo.

Privacidad: en fase de espera el audio vive en memoria unos segundos y se
descarta. Nada se escribe a disco y nada sale de tu máquina salvo la llamada
a tu propio Whisper, que corre en local.
"""
from __future__ import annotations

import io
import queue
import threading
import time
import wave
from collections.abc import Callable

RATE = 16000
BLOCK = 1600  # 100 ms
CALIBRATION_BLOCKS = 12
FLOOR_MARGIN = 2.6
FLOOR_MIN = 220.0

WAKE_MAX_S = 3.0
COMMAND_MAX_S = 12.0
SILENCE_END_S = 1.0


def _wav(frames: bytes) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(frames)
    return buffer.getvalue()


def _rms(block) -> float:  # type: ignore[no-untyped-def]
    import numpy as np

    samples = np.frombuffer(block, dtype="int16").astype("float32")
    if samples.size == 0:
        return 0.0
    return float((samples**2).mean() ** 0.5)


class WakeListener:
    """Bucle de escucha. `on_wake_phrase` recibe el WAV de la orden."""

    def __init__(
        self,
        transcribe: Callable[[bytes], str],
        device: int | None,
        on_command: Callable[[str], None],
        wake_words: list[str],
        on_state: Callable[[str], None] | None = None,
    ) -> None:
        self._transcribe = transcribe
        # Windows expone el mismo microfono varias veces (MME,
        # DirectSound, WASAPI) y sounddevice no siempre coge el que
        # funciona. Fijarlo por indice es la unica forma fiable.
        self._device = device
        self._on_command = on_command
        self._wake = [w.lower() for w in wake_words]
        self._on_state = on_state or (lambda _: None)
        self._stop = threading.Event()
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._floor = FLOOR_MIN

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            print("[escucha] falta sounddevice: pip install sounddevice numpy")
            return

        def callback(indata, frames, time_info, status):  # type: ignore[no-untyped-def]
            self._queue.put(bytes(indata))

        with sd.RawInputStream(
            samplerate=RATE, blocksize=BLOCK, dtype="int16", channels=1,
            device=self._device, callback=callback
        ):
            print("[escucha] activa. Di la palabra de activacion.")
            self._calibrate()
            while not self._stop.is_set():
                self._cycle()

    def _calibrate(self) -> None:
        """Mide el ruido de la habitacion. Ventiladores incluidos."""
        levels = []
        for _ in range(CALIBRATION_BLOCKS):
            try:
                levels.append(_rms(self._queue.get(timeout=2)))
            except queue.Empty:
                break
        if not levels:
            print("[escucha] !! el microfono no entrega audio. Ejecuta diagnostico.py")
            return
        media = sum(levels) / len(levels)
        self._floor = max(FLOOR_MIN, media * FLOOR_MARGIN)
        print(f"[escucha] ruido medio {media:.0f} -> umbral {self._floor:.0f}")
        if media < 10:
            print("[escucha] !! nivel casi nulo: revisa que el microfono correcto")
            print("[escucha]    este seleccionado en Windows > Sonido > Entrada.")

    def _collect(self, max_seconds: float) -> bytes | None:
        """Acumula audio mientras haya voz. Devuelve None si no hubo nada."""
        frames = bytearray()
        heard = False
        quiet_since = 0.0
        started = time.time()

        while not self._stop.is_set():
            try:
                block = self._queue.get(timeout=1.0)
            except queue.Empty:
                return _wav(bytes(frames)) if heard else None

            level = _rms(block)
            if level > self._floor:
                heard = True
                quiet_since = 0.0
                frames += block
            elif heard:
                frames += block
                if quiet_since == 0.0:
                    quiet_since = time.time()
                elif time.time() - quiet_since > SILENCE_END_S:
                    return _wav(bytes(frames))

            if time.time() - started > max_seconds:
                return _wav(bytes(frames)) if heard else None

        return None

    def _cycle(self) -> None:
        # --- fase de espera: solo busca la palabra de activacion ---
        audio = self._collect(WAKE_MAX_S)
        if not audio:
            return

        text = self._transcribe(audio).lower()
        # Salida verbosa: sin ver que transcribe es imposible saber si el
        # problema es el microfono, el umbral o la palabra de activacion.
        if text.strip():
            print(f"[escucha] oido: {text!r}")
        else:
            print("[escucha] segmento sin texto (¿nucleo autenticado?)")
        if not any(word in text for word in self._wake):
            return  # audio descartado, nada se guarda

        print(f"[escucha] activado por: {text!r}")
        self._on_state("despierto")

        # Si la orden venia en la misma frase ("kairos, abre el perfil
        # trabajo"), no hace falta pedir nada mas.
        tail = text
        for word in self._wake:
            if word in tail:
                tail = tail.split(word, 1)[1]
        if len(tail.strip()) > 6:
            self._on_command(tail.strip())
            self._on_state("espera")
            return

        # --- fase de escucha: graba la orden completa ---
        command_audio = self._collect(COMMAND_MAX_S)
        if command_audio:
            command = self._transcribe(command_audio)
            if command.strip():
                self._on_command(command.strip())
        self._on_state("espera")

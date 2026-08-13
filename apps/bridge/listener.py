"""Escucha permanente con palabra de activacion y ventana de seguimiento.

Tres problemas de la version anterior, corregidos aqui:

1. **Frases cortadas.** La fase de espera grababa 3 s como maximo, asi que
   "kairos entra en modo trabajo" llegaba como "kairos entra en modo...".
   Ahora el limite lo marca el silencio, no el reloj: se graba mientras hables
   y se corta cuando callas.

2. **Umbral congelado.** Se calibraba una vez al arrancar. Si en ese momento
   sonaba musica, el umbral quedaba absurdamente alto (3059) y no oia nada;
   si habia silencio total, quedaba en el minimo (220) y cualquier ruido lo
   despertaba. Ahora se recalcula continuamente con la mediana de los bloques
   silenciosos recientes.

3. **Hay que repetir la palabra en cada frase.** Tras ejecutar algo, se abre
   una ventana de seguimiento: durante un minuto puedes seguir dando ordenes
   sin decir "kairos".
"""
from __future__ import annotations

import io
import queue
import statistics
import threading
import time
import wave
from collections.abc import Callable

RATE = 16000
BLOCK = 1600  # 100 ms

FLOOR_MIN = 180.0
FLOOR_MARGIN = 2.4
CALIBRATION_BLOCKS = 12
# Ventana movil para el ruido de fondo: 30 s de bloques silenciosos.
NOISE_WINDOW = 300

# Sin tope de reloj para la frase: manda el silencio. El tope duro solo evita
# que un ruido continuo grabe indefinidamente.
UTTERANCE_MAX_S = 15.0
SILENCE_END_S = 0.9
MIN_SPEECH_BLOCKS = 4  # 400 ms: por debajo es un golpe, no una frase

# Tras ejecutar una orden, un minuto escuchando sin palabra de activacion.
FOLLOW_UP_S = 60.0


def _wav(frames: bytes) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(frames)
    return buffer.getvalue()


def _rms(block: bytes) -> float:
    import numpy as np

    samples = np.frombuffer(block, dtype="int16").astype("float32")
    if samples.size == 0:
        return 0.0
    return float((samples**2).mean() ** 0.5)


class WakeListener:
    def __init__(
        self,
        transcribe: Callable[[bytes], str],
        device: int | None,
        on_command: Callable[[str], bool],
        wake_words: list[str],
        on_state: Callable[[str], None] | None = None,
    ) -> None:
        self._transcribe = transcribe
        self._device = device
        # Devuelve True si la orden se ejecuto: eso abre la ventana de
        # seguimiento. Si fue conversacion, no la abre.
        self._on_command = on_command
        self._wake = [w.lower() for w in wake_words]
        self._on_state = on_state or (lambda _: None)
        self._stop = threading.Event()
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._floor = FLOOR_MIN
        self._noise: list[float] = []
        self._awake_until = 0.0

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
            device=self._device, callback=callback,
        ):
            self._calibrate()
            print("[escucha] activa. Di la palabra de activacion.")
            while not self._stop.is_set():
                self._cycle()

    # ------------------------------------------------------------- ruido

    def _calibrate(self) -> None:
        levels = []
        for _ in range(CALIBRATION_BLOCKS):
            try:
                levels.append(_rms(self._queue.get(timeout=2)))
            except queue.Empty:
                break
        if not levels:
            print("[escucha] !! el microfono no entrega audio")
            return
        self._noise = levels[:]
        self._update_floor()
        print(f"[escucha] umbral inicial: {self._floor:.0f}")

    def _update_floor(self) -> None:
        """Mediana de los bloques silenciosos recientes.

        La mediana, y no la media, porque un pico aislado —una puerta, un
        acorde— no debe mover el umbral. Y ventana movil porque el ruido de
        una habitacion cambia: no es lo mismo con musica que sin ella.
        """
        if not self._noise:
            return
        base = statistics.median(self._noise)
        self._floor = max(FLOOR_MIN, base * FLOOR_MARGIN)

    def _note_noise(self, level: float) -> None:
        self._noise.append(level)
        if len(self._noise) > NOISE_WINDOW:
            self._noise.pop(0)
        # Recalcular cada 5 s es suficiente y evita recalcular en cada bloque.
        if len(self._noise) % 50 == 0:
            self._update_floor()

    # ------------------------------------------------------------ captura

    def _collect(self) -> bytes | None:
        """Graba mientras haya voz. El silencio decide cuando parar."""
        frames = bytearray()
        speech_blocks = 0
        quiet_since = 0.0
        started = time.time()

        while not self._stop.is_set():
            try:
                block = self._queue.get(timeout=1.0)
            except queue.Empty:
                return _wav(bytes(frames)) if speech_blocks >= MIN_SPEECH_BLOCKS else None

            level = _rms(block)

            if level > self._floor:
                speech_blocks += 1
                quiet_since = 0.0
                frames += block
            else:
                self._note_noise(level)
                if speech_blocks:
                    frames += block
                    if quiet_since == 0.0:
                        quiet_since = time.time()
                    elif time.time() - quiet_since > SILENCE_END_S:
                        break
                elif time.time() - started > 1.5:
                    # Nada que grabar todavia: devolver el control para que el
                    # bucle exterior compruebe la ventana de seguimiento.
                    return None

            if time.time() - started > UTTERANCE_MAX_S:
                break

        if speech_blocks < MIN_SPEECH_BLOCKS:
            return None
        return _wav(bytes(frames))

    # -------------------------------------------------------------- ciclo

    def _cycle(self) -> None:
        audio = self._collect()
        if not audio:
            return

        text = self._transcribe(audio).strip()
        if not text:
            return

        siguiendo = time.time() < self._awake_until
        lower = text.lower()
        tiene_palabra = any(word in lower for word in self._wake)

        if not tiene_palabra and not siguiendo:
            print(f"[escucha] ignorado: {text!r}")
            return

        # Quita la palabra de activacion del principio, si venia.
        orden = text
        if tiene_palabra:
            for word in self._wake:
                if word in lower:
                    idx = lower.index(word)
                    orden = text[idx + len(word) :]
                    break
        orden = orden.strip(" ,.;:!?¡¿-")

        if len(orden) < 3:
            # Solo la palabra de activacion: abre la ventana y espera orden.
            print("[escucha] despierto, esperando orden")
            self._on_state("despierto")
            self._awake_until = time.time() + FOLLOW_UP_S
            return

        etiqueta = "seguimiento" if siguiendo and not tiene_palabra else "activado"
        print(f"[escucha] {etiqueta}: {orden!r}")
        self._on_state("despierto")

        ejecutado = bool(self._on_command(orden))
        # La ventana solo se renueva si se ejecuto algo. Asi una charla de
        # fondo no mantiene a KAIROS despierto indefinidamente.
        self._awake_until = time.time() + FOLLOW_UP_S if ejecutado else 0.0
        self._on_state("seguimiento" if ejecutado else "espera")

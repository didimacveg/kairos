"""Servicio de voz de KAIROS — transcripcion (Whisper) y sintesis (Piper).

Ambos motores viven aqui, fuera del nucleo, y ambos corren en CPU: transcribir
y hablar son rafagas, razonar es el bucle principal. La VRAM se reserva entera
para el modelo que razona.
"""
from __future__ import annotations

import deepgram
import tts

import io
import os
import re
import tempfile
import time
import wave
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

MODEL_SIZE = os.getenv("KAIROS_WHISPER_MODEL", "medium")
DEVICE = os.getenv("KAIROS_WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("KAIROS_WHISPER_COMPUTE", "int8")
LANGUAGE = os.getenv("KAIROS_WHISPER_LANGUAGE", "es")
MAX_AUDIO_BYTES = int(os.getenv("KAIROS_MAX_AUDIO_BYTES", str(25 * 1024 * 1024)))

PIPER_VOICE = os.getenv("KAIROS_PIPER_VOICE", "es_ES-sharvard-medium")
# Segunda voz para el ingles. Un modelo de Piper contiene SOLO los fonemas de
# su idioma: la voz espanola no puede pronunciar "Bye Bye Bye" porque esos
# sonidos no existen en su repertorio, y lo lee como si fuera espanol. No es
# un ajuste que se pueda corregir; hace falta otro modelo.
PIPER_VOICE_EN = os.getenv("KAIROS_PIPER_VOICE_EN", "en_US-ryan-medium")
PIPER_DIR = Path(os.getenv("KAIROS_PIPER_DIR", "/var/lib/kairos/voices"))
# length_scale > 1 = habla mas despacio. Una diccion algo mas lenta se lee
# como deliberada; acelerada suena a ardilla.
PIPER_LENGTH = float(os.getenv("KAIROS_PIPER_LENGTH_SCALE", "1.08"))
# Grave el resultado bajando la frecuencia de reproduccion del WAV: el truco
# del vinilo a menos revoluciones. Baja el tono Y alarga el audio, asi que se
# compensa generando mas rapido con length_scale. Crudo, pero no necesita
# librerias de procesado de senal ni GPU.
PIPER_PITCH = float(os.getenv("KAIROS_PIPER_PITCH", "0.90"))
# Los dos parametros que de verdad mueven la naturalidad, y que no estabamos
# tocando:
#   noise_scale  variacion del timbre. Bajo = plano y robotico; alto = ronco.
#   noise_w      variacion de la DURACION de cada fonema. Es el que mas se
#                nota: sin el, todas las silabas duran lo mismo y suena a
#                metronomo. El habla humana no es isocrona.
PIPER_NOISE = float(os.getenv("KAIROS_PIPER_NOISE", "0.667"))
PIPER_NOISE_W = float(os.getenv("KAIROS_PIPER_NOISE_W", "0.9"))
MAX_SPEECH_CHARS = 2000

# faster-whisper devuelve avg_logprob por segmento: cuanto mas negativo, menos
# seguro esta de lo que ha oido. -0.9 marca la frontera entre entender y adivinar.
LOW_CONFIDENCE = float(os.getenv("KAIROS_WHISPER_MIN_LOGPROB", "-0.9"))

# Whisper transcribe hacia palabras que conoce: "KAIROS" no existe en espanol
# y acaba como "chairos" o "gairos". El initial_prompt le da contexto de que
# vocabulario esperar en este dominio, sin forzar nada.
INITIAL_PROMPT = os.getenv(
    "KAIROS_WHISPER_PROMPT",
    "KAIROS. Ordenes para KAIROS: abre el perfil trabajo, estudio o juego. "
    "Cierra el perfil. Pon musica, pausa la musica, siguiente cancion, "
    "volumen. Spotify, Discord, Valorant, Roblox, Visual Studio Code.",
)

_whisper: Any = None
_piper: Any = None
_piper_en: Any = None


class Transcription(BaseModel):
    text: str
    language: str
    duration_s: float
    latency_ms: int
    model: str
    segments: int
    confidence: float = Field(description="avg_logprob medio; mas alto es mejor")
    low_confidence: bool
    no_speech: bool


class SpeechRequest(BaseModel):
    # Para que decidir si merece la voz buena. Vacio = rutina.
    # Sin este campo Pydantic descartaba el motivo al recibirlo, y TODO
    # el audio caia en Deepgram aunque el presupuesto lo aprobara.
    motivo: str = ""
    # Sin restricciones de longitud en el esquema: una frase vacia o larga debe
    # producir una respuesta manejable, no un 422 que el cliente no interpreta.
    text: str = ""


def _load_whisper() -> Any:
    from faster_whisper import WhisperModel

    try:
        return WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    except Exception:  # noqa: BLE001
        return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def _load_voice(name: str) -> Any:
    """Si falta el modelo, el servicio sigue vivo: KAIROS puede escuchar
    aunque no pueda hablar, y hablar espanol aunque no tenga voz inglesa."""
    try:
        from piper import PiperVoice

        onnx = PIPER_DIR / f"{name}.onnx"
        if not onnx.exists():
            print(f"[voz] falta el modelo {name}")
            return None
        return PiperVoice.load(str(onnx), config_path=str(onnx.with_suffix(".onnx.json")))
    except Exception as exc:  # noqa: BLE001
        print(f"[voz] no se pudo cargar {name}: {exc}")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _whisper, _piper, _piper_en
    _whisper = _load_whisper()
    _piper = _load_voice(PIPER_VOICE)
    _piper_en = _load_voice(PIPER_VOICE_EN)
    yield
    _whisper = None
    _piper = None
    _piper_en = None


app = FastAPI(title="KAIROS Voice", version="0.3.0", lifespan=lifespan)


@app.get("/voces")
async def voces() -> dict:
    """Voces disponibles en la cuenta de ElevenLabs.

    Existe para poder elegir sin salir de KAIROS: pruebas una, pegas su id en
    el .env y recreas el contenedor.
    """
    return {"elevenlabs": await tts.elevenlabs_voces()}


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok" if _whisper is not None else "loading",
        "model": MODEL_SIZE,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "speech": "ok" if _piper is not None else "unavailable",
        "voice": PIPER_VOICE,
        "tts": await tts.estado(),
        "voice_en": PIPER_VOICE_EN if _piper_en else None,
        "pitch": PIPER_PITCH,
        "length_scale": PIPER_LENGTH,
        "noise": PIPER_NOISE,
        "noise_w": PIPER_NOISE_W,
    }


@app.post("/transcribe", response_model=Transcription)
async def transcribe(audio: UploadFile = File(...)) -> Transcription:
    if _whisper is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "El modelo aun se esta cargando")

    payload = await audio.read()
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Audio vacio")
    if len(payload) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Audio demasiado largo")

    started = time.perf_counter()
    # Deepgram primero: ~300 ms frente a los segundos de Whisper en CPU.
    # Si falla —sin red, sin clave, error de la API— se sigue al camino
    # local sin que el usuario note mas que la espera. La regla de la
    # Fase 1 sigue en pie: KAIROS no depende de Internet para funcionar.
    if deepgram.disponible():
        remoto = await deepgram.transcribir(payload, audio.content_type or "")
        if remoto is not None:
            return Transcription(**{k: v for k, v in remoto.items() if k != "motor"})

    with tempfile.NamedTemporaryFile(suffix=".bin") as handle:
        handle.write(payload)
        handle.flush()
        try:
            segments, info = _whisper.transcribe(
                handle.name,
                language=LANGUAGE,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 400},
                beam_size=5,
                initial_prompt=INITIAL_PROMPT,
            )
            collected = list(segments)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"No se pudo transcribir: {exc}"
            ) from exc

    text = "".join(s.text for s in collected).strip()
    if collected:
        confidence = sum(s.avg_logprob for s in collected) / len(collected)
        no_speech = all(s.no_speech_prob > 0.6 for s in collected)
    else:
        confidence = -10.0
        no_speech = True

    return Transcription(
        text=text,
        language=info.language,
        duration_s=round(info.duration, 2),
        latency_ms=int((time.perf_counter() - started) * 1000),
        model=MODEL_SIZE,
        segments=len(collected),
        confidence=round(confidence, 3),
        low_confidence=bool(text) and confidence < LOW_CONFIDENCE,
        no_speech=no_speech or not text,
    )


def _pcm(text: str, voice: Any) -> tuple[bytes, int]:
    """Sintetiza un fragmento y devuelve las muestras crudas.

    API real de piper-tts (comprobada, no supuesta):

        synthesize(text, syn_config=None, include_alignments=False)
            -> Iterable[AudioChunk]

    NO recibe un objeto WAV. Devuelve trozos con las muestras dentro. Toda la
    gimnasia anterior con `wave` sobraba: se pide el audio, se concatena, y el
    WAV se monta una sola vez al final con los tramos ya listos.
    """
    engine = voice if voice is not None else _piper

    config = None
    try:
        from piper import SynthesisConfig

        config = SynthesisConfig(
            length_scale=PIPER_LENGTH,
            noise_scale=PIPER_NOISE,
            noise_w_scale=PIPER_NOISE_W,
        )
    except TypeError:
        try:
            config = SynthesisConfig(
                length_scale=PIPER_LENGTH, noise_scale=PIPER_NOISE, noise_w=PIPER_NOISE_W
            )
        except Exception:  # noqa: BLE001
            config = None
    except Exception:  # noqa: BLE001
        # Versiones sin SynthesisConfig: se sintetiza a velocidad nominal.
        pass

    piezas: list[bytes] = []
    rate = int(getattr(getattr(engine, "config", None), "sample_rate", 22050))

    trozos = engine.synthesize(text, config) if config else engine.synthesize(text)
    for chunk in trozos:
        data = getattr(chunk, "audio_int16_bytes", None)
        if data is None:
            data = bytes(chunk)
        piezas.append(data)
        rate = int(getattr(chunk, "sample_rate", rate))

    return b"".join(piezas), rate


def _clean(text: str) -> str:
    """Quita el marcado que el modelo escribe y que Piper leeria en alto.

    Sin esto, KAIROS pronuncia "asterisco asterisco No mirar al sol asterisco
    asterisco". El texto en pantalla conserva su formato; solo se limpia lo
    que se manda a la voz.
    """
    cleaned = re.sub(r"[*_`#]+", " ", text)
    cleaned = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


# Palabras castellanas muy frecuentes. Su presencia es mejor senal que la de
# palabras inglesas: "Bye Bye Bye" no tiene ninguna, pero "Reproduciendo Bye
# Bye Bye" si, y hay que partir la frase en dos tramos.
# Deteccion de idioma: ESPANOL POR DEFECTO.
#
# La version anterior marcaba como ingles todo lo que no tuviera evidencia de
# espanol, y "Buenas noches, Diego" —sin acentos y sin palabras de la lista—
# se colaba. La carga de la prueba estaba al reves: hay que demostrar que algo
# ES ingles, no que no es espanol. Equivocarse hacia el espanol solo suena
# raro en un titulo; equivocarse hacia el ingles destroza una frase entera.

EN_WORDS = re.compile(
    r"\b(the|and|you|your|are|for|with|this|that|never|dont|don't|love|"
    r"heart|night|life|time|baby|bye|feat|remix|live|acoustic|rock|"
    r"blood|black|sky|fire|dream|day|man|girl|boy|world|home|way|"
    r"is|was|be|to|of|in|on|it|my|me|we|no|yes|out|up|down|all)\b",
    re.I,
)
ES_CHARS = re.compile(r"[áéíóúüñ¿¡ÁÉÍÓÚÑ]")
ES_WORDS = re.compile(
    r"\b(el|la|los|las|de|del|que|con|para|por|una|un|es|esta|estas|tu|te|"
    r"se|su|sus|al|lo|le|mi|ya|muy|mas|pero|como|cuando|donde|todo|nada|"
    r"buenas|buenos|noches|dias|tardes|hola|adios|gracias|reproduciendo|"
    r"suena|modo|perfil|abriendo|cerrando|bienvenido|informe|hoy|manana)\b",
    re.I,
)


def _looks_english(fragment: str) -> bool:
    """Solo True si hay evidencia POSITIVA de ingles y ninguna de espanol."""
    text = fragment.strip()
    if len(text) < 4:
        return False
    if ES_CHARS.search(text) or ES_WORDS.search(text):
        return False
    palabras = re.findall(r"[a-zA-Z']+", text)
    if len(palabras) < 2:
        return False
    # Al menos una palabra inglesa reconocible, o todas las palabras sin
    # ninguna castellana en un fragmento de varias.
    return bool(EN_WORDS.search(text))


def _split_by_language(text: str) -> list[tuple[str, bool]]:
    """Parte la frase en tramos, marcando cuales van en ingles."""
    piezas = re.split(r"(,|\s+de\s+|\.\s+)", text)
    tramos: list[tuple[str, bool]] = []
    for pieza in piezas:
        limpio = pieza.strip()
        if not limpio:
            continue
        ingles = _looks_english(limpio)
        if tramos and tramos[-1][1] == ingles:
            tramos[-1] = (f"{tramos[-1][0]} {limpio}", ingles)
        else:
            tramos.append((limpio, ingles))
    return tramos or [(text, False)]


@app.post("/speak")
async def speak(body: SpeechRequest) -> Response:
    """Sintetiza una frase y devuelve WAV.

    Se sintetiza por frases, no por respuesta entera: el cliente pide cada
    frase en cuanto el modelo la termina, asi KAIROS empieza a hablar mientras
    todavia esta pensando el resto.
    """
    if _piper is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Voz no disponible: falta el modelo {PIPER_VOICE} en {PIPER_DIR}",
        )

    text = _clean(body.text)[:MAX_SPEECH_CHARS]
    if not text:
        # Nada que decir no es un error: WAV vacio y el cliente sigue con la
        # frase siguiente sin romper la cola de reproduccion.
        empty = io.BytesIO()
        with wave.open(empty, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
        return Response(content=empty.getvalue(), media_type="audio/wav")

    # Un solo WAV con todos los tramos concatenados: el cliente recibe un
    # audio, no cinco, y no hay huecos entre trozos.
    # La capa prueba los proveedores en orden y devuelve el primero que
    # responda. Si todos fallan, sigue el camino local de Piper: KAIROS
    # habla siempre, aunque peor.
    remoto = await tts.sintetizar(text, body.motivo)
    if remoto is not None:
        audio_bytes, tipo = remoto
        return Response(content=audio_bytes, media_type=tipo)

    tramos = _split_by_language(text) if _piper_en else [(text, False)]
    try:
        piezas: list[bytes] = []
        rate = 22050
        for fragmento, en_ingles in tramos:
            voz = _piper_en if (en_ingles and _piper_en) else _piper
            pcm, rate = _pcm(fragmento, voz)
            piezas.append(pcm)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"No se pudo sintetizar: {exc}"
        ) from exc

    # Un solo WAV de salida. La frecuencia se baja aqui para el timbre grave:
    # el truco del vinilo a menos revoluciones, aplicado una vez al final.
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(max(8000, int(rate * PIPER_PITCH)))
        # 180 ms de silencio entre tramos. Sin pausa, un informe de cinco
        # frases sale de carrerilla y cuesta seguirlo al oido.
        silencio = b"\x00\x00" * int(rate * 0.18)
        for i, pieza in enumerate(piezas):
            if i:
                wav.writeframes(silencio)
            wav.writeframes(pieza)

    return Response(
        content=buffer.getvalue(),
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )

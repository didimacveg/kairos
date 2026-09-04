"""Video — encuentra los momentos buenos de una grabacion larga.

LA TESIS, y es lo que hace que esto sea viable: **el valor no es generar, es
comprimir.** Nadie le pide a un modelo que invente un video; se le pide que
lea una grabacion de veinte minutos y diga que treinta segundos merecen la
pena, con los tiempos exactos.

EL FLUJO:

  1. ffmpeg extrae el audio de la grabacion
  2. Deepgram lo transcribe CON MARCAS DE TIEMPO — esa es la clave
  3. el modelo lee la transcripcion y elige los momentos
  4. se generan los comandos de corte, listos para ejecutar

LO QUE NO HACE, y no es una limitacion tecnica sino una decision: no ejecuta
los cortes. Devuelve los comandos. Un corte mal calculado sobre el fichero
original es irrecuperable, y KAIROS no toca lo que no puede deshacer.

POR QUE FUNCIONA SIN VER EL VIDEO: en un video hablado, lo que decide donde
cortar es lo que se DICE. La imagen importa para el montaje fino, no para
elegir los momentos. Por eso basta la transcripcion.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider
from kairos.logging import get_logger

log = get_logger("kairos.video")

MAX_MINUTOS = 90
PROMPT = """Tienes la transcripcion con marcas de tiempo de una grabacion.
Elige los momentos que merecen estar en un video corto de {duracion} segundos.

QUE BUSCAR:
- Frases que se sostienen solas, sin necesitar contexto previo
- Momentos donde se dice algo concreto: un dato, una decision, un fallo
- El principio de una idea, no su desarrollo entero

QUE DESCARTAR:
- Preambulos: "bueno", "a ver", "entonces lo que pasa es que"
- Repeticiones y correcciones a media frase
- Silencios y titubeos
- Explicaciones largas que necesitan lo anterior para entenderse

REGLAS DE CORTE:
- Empieza el corte 0.3 s ANTES de la primera palabra: cortar justo encima
  suena amputado.
- Termina 0.4 s DESPUES de la ultima: dejar respirar el final es lo que
  separa un montaje bueno de uno nervioso.
- Ningun fragmento por debajo de 2 s ni por encima de 15.
- ORDENALOS por como cuentan mejor la historia, no por como aparecen en la
  grabacion. Un buen corte no respeta el orden original.

Devuelve SOLO JSON:
{{"cortes": [
   {{"desde": 12.4, "hasta": 19.8, "dice": "las primeras palabras...",
     "por_que": "por que este momento"}}
 ],
 "gancho": "cual de los cortes deberia ir primero, por indice",
 "descartado": "que has dejado fuera y por que, en una frase"}}"""


def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


class VideoAgent(Agent):
    name = "video"
    capabilities = frozenset({"video.analizar", "video.cortes"})

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability not in self.capabilities:
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        ruta = Path((request.payload.get("ruta") or "").strip())
        if not ruta.exists():
            return AgentResponse.failure(f"No encuentro el fichero: {ruta}")
        if _ffmpeg() is None:
            return AgentResponse.failure(
                "Falta ffmpeg. En Ubuntu: sudo apt install ffmpeg"
            )

        started = time.perf_counter()
        traza: list[TraceEvent] = []

        # --- 1. audio ------------------------------------------------------
        audio = ruta.with_suffix(".kairos.wav")
        try:
            subprocess.run(
                [
                    _ffmpeg(), "-y", "-i", str(ruta),
                    "-vn", "-acodec", "pcm_s16le",
                    # 16 kHz mono es lo que esperan los transcriptores. Mas
                    # calidad no mejora la transcripcion y multiplica el peso.
                    "-ar", "16000", "-ac", "1",
                    str(audio),
                ],
                capture_output=True, timeout=600, check=True, shell=False,
            )
        except subprocess.CalledProcessError as exc:
            return AgentResponse.failure(
                f"ffmpeg fallo: {exc.stderr.decode('utf-8', 'replace')[-200:]}"
            )
        except subprocess.TimeoutExpired:
            return AgentResponse.failure("ffmpeg tardo demasiado")

        peso = audio.stat().st_size / 1_000_000
        traza.append(TraceEvent(
            agent=self.name, step="audio", detail={"mb": round(peso, 1)}))

        # --- 2. transcripcion con marcas ----------------------------------
        palabras = await self._transcribir(audio)
        audio.unlink(missing_ok=True)

        if not palabras:
            return AgentResponse.failure(
                "No se pudo transcribir. Hace falta KAIROS_DEEPGRAM_KEY: es el "
                "unico que da marcas de tiempo por palabra."
            )

        # Se agrupa en lineas de ~12 palabras con su marca. El modelo necesita
        # ver tiempos para poder elegir cortes, no solo texto.
        lineas = []
        bloque: list[str] = []
        inicio = palabras[0]["inicio"]
        for p in palabras:
            bloque.append(p["palabra"])
            if len(bloque) >= 12:
                lineas.append(f"[{inicio:.1f}] {' '.join(bloque)}")
                bloque = []
                inicio = p["fin"]
        if bloque:
            lineas.append(f"[{inicio:.1f}] {' '.join(bloque)}")

        transcripcion = "\n".join(lineas)
        traza.append(TraceEvent(
            agent=self.name, step="transcribir",
            detail={"palabras": len(palabras), "lineas": len(lineas)}))

        # --- 3. elegir los momentos ---------------------------------------
        duracion = int(request.payload.get("duracion", 60))
        try:
            completion = await self._provider.complete([
                ChatTurn(role="system", content=PROMPT.format(duracion=duracion)),
                ChatTurn(role="user", content=transcripcion[:60_000]),
            ])
        except Exception as exc:  # noqa: BLE001
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")

        datos = self._json(completion.text)
        cortes = [
            c for c in datos.get("cortes", [])
            if isinstance(c, dict) and "desde" in c and "hasta" in c
        ]
        if not cortes:
            return AgentResponse.failure("No he encontrado momentos aprovechables")

        # --- 4. los comandos ----------------------------------------------
        base = ruta.with_suffix("")
        comandos = []
        for i, c in enumerate(cortes, 1):
            desde, hasta = float(c["desde"]), float(c["hasta"])
            if hasta <= desde:
                continue
            salida = f"{base}_corte{i:02d}.mp4"
            comandos.append(
                # -ss ANTES de -i busca rapido; -c copy no recodifica, asi que
                # el corte es instantaneo y sin perdida de calidad.
                f'ffmpeg -y -ss {desde:.2f} -to {hasta:.2f} -i "{ruta}" '
                f'-c copy "{salida}"'
            )

        lista = base.with_name(base.name + "_lista.txt")
        concat = (
            f'# Escribe estas lineas en {lista} y luego:\n'
            f'# ffmpeg -f concat -safe 0 -i "{lista}" -c copy "{base}_montado.mp4"'
        )

        total = sum(float(c["hasta"]) - float(c["desde"]) for c in cortes)
        log.info("video.analizado", cortes=len(cortes), segundos=round(total))

        return AgentResponse(
            ok=True,
            data={
                "cortes": cortes,
                "comandos": comandos,
                "montaje": concat,
                "segundos_totales": round(total, 1),
                "descartado": datos.get("descartado", ""),
                # Se devuelven los comandos, NO se ejecutan: un corte mal
                # calculado sobre el original es irrecuperable.
                "aviso": "Revisa los tiempos antes de ejecutar. KAIROS no corta solo.",
            },
            trace=traza + [TraceEvent(
                agent=self.name, step="elegir",
                detail={"cortes": len(cortes), "segundos": round(total)},
                duration_ms=int((time.perf_counter() - started) * 1000))],
        )

    @staticmethod
    async def _transcribir(audio: Path) -> list[dict[str, Any]]:
        """Deepgram con marcas por palabra.

        Whisper local tambien da marcas, pero por segmento y menos precisas.
        Para elegir cortes hacen falta las de palabra.
        """
        import os

        import httpx

        clave = os.getenv("KAIROS_DEEPGRAM_KEY", "")
        if not clave:
            return []

        try:
            async with httpx.AsyncClient(timeout=600) as client:
                r = await client.post(
                    "https://api.deepgram.com/v1/listen",
                    params={
                        "model": "nova-3", "language": "es",
                        "punctuate": "true", "utterances": "true",
                    },
                    headers={
                        "Authorization": f"Token {clave}",
                        "Content-Type": "audio/wav",
                    },
                    content=audio.read_bytes(),
                )
            if r.status_code != 200:
                print(f"[video] deepgram {r.status_code}: {r.text[:200]}")
                return []
            cuerpo = r.json()
        except Exception as exc:  # noqa: BLE001
            print(f"[video] {type(exc).__name__}")
            return []

        canal = (cuerpo.get("results") or {}).get("channels", [{}])[0]
        alt = (canal.get("alternatives") or [{}])[0]
        return [
            {
                "palabra": w.get("punctuated_word") or w.get("word", ""),
                "inicio": float(w.get("start", 0)),
                "fin": float(w.get("end", 0)),
            }
            for w in alt.get("words", [])
        ]

    @staticmethod
    def _json(bruto: str) -> dict[str, Any]:
        i, j = bruto.find("{"), bruto.rfind("}")
        if i == -1 or j == -1:
            return {}
        try:
            d = json.loads(bruto[i : j + 1])
            return d if isinstance(d, dict) else {}
        except json.JSONDecodeError:
            return {}

    async def health(self) -> dict[str, Any]:
        return {
            "agent": self.name,
            "status": "ok" if _ffmpeg() else "falta ffmpeg",
        }

"""KAIROS Bridge — el agente que vive en el escritorio.

Es el unico componente de KAIROS que corre FUERA de Docker, en Windows. Tiene
que serlo: solo un proceso del host puede ver tus monitores, registrar un
atajo global y abrir aplicaciones.

Lo que hace:
  - atajo global (por defecto Win+Shift+K) que despierta a KAIROS
  - graba, manda el audio al nucleo y ejecuta el perfil que coincida
  - lanza y coloca aplicaciones segun perfiles declarados
  - icono en la bandeja del sistema
  - expone una API local para que el nucleo pueda pedirle acciones

MODELO DE SEGURIDAD — leelo antes de tocar nada:

1. **Lista blanca cerrada.** El puente solo ejecuta acciones y perfiles
   declarados en `bridge-config.json`, que escribes tu. No hay endpoint que
   acepte un comando arbitrario. El nucleo pide "ejecuta el perfil trabajo",
   nunca "ejecuta esto".
2. **Solo escucha en loopback.** 127.0.0.1. Ninguna otra maquina de la red
   puede hablar con el.
3. **Token compartido.** Toda peticion lleva un secreto que se genera en el
   primer arranque. Sin el, 401.
4. **Confirmacion para lo destructivo.** Cerrar ventanas exige `confirm: true`
   explicito en la peticion.

Por que tanto: un modelo de lenguaje con capacidad de ejecutar comandos
arbitrarios es el escenario de riesgo mas serio de todo el proyecto. La
defensa no es que el modelo se porte bien — es que no pueda portarse mal.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

import actions
import commands
import speech
from listener import WakeListener

CONFIG_PATH = Path(os.getenv("KAIROS_BRIDGE_CONFIG", "bridge-config.json"))
SECRET_PATH = Path(os.getenv("KAIROS_BRIDGE_SECRET", ".bridge-secret"))
HOST, PORT = "127.0.0.1", int(os.getenv("KAIROS_BRIDGE_PORT", "8200"))
CORE_URL = os.getenv("KAIROS_CORE_URL", "http://127.0.0.1:8000")


# --------------------------------------------------------------- configuracion

class Config:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            print(f"[bridge] falta {self.path}; copia bridge-config.example.json")
            self.data = {"profiles": {}, "phrases": {}, "hotkey": "win+shift+k"}
            return
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        print(f"[bridge] perfiles: {', '.join(self.profiles) or 'ninguno'}")

    @property
    def profiles(self) -> dict[str, Any]:
        return self.data.get("profiles", {})

    @property
    def phrases(self) -> dict[str, str]:
        """frase -> nombre de perfil."""
        return {k.lower(): v for k, v in self.data.get("phrases", {}).items()}

    @property
    def chains(self) -> dict[str, Any]:
        return {k: v for k, v in self.data.get("chains", {}).items() if isinstance(v, dict)}

    @property
    def input_device(self) -> int | None:
        value = self.data.get("input_device")
        return int(value) if value is not None else None

    @property
    def wake_words(self) -> list[str]:
        return self.data.get("wake_words", ["kairos"])

    @property
    def always_listening(self) -> bool:
        return bool(self.data.get("always_listening", False))

    @property
    def hotkey(self) -> str:
        return self.data.get("hotkey", "win+shift+k")


config = Config(CONFIG_PATH)


def get_secret() -> str:
    if SECRET_PATH.exists():
        return SECRET_PATH.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(32)
    SECRET_PATH.write_text(token, encoding="utf-8")
    print(f"[bridge] token nuevo escrito en {SECRET_PATH}")
    print(f"[bridge] pon esto en el .env del nucleo:\n  KAIROS_BRIDGE_TOKEN={token}")
    return token


SECRET = get_secret()


def authorize(x_bridge_token: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_bridge_token, SECRET):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido")


# ---------------------------------------------------------------- ejecucion

def _specs(entry: dict[str, Any]) -> list[actions.AppSpec]:
    return [
        actions.AppSpec(
            name=app.get("name", app.get("launch", "?")),
            launch=app["launch"],
            window=app.get("window", ""),
            monitor=app.get("monitor", "principal"),
            slot=app.get("slot", "full"),
            args=list(app.get("args", [])),
            play=bool(app.get("play", False)),
            background=bool(app.get("background", False)),
        )
        for app in entry.get("apps", [])
    ]


def run_profile(name: str) -> dict[str, Any]:
    """Ejecuta un perfil o una cadena declarada. Nombres desconocidos: no."""
    entry = config.profiles.get(name) or config.chains.get(name)
    if entry is None:
        return {"ok": False, "error": f"perfil no declarado: {name}"}

    # Hablar PRIMERO y esperar a terminar: si no, la frase y la musica se
    # pisan. Un segundo de voz antes de que arranque todo.
    frase = entry.get("say", "")
    if frase:
        threading.Thread(target=speech.say, args=(frase, SECRET), daemon=False).start()
        time.sleep(0.2)

    results = [actions.launch(spec) for spec in _specs(entry)]

    # Una cadena puede encadenar con un perfil: "papi esta en casa" pone la
    # cancion y despues abre trabajo.
    following = entry.get("then")
    if following:
        chained = run_profile(following)
        results += chained.get("results", [])

    return {"ok": True, "profile": name, "results": results,
            "say": entry.get("say", f"Perfil {name} listo.")}


def close_profile(name: str) -> dict[str, Any]:
    """Cierra las ventanas de un perfil.

    Solo cierra lo que ese perfil declara, y por WM_CLOSE: cada aplicacion
    decide si guardar o preguntar. Nunca se mata un proceso.
    """
    entry = config.profiles.get(name) or config.chains.get(name)
    if entry is None:
        return {"ok": False, "error": f"perfil no declarado: {name}"}

    frase = entry.get("say_close", f"Cerrando el perfil {name}.")
    threading.Thread(target=speech.say, args=(frase, SECRET), daemon=False).start()

    results = [
        actions.close_window(spec.window)
        for spec in _specs(entry)
        if spec.window
    ]
    return {"ok": True, "profile": name, "results": results,
            "say": f"Perfil {name} cerrado."}


def _unused_legacy(name: str, profile: dict[str, Any]) -> dict[str, Any]:
    results: list[str] = []
    for app in profile.get("apps", []):
        spec = actions.AppSpec(
            name=app.get("name", app.get("launch", "?")),
            launch=app["launch"],
            window=app.get("window", ""),
            monitor=app.get("monitor", "principal"),
            slot=app.get("slot", "full"),
            args=list(app.get("args", [])),
            play=bool(app.get("play", False)),
            background=bool(app.get("background", False)),
        )
        results.append(actions.launch(spec))

    return {"ok": True, "profile": name, "results": results}


# ------------------------------------------------------------------- API

app = FastAPI(title="KAIROS Bridge", version="0.1.0")


class ProfileRequest(BaseModel):
    name: str


class WindowRequest(BaseModel):
    pattern: str
    confirm: bool = False


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "perfiles": sorted(config.profiles),
        "frases": sorted(config.phrases),
        "escritorio": actions.describe_desktop(),
    }


@app.post("/profile", dependencies=[Depends(authorize)])
async def profile(body: ProfileRequest) -> dict[str, Any]:
    return run_profile(body.name)


@app.post("/profile/close", dependencies=[Depends(authorize)])
async def profile_close(body: ProfileRequest) -> dict[str, Any]:
    return close_profile(body.name)


@app.post("/focus", dependencies=[Depends(authorize)])
async def focus(body: WindowRequest) -> dict[str, Any]:
    return {"ok": True, "result": actions.focus(body.pattern)}


@app.post("/close", dependencies=[Depends(authorize)])
async def close(body: WindowRequest) -> dict[str, Any]:
    # Lo destructivo exige intencion explicita, aunque el token sea valido.
    if not body.confirm:
        return {"ok": False, "error": "cerrar requiere confirm=true"}
    return {"ok": True, "result": actions.close_window(body.pattern)}


@app.post("/reload", dependencies=[Depends(authorize)])
async def reload_config() -> dict[str, Any]:
    config.load()
    return {"ok": True, "perfiles": sorted(config.profiles)}


# ------------------------------------------------------- atajo global y voz

def transcribe_and_dispatch(audio: bytes) -> None:
    """Manda el audio al nucleo y ejecuta el perfil cuya frase coincida."""
    try:
        with httpx.Client(timeout=90) as client:
            response = client.post(
                f"{CORE_URL}/api/v1/voice/transcribe",
                files={"audio": ("audio.wav", audio, "audio/wav")},
                headers=_core_headers(),
            )
            if response.status_code != 200:
                print(f"[bridge] transcripcion fallida: {response.status_code}")
                if response.status_code == 401:
                    print("[bridge] el nucleo rechaza el token: aplica el parche 5B")
                return
            text = response.json().get("text", "").lower().strip()
    except httpx.HTTPError as exc:
        print(f"[bridge] nucleo inalcanzable: {exc}")
        return

    dispatch(text)


def dispatch(text: str) -> None:
    """Traduce voz a accion sobre perfiles.

    Si no encaja con ningun patron, NO se toca el escritorio. Es la garantia
    de que una conversacion normal no acaba abriendo ventanas.
    """
    command = commands.parse(text, config.phrases)

    if command.kind == "none":
        print(f"[bridge] no es una orden de perfil: {text!r}")
        return

    if command.kind == "switch":
        print(f"[bridge] cerrando {command.other} y abriendo {command.name}")
        print(f"[bridge] {close_profile(command.other)}")
        print(f"[bridge] {run_profile(command.name)}")
        return

    if command.kind == "close":
        print(f"[bridge] {close_profile(command.name)}")
        return

    print(f"[bridge] {run_profile(command.name)}")


def _core_headers() -> dict[str, str]:
    """Credencial de maquina: el mismo secreto que el nucleo usa para hablar
    con el puente, en la direccion contraria. Solo abre /voice/transcribe."""
    return {"x-bridge-token": SECRET}


def record(seconds: float = 5.0) -> bytes | None:
    """Graba del microfono por defecto. Requiere sounddevice."""
    try:
        import io
        import wave

        import sounddevice as sd
    except ImportError:
        print("[bridge] falta sounddevice: pip install sounddevice")
        return None

    rate = 16000
    print(f"[bridge] escuchando {seconds}s...")
    data = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype="int16")
    sd.wait()

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(data.tobytes())
    return buffer.getvalue()


def on_hotkey() -> None:
    audio = record()
    if audio:
        threading.Thread(target=transcribe_and_dispatch, args=(audio,), daemon=True).start()


def start_hotkey() -> None:
    try:
        import keyboard
    except ImportError:
        print("[bridge] falta keyboard: pip install keyboard  (atajo desactivado)")
        return
    combo = config.hotkey
    keyboard.add_hotkey(combo, on_hotkey)
    print(f"[bridge] atajo global: {combo}")


def start_tray() -> None:
    try:
        from PIL import Image, ImageDraw
        import pystray
    except ImportError:
        print("[bridge] falta pystray/pillow: sin icono en bandeja")
        return

    image = Image.new("RGB", (64, 64), (5, 7, 13))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), outline=(79, 216, 255), width=4)
    draw.ellipse((22, 22, 42, 42), fill=(166, 120, 255))

    def items():  # type: ignore[no-untyped-def]
        yield pystray.MenuItem("Escuchar ahora", lambda: on_hotkey())
        for name in sorted(config.profiles):
            yield pystray.MenuItem(f"Abrir: {name}",
                                   lambda _, n=name: run_profile(n))
        for name in sorted(config.profiles):
            yield pystray.MenuItem(f"Cerrar: {name}",
                                   lambda _, n=name: close_profile(n))
        yield pystray.MenuItem("Recargar configuración", lambda: config.load())
        yield pystray.MenuItem("Salir", lambda icon: icon.stop())

    icon = pystray.Icon("kairos", image, "KAIROS Bridge", pystray.Menu(items))
    threading.Thread(target=icon.run, daemon=True).start()
    print("[bridge] icono en bandeja activo")


def transcribe(audio: bytes) -> str:
    try:
        with httpx.Client(timeout=90) as client:
            response = client.post(
                f"{CORE_URL}/api/v1/voice/transcribe",
                files={"audio": ("audio.wav", audio, "audio/wav")},
                headers=_core_headers(),
            )
            if response.status_code == 401:
                print("[bridge] 401 del nucleo: falta el parche 5B o el token no coincide")
                return ""
            if response.status_code != 200:
                return ""
            return response.json().get("text", "")
    except httpx.HTTPError:
        return ""


def start_listening() -> None:
    """Escucha permanente con palabra de activacion.

    El microfono esta siempre abierto, pero solo se transcribe lo que un
    detector de energia considera voz. En silencio, el coste es ~0.
    """
    if not config.always_listening:
        print("[bridge] escucha permanente desactivada en la configuracion")
        return

    listener = WakeListener(
        transcribe=transcribe,
        on_command=dispatch,
        wake_words=config.wake_words,
        device=config.input_device,
        on_state=lambda s: print(f"[escucha] {s}"),
    )
    threading.Thread(target=listener.run, daemon=True).start()
    print(f"[bridge] palabra de activacion: {', '.join(config.wake_words)}")


def main() -> None:
    if sys.platform != "win32":
        print("[bridge] aviso: fuera de Windows, el control de ventanas no hace nada")
    start_hotkey()
    start_tray()
    start_listening()
    print(f"[bridge] escuchando en http://{HOST}:{PORT} (solo loopback)")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()

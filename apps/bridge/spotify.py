"""Control de Spotify por su API oficial.

Por que la API y no los URI: abrir `spotify:track:ID` navega a la cancion pero
no siempre la reproduce, y nunca garantiza que empiece por el principio — si
Spotify tenia otra cosa cargada, el play reanuda lo anterior. Eso es lo que
hacia sonar Thunderstruck en vez de Back in Black.

Con la API se pide exactamente "reproduce esta cancion desde el segundo cero"
y no hay ambiguedad. Ademas desbloquea buscar por nombre, pausar, saltar y
ajustar volumen, que con URI no se puede.

Requiere Spotify Premium: la API de reproduccion no funciona con cuenta
gratuita. Es una limitacion de Spotify, no del diseno.

Los secretos viven en `.spotify-auth.json` junto al puente, nunca en el
repositorio. El fichero incluye el refresh_token, que es un secreto de larga
duracion: si se filtra, alguien puede controlar tu reproduccion.
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import httpx

AUTH_PATH = Path(".spotify-auth.json")
API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"

SCOPES = (
    "user-modify-playback-state user-read-playback-state "
    "user-read-currently-playing"
)


class Spotify:
    def __init__(self, path: Path = AUTH_PATH) -> None:
        self._path = path
        self._data: dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------ credenciales

    def load(self) -> None:
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    @property
    def configured(self) -> bool:
        return bool(self._data.get("refresh_token"))

    def _refresh(self) -> str | None:
        """Renueva el token de acceso. Los de Spotify caducan en una hora."""
        creds = base64.b64encode(
            f"{self._data['client_id']}:{self._data['client_secret']}".encode()
        ).decode()
        try:
            response = httpx.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._data["refresh_token"],
                },
                headers={"Authorization": f"Basic {creds}"},
                timeout=20,
            )
            if response.status_code != 200:
                print(f"[spotify] no se pudo renovar el token: {response.status_code}")
                return None
            body = response.json()
        except httpx.HTTPError as exc:
            print(f"[spotify] sin conexion: {type(exc).__name__}")
            return None

        self._data["access_token"] = body["access_token"]
        self._data["expires_at"] = time.time() + body.get("expires_in", 3600) - 60
        # Spotify a veces rota el refresh_token; hay que quedarse con el nuevo.
        if body.get("refresh_token"):
            self._data["refresh_token"] = body["refresh_token"]
        self._save()
        return self._data["access_token"]

    def _token(self) -> str | None:
        if not self.configured:
            return None
        if self._data.get("access_token") and time.time() < self._data.get("expires_at", 0):
            return self._data["access_token"]
        return self._refresh()

    def _headers(self) -> dict[str, str] | None:
        token = self._token()
        return {"Authorization": f"Bearer {token}"} if token else None

    # --------------------------------------------------------------- llamadas

    def _call(self, method: str, path: str, **kwargs: Any) -> tuple[bool, Any]:
        headers = self._headers()
        if headers is None:
            return False, "Spotify no esta autorizado. Ejecuta autorizar-spotify.py"
        try:
            response = httpx.request(
                method, f"{API}{path}", headers=headers, timeout=20, **kwargs
            )
        except httpx.HTTPError as exc:
            return False, f"sin conexion con Spotify: {type(exc).__name__}"

        if response.status_code == 404:
            return False, "no hay ningun dispositivo activo. Abre Spotify primero."
        if response.status_code == 403:
            return False, "Spotify lo rechaza (¿la cuenta es Premium?)"
        if response.status_code >= 400:
            return False, f"Spotify respondio {response.status_code}"
        # Spotify devuelve 204 sin cuerpo en play/pause/next, y a veces un 200
        # con cuerpo vacio. Asumir JSON siempre reventaba el hilo de escucha.
        if response.status_code == 204 or not response.content.strip():
            return True, {}
        try:
            return True, response.json()
        except ValueError:
            return True, {}

    def _devices(self) -> list[dict[str, Any]]:
        ok, body = self._call("GET", "/me/player/devices")
        return body.get("devices", []) if ok else []

    def _active_device(self) -> str | None:
        """Prefiere el dispositivo activo; si no, el primero disponible."""
        devices = self._devices()
        for device in devices:
            if device.get("is_active"):
                return device["id"]
        return devices[0]["id"] if devices else None

    # ---------------------------------------------------------------- acciones

    def play_track(self, track_id: str) -> str:
        """Reproduce una cancion DESDE EL PRINCIPIO.

        `position_ms: 0` es lo que garantiza que empiece por el principio,
        cosa que abrir el URI no hacia.
        """
        device = self._active_device()
        params = {"device_id": device} if device else {}
        ok, body = self._call(
            "PUT", "/me/player/play",
            params=params,
            json={"uris": [f"spotify:track:{track_id}"], "position_ms": 0},
        )
        if not ok:
            return str(body)
        return "reproduciendo desde el principio"

    def search_and_play(self, query: str) -> str:
        ok, body = self._call(
            "GET", "/search", params={"q": query, "type": "track", "limit": 1}
        )
        if not ok:
            return str(body)
        items = body.get("tracks", {}).get("items", [])
        if not items:
            return f"no encontre nada para {query!r}"
        track = items[0]
        artist = track["artists"][0]["name"] if track.get("artists") else "?"
        result = self.play_track(track["id"])
        if result.startswith("reproduciendo"):
            return f"{track['name']} de {artist}"
        return result

    def pause(self) -> str:
        ok, body = self._call("PUT", "/me/player/pause")
        return "musica pausada" if ok else str(body)

    def resume(self) -> str:
        ok, body = self._call("PUT", "/me/player/play")
        return "musica reanudada" if ok else str(body)

    def next_track(self) -> str:
        ok, body = self._call("POST", "/me/player/next")
        return "siguiente cancion" if ok else str(body)

    def previous_track(self) -> str:
        ok, body = self._call("POST", "/me/player/previous")
        return "cancion anterior" if ok else str(body)

    def set_volume(self, percent: int) -> str:
        percent = max(0, min(100, percent))
        ok, body = self._call("PUT", "/me/player/volume", params={"volume_percent": percent})
        return f"volumen al {percent}%" if ok else str(body)

    def now_playing(self) -> str:
        ok, body = self._call("GET", "/me/player/currently-playing")
        if not ok or not body:
            return "no hay nada sonando"
        item = body.get("item") or {}
        artist = item.get("artists", [{}])[0].get("name", "?")
        return f"{item.get('name', '?')} de {artist}"

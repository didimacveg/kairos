"""Autorizacion de Spotify. Se ejecuta UNA vez.

Antes de correrlo:

1. Entra en https://developer.spotify.com/dashboard y crea una app
   (es gratis y no pide tarjeta).
2. En Settings de la app, anade esta Redirect URI EXACTA:
       http://127.0.0.1:8888/callback
3. Copia el Client ID y el Client Secret.

Guarda el refresh_token en `.spotify-auth.json`, junto al puente. Ese fichero
NO debe subirse a GitHub: contiene un secreto de larga duracion.
"""
from __future__ import annotations

import base64
import http.server
import json
import secrets
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import httpx

REDIRECT = "http://127.0.0.1:8888/callback"
SCOPES = "user-modify-playback-state user-read-playback-state user-read-currently-playing"

print("=" * 62)
print("AUTORIZACION DE SPOTIFY")
print("=" * 62)
print("Necesitas una app en https://developer.spotify.com/dashboard")
print(f"con esta Redirect URI exacta:\n    {REDIRECT}\n")

client_id = input("Client ID: ").strip()
client_secret = input("Client Secret: ").strip()

if not client_id or not client_secret:
    print("Faltan credenciales.")
    raise SystemExit(1)

state = secrets.token_urlsafe(16)
code_holder: dict[str, str] = {}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if params.get("state", [""])[0] != state:
            self.wfile.write("<h2>Estado invalido. Cierra y reintenta.</h2>".encode())
            return
        if "code" in params:
            code_holder["code"] = params["code"][0]
            self.wfile.write(
                "<h2>KAIROS autorizado. Ya puedes cerrar esta pestana.</h2>".encode()
            )
        else:
            self.wfile.write("<h2>Autorizacion denegada.</h2>".encode())

    def log_message(self, *args: object) -> None:
        pass


server = http.server.HTTPServer(("127.0.0.1", 8888), Handler)
threading.Thread(target=server.handle_request, daemon=True).start()

url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(
    {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT,
        "scope": SCOPES,
        "state": state,
    }
)
print("\nAbriendo el navegador para que autorices...")
webbrowser.open(url)
print(f"Si no se abre solo, entra aqui:\n{url}\n")

import time

for _ in range(120):
    if "code" in code_holder:
        break
    time.sleep(1)

if "code" not in code_holder:
    print("No llego la autorizacion. Reintenta.")
    raise SystemExit(1)

creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
response = httpx.post(
    "https://accounts.spotify.com/api/token",
    data={
        "grant_type": "authorization_code",
        "code": code_holder["code"],
        "redirect_uri": REDIRECT,
    },
    headers={"Authorization": f"Basic {creds}"},
    timeout=20,
)

if response.status_code != 200:
    print(f"Spotify rechazo el intercambio: {response.status_code}")
    print(response.text[:400])
    raise SystemExit(1)

body = response.json()
Path(".spotify-auth.json").write_text(
    json.dumps(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": body["refresh_token"],
            "access_token": body["access_token"],
            "expires_at": 0,
        },
        indent=2,
    ),
    encoding="utf-8",
)
print("\nListo. Credenciales en .spotify-auth.json")
print("No subas ese fichero a GitHub.")

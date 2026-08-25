"""Autorizacion de Google. Se ejecuta UNA vez, desde Ubuntu.

Solo libreria estandar: nada que instalar. Abre un servidor local, te manda al
navegador, y guarda el refresh_token.
"""
from __future__ import annotations

import http.server
import json
import secrets
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

REDIRECT = "http://localhost:8765/callback"
SCOPES = " ".join([
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
])

print("=" * 62)
print("AUTORIZACION DE GOOGLE PARA KAIROS")
print("=" * 62)

client_id = input("Client ID: ").strip()
client_secret = input("Client Secret: ").strip()
if not client_id or not client_secret:
    raise SystemExit("Faltan credenciales.")

state = secrets.token_urlsafe(16)
recibido: dict[str, str] = {}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if params.get("state", [""])[0] != state:
            self.wfile.write(b"<h2>Estado invalido.</h2>")
            return
        if "code" in params:
            recibido["code"] = params["code"][0]
            self.wfile.write(
                "<h2>KAIROS autorizado. Ya puedes cerrar esta pestana.</h2>".encode())
        else:
            self.wfile.write(b"<h2>Autorizacion denegada.</h2>")

    def log_message(self, *a: object) -> None:
        pass


servidor = http.server.HTTPServer(("127.0.0.1", 8765), Handler)
threading.Thread(target=servidor.handle_request, daemon=True).start()

url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": client_id,
    "redirect_uri": REDIRECT,
    "response_type": "code",
    "scope": SCOPES,
    "access_type": "offline",
    # Fuerza que Google devuelva refresh_token. Sin esto, en la segunda
    # autorizacion no lo manda y el acceso caduca en una hora.
    "prompt": "consent",
    "state": state,
})

print("\nAbre esto en el navegador de Windows:\n")
print(url)
print("\nEsperando la autorizacion (3 minutos)...\n")

for _ in range(180):
    if "code" in recibido:
        break
    time.sleep(1)

if "code" not in recibido:
    raise SystemExit("No llego la autorizacion.")

datos = urllib.parse.urlencode({
    "code": recibido["code"],
    "client_id": client_id,
    "client_secret": client_secret,
    "redirect_uri": REDIRECT,
    "grant_type": "authorization_code",
}).encode()

peticion = urllib.request.Request(
    "https://oauth2.googleapis.com/token", data=datos,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
try:
    with urllib.request.urlopen(peticion, timeout=30) as r:
        cuerpo = json.loads(r.read().decode())
except urllib.error.HTTPError as e:
    print("Google rechazo el intercambio:", e.code)
    print(e.read().decode()[:400])
    raise SystemExit(1)

if "refresh_token" not in cuerpo:
    raise SystemExit(
        "Google no devolvio refresh_token. Revoca el acceso en "
        "myaccount.google.com/permissions y reintenta."
    )

Path("google-token.json").write_text(json.dumps({
    "refresh_token": cuerpo["refresh_token"],
    "access_token": cuerpo.get("access_token", ""),
    "expires_at": 0,
}, indent=2), encoding="utf-8")

print("\nListo. Token en ./google-token.json")

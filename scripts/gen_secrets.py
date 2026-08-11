#!/usr/bin/env python3
"""Rellena los secretos placeholder de .env con valores aleatorios.

Idempotente: solo sustituye valores que sigan siendo el placeholder.
"""
from __future__ import annotations

import pathlib
import secrets
import sys

PLACEHOLDERS = {
    "POSTGRES_PASSWORD": "cambia-esto-por-algo-largo-y-aleatorio",
    "KAIROS_SESSION_SECRET": "cambia-esto-por-un-secreto-de-48-bytes",
}

env_path = pathlib.Path(__file__).resolve().parents[1] / ".env"
if not env_path.exists():
    print("No existe .env. Ejecuta primero: cp .env.example .env", file=sys.stderr)
    raise SystemExit(1)

lines = env_path.read_text(encoding="utf-8").splitlines()
changed = []
for i, line in enumerate(lines):
    for key, placeholder in PLACEHOLDERS.items():
        if line.strip() == f"{key}={placeholder}":
            lines[i] = f"{key}={secrets.token_urlsafe(48)}"
            changed.append(key)

if changed:
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Secretos generados para: " + ", ".join(changed))
else:
    print("Nada que hacer: los secretos ya no son placeholders.")

"""Utilidades de administracion.

Uso:
    python -m kairos.cli migrate
    python -m kairos.cli create-user
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from kairos.auth.service import create_user, get_user_by_username
from kairos.db.bootstrap import create_schema
from kairos.db.session import get_session_factory


async def _migrate() -> None:
    await create_schema()
    print("Esquema creado/actualizado.")


async def _create_user() -> None:
    username = input("Usuario: ").strip()
    password = getpass.getpass("Contrasena (min 12 caracteres): ")
    confirm = getpass.getpass("Repite la contrasena: ")
    if password != confirm:
        print("Las contrasenas no coinciden.", file=sys.stderr)
        raise SystemExit(1)
    async with get_session_factory()() as db:
        if await get_user_by_username(db, username) is not None:
            print("Ese usuario ya existe.", file=sys.stderr)
            raise SystemExit(1)
        try:
            user = await create_user(db, username, password)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc
    print(f"Usuario creado: {user.username} ({user.role})")


def main() -> None:
    parser = argparse.ArgumentParser(prog="kairos")
    parser.add_argument("command", choices=["migrate", "create-user"])
    args = parser.parse_args()
    if args.command == "migrate":
        asyncio.run(_migrate())
    else:
        asyncio.run(_create_user())


if __name__ == "__main__":
    main()

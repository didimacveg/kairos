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
from kairos.agents.memory.audit import review
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


async def _memory_audit(apply: bool) -> None:
    async with get_session_factory()() as db:
        verdicts, total = await review(db, apply=apply)
    if not verdicts:
        print(f"Memoria limpia: {total} recuerdos activos, nada que retirar.")
        return
    print(f"{len(verdicts)} de {total} recuerdos activos no parecen hechos:\n")
    for v in verdicts:
        print(f"  [{v.reason}] {v.content[:80]}")
    if apply:
        print(f"\nRetirados {len(verdicts)} (status=discarded, reversible).")
    else:
        print("\nNada modificado. Para aplicarlo: memory-audit --apply")


def main() -> None:
    parser = argparse.ArgumentParser(prog="kairos")
    parser.add_argument("command", choices=["migrate", "create-user", "memory-audit"])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.command == "migrate":
        asyncio.run(_migrate())
    elif args.command == "memory-audit":
        asyncio.run(_memory_audit(args.apply))
    else:
        asyncio.run(_create_user())


if __name__ == "__main__":
    main()

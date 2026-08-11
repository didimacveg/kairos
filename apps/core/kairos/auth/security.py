"""Primitivas criptograficas de autenticacion.

Argon2id con parametros por encima del minimo OWASP. El coste esta calibrado
para hardware de escritorio: si el login tarda menos de ~200 ms, sube memory_cost.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def new_session_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_session_token(token: str, secret: str) -> str:
    """HMAC-SHA256 del token con el secreto de instancia.

    Se usa HMAC y no SHA256 a secas para que un volcado de la base de datos
    sin el secreto no permita construir hashes candidatos por fuerza bruta.
    """
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()

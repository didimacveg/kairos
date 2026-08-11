from __future__ import annotations

from kairos.auth.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    verify_password,
)


def test_password_hash_is_argon2id_and_salted() -> None:
    h1 = hash_password("contrasena-larga-de-prueba")
    h2 = hash_password("contrasena-larga-de-prueba")
    assert h1.startswith("$argon2id$")
    assert h1 != h2, "dos hashes de la misma contrasena deben diferir (salt aleatorio)"


def test_password_verification() -> None:
    stored = hash_password("contrasena-larga-de-prueba")
    assert verify_password("contrasena-larga-de-prueba", stored)
    assert not verify_password("otra-contrasena-distinta", stored)


def test_verify_password_does_not_raise_on_garbage_hash() -> None:
    assert not verify_password("cualquiera", "no-es-un-hash")


def test_session_token_is_high_entropy_and_unique() -> None:
    tokens = {new_session_token() for _ in range(200)}
    assert len(tokens) == 200
    assert all(len(t) >= 40 for t in tokens)


def test_session_hash_depends_on_instance_secret() -> None:
    token = new_session_token()
    assert hash_session_token(token, "secreto-a") != hash_session_token(token, "secreto-b")
    assert hash_session_token(token, "secreto-a") == hash_session_token(token, "secreto-a")

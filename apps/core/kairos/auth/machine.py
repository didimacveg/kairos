"""Credencial de maquina para el puente.

El puente no es una persona: no tiene navegador, ni sesion, ni contrasena que
deba conocer. Necesita una forma de identificarse ante el nucleo.

Diseno, y sus limites deliberados:

- Es el MISMO token que el nucleo usa para hablar con el puente. Un unico
  secreto compartido entre dos procesos de la misma maquina, no dos.
- Solo sirve para `/voice/transcribe`. No da acceso al chat, ni a la memoria,
  ni a la auditoria, ni a nada mas. Un puente comprometido puede transcribir
  audio; no puede leer tus conversaciones.
- Las acciones que ejecuta actuan a nombre del propietario, y quedan
  auditadas como tales.

La alternativa —guardar tu usuario y contrasena en un fichero de texto en
Windows— seria peor: un secreto con muchos mas permisos, en un sitio menos
protegido.
"""
from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.auth.deps import SESSION_COOKIE
from kairos.auth.service import resolve_session
from kairos.config import get_settings
from kairos.db.models import User
from kairos.db.session import get_db


async def user_or_machine(
    kairos_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    x_bridge_token: Annotated[str, Header()] = "",
    db: AsyncSession = Depends(get_db),
) -> User:
    """Acepta una sesion de navegador O el token del puente.

    El orden importa: si hay cookie valida, gana. El token de maquina es el
    camino secundario, no el principal.
    """
    if kairos_session:
        user = await resolve_session(db, kairos_session)
        if user is not None:
            return user

    settings = get_settings()
    if (
        settings.bridge_enabled
        and settings.bridge_token
        and x_bridge_token
        and secrets.compare_digest(x_bridge_token, settings.bridge_token)
    ):
        # El puente actua a nombre del propietario de la instancia.
        result = await db.execute(
            select(User).where(User.role == "owner", User.is_active.is_(True)).limit(1)
        )
        owner = result.scalar_one_or_none()
        if owner is not None:
            return owner

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesion no iniciada")


MachineOrUser = Annotated[User, Depends(user_or_machine)]

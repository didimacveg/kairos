"""Historial de conversaciones.

Las conversaciones ya se guardaban en Postgres desde la Fase 1; lo que no
habia era forma de volver a ellas. Al recargar la pagina, KAIROS empezaba de
cero aunque el hilo entero siguiera en la base de datos.

Es la diferencia mas visible entre una herramienta y un juguete: poder
retomar lo que estabas haciendo.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, select

from kairos.auth.deps import CurrentUser, DbSession
from kairos.db.models import Conversation, Message

router = APIRouter(prefix="/conversaciones", tags=["conversaciones"])

MAX_LISTA = 40


@router.get("")
async def listar(user: CurrentUser, db: DbSession) -> dict:
    """Las conversaciones con su primer mensaje como titulo.

    El titulo sale del primer mensaje del usuario, no de un resumen generado:
    es lo que de verdad recuerdas haber preguntado, y no cuesta una llamada
    al modelo por conversacion.
    """
    filas = (
        await db.execute(
            select(
                Conversation.id,
                Conversation.created_at,
                func.count(Message.id).label("mensajes"),
                func.max(Message.created_at).label("ultimo"),
            )
            .outerjoin(Message, Message.conversation_id == Conversation.id)
            .where(Conversation.owner_id == user.id)
            .group_by(Conversation.id)
            .order_by(func.max(Message.created_at).desc().nulls_last())
            .limit(MAX_LISTA)
        )
    ).all()

    salida = []
    for f in filas:
        if not f.mensajes:
            continue
        primero = (
            await db.execute(
                select(Message.content)
                .where(Message.conversation_id == f.id, Message.role == "user")
                .order_by(Message.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        salida.append({
            "id": str(f.id),
            "titulo": (primero or "(sin titulo)")[:90],
            "mensajes": f.mensajes,
            "ultimo": f.ultimo.isoformat() if f.ultimo else None,
        })
    return {"conversaciones": salida}


@router.get("/{conv_id}")
async def abrir(conv_id: uuid.UUID, user: CurrentUser, db: DbSession) -> dict:
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conv_id, Conversation.owner_id == user.id
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe")

    mensajes = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
            .limit(200)
        )
    ).scalars().all()

    return {
        "id": str(conv.id),
        "mensajes": [
            {"de": "me" if m.role == "user" else "kairos", "said": m.content}
            for m in mensajes
        ],
    }


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar(conv_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conv_id, Conversation.owner_id == user.id
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe")

    # Los mensajes se borran; los RECUERDOS que salieron de ellos NO. Lo que
    # KAIROS aprendio de una conversacion no deja de ser cierto porque borres
    # el hilo, y perder memoria al limpiar el historial seria una sorpresa
    # desagradable.
    await db.execute(delete(Message).where(Message.conversation_id == conv_id))
    await db.delete(conv)
    await db.commit()

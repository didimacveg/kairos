from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from kairos.api.v1.schemas import ChatRequest, ChatResponse
from kairos.auth.deps import CurrentUser, DbSession
from kairos.db.session import get_session_factory
from kairos.logging import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
log = get_logger("kairos.api.chat")


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest, request: Request, user: CurrentUser, db: DbSession
) -> ChatResponse:
    """Respuesta completa de una vez. Se mantiene para depurar con curl."""
    core = request.app.state.core
    try:
        result = await core.chat(
            db, user=user, message=body.message, conversation_id=body.conversation_id,
            attachments=body.attachments
        )
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    return ChatResponse(
        conversation_id=result.conversation_id,
        reply=result.reply,
        model=result.model,
        latency_ms=result.latency_ms,
        local=result.local,
        memories=result.memories,
        trace=[t.model_dump() for t in result.trace],
    )


def _sse(payload: dict[str, object]) -> str:
    """Serializa un evento en formato Server-Sent Events.

    El doble salto de linea es el delimitador del protocolo; sin el, el
    navegador nunca entrega el evento.
    """
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


@router.post("/stream")
async def chat_stream(body: ChatRequest, request: Request, user: CurrentUser) -> StreamingResponse:
    """Respuesta incremental por SSE.

    Nota importante: aqui NO se inyecta la sesion de base de datos por
    dependencia. FastAPI cierra las dependencias con `yield` antes de que el
    cuerpo de una StreamingResponse se haya consumido, asi que la sesion
    estaria muerta justo cuando el generador la necesita. Se abre una sesion
    propia dentro del generador y se cierra con el.

    `user` viene de una sesion ya cerrada, pero la fabrica usa
    expire_on_commit=False, asi que sus atributos siguen cargados.
    """
    core = request.app.state.core

    async def event_source() -> AsyncIterator[str]:
        async with get_session_factory()() as db:
            try:
                async for event in core.chat_stream(
                    db, user=user, message=body.message, conversation_id=body.conversation_id,
            attachments=body.attachments
                ):
                    payload: dict[str, object] = {"type": event.type}
                    if event.text is not None:
                        payload["text"] = event.text
                    if event.trace is not None:
                        payload["trace"] = event.trace.model_dump(mode="json")
                    if event.error is not None:
                        payload["error"] = event.error
                    if event.data:
                        payload["data"] = event.data
                    yield _sse(payload)
            except Exception as exc:  # noqa: BLE001
                # El cliente ya puede tener tokens en pantalla: hay que
                # cerrarle el flujo con un error explicito, no colgarlo.
                log.error("chat_stream.failed", error=str(exc))
                yield _sse({"type": "error", "error": f"{type(exc).__name__}: {exc}"})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Desactiva el buffering de proxies intermedios; sin esto el
            # streaming llega de golpe al final y no sirve de nada.
            "X-Accel-Buffering": "no",
        },
    )

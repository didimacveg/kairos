from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from kairos.api.v1.schemas import ChatRequest, ChatResponse
from kairos.auth.deps import CurrentUser, DbSession

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request, user: CurrentUser, db: DbSession) -> ChatResponse:
    core = request.app.state.core
    try:
        result = await core.chat(
            db, user=user, message=body.message, conversation_id=body.conversation_id
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

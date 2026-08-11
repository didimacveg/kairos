from __future__ import annotations

from fastapi import APIRouter, Request

from kairos.api.v1.schemas import HealthResponse
from kairos.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = get_settings()
    agents = await request.app.state.core.health()
    degraded = any(a.get("status") not in {"ok", "unknown"} for a in agents)
    return HealthResponse(
        status="degraded" if degraded else "ok",
        instance=settings.instance_name,
        egress_allowed=settings.allow_egress,
        agents=agents,
    )

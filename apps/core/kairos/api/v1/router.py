from __future__ import annotations

from fastapi import APIRouter

from kairos.api.v1 import routes_auth, routes_chat, routes_health, routes_voice

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(routes_health.router)
api_router.include_router(routes_auth.router)
api_router.include_router(routes_chat.router)
api_router.include_router(routes_voice.router)

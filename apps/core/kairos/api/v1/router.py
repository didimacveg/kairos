from __future__ import annotations

from fastapi import APIRouter

from kairos.api.v1 import (
    routes_auth,
    routes_briefing,
    routes_chat,
    routes_conversaciones,
    routes_device,
    routes_documentos,
    routes_files,
    routes_google,
    routes_health,
    routes_intent,
    routes_proposals,
    routes_smith,
    routes_voice,
    routes_warden,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(routes_auth.router)
api_router.include_router(routes_briefing.router)
api_router.include_router(routes_chat.router)
api_router.include_router(routes_conversaciones.router)
api_router.include_router(routes_device.router)
api_router.include_router(routes_documentos.router)
api_router.include_router(routes_files.router)
api_router.include_router(routes_google.router)
api_router.include_router(routes_health.router)
api_router.include_router(routes_intent.router)
api_router.include_router(routes_proposals.router)
api_router.include_router(routes_smith.router)
api_router.include_router(routes_voice.router)
api_router.include_router(routes_warden.router)

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from pydantic import BaseModel, Field

from kairos.agents.base import AgentRequest
from kairos.audit import service as audit
from kairos.auth.deps import CurrentUser, DbSession

router = APIRouter(prefix="/smith", tags=["smith"])


class Peticion(BaseModel):
    peticion: str = Field(min_length=8, max_length=1000)


async def _trabajar(core, user_id, peticion: str) -> None:
    """Ejecuta Smith en segundo plano, con su propia sesion.

    Smith tarda minutos: dos llamadas al modelo, el ensayo completo en el
    forge, y la relectura. Cualquier navegador corta la peticion mucho antes
    y el usuario ve un 500 mientras el servidor sigue trabajando — que es
    exactamente lo que pasaba.

    Ahora la ruta confirma al instante y la propuesta aparece sola en el
    panel cuando esta lista.
    """
    from kairos.db.session import get_session_factory

    async with get_session_factory()() as db:
        try:
            agente = core.registry.find("smith.proponer")
        except KeyError:
            return
        await agente.handle(
            AgentRequest(
                capability="smith.proponer", actor_id=user_id,
                payload={"peticion": peticion},
            ),
            db=db,
        )


@router.post("/proponer")
async def proponer(
    body: Peticion, tareas: BackgroundTasks, request: Request,
    user: CurrentUser, db: DbSession,
) -> dict:
    """Pide a KAIROS que escriba un cambio sobre si mismo.

    Devuelve INMEDIATAMENTE. El trabajo va en segundo plano y la propuesta
    aparece en el panel cuando esta lista, en unos minutos.
    """
    try:
        request.app.state.core.registry.find("smith.proponer")
    except KeyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "La auto-mejora no esta activa. Requiere KAIROS_SMITH_ENABLED y el forge.",
        ) from None

    await audit.record(
        db, action="smith.proponer", outcome="success",
        actor_id=user.id, detail={"peticion": body.peticion[:200], "modo": "segundo plano"},
    )

    tareas.add_task(_trabajar, request.app.state.core, user.id, body.peticion)
    return {
        "aceptado": True,
        "mensaje": "Me pongo con ello. La propuesta aparecera aqui en unos minutos.",
    }

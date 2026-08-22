"""Smith Agent — KAIROS se escribe a si mismo.

El ciclo completo, con las cuatro piezas ya construidas:

    peticion -> Smith lee su codigo y escribe los ficheros nuevos
             -> difflib calcula el parche
             -> Forge lo ensaya aislado y sin red
             -> si los tests pasan, se crea una PROPUESTA
             -> Diego aprueba o rechaza

Lo que NO hace, y es deliberado:
- No aplica nada. Ni siquiera cuando los tests pasan.
- No escribe en el repositorio. Solo lee; los cambios viven en la propuesta.
- No decide que es importante. La peticion la pone el usuario.

Si los tests fallan, la propuesta se crea igualmente pero marcada, con la
salida del fallo. Un intento fallido tambien es informacion: dice que KAIROS
no supo hacerlo, y por que.
"""
from __future__ import annotations

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.proposals import store
from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider
from kairos.agents.registry import AgentRegistry
from kairos.agents.smith import diffs, repo
from kairos.logging import get_logger

log = get_logger("kairos.smith")

MAX_FICHEROS_CONTEXTO = 8

PROMPT = """Eres el ingeniero de KAIROS, un asistente personal. Tu trabajo es
escribir el codigo de un cambio que se te pide sobre TU PROPIO sistema.

Arquitectura, para que sepas donde tocar:
- apps/core/kairos/agents/   agentes; cada uno es un bounded context con
  capacidades nombradas y contrato Agent/AgentRequest/AgentResponse
- apps/core/kairos/core/     orquestador y composicion (bootstrap.py)
- apps/core/kairos/api/v1/   rutas HTTP
- apps/core/tests/           pruebas
- apps/web/                  interfaz Next.js
- apps/bridge/               proceso que corre en Windows y controla el escritorio

Reglas que NO se negocian en este proyecto:
- Un agente nunca lanza excepciones hacia arriba: devuelve AgentResponse.failure.
- Nada que ejecute acciones acepta comandos libres: solo listas cerradas.
- Todo cambio va acompanado de sus tests.
- Sin `shell=True`, sin interpolar cadenas en comandos, nunca.

FORMATO DE RESPUESTA — solo JSON, sin texto alrededor ni ```:

{{"motivo": "que hace el cambio y por que, en 2-4 frases",
  "riesgo": "bajo|medio|alto",
  "ficheros": [{{"ruta": "apps/core/...", "contenido": "FICHERO COMPLETO"}}]}}

En "contenido" va el fichero ENTERO tal y como debe quedar, no un fragmento ni
un diff. Si creas un fichero nuevo, tambien entero.

Maximo {max_ficheros} ficheros. Si el cambio necesita mas, hazlo en el minimo
imprescindible y explica en "motivo" que falta.

Riesgo: bajo si solo anade; medio si modifica logica existente; alto si toca
autenticacion, la base de datos, el puente o el propio Smith."""


class SmithAgent(Agent):
    name = "smith"
    capabilities = frozenset({"smith.proponer"})

    def __init__(self, provider: LLMProvider, registry: AgentRegistry) -> None:
        self._provider = provider
        self._registry = registry

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "smith.proponer":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        peticion = (request.payload.get("peticion") or "").strip()
        if not peticion:
            return AgentResponse.failure("Falta la peticion")

        started = time.perf_counter()
        traza: list[TraceEvent] = []

        # --- 1. Elegir que ficheros mirar ---------------------------------
        indice = repo.arbol_resumido()
        if not indice:
            return AgentResponse.failure(
                "No veo el repositorio. ¿Esta montado /repo en el nucleo?"
            )

        relevantes = await self._elegir_ficheros(peticion, indice)
        traza.append(TraceEvent(
            agent=self.name, step="explorar",
            detail={"ficheros_indice": len(indice.splitlines()),
                    "elegidos": ", ".join(relevantes[:6])},
        ))

        contexto = []
        for ruta in relevantes[:MAX_FICHEROS_CONTEXTO]:
            contenido = repo.leer(ruta)
            if contenido is not None:
                contexto.append(f"=== {ruta} ===\n{contenido}")

        # --- 2. Escribir el cambio ----------------------------------------
        sistema = PROMPT.format(max_ficheros=diffs.MAX_FICHEROS)
        usuario = (
            f"PETICION: {peticion}\n\n"
            f"INDICE DEL REPOSITORIO:\n{indice}\n\n"
            f"FICHEROS RELEVANTES:\n\n" + "\n\n".join(contexto)
        )
        t0 = time.perf_counter()
        try:
            completion = await self._provider.complete([
                ChatTurn(role="system", content=sistema),
                ChatTurn(role="user", content=usuario),
            ])
        except Exception as exc:  # noqa: BLE001
            log.warning('smith.fallo', paso='generar', error=str(exc)[:400])
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")

        cambios, motivo = diffs.parsear_respuesta(completion.text)
        if not cambios:
            log.warning('smith.fallo', paso='parsear',
                        respuesta=completion.text[:600])
        traza.append(TraceEvent(
            agent=self.name, step="escribir",
            detail={"ficheros": len(cambios), "modelo": completion.model},
            duration_ms=int((time.perf_counter() - t0) * 1000),
        ))
        if not cambios:
            return AgentResponse.failure("No consegui escribir un cambio valido")

        # --- 3. Construir el parche ---------------------------------------
        partes = []
        for cambio in cambios:
            original = repo.leer(cambio.ruta)
            trozo = diffs.construir_diff(original, cambio.contenido, cambio.ruta)
            if trozo:
                partes.append(trozo)
        parche = "".join(partes)
        if not parche.strip():
            log.warning('smith.fallo', paso='diff',
                        rutas=', '.join(c.ruta for c in cambios))
            return AgentResponse.failure("El cambio propuesto no modifica nada")

        rama = diffs.nombre_rama(peticion)

        # --- 4. Ensayarlo aislado -----------------------------------------
        try:
            forge = self._registry.find("forge.ensayar")
        except KeyError:
            return AgentResponse.failure(
                "El banco de pruebas no esta activo. Sin ensayar no se crean propuestas."
            )

        ensayo = await forge.handle(AgentRequest(
            capability="forge.ensayar",
            actor_id=request.actor_id,
            payload={"rama": rama, "parche": parche},
        ))
        traza += ensayo.trace
        if not ensayo.ok:
            return AgentResponse.failure(f"El ensayo no pudo ejecutarse: {ensayo.error}")

        verde = bool(ensayo.data.get("ok"))
        salida = "\n\n".join(
            f"[{p['paso']}] {'OK' if p['ok'] else 'FALLA'}\n{p['salida']}"
            for p in ensayo.data.get("pasos", [])
        )

        # --- 5. Dejar la propuesta ----------------------------------------
        riesgo = "alto" if not verde else self._riesgo_por_rutas(cambios)
        propuesta = await store.crear(
            db,
            owner_id=request.actor_id,
            titulo=peticion[:200],
            motivo=motivo or "Sin motivo declarado por el modelo.",
            diff=ensayo.data.get("diff") or parche,
            rama=rama,
            riesgo=riesgo,
            tests="VERDE\n\n" + salida if verde else "ROJO\n\n" + salida,
        )

        log.info("smith.propuesta", rama=rama, verde=verde, ficheros=len(cambios))
        return AgentResponse(
            ok=True,
            data={
                "propuesta_id": str(propuesta.id),
                "rama": rama,
                "tests_verdes": verde,
                "ficheros": [c.ruta for c in cambios],
                "riesgo": riesgo,
            },
            trace=traza + [TraceEvent(
                agent=self.name, step="proponer",
                detail={"rama": rama, "tests": "verde" if verde else "rojo", "riesgo": riesgo},
                duration_ms=int((time.perf_counter() - started) * 1000),
            )],
        )

    async def _elegir_ficheros(self, peticion: str, indice: str) -> list[str]:
        """Pregunta al modelo que ficheros necesita ver.

        Meter el repositorio entero en el contexto es caro y empeora el
        resultado: el modelo se pierde. Dos pasadas —una para elegir, otra
        para escribir— dan mejores parches y salen mas baratas.
        """
        try:
            respuesta = await self._provider.complete([
                ChatTurn(role="system", content=(
                    "Te dan un indice de ficheros y una peticion de cambio. "
                    "Devuelve SOLO un array JSON con las rutas que hay que leer "
                    "para escribir ese cambio, maximo 8, las mas relevantes "
                    "primero. Incluye siempre el fichero de tests que "
                    "correspondera al cambio. Nada de texto alrededor."
                )),
                ChatTurn(role="user", content=f"PETICION: {peticion}\n\nINDICE:\n{indice}"),
            ])
        except Exception:  # noqa: BLE001
            return []

        import json
        texto = respuesta.text
        i, j = texto.find("["), texto.rfind("]")
        if i == -1 or j == -1:
            return []
        try:
            rutas = json.loads(texto[i : j + 1])
        except json.JSONDecodeError:
            return []
        return [str(r).strip().lstrip("/") for r in rutas if isinstance(r, str)][:8]

    @staticmethod
    def _riesgo_por_rutas(cambios: list[diffs.Cambio]) -> str:
        """El riesgo lo decide la ruta, no el modelo.

        Un modelo que se autoevalua el riesgo tiende a decir "bajo". Las rutas
        sensibles estan aqui, en codigo, y no se negocian.
        """
        sensibles = ("auth/", "db/models.py", "agents/smith/", "agents/forge/",
                     "bridge.py", "docker-compose.yml")
        for cambio in cambios:
            if any(s in cambio.ruta for s in sensibles):
                return "alto"
        if any(not c.ruta.startswith("apps/core/tests/") for c in cambios):
            return "medio"
        return "bajo"

    async def health(self) -> dict[str, Any]:
        ficheros = len(repo.listar())
        return {
            "agent": self.name,
            "status": "ok" if ficheros else "sin repositorio",
            "ficheros_visibles": ficheros,
        }

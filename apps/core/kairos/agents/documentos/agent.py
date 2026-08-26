"""Documents Agent — los apuntes de Diego, indexados.

Que resuelve: KAIROS resuelve fisica en general. Con esto responde con TU
temario: los apuntes de tu profesor, el libro de tu curso, la notacion que
usais en clase.

COMO SE INDEXA, y por que asi:

**Se trocea por parrafos, no por caracteres.** Cortar cada 500 caracteres
parte frases y conceptos por la mitad, y un trozo que empieza a media
explicacion no sirve para nada al recuperarlo. Se agrupan parrafos hasta
llegar al tamano objetivo, y se corta en el limite de parrafo mas cercano.

**Cada trozo lleva el titulo del documento delante.** Al recuperarlo suelto,
"la energia cinetica es 1/2mv2" sin contexto podria venir de cualquier sitio;
con "Fisica 1BACH - Tema 3" delante, KAIROS sabe de que asignatura habla.

**Solapamiento entre trozos.** Un concepto que cae justo en la frontera
aparece en los dos trozos vecinos, asi que se recupera igual venga la
pregunta por donde venga.

SEPARADO DE LA MEMORIA PERSONAL a proposito. La memoria son cosas sobre
Diego; esto son documentos. Mezclarlas haria que un apunte de historia
compitiera con "a Diego le gusta el heavy metal" al buscar, y las dos cosas
saldrian peor.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.reasoning.providers.base import LLMProvider
from kairos.db.models import Document, DocumentChunk
from kairos.logging import get_logger

log = get_logger("kairos.documentos")

# Tamano objetivo de cada trozo, en caracteres. ~250 palabras: suficiente para
# un concepto completo, poco para llenar el contexto con paja.
OBJETIVO = 1400
SOLAPE = 250
MAX_TROZOS = 600
MIN_SIMILITUD = 0.35


def trocear(texto: str, titulo: str) -> list[str]:
    """Parte el texto en trozos que respetan los limites de parrafo."""
    parrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    if not parrafos:
        parrafos = [t.strip() for t in texto.split("\n") if t.strip()]

    trozos: list[str] = []
    actual = ""
    for parrafo in parrafos:
        # Un parrafo mas largo que el objetivo va solo, partido por frases.
        if len(parrafo) > OBJETIVO * 1.6:
            if actual:
                trozos.append(actual)
                actual = ""
            frases = parrafo.replace(". ", ".\n").split("\n")
            bloque = ""
            for frase in frases:
                if len(bloque) + len(frase) > OBJETIVO and bloque:
                    trozos.append(bloque.strip())
                    bloque = bloque[-SOLAPE:] if len(bloque) > SOLAPE else ""
                bloque += frase + " "
            if bloque.strip():
                trozos.append(bloque.strip())
            continue

        if len(actual) + len(parrafo) > OBJETIVO and actual:
            trozos.append(actual.strip())
            # El solape arrastra el final del trozo anterior: un concepto en
            # la frontera aparece en los dos y se recupera igual.
            actual = actual[-SOLAPE:] if len(actual) > SOLAPE else ""
        actual += parrafo + "\n\n"

    if actual.strip():
        trozos.append(actual.strip())

    # El titulo va en cada trozo: recuperado suelto, hace falta para saber de
    # que asignatura o documento viene.
    return [f"[{titulo}]\n{t}" for t in trozos[:MAX_TROZOS]]


class DocumentosAgent(Agent):
    name = "documentos"
    capabilities = frozenset({
        "documentos.indexar", "documentos.buscar", "documentos.listar",
        "documentos.borrar",
    })

    def __init__(self, embedder: LLMProvider) -> None:
        self._embedder = embedder

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        cap = request.capability
        if cap == "documentos.indexar":
            return await self._indexar(db, request)
        if cap == "documentos.buscar":
            return await self._buscar(db, request)
        if cap == "documentos.listar":
            return await self._listar(db, request)
        if cap == "documentos.borrar":
            return await self._borrar(db, request)
        return AgentResponse.failure(f"Capacidad no soportada: {cap}")

    async def _indexar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        titulo = (request.payload.get("titulo") or "").strip()[:200]
        texto = (request.payload.get("texto") or "").strip()
        materia = (request.payload.get("materia") or "").strip()[:80]
        if not titulo or len(texto) < 100:
            return AgentResponse.failure("Hace falta titulo y algo de texto")

        started = time.perf_counter()
        doc = Document(
            owner_id=request.actor_id, title=titulo, subject=materia,
            chars=len(texto),
        )
        db.add(doc)
        await db.flush()

        trozos = trocear(texto, f"{materia} · {titulo}" if materia else titulo)
        for i, trozo in enumerate(trozos):
            vector = await self._embedder.embed(trozo)
            db.add(DocumentChunk(
                document_id=doc.id, owner_id=request.actor_id,
                position=i, content=trozo, embedding=vector,
            ))

        doc.chunks = len(trozos)
        await db.commit()
        await db.refresh(doc)

        log.info("documentos.indexado", titulo=titulo, trozos=len(trozos))
        return AgentResponse(
            ok=True,
            data={"id": str(doc.id), "titulo": titulo, "trozos": len(trozos)},
            trace=[TraceEvent(
                agent=self.name, step="indexar",
                detail={"titulo": titulo, "trozos": len(trozos), "caracteres": len(texto)},
                duration_ms=int((time.perf_counter() - started) * 1000))],
        )

    async def _buscar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        consulta = (request.payload.get("consulta") or "").strip()
        if not consulta:
            return AgentResponse.failure("Consulta vacia")
        limite = int(request.payload.get("limite", 5))
        minimo = float(request.payload.get("min_similitud", MIN_SIMILITUD))

        started = time.perf_counter()
        vector = await self._embedder.embed(consulta)

        filas = (
            await db.execute(
                select(
                    DocumentChunk.content,
                    Document.title,
                    Document.subject,
                    (1 - DocumentChunk.embedding.cosine_distance(vector)).label("sim"),
                )
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(DocumentChunk.owner_id == request.actor_id)
                .order_by(DocumentChunk.embedding.cosine_distance(vector))
                .limit(limite)
            )
        ).all()

        hits = [
            {
                "contenido": f.content,
                "documento": f.title,
                "materia": f.subject,
                "similitud": round(float(f.sim), 3),
            }
            for f in filas
            if float(f.sim) >= minimo
        ]
        return AgentResponse(
            ok=True, data={"hits": hits},
            trace=[TraceEvent(
                agent=self.name, step="buscar",
                detail={"consulta": consulta[:80], "encontrados": len(hits)},
                duration_ms=int((time.perf_counter() - started) * 1000))],
        )

    async def _listar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        filas = (
            await db.execute(
                select(Document)
                .where(Document.owner_id == request.actor_id)
                .order_by(Document.created_at.desc())
                .limit(50)
            )
        ).scalars().all()
        return AgentResponse(ok=True, data={"documentos": [
            {
                "id": str(f.id), "titulo": f.title, "materia": f.subject,
                "trozos": f.chunks, "caracteres": f.chars,
                "created_at": f.created_at.isoformat(),
            }
            for f in filas
        ]})

    async def _borrar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        try:
            doc_id = uuid.UUID(str(request.payload.get("id")))
        except (TypeError, ValueError):
            return AgentResponse.failure("Identificador invalido")

        doc = (
            await db.execute(
                select(Document).where(
                    Document.id == doc_id, Document.owner_id == request.actor_id
                )
            )
        ).scalar_one_or_none()
        if doc is None:
            return AgentResponse.failure("No existe")

        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc_id))
        await db.delete(doc)
        await db.commit()
        return AgentResponse(ok=True, data={"borrado": str(doc_id)})

    async def health(self) -> dict[str, Any]:
        return {"agent": self.name, "status": "ok"}

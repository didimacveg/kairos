"""Tests de integracion de la memoria contra Postgres REAL.

Por que hacen falta: los tests con dobles verifican que el codigo hace lo que
dice su firma, no que KAIROS funcione. Y esa distincion es critica ahora que
KAIROS va a proponerse parches: `make test-todo` sera lo unico que separe un
cambio bueno de uno que rompe el sistema.

NOTA SOBRE EL AMBITO DE LAS FIXTURES: todo es de ambito FUNCION, a proposito.
Una fixture de modulo compartiria la conexion asyncpg entre tests que corren
en bucles de eventos distintos, y asyncpg lo rechaza con "another operation is
in progress". Crear una base por test cuesta menos de un segundo y elimina la
clase entera de fallos.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from kairos.agents.base import AgentRequest
from kairos.agents.memory.agent import MemoryAgent
from kairos.config import get_settings
from kairos.db.bootstrap import APPEND_ONLY_GUARD, MEMORY_CURATION_2B
from kairos.db.models import AuditLog, Base, MemoryItem, User
from tests.conftest import FakeProvider


def _url(nombre: str) -> str:
    s = get_settings()
    return (
        f"postgresql+asyncpg://{s.postgres_user}:{s.postgres_password}"
        f"@{s.postgres_host}:{s.postgres_port}/{nombre}"
    )


@pytest_asyncio.fixture
async def engine():
    """Base efimera propia de cada test. Nunca toca los datos reales."""
    nombre = f"kairos_test_{uuid.uuid4().hex[:10]}"
    admin = create_async_engine(
        _url(get_settings().postgres_db), isolation_level="AUTOCOMMIT"
    )
    async with admin.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{nombre}"'))
    await admin.dispose()

    motor = create_async_engine(_url(nombre))
    async with motor.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        for sentencia in APPEND_ONLY_GUARD + MEMORY_CURATION_2B:
            await conn.exec_driver_sql(sentencia)

    try:
        yield motor
    finally:
        await motor.dispose()
        admin = create_async_engine(
            _url(get_settings().postgres_db), isolation_level="AUTOCOMMIT"
        )
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        await admin.dispose()


@pytest_asyncio.fixture
async def db(engine):
    async with async_sessionmaker(engine, expire_on_commit=False)() as sesion:
        yield sesion


@pytest_asyncio.fixture
async def owner(db):
    usuario = User(username=f"u{uuid.uuid4().hex[:6]}", password_hash="x", role="owner")
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)
    return usuario


def _agente() -> MemoryAgent:
    return MemoryAgent(embedder=FakeProvider())


async def _guardar(agente, db, owner, texto, subject=""):
    vector = await agente._embedder.embed(texto)
    item = MemoryItem(
        owner_id=owner.id, kind="semantic", subject=subject, source="test",
        content=texto, embedding=vector, meta={},
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


# --------------------------------------------------------------- recuperacion

async def test_pgvector_recupera_lo_mas_parecido(db, owner) -> None:
    """El operador de coseno funciona de verdad, no solo en el doble."""
    agente = _agente()
    await _guardar(agente, db, owner, "Diego vive en Madrid")
    await _guardar(agente, db, owner, "A Diego le gusta el heavy metal")

    r = await agente.handle(
        AgentRequest(
            capability="memory.retrieve", actor_id=owner.id,
            payload={"query": "Diego vive en Madrid", "min_similarity": 0.5},
        ),
        db=db,
    )
    assert r.ok, r.error
    assert r.data["hits"], "no recupero nada con una consulta identica"
    assert "Madrid" in r.data["hits"][0]["content"]


async def test_la_memoria_de_otro_usuario_no_se_recupera(db, owner) -> None:
    agente = _agente()
    otro = User(username=f"o{uuid.uuid4().hex[:6]}", password_hash="x", role="owner")
    db.add(otro)
    await db.commit()
    await db.refresh(otro)

    await _guardar(agente, db, otro, "secreto del otro usuario")

    r = await agente.handle(
        AgentRequest(
            capability="memory.retrieve", actor_id=owner.id,
            payload={"query": "secreto del otro usuario", "min_similarity": 0.1},
        ),
        db=db,
    )
    assert r.ok
    assert r.data["hits"] == []


async def test_los_recuerdos_retirados_no_se_recuperan(db, owner) -> None:
    agente = _agente()
    item = await _guardar(agente, db, owner, "dato que se retira")
    item.status = "discarded"
    await db.commit()

    r = await agente.handle(
        AgentRequest(
            capability="memory.retrieve", actor_id=owner.id,
            payload={"query": "dato que se retira", "min_similarity": 0.1},
        ),
        db=db,
    )
    assert r.data["hits"] == []


# ------------------------------------------------------------------ auditoria

async def test_la_auditoria_es_realmente_append_only(engine, db, owner) -> None:
    """El trigger de Postgres, no la convencion del codigo.

    Se usa una conexion NUEVA para el UPDATE: la sesion ya tiene transaccion
    abierta y asyncpg no permite anidar otra encima.
    """
    fila = AuditLog(actor_id=owner.id, action="test", outcome="success", detail={})
    db.add(fila)
    await db.commit()

    for sentencia in (
        "UPDATE audit_log SET outcome='cambiado' WHERE action='test'",
        "DELETE FROM audit_log WHERE action='test'",
    ):
        with pytest.raises(Exception):
            async with engine.begin() as conn:
                await conn.exec_driver_sql(sentencia)

    # La fila sigue ahi, intacta.
    async with engine.connect() as conn:
        filas = (
            await conn.exec_driver_sql(
                "SELECT outcome FROM audit_log WHERE action='test'"
            )
        ).fetchall()
    assert [f[0] for f in filas] == ["success"]


# ------------------------------------------------------------------- esquema

async def test_el_esquema_tiene_las_columnas_de_curado(engine) -> None:
    """Si una migracion se pierde, esto lo detecta antes que el usuario."""
    async with engine.connect() as conn:
        filas = (
            await conn.exec_driver_sql(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='memory_items'"
            )
        ).fetchall()
    columnas = {f[0] for f in filas}
    for columna in ("status", "subject", "superseded_by", "superseded_at", "embedding"):
        assert columna in columnas, f"falta la columna {columna}"


async def test_el_indice_vectorial_existe(engine) -> None:
    async with engine.connect() as conn:
        filas = (
            await conn.exec_driver_sql(
                "SELECT indexname FROM pg_indexes WHERE tablename='memory_items'"
            )
        ).fetchall()
    nombres = {f[0] for f in filas}
    assert any("embedding" in i for i in nombres), "sin indice vectorial la busqueda no escala"

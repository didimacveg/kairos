"""Tests del Memory Agent que no requieren Postgres.

La recuperacion real (operador de coseno de pgvector) se prueba en la suite de
integracion, que si necesita base de datos. Aqui verificamos el contrato: que
el agente no lanza excepciones y que produce trazas.
"""
from __future__ import annotations

from kairos.agents.base import AgentRequest
from kairos.agents.memory.agent import MemoryAgent
from tests.conftest import FakeProvider


async def test_missing_db_returns_failure_not_exception(fake_provider: FakeProvider) -> None:
    agent = MemoryAgent(fake_provider)
    result = await agent.handle(
        AgentRequest(capability="memory.retrieve", payload={"query": "hola"})
    )
    assert not result.ok
    assert "base de datos" in (result.error or "")


async def test_embedding_dimension_matches_schema(fake_provider: FakeProvider) -> None:
    from kairos.db.models import EMBEDDING_DIM

    vector = await fake_provider.embed("texto de prueba")
    assert len(vector) == EMBEDDING_DIM


async def test_capabilities_are_declared(fake_provider: FakeProvider) -> None:
    agent = MemoryAgent(fake_provider)
    assert agent.supports("memory.store")
    assert agent.supports("memory.retrieve")
    assert not agent.supports("reasoning.respond")

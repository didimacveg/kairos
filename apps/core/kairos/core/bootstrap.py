"""Composicion de la instancia: quien se instancia y con que.

Todo el cableado del sistema esta aqui. Si quieres saber que compone KAIROS,
este es el unico fichero que hay que leer.
"""
from __future__ import annotations

from kairos.agents.memory.agent import MemoryAgent
from kairos.agents.memory.extractor import FactExtractor
from kairos.agents.reasoning.agent import ReasoningAgent
from kairos.agents.reasoning.providers.ollama import OllamaProvider
from kairos.agents.registry import AgentRegistry
from kairos.core.orchestrator import KairosCore


def build_core() -> KairosCore:
    provider = OllamaProvider()
    registry = AgentRegistry()
    registry.register(MemoryAgent(embedder=provider, extractor=FactExtractor(provider)))
    registry.register(ReasoningAgent(provider=provider))
    return KairosCore(registry)

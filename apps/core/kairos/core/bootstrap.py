"""Composicion de la instancia: quien se instancia y con que.

Todo el cableado del sistema esta aqui. Si quieres saber que compone KAIROS,
este es el unico fichero que hay que leer.
"""
from __future__ import annotations

from kairos.agents.memory.agent import MemoryAgent
from kairos.agents.memory.extractor import FactExtractor
from kairos.agents.reasoning.agent import ReasoningAgent
from kairos.agents.reasoning.providers.base import LLMProvider
from kairos.agents.reasoning.providers.failover import FailoverProvider
from kairos.agents.reasoning.providers.ollama import OllamaProvider
from kairos.agents.registry import AgentRegistry
from kairos.agents.search.agent import SearchAgent
from kairos.agents.voice.agent import VoiceAgent
from kairos.config import get_settings
from kairos.core.orchestrator import KairosCore
from kairos.logging import get_logger

log = get_logger("kairos.bootstrap")


def build_provider() -> LLMProvider:
    """Elige el proveedor de razonamiento.

    Reglas, en orden:
      - Sin `allow_egress`, siempre local. Tener clave no basta.
      - En modo `local`, siempre local aunque haya clave y egress.
      - Si hay clave y egress, remoto CON CAIDA a local: si Internet falla,
        KAIROS sigue respondiendo. La regla fundacional sigue en pie.

    Los embeddings se calculan SIEMPRE en local: la memoria semantica es el
    dato mas sensible del sistema y no viaja bajo ninguna configuracion.
    """
    settings = get_settings()
    local = OllamaProvider()

    if settings.provider_mode == "local":
        log.info("provider.selected", mode="local", reason="configurado")
        return local
    if not settings.allow_egress:
        log.info("provider.selected", mode="local", reason="egress desactivado")
        return local
    if not settings.anthropic_api_key:
        log.info("provider.selected", mode="local", reason="sin clave")
        return local

    from kairos.agents.reasoning.providers.anthropic import AnthropicProvider

    remote = AnthropicProvider(api_key=settings.anthropic_api_key)
    log.info("provider.selected", mode="cloud", model=settings.cloud_model, fallback="ollama")
    return FailoverProvider(preferred=remote, fallback=local)


def build_core() -> KairosCore:
    settings = get_settings()
    provider = build_provider()
    embedder = OllamaProvider()

    registry = AgentRegistry()
    registry.register(MemoryAgent(embedder=embedder, extractor=FactExtractor(embedder)))
    registry.register(ReasoningAgent(provider=provider))
    registry.register(VoiceAgent())
    if settings.search_enabled:
        registry.register(SearchAgent())
    return KairosCore(registry)

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
from kairos.agents.rutinas.agent import RutinasAgent
from kairos.agents.smith.agent import SmithAgent
from kairos.agents.tareas.agent import TareasAgent
from kairos.agents.warden.agent import WardenAgent
from kairos.agents.search.agent import SearchAgent
from kairos.agents.agenda.agent import AgendaAgent
from kairos.agents.briefing.agent import BriefingAgent
from kairos.agents.consciencia.agent import ConscienciaAgent
from kairos.agents.curiosidad.agent import CuriosidadAgent
from kairos.agents.device.agent import DeviceAgent
from kairos.agents.documentos.agent import DocumentosAgent
from kairos.agents.forge.agent import ForgeAgent
from kairos.agents.google.agent import GoogleAgent
from kairos.agents.intent.agent import IntentAgent
from kairos.agents.voice.agent import VoiceAgent
from kairos.agents.watch.agent import WatchAgent
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
    registry.register(GoogleAgent())
    registry.register(DocumentosAgent(embedder=embedder))
    registry.register(WatchAgent(registry=registry))
    registry.register(IntentAgent(provider=provider))
    registry.register(AgendaAgent(provider=provider, registry=registry))
    registry.register(CuriosidadAgent(provider=provider, registry=registry))
    registry.register(TareasAgent(provider=provider, registry=registry))
    registry.register(RutinasAgent(registry=registry))
    registry.register(ConscienciaAgent(provider=provider, registry=registry))
    registry.register(BriefingAgent(provider=provider, registry=registry))
    if settings.search_enabled:
        registry.register(SearchAgent())
    # El puente es opt-in: sin token declarado, el agente ni se registra.
    # Control del escritorio no es algo que deba activarse por descuido.
    if settings.bridge_enabled and settings.bridge_token:
        registry.register(DeviceAgent())
    # Doble opt-in, igual que el puente: ejecutar codigo propuesto no es algo
    # que deba activarse por descuido.
    if settings.forge_enabled and settings.forge_token:
        registry.register(ForgeAgent())
    # Smith exige el forge: sin banco de pruebas no se crean propuestas, punto.
    # Un parche sin ensayar no es una propuesta, es una apuesta.
    if settings.smith_enabled and settings.forge_enabled and settings.forge_token:
        registry.register(SmithAgent(provider=provider, registry=registry))
    # El aplicador es lo unico que escribe en el repositorio. Opt-in aparte
    # de Smith: puedes querer propuestas sin querer que se apliquen solas.
    if settings.warden_enabled and settings.warden_token:
        registry.register(WardenAgent())
    elif settings.bridge_enabled:
        # Fallar en silencio aqui cuesta caro: el chat responde "no puedo
        # hacer nada" y parece un problema del modelo, no de configuracion.
        log.warning("bridge.sin_token", detalle="KAIROS_BRIDGE_ENABLED=true pero falta KAIROS_BRIDGE_TOKEN")
    return KairosCore(registry)

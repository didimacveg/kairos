from __future__ import annotations

from kairos.agents.base import Agent


class AgentRegistry:
    """Directorio de agentes cargados en esta instancia.

    Sustituye a un service discovery. Cuando haya agentes remotos, el registro
    devolvera proxies que hablan por red en vez de instancias locales, y el
    resto del codigo no se entera.
    """

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"Agente duplicado: {agent.name}")
        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise KeyError(f"Agente no registrado: {name}") from exc

    def find(self, capability: str) -> Agent:
        for agent in self._agents.values():
            if agent.supports(capability):
                return agent
        raise KeyError(f"Ninguna agente expone la capacidad: {capability}")

    @property
    def names(self) -> list[str]:
        return sorted(self._agents)

    def all(self) -> list[Agent]:
        return [self._agents[n] for n in self.names]

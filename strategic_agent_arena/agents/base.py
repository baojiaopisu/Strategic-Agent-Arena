"""Base agent interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from strategic_agent_arena.envs.supply_graph_war.actions import Action
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv


class BaseAgent(ABC):
    """Minimal agent interface."""

    def __init__(self, name: str | None = None) -> None:
        self.name = name or self.__class__.__name__

    @abstractmethod
    def select_action(self, env: SupplyGraphWarEnv, player: int) -> Action:
        """Return one legal action for player."""


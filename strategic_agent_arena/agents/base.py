"""Base agent interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from strategic_agent_arena.envs.supply_graph_war.actions import Action
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv


class BaseAgent(ABC):
    """Minimal agent interface."""

    def __init__(self, name: str | None = None) -> None:
        self.name = name or self.__class__.__name__

    @abstractmethod
    def select_action(self, env: SupplyGraphWarEnv, player: int) -> Action:
        """Return one legal action for player."""

    def on_game_start(self, env: SupplyGraphWarEnv, player: int) -> None:
        """Hook called before the first action of a game."""

    def on_game_end(
        self,
        env: SupplyGraphWarEnv,
        player: int,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Hook called after a game finishes or is aborted."""

    def close(self) -> None:
        """Release resources held by the agent."""

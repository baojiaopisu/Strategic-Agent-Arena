"""Random baseline agent."""

from __future__ import annotations

from strategic_agent_arena.agents.base import BaseAgent
from strategic_agent_arena.envs.supply_graph_war.actions import Action
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv


class RandomAgent(BaseAgent):
    """Uniformly samples one legal action using the environment RNG."""

    def select_action(self, env: SupplyGraphWarEnv, player: int) -> Action:
        actions = env.legal_actions(player)
        index = int(env.rng.integers(0, len(actions)))
        return actions[index]


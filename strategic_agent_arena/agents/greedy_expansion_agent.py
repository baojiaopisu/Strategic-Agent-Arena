"""Greedy expansion baseline agent."""

from __future__ import annotations

import math

import numpy as np

from strategic_agent_arena.agents.base import BaseAgent
from strategic_agent_arena.envs.supply_graph_war.actions import Action, ActionKind
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv
from strategic_agent_arena.envs.supply_graph_war.rules import (
    NEUTRAL,
    UNSUPPLIED_ATTACK_MULTIPLIER,
    calculate_sent_units,
    enemy,
)


class GreedyExpansionAgent(BaseAgent):
    """Simple deterministic baseline that expands before consolidating."""

    def select_action(self, env: SupplyGraphWarEnv, player: int) -> Action:
        actions = env.legal_actions(player)
        units_after_production = env._units_after_pending_production()

        neutral_captures = [
            action
            for action in actions
            if action.kind == ActionKind.MOVE_ATTACK
            and env.state is not None
            and env.state.owners[int(action.target)] == NEUTRAL
            and self._captures(env, player, action, units_after_production)
        ]
        if neutral_captures:
            return max(
                neutral_captures,
                key=lambda action: self._neutral_key(env, action, units_after_production),
            )

        enemy_attacks = [
            action
            for action in actions
            if action.kind == ActionKind.MOVE_ATTACK
            and env.state is not None
            and env.state.owners[int(action.target)] == enemy(player)
        ]
        if enemy_attacks:
            return max(
                enemy_attacks,
                key=lambda action: self._enemy_attack_key(
                    env,
                    player,
                    action,
                    units_after_production,
                ),
            )

        upgrades = [action for action in actions if action.kind == ActionKind.UPGRADE]
        if upgrades:
            return max(upgrades, key=lambda action: self._upgrade_key(env, player, action))

        fortifies = [action for action in actions if action.kind == ActionKind.FORTIFY]
        if fortifies:
            return max(fortifies, key=lambda action: self._fortify_key(env, player, action))

        return Action.pass_turn()

    @staticmethod
    def _captures(env: SupplyGraphWarEnv, player: int, action: Action, units: np.ndarray) -> bool:
        state = env.state
        assert state is not None
        target = int(action.target)
        if state.owners[target] == player:
            return False

        source = int(action.source)
        attack_power = calculate_sent_units(int(units[source]), float(action.ratio))
        if not state.supplied[player, source]:
            attack_power = math.floor(attack_power * UNSUPPLIED_ATTACK_MULTIPLIER)

        defense_power = int(units[target] + 2 * state.defense[target])
        return attack_power > defense_power

    @staticmethod
    def _neutral_key(
        env: SupplyGraphWarEnv,
        action: Action,
        units: np.ndarray,
    ) -> tuple[int, int, int, int]:
        state = env.state
        assert state is not None
        target = int(action.target)
        source = int(action.source)
        sent = calculate_sent_units(int(units[source]), float(action.ratio))
        defense_power = int(state.units[target] + 2 * state.defense[target])
        return (int(state.production[target]), -defense_power, -sent, -target)

    @staticmethod
    def _enemy_attack_key(
        env: SupplyGraphWarEnv,
        player: int,
        action: Action,
        units: np.ndarray,
    ) -> tuple[int, int, int, int, int]:
        state = env.state
        assert state is not None
        target = int(action.target)
        source = int(action.source)
        sent = calculate_sent_units(int(units[source]), float(action.ratio))
        defense_power = int(state.units[target] + 2 * state.defense[target])
        captures = GreedyExpansionAgent._captures(env, player, action, units)
        is_base = target == state.bases[enemy(player)]
        return (int(captures), int(is_base), int(state.production[target]), -defense_power, sent)

    @staticmethod
    def _upgrade_key(env: SupplyGraphWarEnv, player: int, action: Action) -> tuple[int, int, int]:
        state = env.state
        assert state is not None
        source = int(action.source)
        is_base = source == state.bases[player]
        return (int(is_base), int(state.production[source]), int(state.units[source]))

    @staticmethod
    def _fortify_key(env: SupplyGraphWarEnv, player: int, action: Action) -> tuple[int, int, int]:
        state = env.state
        assert state is not None
        source = int(action.source)
        enemy_neighbors = sum(1 for node in state.graph.neighbors(source) if state.owners[node] == enemy(player))
        is_base = source == state.bases[player]
        return (int(is_base), enemy_neighbors, int(state.units[source]))

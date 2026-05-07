"""Core rules for Supply Graph War."""

from __future__ import annotations

import math

import networkx as nx
import numpy as np

from strategic_agent_arena.envs.supply_graph_war.actions import VALID_RATIOS
from strategic_agent_arena.envs.supply_graph_war.state import SupplyGraphWarState

NEUTRAL = -1
PLAYER_IDS: tuple[int, int] = (0, 1)
MAX_DEFENSE = 2
MAX_PRODUCTION = 3
BASE_PRODUCTION_BONUS = 2
UNSUPPLIED_ATTACK_MULTIPLIER = 0.75


def enemy(player: int) -> int:
    if player not in PLAYER_IDS:
        raise ValueError(f"invalid player: {player}")
    return 1 - player


def initiative_order(round_index: int) -> tuple[int, int]:
    return (0, 1) if round_index % 2 == 1 else (1, 0)


def current_player_for_turn(round_index: int, turn_index: int) -> int:
    if turn_index not in (0, 1):
        raise ValueError(f"invalid turn index: {turn_index}")
    return initiative_order(round_index)[turn_index]


def compute_supply(graph: nx.Graph, owners: np.ndarray, bases: tuple[int, int]) -> np.ndarray:
    """Return a bool array shaped (2, n_nodes), true for supplied player nodes."""

    supplied = np.zeros((2, int(owners.shape[0])), dtype=bool)
    for player in PLAYER_IDS:
        base = bases[player]
        if owners[base] != player:
            continue

        stack = [base]
        supplied[player, base] = True
        while stack:
            node = stack.pop()
            for neighbor in graph.neighbors(node):
                if owners[neighbor] == player and not supplied[player, neighbor]:
                    supplied[player, neighbor] = True
                    stack.append(neighbor)

    return supplied


def calculate_sent_units(available_units: int, ratio: float) -> int:
    """Calculate units sent by MOVE_ATTACK while leaving one unit behind."""

    ratio = normalize_ratio(ratio)
    if available_units <= 1:
        return 0
    sent = max(1, math.floor(available_units * ratio))
    return min(sent, available_units - 1)


def normalize_ratio(ratio: float) -> float:
    for valid_ratio in VALID_RATIOS:
        if math.isclose(ratio, valid_ratio):
            return valid_ratio
    raise ValueError(f"invalid ratio: {ratio}")


def apply_production(state: SupplyGraphWarState) -> None:
    """Apply simultaneous production to all supplied nodes."""

    for player in PLAYER_IDS:
        for node in np.flatnonzero(state.owners == player):
            if not state.supplied[player, node]:
                continue
            amount = int(state.production[node])
            if node == state.bases[player]:
                amount += BASE_PRODUCTION_BONUS
            state.units[node] += amount


def score_state(state: SupplyGraphWarState, player: int) -> int:
    """Compute the current score for a player."""

    supplied = compute_supply(state.graph, state.owners, state.bases)
    owned = state.owners == player
    owned_nodes = int(np.count_nonzero(owned))
    supplied_nodes = int(np.count_nonzero(supplied[player] & owned))
    total_production = int(np.sum(state.production[owned]))
    total_units = int(np.sum(state.units[owned]))
    return 10 * owned_nodes + 5 * supplied_nodes + 3 * total_production + total_units

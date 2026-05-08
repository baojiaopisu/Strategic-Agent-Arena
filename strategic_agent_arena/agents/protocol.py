"""JSON-serializable agent protocol helpers."""

from __future__ import annotations

from typing import Any

from strategic_agent_arena.envs.supply_graph_war.actions import Action
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv
from strategic_agent_arena.envs.supply_graph_war.rules import compute_supply

PROTOCOL_VERSION = "saa-jsonl-v1"


def serialize_action(index: int, action: Action) -> dict[str, Any]:
    return {
        "index": index,
        "kind": action.kind.value,
        "source": action.source,
        "target": action.target,
        "ratio": action.ratio,
        "label": str(action),
    }


def serialize_observation(
    env: SupplyGraphWarEnv,
    player: int,
    request_id: str,
    legal_actions: list[Action] | None = None,
) -> dict[str, Any]:
    state = env.state
    if state is None:
        raise RuntimeError("environment has not been reset")

    actions = legal_actions if legal_actions is not None else env.legal_actions(player)
    supplied = compute_supply(state.graph, state.owners, state.bases)
    available_units = env._units_after_pending_production()

    nodes = []
    for node in range(state.n_nodes):
        owner = int(state.owners[node])
        nodes.append(
            {
                "id": node,
                "owner": owner,
                "units": int(state.units[node]),
                "available_units": int(available_units[node]),
                "production": int(state.production[node]),
                "defense": int(state.defense[node]),
                "supplied": bool(owner in (0, 1) and supplied[owner, node]),
                "base_player": _base_player(node, state.bases),
                "x": env.map_positions.get(node, (0.0, 0.0))[0],
                "y": env.map_positions.get(node, (0.0, 0.0))[1],
            }
        )

    return {
        "type": "act",
        "protocol": PROTOCOL_VERSION,
        "request_id": request_id,
        "game": {
            "map_id": env.map_id,
            "map_name": env.map_name,
            "round_index": state.round_index,
            "turn_index": state.turn_index,
            "current_player": env.current_player,
            "player_id": player,
            "first_player": state.first_player,
            "max_rounds": env.max_rounds,
            "terminal": env.is_terminal(),
            "production_pending": env._production_pending,
        },
        "scores": {
            "0": env.score(0),
            "1": env.score(1),
        },
        "graph": {
            "nodes": nodes,
            "edges": [
                [int(source), int(target)] for source, target in sorted(state.graph.edges())
            ],
            "bases": {
                "0": int(state.bases[0]),
                "1": int(state.bases[1]),
            },
        },
        "legal_actions": [
            serialize_action(index, action) for index, action in enumerate(actions)
        ],
    }


def _base_player(node: int, bases: tuple[int, int]) -> int | None:
    if node == bases[0]:
        return 0
    if node == bases[1]:
        return 1
    return None

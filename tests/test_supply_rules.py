from __future__ import annotations

import networkx as nx
import numpy as np

from strategic_agent_arena.envs.supply_graph_war.rules import apply_production, compute_supply
from strategic_agent_arena.envs.supply_graph_war.state import SupplyGraphWarState


def test_supply_connectivity_correctness() -> None:
    graph = nx.path_graph(4)
    owners = np.array([0, -1, 0, 1])
    supplied = compute_supply(graph, owners, bases=(0, 3))

    assert supplied[0, 0]
    assert not supplied[0, 2]
    assert supplied[1, 3]

    owners[1] = 0
    supplied = compute_supply(graph, owners, bases=(0, 3))

    assert supplied[0, 2]


def test_production_only_applies_to_supplied_nodes() -> None:
    graph = nx.path_graph(4)
    owners = np.array([0, -1, 0, 1])
    units = np.array([1, 1, 1, 1])
    production = np.array([1, 2, 3, 1])
    defense = np.zeros(4, dtype=int)
    supplied = compute_supply(graph, owners, bases=(0, 3))
    state = SupplyGraphWarState(
        graph=graph,
        owners=owners,
        units=units,
        production=production,
        defense=defense,
        bases=(0, 3),
        supplied=supplied,
    )

    apply_production(state)

    assert state.units[0] == 4
    assert state.units[2] == 1
    assert state.units[3] == 4


def test_combat_captures_node_correctly() -> None:
    from strategic_agent_arena.envs.supply_graph_war.actions import Action
    from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv

    graph = nx.Graph()
    graph.add_edges_from([(0, 1), (1, 2)])
    owners = np.array([0, -1, 1])
    units = np.array([8, 1, 10])
    production = np.ones(3, dtype=int)
    defense = np.zeros(3, dtype=int)

    env = SupplyGraphWarEnv(max_rounds=10)
    env.state = SupplyGraphWarState(
        graph=graph,
        owners=owners,
        units=units,
        production=production,
        defense=defense,
        bases=(0, 2),
        supplied=compute_supply(graph, owners, bases=(0, 2)),
        round_index=1,
        turn_index=0,
    )
    env._production_pending = False

    env.step(Action.move_attack(0, 1, 1.0))

    assert env.state is not None
    assert env.state.owners[1] == 0
    assert env.state.units[0] == 1
    assert env.state.units[1] == 6


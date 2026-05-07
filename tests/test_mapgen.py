from __future__ import annotations

import math

import networkx as nx
import numpy as np
import pytest

from strategic_agent_arena.envs.supply_graph_war.mapgen import available_maps, generate_map
from strategic_agent_arena.envs.supply_graph_war.maps import FIXED_MAPS


def test_fixed_map_library_contains_expected_maps() -> None:
    assert [map_info.id for map_info in available_maps()] == [
        "twin_pass",
        "island_ring",
        "trident_front",
    ]


def test_fixed_maps_are_connected_and_fully_specified() -> None:
    for map_info in available_maps():
        spec = generate_map(map_id=map_info.id)

        assert nx.is_connected(spec.graph)
        assert spec.graph.number_of_nodes() == map_info.node_count
        assert spec.bases[0] != spec.bases[1]
        assert spec.owners[spec.bases[0]] == 0
        assert spec.owners[spec.bases[1]] == 1
        assert spec.units[spec.bases[0]] == 10
        assert spec.units[spec.bases[1]] == 10
        assert len(spec.positions) == spec.node_count
        assert len(spec.mirror) == spec.node_count
        assert np.all((1 <= spec.production) & (spec.production <= 3))
        assert np.all((0 <= spec.units) & (spec.units <= 10))
        assert np.all((0 <= spec.units[spec.owners == -1]) & (spec.units[spec.owners == -1] <= 3))
        assert np.all((0 <= spec.defense) & (spec.defense <= 2))
        for x, y in spec.positions.values():
            assert 0 <= x <= 1
            assert 0 <= y <= 1


def test_fixed_maps_are_structurally_symmetric() -> None:
    for map_def in FIXED_MAPS.values():
        spec = generate_map(map_id=map_def.id)
        edge_set = {_edge(source, target) for source, target in spec.graph.edges()}
        base_0, base_1 = spec.bases

        assert spec.mirror[base_0] == base_1
        assert spec.mirror[base_1] == base_0

        lengths_from_base_0 = nx.shortest_path_length(spec.graph, source=base_0)
        lengths_from_base_1 = nx.shortest_path_length(spec.graph, source=base_1)

        for node, mirror in spec.mirror.items():
            assert spec.mirror[mirror] == node
            assert spec.production[node] == spec.production[mirror]
            assert spec.units[node] == spec.units[mirror]
            assert spec.defense[node] == spec.defense[mirror]
            assert lengths_from_base_0[node] == lengths_from_base_1[mirror]

            x, y = spec.positions[node]
            mirror_x, mirror_y = spec.positions[mirror]
            assert math.isclose(x, 1.0 - mirror_x)
            assert math.isclose(y, mirror_y)

        for source, target in edge_set:
            assert _edge(spec.mirror[source], spec.mirror[target]) in edge_set


def test_unknown_fixed_map_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown map_id"):
        generate_map(map_id="random_sparse")


def _edge(source: int, target: int) -> tuple[int, int]:
    return (source, target) if source < target else (target, source)

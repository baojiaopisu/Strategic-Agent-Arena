"""Fixed map loading for Supply Graph War."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import numpy as np

from strategic_agent_arena.envs.supply_graph_war.maps import (
    DEFAULT_MAP_ID,
    FixedMapDefinition,
    MapMetadata,
    get_fixed_map,
    list_map_metadata,
)
from strategic_agent_arena.envs.supply_graph_war.rules import NEUTRAL


@dataclass(frozen=True, slots=True)
class MapSpec:
    graph: nx.Graph
    bases: tuple[int, int]
    owners: np.ndarray
    units: np.ndarray
    production: np.ndarray
    defense: np.ndarray
    map_id: str
    map_name: str
    description: str
    positions: dict[int, tuple[float, float]]
    mirror: dict[int, int]

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()


def available_maps() -> list[MapMetadata]:
    return list_map_metadata()


def generate_map(map_id: str = DEFAULT_MAP_ID) -> MapSpec:
    """Load one fixed map by id."""

    return _from_definition(get_fixed_map(map_id))


def _from_definition(map_def: FixedMapDefinition) -> MapSpec:
    graph = nx.Graph()
    graph.add_nodes_from(range(map_def.node_count))
    graph.add_edges_from(map_def.edges)

    owners = np.full(map_def.node_count, NEUTRAL, dtype=int)
    owners[map_def.bases[0]] = 0
    owners[map_def.bases[1]] = 1

    return MapSpec(
        graph=graph,
        bases=map_def.bases,
        owners=owners,
        units=np.array(map_def.units, dtype=int),
        production=np.array(map_def.production, dtype=int),
        defense=np.array(map_def.defense, dtype=int),
        map_id=map_def.id,
        map_name=map_def.name,
        description=map_def.description,
        positions={node: position for node, position in enumerate(map_def.positions)},
        mirror={node: mirror for node, mirror in enumerate(map_def.mirror)},
    )

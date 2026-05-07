"""State container for Supply Graph War."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import numpy as np


@dataclass(slots=True)
class SupplyGraphWarState:
    """Mutable game state.

    Node ids are expected to be contiguous integers in [0, n_nodes).
    """

    graph: nx.Graph
    owners: np.ndarray
    units: np.ndarray
    production: np.ndarray
    defense: np.ndarray
    bases: tuple[int, int]
    supplied: np.ndarray
    round_index: int = 1
    turn_index: int = 0

    @property
    def n_nodes(self) -> int:
        return int(self.owners.shape[0])

    def clone(self) -> "SupplyGraphWarState":
        return SupplyGraphWarState(
            graph=self.graph.copy(),
            owners=self.owners.copy(),
            units=self.units.copy(),
            production=self.production.copy(),
            defense=self.defense.copy(),
            bases=self.bases,
            supplied=self.supplied.copy(),
            round_index=self.round_index,
            turn_index=self.turn_index,
        )


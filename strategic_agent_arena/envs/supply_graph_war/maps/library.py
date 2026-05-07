"""Original fixed maps for Supply Graph War."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAP_ID = "twin_pass"


@dataclass(frozen=True, slots=True)
class MapMetadata:
    id: str
    name: str
    description: str
    node_count: int


@dataclass(frozen=True, slots=True)
class FixedMapDefinition:
    id: str
    name: str
    description: str
    bases: tuple[int, int]
    edges: tuple[tuple[int, int], ...]
    production: tuple[int, ...]
    units: tuple[int, ...]
    defense: tuple[int, ...]
    positions: tuple[tuple[float, float], ...]
    mirror: tuple[int, ...]

    @property
    def node_count(self) -> int:
        return len(self.production)

    def metadata(self) -> MapMetadata:
        return MapMetadata(
            id=self.id,
            name=self.name,
            description=self.description,
            node_count=self.node_count,
        )


def get_fixed_map(map_id: str) -> FixedMapDefinition:
    try:
        return FIXED_MAPS[map_id]
    except KeyError as exc:
        raise ValueError(f"unknown map_id: {map_id}") from exc


def list_map_metadata() -> list[MapMetadata]:
    return [map_def.metadata() for map_def in FIXED_MAPS.values()]


def _mirror_positions(
    left_positions: dict[int, tuple[float, float]],
    center: tuple[int, ...],
) -> dict[int, tuple[float, float]]:
    positions = dict(left_positions)
    node_count = max(left_positions) * 2 + 1 if center else (max(left_positions) + 1) * 2
    for node, (x, y) in left_positions.items():
        mirror = node_count - 1 - node
        positions[mirror] = (1.0 - x, y)
    for node in center:
        positions[node] = (0.5, left_positions[node][1])
    return positions


def _mirror_edges(left_edges: tuple[tuple[int, int], ...], node_count: int) -> set[tuple[int, int]]:
    edges: set[tuple[int, int]] = set()
    for u, v in left_edges:
        edges.add(_edge(u, v))
        edges.add(_edge(node_count - 1 - u, node_count - 1 - v))
    return edges


def _edge(u: int, v: int) -> tuple[int, int]:
    return (u, v) if u < v else (v, u)


def _values_from_pairs(
    node_count: int,
    left_values: dict[int, int],
    center_values: dict[int, int],
) -> tuple[int, ...]:
    values = [0] * node_count
    for node, value in left_values.items():
        values[node] = value
        values[node_count - 1 - node] = value
    for node, value in center_values.items():
        values[node] = value
    return tuple(values)


def _positions_tuple(
    node_count: int,
    positions: dict[int, tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
    return tuple(positions[node] for node in range(node_count))


def _mirror_tuple(node_count: int) -> tuple[int, ...]:
    return tuple(node_count - 1 - node for node in range(node_count))


def _twin_pass() -> FixedMapDefinition:
    node_count = 21
    left_edges = (
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 2),
        (2, 3),
        (1, 4),
        (2, 5),
        (3, 6),
        (4, 5),
        (5, 6),
        (4, 7),
        (5, 9),
        (6, 8),
        (7, 9),
        (8, 9),
        (7, 10),
        (8, 10),
        (9, 10),
    )
    edges = _mirror_edges(left_edges, node_count)
    left_positions = {
        0: (0.08, 0.50),
        1: (0.18, 0.32),
        2: (0.20, 0.50),
        3: (0.18, 0.68),
        4: (0.32, 0.22),
        5: (0.34, 0.50),
        6: (0.32, 0.78),
        7: (0.45, 0.32),
        8: (0.45, 0.68),
        9: (0.42, 0.50),
        10: (0.50, 0.50),
    }
    positions = _mirror_positions(left_positions, center=(10,))
    production = _values_from_pairs(
        node_count,
        {0: 2, 1: 1, 2: 2, 3: 1, 4: 2, 5: 3, 6: 2, 7: 2, 8: 2, 9: 2},
        {10: 3},
    )
    units = _values_from_pairs(
        node_count,
        {0: 10, 1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 1, 8: 1, 9: 2},
        {10: 3},
    )
    defense = _values_from_pairs(
        node_count,
        {node: 0 for node in range(10)},
        {10: 1},
    )
    return FixedMapDefinition(
        id="twin_pass",
        name="Twin Pass",
        description="A compact mirrored map with two side passes and a contested central city.",
        bases=(0, 20),
        edges=tuple(sorted(edges)),
        production=production,
        units=units,
        defense=defense,
        positions=_positions_tuple(node_count, positions),
        mirror=_mirror_tuple(node_count),
    )


def _island_ring() -> FixedMapDefinition:
    node_count = 23
    left_edges = (
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 2),
        (2, 3),
        (1, 4),
        (1, 5),
        (2, 5),
        (2, 6),
        (3, 6),
        (3, 7),
        (4, 5),
        (5, 6),
        (6, 7),
        (4, 8),
        (5, 8),
        (5, 9),
        (6, 9),
        (6, 10),
        (7, 10),
        (8, 9),
        (9, 10),
        (8, 11),
        (9, 11),
        (10, 11),
    )
    edges = _mirror_edges(left_edges, node_count)
    left_positions = {
        0: (0.07, 0.52),
        1: (0.18, 0.30),
        2: (0.20, 0.52),
        3: (0.18, 0.74),
        4: (0.32, 0.18),
        5: (0.33, 0.40),
        6: (0.33, 0.64),
        7: (0.32, 0.86),
        8: (0.45, 0.33),
        9: (0.43, 0.52),
        10: (0.45, 0.72),
        11: (0.50, 0.52),
    }
    positions = _mirror_positions(left_positions, center=(11,))
    production = _values_from_pairs(
        node_count,
        {
            0: 2,
            1: 1,
            2: 2,
            3: 1,
            4: 2,
            5: 2,
            6: 2,
            7: 2,
            8: 3,
            9: 2,
            10: 3,
        },
        {11: 3},
    )
    units = _values_from_pairs(
        node_count,
        {
            0: 10,
            1: 1,
            2: 1,
            3: 1,
            4: 2,
            5: 1,
            6: 1,
            7: 2,
            8: 2,
            9: 1,
            10: 2,
        },
        {11: 3},
    )
    defense = _values_from_pairs(
        node_count,
        {node: 0 for node in range(11)},
        {11: 1},
    )
    return FixedMapDefinition(
        id="island_ring",
        name="Island Ring",
        description="A medium mirrored map with regional loops around a central high-value island.",
        bases=(0, 22),
        edges=tuple(sorted(edges)),
        production=production,
        units=units,
        defense=defense,
        positions=_positions_tuple(node_count, positions),
        mirror=_mirror_tuple(node_count),
    )


def _trident_front() -> FixedMapDefinition:
    node_count = 27
    left_edges = (
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 2),
        (2, 3),
        (1, 4),
        (1, 5),
        (2, 5),
        (2, 6),
        (3, 7),
        (3, 8),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 8),
        (4, 9),
        (5, 9),
        (5, 12),
        (6, 10),
        (7, 11),
        (8, 11),
        (9, 12),
        (12, 10),
        (10, 11),
        (9, 13),
        (12, 13),
        (10, 13),
        (11, 13),
    )
    edges = _mirror_edges(left_edges, node_count)
    edges.update({_edge(9, 17), _edge(11, 15), _edge(12, 14), _edge(13, 14)})
    left_positions = {
        0: (0.06, 0.50),
        1: (0.16, 0.25),
        2: (0.18, 0.50),
        3: (0.16, 0.75),
        4: (0.30, 0.16),
        5: (0.31, 0.36),
        6: (0.33, 0.50),
        7: (0.31, 0.64),
        8: (0.30, 0.84),
        9: (0.44, 0.20),
        10: (0.43, 0.50),
        11: (0.44, 0.80),
        12: (0.46, 0.36),
        13: (0.50, 0.50),
    }
    positions = _mirror_positions(left_positions, center=(13,))
    production = _values_from_pairs(
        node_count,
        {
            0: 2,
            1: 1,
            2: 2,
            3: 1,
            4: 2,
            5: 2,
            6: 1,
            7: 2,
            8: 2,
            9: 2,
            10: 3,
            11: 2,
            12: 1,
        },
        {13: 3},
    )
    units = _values_from_pairs(
        node_count,
        {
            0: 10,
            1: 1,
            2: 1,
            3: 1,
            4: 2,
            5: 1,
            6: 2,
            7: 1,
            8: 2,
            9: 2,
            10: 2,
            11: 2,
            12: 0,
        },
        {13: 3},
    )
    defense = _values_from_pairs(
        node_count,
        {node: 0 for node in range(13)},
        {13: 1},
    )
    return FixedMapDefinition(
        id="trident_front",
        name="Trident Front",
        description="A larger mirrored map with north, center, and south fronts around a neutral fort.",
        bases=(0, 26),
        edges=tuple(sorted(edges)),
        production=production,
        units=units,
        defense=defense,
        positions=_positions_tuple(node_count, positions),
        mirror=_mirror_tuple(node_count),
    )


FIXED_MAPS: dict[str, FixedMapDefinition] = {
    map_def.id: map_def
    for map_def in (
        _twin_pass(),
        _island_ring(),
        _trident_front(),
    )
}

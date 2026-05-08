#!/usr/bin/env python3
"""Run a small Supply Graph War tournament."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategic_agent_arena.agents import available_agent_specs, make_agent
from strategic_agent_arena.envs.supply_graph_war.mapgen import available_maps
from strategic_agent_arena.evaluation import run_tournament


def main() -> None:
    agents = {spec.name: make_agent(spec.id) for spec in available_agent_specs()}
    result = run_tournament(
        agents,
        seeds=[1, 2, 3],
        map_ids=[map_info.id for map_info in available_maps()],
        max_rounds=80,
    )

    names = result["agents"]
    print("Win-rate matrix (row agent vs column agent)")
    print("agent".ljust(18) + "".join(name[:16].rjust(18) for name in names))
    for row in names:
        cells = []
        for col in names:
            value = result["win_rate_matrix"][row][col]
            cells.append("-".rjust(18) if value is None else f"{value:.2f}".rjust(18))
        print(row[:16].ljust(18) + "".join(cells))

    print("\nRecords")
    for row, opponents in result["records"].items():
        for col, record in opponents.items():
            print(
                f"{row} vs {col}: "
                f"{record['wins']}W-{record['losses']}L-{record['draws']}D "
                f"({record['games']} games)"
            )


if __name__ == "__main__":
    main()

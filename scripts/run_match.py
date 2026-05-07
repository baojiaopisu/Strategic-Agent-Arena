#!/usr/bin/env python3
"""Run a sample Supply Graph War match."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategic_agent_arena.agents import GreedyExpansionAgent, RandomAgent
from strategic_agent_arena.envs.supply_graph_war.mapgen import available_maps
from strategic_agent_arena.envs.supply_graph_war.maps import DEFAULT_MAP_ID
from strategic_agent_arena.evaluation import play_match


def main() -> None:
    map_choices = [map_info.id for map_info in available_maps()]
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--map-id", choices=map_choices, default=DEFAULT_MAP_ID)
    parser.add_argument("--max-rounds", type=int, default=80)
    args = parser.parse_args()

    result = play_match(
        RandomAgent(),
        GreedyExpansionAgent(),
        seed=args.seed,
        map_id=args.map_id,
        max_rounds=args.max_rounds,
    )

    print("RandomAgent (P0) vs GreedyExpansionAgent (P1)")
    print(f"seed={result.seed} map={result.map_name} ({result.map_id}) nodes={result.node_count}")
    print(f"winner={_winner_text(result.winner)} captured_base={result.captured_base}")
    print(f"scores: P0={result.scores[0]} P1={result.scores[1]} rounds={result.rounds}")
    print(
        "final: "
        f"owned P0={result.final_owned[0]} P1={result.final_owned[1]}, "
        f"supplied P0={result.final_supplied[0]} P1={result.final_supplied[1]}, "
        f"units P0={result.final_units[0]} P1={result.final_units[1]}"
    )
    print("actions:")
    shown = result.actions[:20]
    for item in shown:
        print(f"  r{item['round']:02d} P{item['player']}: {item['action']}")
    if len(result.actions) > len(shown):
        print(f"  ... {len(result.actions) - len(shown)} more actions")


def _winner_text(winner: int | None) -> str:
    return "draw" if winner is None else f"P{winner}"


if __name__ == "__main__":
    main()

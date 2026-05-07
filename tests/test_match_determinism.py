from __future__ import annotations

from strategic_agent_arena.agents import GreedyExpansionAgent, RandomAgent
from strategic_agent_arena.evaluation import play_match, side_swapped_match


def test_same_seed_produces_same_result() -> None:
    result_a = play_match(
        RandomAgent(),
        GreedyExpansionAgent(),
        seed=42,
        map_id="island_ring",
        max_rounds=20,
    )
    result_b = play_match(
        RandomAgent(),
        GreedyExpansionAgent(),
        seed=42,
        map_id="island_ring",
        max_rounds=20,
    )

    assert result_a.as_dict() == result_b.as_dict()


def test_side_swapped_match_runs_without_crashing() -> None:
    result = side_swapped_match(
        RandomAgent(),
        GreedyExpansionAgent(),
        seed=3,
        map_id="trident_front",
        max_rounds=10,
    )

    assert set(result) == {"agent_a_as_player_0", "agent_a_as_player_1"}
    assert result["agent_a_as_player_0"].rounds >= 1
    assert result["agent_a_as_player_1"].rounds >= 1

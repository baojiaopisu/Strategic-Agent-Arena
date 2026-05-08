"""Small tournament runner."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from strategic_agent_arena.agents.base import BaseAgent
from strategic_agent_arena.envs.supply_graph_war.maps import DEFAULT_MAP_ID
from strategic_agent_arena.evaluation.match import side_swapped_match


def run_tournament(
    agents: Mapping[str, BaseAgent] | Sequence[BaseAgent],
    seeds: Sequence[int],
    map_ids: Sequence[str] = (DEFAULT_MAP_ID,),
    max_rounds: int = 80,
    first_player: int = 0,
) -> dict:
    """Run a small side-swapped round robin tournament."""

    named_agents = _named_agents(agents)
    names = list(named_agents)
    records = {
        row: {
            col: {"wins": 0, "losses": 0, "draws": 0, "games": 0}
            for col in names
            if col != row
        }
        for row in names
    }

    for i, name_a in enumerate(names):
        for name_b in names[i + 1 :]:
            agent_a = named_agents[name_a]
            agent_b = named_agents[name_b]
            for seed in seeds:
                for map_id in map_ids:
                    pair = side_swapped_match(
                        agent_a,
                        agent_b,
                        seed=seed,
                        map_id=map_id,
                        max_rounds=max_rounds,
                        first_player=first_player,
                    )
                    _record_game(records, name_a, name_b, pair["agent_a_as_player_0"].winner, a_player=0)
                    _record_game(records, name_a, name_b, pair["agent_a_as_player_1"].winner, a_player=1)

    matrix = {
        row: {
            col: None if row == col else _win_rate(records[row][col])
            for col in names
        }
        for row in names
    }
    return {"agents": names, "records": records, "win_rate_matrix": matrix}


def _named_agents(agents: Mapping[str, BaseAgent] | Sequence[BaseAgent]) -> dict[str, BaseAgent]:
    if isinstance(agents, Mapping):
        return dict(agents)

    named: dict[str, BaseAgent] = {}
    for agent in agents:
        base_name = agent.name
        name = base_name
        suffix = 2
        while name in named:
            name = f"{base_name}_{suffix}"
            suffix += 1
        named[name] = agent
    return named


def _record_game(
    records: dict[str, dict[str, dict[str, int]]],
    name_a: str,
    name_b: str,
    winner: int | None,
    a_player: int,
) -> None:
    b_player = 1 - a_player
    records[name_a][name_b]["games"] += 1
    records[name_b][name_a]["games"] += 1

    if winner is None:
        records[name_a][name_b]["draws"] += 1
        records[name_b][name_a]["draws"] += 1
        return

    a_won = winner == a_player
    b_won = winner == b_player
    records[name_a][name_b]["wins"] += int(a_won)
    records[name_a][name_b]["losses"] += int(b_won)
    records[name_b][name_a]["wins"] += int(b_won)
    records[name_b][name_a]["losses"] += int(a_won)


def _win_rate(record: dict[str, int]) -> float:
    if record["games"] == 0:
        return 0.0
    return record["wins"] / record["games"]

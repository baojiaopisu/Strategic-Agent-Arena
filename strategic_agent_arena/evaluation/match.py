"""Match runners for Supply Graph War."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from strategic_agent_arena.agents.base import BaseAgent
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv
from strategic_agent_arena.envs.supply_graph_war.maps import DEFAULT_MAP_ID
from strategic_agent_arena.envs.supply_graph_war.rules import compute_supply


@dataclass(frozen=True, slots=True)
class MatchResult:
    winner: int | None
    scores: dict[int, int]
    rounds: int
    captured_base: bool
    final_owned: dict[int, int]
    final_supplied: dict[int, int]
    final_units: dict[int, int]
    seed: int
    map_id: str
    map_name: str
    node_count: int
    actions: list[dict[str, int | str]]

    def as_dict(self) -> dict:
        return asdict(self)


def play_match(
    agent_a: BaseAgent,
    agent_b: BaseAgent,
    seed: int,
    map_id: str = DEFAULT_MAP_ID,
    max_rounds: int = 80,
) -> MatchResult:
    """Play one match with agent_a as player 0 and agent_b as player 1."""

    env = SupplyGraphWarEnv(max_rounds=max_rounds).reset(
        seed=seed,
        map_id=map_id,
    )
    agents = (agent_a, agent_b)
    action_log: list[dict[str, int | str]] = []

    while not env.is_terminal():
        player = env.current_player
        action = agents[player].select_action(env, player)
        round_index = env.round_index
        env.step(action)
        action_log.append({"round": round_index, "player": player, "action": str(action)})

    state = env.state
    assert state is not None
    supplied = compute_supply(state.graph, state.owners, state.bases)
    final_owned = {player: int((state.owners == player).sum()) for player in (0, 1)}
    final_supplied = {
        player: int(((state.owners == player) & supplied[player]).sum()) for player in (0, 1)
    }
    final_units = {player: int(state.units[state.owners == player].sum()) for player in (0, 1)}

    return MatchResult(
        winner=env.winner(),
        scores={0: env.score(0), 1: env.score(1)},
        rounds=env.round_index,
        captured_base=env.captured_base,
        final_owned=final_owned,
        final_supplied=final_supplied,
        final_units=final_units,
        seed=seed,
        map_id=env.map_id,
        map_name=env.map_name,
        node_count=state.n_nodes,
        actions=action_log,
    )


def side_swapped_match(
    agent_a: BaseAgent,
    agent_b: BaseAgent,
    seed: int,
    map_id: str = DEFAULT_MAP_ID,
    max_rounds: int = 80,
) -> dict[str, MatchResult]:
    """Run two games with the same map setting and swapped sides."""

    return {
        "agent_a_as_player_0": play_match(
            agent_a,
            agent_b,
            seed=seed,
            map_id=map_id,
            max_rounds=max_rounds,
        ),
        "agent_a_as_player_1": play_match(
            agent_b,
            agent_a,
            seed=seed,
            map_id=map_id,
            max_rounds=max_rounds,
        ),
    }

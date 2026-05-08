from __future__ import annotations

from strategic_agent_arena.agents.protocol import PROTOCOL_VERSION, serialize_observation
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv


def test_serialize_observation_contains_state_and_legal_action_indices() -> None:
    env = SupplyGraphWarEnv().reset(seed=7, map_id="twin_pass", first_player=1)
    player = env.current_player
    legal_actions = env.legal_actions(player)

    observation = serialize_observation(env, player, "req-1", legal_actions)

    assert observation["type"] == "act"
    assert observation["protocol"] == PROTOCOL_VERSION
    assert observation["request_id"] == "req-1"
    assert observation["game"]["player_id"] == 1
    assert observation["game"]["first_player"] == 1
    assert observation["graph"]["bases"] == {"0": 0, "1": 20}
    assert len(observation["graph"]["nodes"]) == 21
    assert observation["graph"]["nodes"][20]["available_units"] >= 10
    assert [action["index"] for action in observation["legal_actions"]] == list(
        range(len(legal_actions))
    )
    assert observation["legal_actions"][-1]["kind"] == "PASS"

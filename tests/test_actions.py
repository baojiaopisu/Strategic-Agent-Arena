from __future__ import annotations

from strategic_agent_arena.envs.supply_graph_war.actions import ActionKind, VALID_RATIOS
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv


def test_legal_actions_only_generated_correctly() -> None:
    env = SupplyGraphWarEnv().reset(seed=1, map_id="twin_pass")
    player = env.current_player
    assert env.state is not None

    actions = env.legal_actions(player)

    assert any(action.kind == ActionKind.PASS for action in actions)
    for action in actions:
        if action.kind == ActionKind.MOVE_ATTACK:
            assert action.source is not None
            assert action.target is not None
            assert action.ratio in VALID_RATIOS
            assert env.state.owners[action.source] == player
            assert env.state.graph.has_edge(action.source, action.target)
        elif action.kind in {ActionKind.FORTIFY, ActionKind.UPGRADE}:
            assert action.source is not None
            assert env.state.owners[action.source] == player


def test_first_player_can_be_configured() -> None:
    env = SupplyGraphWarEnv().reset(seed=1, map_id="twin_pass", first_player=1)

    assert env.current_player == 1
    env.step(next(action for action in env.legal_actions(1) if action.kind == ActionKind.PASS))
    assert env.current_player == 0
    env.step(next(action for action in env.legal_actions(0) if action.kind == ActionKind.PASS))
    assert env.round_index == 2
    assert env.current_player == 0

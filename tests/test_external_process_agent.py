from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from strategic_agent_arena.agents.external_process_agent import ExternalProcessAgent
from strategic_agent_arena.envs.supply_graph_war.actions import ActionKind
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv
from strategic_agent_arena.evaluation import play_match


def test_external_process_agent_selects_valid_action(tmp_path: Path) -> None:
    script = _write_agent(
        tmp_path,
        """
        import json
        import sys

        for line in sys.stdin:
            message = json.loads(line)
            if message["type"] == "init":
                print(json.dumps({"type": "ready"}), flush=True)
            elif message["type"] == "act":
                print(json.dumps({
                    "type": "action",
                    "request_id": message["request_id"],
                    "action_index": 0,
                }), flush=True)
            elif message["type"] == "shutdown":
                break
        """,
    )
    env = SupplyGraphWarEnv().reset(seed=1, map_id="twin_pass")
    agent = ExternalProcessAgent(
        [sys.executable, str(script)],
        agent_id="test_external",
        timeout_ms=500,
    )

    try:
        agent.on_game_start(env, env.current_player)
        action = agent.select_action(env, env.current_player)
    finally:
        agent.close()

    assert action == env.legal_actions(env.current_player)[0]
    assert agent.diagnostics["fallbacks"] == 0


def test_external_process_agent_invalid_index_falls_back_to_pass(tmp_path: Path) -> None:
    script = _write_agent(
        tmp_path,
        """
        import json
        import sys

        for line in sys.stdin:
            message = json.loads(line)
            if message["type"] == "init":
                print(json.dumps({"type": "ready"}), flush=True)
            elif message["type"] == "act":
                print(json.dumps({
                    "type": "action",
                    "request_id": message["request_id"],
                    "action_index": 9999,
                }), flush=True)
            elif message["type"] == "shutdown":
                break
        """,
    )
    env = SupplyGraphWarEnv().reset(seed=1, map_id="twin_pass")
    agent = ExternalProcessAgent(
        [sys.executable, str(script)],
        agent_id="test_external_bad_index",
        timeout_ms=500,
    )

    try:
        action = agent.select_action(env, env.current_player)
    finally:
        agent.close()

    assert action.kind == ActionKind.PASS
    assert agent.diagnostics["fallbacks"] == 1
    assert agent.diagnostics["invalid_responses"] == 1


def test_external_process_agent_timeout_falls_back_to_pass(tmp_path: Path) -> None:
    script = _write_agent(
        tmp_path,
        """
        import json
        import sys
        import time

        for line in sys.stdin:
            message = json.loads(line)
            if message["type"] == "init":
                print(json.dumps({"type": "ready"}), flush=True)
            elif message["type"] == "act":
                time.sleep(1)
            elif message["type"] == "shutdown":
                break
        """,
    )
    env = SupplyGraphWarEnv().reset(seed=1, map_id="twin_pass")
    agent = ExternalProcessAgent(
        [sys.executable, str(script)],
        agent_id="test_external_timeout",
        timeout_ms=20,
    )

    try:
        action = agent.select_action(env, env.current_player)
    finally:
        agent.close()

    assert action.kind == ActionKind.PASS
    assert agent.diagnostics["fallbacks"] == 1
    assert agent.diagnostics["timeouts"] == 1


def test_external_process_agent_can_play_full_match(tmp_path: Path) -> None:
    script = _write_agent(
        tmp_path,
        """
        import json
        import sys

        for line in sys.stdin:
            message = json.loads(line)
            if message["type"] == "init":
                print(json.dumps({"type": "ready"}), flush=True)
            elif message["type"] == "act":
                action_index = message["legal_actions"][-1]["index"]
                print(json.dumps({
                    "type": "action",
                    "request_id": message["request_id"],
                    "action_index": action_index,
                }), flush=True)
            elif message["type"] == "shutdown":
                break
        """,
    )

    result = play_match(
        ExternalProcessAgent([sys.executable, str(script)], agent_id="pass_a", timeout_ms=500),
        ExternalProcessAgent([sys.executable, str(script)], agent_id="pass_b", timeout_ms=500),
        seed=2,
        map_id="twin_pass",
        max_rounds=3,
    )

    assert result.rounds == 3
    assert result.actions
    assert {item["action"] for item in result.actions} == {"PASS"}


def _write_agent(tmp_path: Path, source: str) -> Path:
    script = tmp_path / "agent.py"
    script.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return script

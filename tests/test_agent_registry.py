from __future__ import annotations

import json
from pathlib import Path

from strategic_agent_arena.agents.external_process_agent import ExternalProcessAgent
from strategic_agent_arena.agents.random_agent import RandomAgent
from strategic_agent_arena.agents.registry import available_agent_specs, load_external_agent_specs, make_agent


def test_registry_includes_builtins_when_manifest_missing(tmp_path: Path) -> None:
    specs = available_agent_specs(tmp_path / "missing.json")

    assert [spec.id for spec in specs] == ["random", "greedy_expansion"]
    assert isinstance(make_agent("random", tmp_path / "missing.json"), RandomAgent)


def test_registry_loads_enabled_external_agents(tmp_path: Path) -> None:
    manifest = tmp_path / "agents.json"
    manifest.write_text(
        json.dumps(
            {
                "agents": [
                    {
                        "id": "external_test",
                        "name": "External Test",
                        "kind": "external_process",
                        "command": ["python", "agent.py"],
                    },
                    {
                        "id": "disabled_test",
                        "name": "Disabled Test",
                        "kind": "external_process",
                        "enabled": False,
                        "command": ["python", "disabled.py"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    specs = available_agent_specs(manifest)
    external_specs = load_external_agent_specs(manifest)
    agent = make_agent("external_test", manifest)

    assert [spec.id for spec in specs] == ["random", "greedy_expansion", "external_test"]
    assert [spec.id for spec in external_specs] == ["external_test", "disabled_test"]
    assert isinstance(agent, ExternalProcessAgent)

"""Agent registry for built-in and manifest-declared agents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from strategic_agent_arena.agents.base import BaseAgent
from strategic_agent_arena.agents.external_process_agent import ExternalProcessAgent
from strategic_agent_arena.agents.greedy_expansion_agent import GreedyExpansionAgent
from strategic_agent_arena.agents.protocol import PROTOCOL_VERSION
from strategic_agent_arena.agents.random_agent import RandomAgent

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AGENT_MANIFEST = REPO_ROOT / "algos" / "agents.json"


@dataclass(frozen=True, slots=True)
class AgentSpec:
    id: str
    name: str
    kind: str
    enabled: bool = True
    command: tuple[str, ...] = ()
    protocol: str = PROTOCOL_VERSION
    timeout_ms: int = 200
    startup_timeout_ms: int = 1_000

    def as_info(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "enabled": self.enabled,
        }


BUILTIN_SPECS: tuple[AgentSpec, ...] = (
    AgentSpec(id="random", name="RandomAgent", kind="builtin"),
    AgentSpec(id="greedy_expansion", name="GreedyExpansionAgent", kind="builtin"),
)


def available_agent_specs(
    manifest_path: Path = DEFAULT_AGENT_MANIFEST,
    *,
    include_disabled: bool = False,
) -> list[AgentSpec]:
    specs = list(BUILTIN_SPECS) + load_external_agent_specs(manifest_path)
    if include_disabled:
        return specs
    return [spec for spec in specs if spec.enabled]


def load_external_agent_specs(manifest_path: Path = DEFAULT_AGENT_MANIFEST) -> list[AgentSpec]:
    if not manifest_path.exists():
        return []

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        agents = raw
    elif isinstance(raw, dict):
        agents = raw.get("agents", [])
    else:
        raise ValueError("agent manifest must be a list or contain an agents list")
    if not isinstance(agents, list):
        raise ValueError("agent manifest must be a list or contain an agents list")

    specs = []
    for item in agents:
        if not isinstance(item, dict):
            raise ValueError("agent manifest entries must be JSON objects")
        specs.append(_external_spec_from_dict(item))
    return specs


def make_agent(agent_id: str, manifest_path: Path = DEFAULT_AGENT_MANIFEST) -> BaseAgent:
    specs = {spec.id: spec for spec in available_agent_specs(manifest_path)}
    try:
        spec = specs[agent_id]
    except KeyError as exc:
        raise KeyError(f"unknown agent: {agent_id}") from exc

    if spec.kind == "builtin":
        if spec.id == "random":
            return RandomAgent()
        if spec.id == "greedy_expansion":
            return GreedyExpansionAgent()
        raise KeyError(f"unknown built-in agent: {spec.id}")

    if spec.kind == "external_process":
        return ExternalProcessAgent(
            spec.command,
            agent_id=spec.id,
            name=spec.name,
            protocol=spec.protocol,
            timeout_ms=spec.timeout_ms,
            startup_timeout_ms=spec.startup_timeout_ms,
            cwd=REPO_ROOT,
        )

    raise KeyError(f"unsupported agent kind: {spec.kind}")


def agent_infos(manifest_path: Path = DEFAULT_AGENT_MANIFEST) -> list[dict[str, Any]]:
    return [spec.as_info() for spec in available_agent_specs(manifest_path)]


def _external_spec_from_dict(item: dict[str, Any]) -> AgentSpec:
    kind = item.get("kind", "external_process")
    if kind != "external_process":
        raise ValueError(f"unsupported external agent kind: {kind}")

    command = item.get("command", [])
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        raise ValueError("external agent command must be a list of strings")

    return AgentSpec(
        id=_required_str(item, "id"),
        name=str(item.get("name") or item["id"]),
        kind=kind,
        enabled=bool(item.get("enabled", True)),
        command=tuple(command),
        protocol=str(item.get("protocol", PROTOCOL_VERSION)),
        timeout_ms=int(item.get("timeout_ms", 200)),
        startup_timeout_ms=int(item.get("startup_timeout_ms", 1_000)),
    )


def _required_str(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"agent manifest field {key!r} must be a non-empty string")
    return value

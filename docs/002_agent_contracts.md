# Agent Contracts

Strategic Agent Arena keeps the game simulator authoritative. Algorithms do not
mutate state directly. They receive observations and return a legal action
choice.

## Contract: `saa-jsonl-v1`

External agents are long-running executables. Python starts the process and
communicates with newline-delimited JSON over stdin/stdout.

Lifecycle:

1. Python sends `init`.
2. Agent replies with `ready`.
3. Python sends `game_start`.
4. Python sends one `act` request whenever the agent must move.
5. Agent replies with an `action` response.
6. Python sends `game_end`.
7. Python sends `shutdown` before closing the process.

Only `init` and `act` require replies.

## `act` Request

The request contains the complete public game state, scores, graph, bases, and
legal actions. Agents should select from `legal_actions` by index.

```json
{
  "type": "act",
  "protocol": "saa-jsonl-v1",
  "request_id": "cpp_agent-12",
  "game": {
    "map_id": "twin_pass",
    "map_name": "Twin Pass",
    "round_index": 4,
    "turn_index": 1,
    "current_player": 0,
    "player_id": 0,
    "first_player": 1,
    "max_rounds": 80,
    "terminal": false,
    "production_pending": false
  },
  "scores": {"0": 140, "1": 132},
  "graph": {
    "nodes": [
      {
        "id": 0,
        "owner": 0,
        "units": 12,
        "available_units": 12,
        "production": 2,
        "defense": 1,
        "supplied": true,
        "base_player": 0,
        "x": 0.05,
        "y": 0.5
      }
    ],
    "edges": [[0, 1], [1, 2]],
    "bases": {"0": 0, "1": 20}
  },
  "legal_actions": [
    {
      "index": 0,
      "kind": "MOVE_ATTACK",
      "source": 0,
      "target": 1,
      "ratio": 0.25,
      "label": "MOVE_ATTACK(0->1, ratio=0.25)"
    },
    {
      "index": 14,
      "kind": "PASS",
      "source": null,
      "target": null,
      "ratio": null,
      "label": "PASS"
    }
  ]
}
```

`available_units` includes pending production when the current action is the
first action of a round. `units` is the stored state before pending production is
applied.

## `action` Response

```json
{
  "type": "action",
  "request_id": "cpp_agent-12",
  "action_index": 0
}
```

The Python referee validates the index and applies the corresponding legal
action. If the process times out, crashes, returns invalid JSON, or chooses an
invalid index, the v1 fallback action is `PASS`.

## Agent Manifest

External agents are registered in `algos/agents.json`.

```json
{
  "agents": [
    {
      "id": "cpp_supply_cut_v1",
      "name": "SupplyCutBot C++ v1",
      "kind": "external_process",
      "enabled": true,
      "command": ["algos/cpp/build/supply_cut_v1"],
      "protocol": "saa-jsonl-v1",
      "timeout_ms": 200,
      "startup_timeout_ms": 1000
    }
  ]
}
```

Commands are executed from the repository root and are launched without a shell.
Do not run untrusted binaries.

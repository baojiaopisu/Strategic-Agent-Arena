# Strategic Agent Arena

Strategic Agent Arena is a personal AI lab for small, deterministic strategy games. The goal is to build environments where heuristic bots, search agents, self-play systems, and eventually neural-guided planners can compete under clear rules and low compute requirements.

The first environment is **Supply Graph War**, a 1v1 turn-based game played on a graph of cities. Players produce units, move through edges, attack cities, fortify positions, upgrade production, and manage supply lines back to their bases.

## What's Included

This repo currently contains a runnable MVP:

- Deterministic Python simulator for Supply Graph War
- Three fixed, fair map-library scenarios: `twin_pass`, `island_ring`, and `trident_front`
- `RandomAgent` and `GreedyExpansionAgent`
- Match, side-swapped match, and tournament runners
- Local browser UI for watching bot-vs-bot games
- Tests for core rules, actions, fixed map symmetry, determinism, and the web API

## Why This Is an AI Playground

Supply Graph War is intentionally small but strategically nontrivial:

- Graph topology matters.
- Local tactical choices can create global supply failures.
- The action space is discrete and easy to enumerate.
- Full state is inspectable, cloneable, and deterministic under a seed.
- Baselines can start simple, then be replaced with MCTS, heuristic search, imitation learning, and self-play RL.

## Quickstart

Install the project with development and web UI dependencies:

```bash
python3 -m pip install -e ".[dev,web]"
```

Run the tests:

```bash
python3 -m pytest
```

Run a single match:

```bash
python3 scripts/run_match.py
```

Run a small tournament:

```bash
python3 scripts/run_tournament.py
```

Run the local browser UI:

```bash
python3 scripts/run_web.py
```

Then open `http://127.0.0.1:8000`.

Example with a different map:

```bash
python3 scripts/run_match.py --map-id island_ring --seed 12
```

## Browser UI

The web UI is local-only and research-oriented. It is meant to make games visible while designing agents.

Current controls:

- choose one of the fixed maps and set seed/max rounds
- choose Player 0 and Player 1 agents
- reset the match
- step one action
- step one round
- autoplay with speed control
- inspect scores, ownership, supply, units, legal actions, and action log
- click a node to inspect owner, units, production, defense, supply, and base status

The backend is a small FastAPI app wrapping live in-memory `SupplyGraphWarEnv` sessions. There is no database or saved replay format yet.

## Current Limitations

- MCTS or search agents
- RL or neural policies
- Replay visualization
- Human-vs-bot play
- Persistent experiment tracking

## Basic Game Rules

Each node is a city with owner, units, production, and defense. Each player starts with one base and 10 units. Neutral nodes start with 0 to 3 units.

At the start of each round, supplied nodes produce units. A player-owned node is supplied if it has a path to that player's base using only that player's nodes. Unsupplied nodes do not produce and attack with a 25% penalty.

Each round alternates initiative:

- Round 1: Player 0, then Player 1
- Round 2: Player 1, then Player 0
- Round 3: Player 0, then Player 1

Actions:

- `MOVE_ATTACK(u, v, ratio)`: move to a friendly adjacent node or attack another adjacent node.
- `FORTIFY(u)`: increase defense up to 2.
- `UPGRADE(u)`: increase production up to 3 if supplied.
- `PASS`: do nothing.

A player wins immediately by capturing the enemy base. Otherwise, the game ends after `max_rounds`, and the higher score wins. Draws are allowed.

## Repository Layout

```text
strategic_agent_arena/
  envs/supply_graph_war/   # simulator, state, actions, rules, fixed maps
  agents/                  # baseline agent interface and bots
  evaluation/              # match and tournament runners
  web/                     # FastAPI app and static browser UI
scripts/                   # command-line entry points
tests/                     # simulator and web API tests
docs/                      # project vision and game design notes
```

## Roadmap

1. `MCTSBot`
2. `SupplyCutBot` and other graph heuristic bots
3. Human play in the browser UI
4. Replay export and visualization
5. Imitation learning from strong heuristic/search agents
6. Self-play RL
7. Neural-guided MCTS

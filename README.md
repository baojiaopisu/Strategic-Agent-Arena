# Strategic Agent Arena

Strategic Agent Arena is a personal AI lab for small, deterministic strategy games. The goal is to build environments where heuristic bots, search agents, self-play systems, and eventually neural-guided planners can compete under clear rules and low compute requirements.

The first environment is **Supply Graph War**, a 1v1 turn-based game played on a graph of cities. Players produce units, move through edges, attack cities, fortify positions, upgrade production, and manage supply lines back to their bases.

## What's Included

This repo currently contains a runnable MVP:

- Deterministic Python simulator for Supply Graph War
- Three fixed, fair map-library scenarios: `twin_pass`, `island_ring`, and `trident_front`
- Python reference `RandomAgent` and `GreedyExpansionAgent`
- Match, side-swapped match, and tournament runners
- Local React/FastAPI browser lab split into dashboard, play, batch analysis, and C++ development pages
- External-process agent contract for isolated C++ algorithms
- C++ ports of the Random and Greedy Expansion baseline agents
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

Run a match with explicit registered agents:

```bash
python3 scripts/run_match.py --agent0 random --agent1 greedy_expansion
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

Rebuild the React frontend after changing website source:

```bash
npm --prefix web/frontend install
npm --prefix web/frontend run build
```

Example with a different map:

```bash
python3 scripts/run_match.py --map-id island_ring --seed 12
```

Build the C++ agents for the browser UI:

```bash
cmake -S algos/cpp -B algos/cpp/build
cmake --build algos/cpp/build
```

## Browser UI

The web UI is local-only and research-oriented. It is meant to become a real
research lab for designing, debugging, and evaluating agents, not just a game
demo.

Pages:

- `/`: dashboard with maps, agents, and lab entry points.
- `/play`: watch one visible agent match, step actions/rounds, autoplay, and inspect the graph.
- `/analysis`: run many headless games and compare win rates, side bias, score deltas, and map breakdowns.
- `/develop`: edit whitelisted C++ `.cpp`/`.hpp` files in the browser with Monaco, save/build through CMake, inspect compiler/runtime logs, and run debug matches.

The backend is a small FastAPI app wrapping live in-memory `SupplyGraphWarEnv`
sessions. Batch analysis jobs are also in memory for now: refreshing the server
clears them.

The `/develop` page can write only to `algos/cpp/agents/*.cpp` and
`algos/cpp/include/*.hpp`. It does not expose arbitrary shell access.

## External Algorithms

C++ algorithms can be integrated as isolated executables through the `saa-jsonl-v1`
JSON Lines contract. Python remains the authoritative referee: it sends
observations and legal actions, the algorithm returns a legal action index, and
Python validates/applies the move.

External agents are registered in `algos/agents.json`. See
`docs/002_agent_contracts.md` for the protocol and `algos/cpp/` for the C++
baseline agents.

Build the C++ agents with:

```bash
cmake -S algos/cpp -B algos/cpp/build
cmake --build algos/cpp/build
```

The browser exposes C++ agents only. Python agents remain in the backend as
reference baselines and tests. The `cpp_mcts_v1` manifest entry stays disabled
for normal play/analysis while it is used by the `/develop` page.

## Current Limitations

- Completed MCTS/search agents
- RL or neural policies
- Replay visualization
- Human-vs-bot play
- Persistent experiment tracking

## Basic Game Rules

Each node is a city with owner, units, production, and defense. Each player starts with one base and 10 units. Neutral nodes start with 0 to 3 units.

At the start of each round, supplied nodes produce units. A player-owned node is supplied if it has a path to that player's base using only that player's nodes. Unsupplied nodes do not produce and attack with a 25% penalty.

Each round alternates initiative:

- Round 1: configured first player, then the opponent
- Round 2: the opponent, then the configured first player
- Round 3: configured first player, then the opponent

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
  agents/                  # baseline bots, registry, external process adapter
  evaluation/              # match and tournament runners
  web/                     # FastAPI app and built browser UI assets
algos/                     # external C++ agents and future Python/RL agents
web/frontend/              # React/TypeScript frontend source
scripts/                   # command-line entry points
tests/                     # simulator and web API tests
docs/                      # project vision and game design notes
```

## Roadmap

1. `MCTSBot`
2. `SupplyCutBot` and other graph heuristic bots
3. Browser IDE for C++ algorithm development
4. Human play in the browser UI
5. Replay export and visualization
6. Imitation learning from strong heuristic/search agents
7. Self-play RL
8. Neural-guided MCTS

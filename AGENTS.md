# Repository Guidelines

## Project Structure & Module Organization

`strategic_agent_arena/` contains the Python package. The main environment lives in
`envs/supply_graph_war/`, with state, actions, rules, fixed-map loading, and built-in map
libraries split into focused modules. Baseline agents are in `agents/`, match and
tournament orchestration is in `evaluation/`, and the local FastAPI browser UI is in
`web/` with static assets under `web/static/`. Command-line entry points are in
`scripts/`. Tests are in `tests/`, and design notes live in `docs/`. Avoid editing
generated metadata such as `strategic_agent_arena.egg-info/` or `__pycache__/`.

## Build, Test, and Development Commands

- `python3 -m pip install -e ".[dev,web]"`: install the package in editable mode with
  test, lint, and web dependencies.
- `python3 -m pytest`: run the full test suite configured in `pyproject.toml`.
- `python3 scripts/run_match.py --map-id island_ring --seed 12`: run a sample
  bot-vs-bot match.
- `python3 scripts/run_tournament.py`: run a small tournament between baseline agents.
- `python3 scripts/run_web.py`: start the local UI at `http://127.0.0.1:8000`.
- `python3 -m ruff check .`: lint Python code using the configured Ruff settings.

## Coding Style & Naming Conventions

Target Python 3.11+. Use 4-space indentation, type hints for public functions and
dataclasses, and `from __future__ import annotations` in Python modules. Keep lines at
or below 100 characters. Use `snake_case` for modules, functions, variables, and test
files; use `PascalCase` for classes such as `SupplyGraphWarEnv` and `RandomAgent`.
Prefer deterministic APIs that accept explicit seeds when adding simulation behavior.

## Testing Guidelines

The project uses `pytest` with `tests/` as the test root. Name tests
`test_<behavior>.py` and functions `test_<expected_behavior>()`. Cover rule changes,
legal action generation, map determinism, match determinism, and web API responses.
For web routes, follow the existing `fastapi.testclient.TestClient` pattern.

## Commit & Pull Request Guidelines

Git history is not available in this checkout. Use concise, imperative commit messages
such as `Add supply cutoff heuristic` or `Fix web session error handling`. Pull
requests should include a short behavior summary, tests run, linked issues or design
notes when relevant, and screenshots or screen recordings for UI changes.

## Agent-Specific Instructions

Keep changes narrowly scoped and consistent with the simulator's deterministic model.
Do not introduce persistent storage, external services, or non-deterministic behavior
without documenting the rationale and adding focused tests.

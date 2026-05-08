"""FastAPI app for the local Supply Graph War frontend."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from importlib.resources import files
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from strategic_agent_arena.agents import BaseAgent
from strategic_agent_arena.agents.registry import agent_infos, available_agent_specs, make_agent
from strategic_agent_arena.envs.supply_graph_war.actions import Action, ActionKind
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv
from strategic_agent_arena.envs.supply_graph_war.mapgen import available_maps
from strategic_agent_arena.envs.supply_graph_war.maps import DEFAULT_MAP_ID
from strategic_agent_arena.envs.supply_graph_war.rules import compute_supply

MAP_INFOS = tuple(available_maps())
MAP_IDS = tuple(map_info.id for map_info in MAP_INFOS)
MAP_NAMES = {map_info.id: map_info.name for map_info in MAP_INFOS}
MAX_BATCH_GAMES = 2_000


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict[str, Any]) -> Any:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


class SessionCreateRequest(BaseModel):
    seed: int | None = 7
    map_id: str = DEFAULT_MAP_ID
    max_rounds: int = Field(default=80, ge=1, le=500)
    first_player: int = Field(default=0, ge=0, le=1)
    player0_agent: str = "random"
    player1_agent: str = "greedy_expansion"


class BatchRunRequest(BaseModel):
    agent_a: str = "random"
    agent_b: str = "greedy_expansion"
    map_ids: list[str] = Field(default_factory=lambda: [DEFAULT_MAP_ID])
    seed_start: int = 1
    games_per_map: int = Field(default=50, ge=1, le=500)
    max_rounds: int = Field(default=80, ge=1, le=500)
    side_swap: bool = True
    initiative_mode: Literal["balanced", "p0", "p1"] = "balanced"


@dataclass(slots=True)
class WebSession:
    session_id: str
    env: SupplyGraphWarEnv
    agents: tuple[BaseAgent, BaseAgent]
    agent_ids: tuple[str, str]
    seed: int | None
    map_id: str
    map_name: str
    max_rounds: int
    first_player: int
    positions: dict[int, tuple[float, float]]
    action_log: list[dict[str, Any]] = field(default_factory=list)
    agents_closed: bool = False


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, WebSession] = {}

    def create(self, request: SessionCreateRequest) -> WebSession:
        _validate_request(request)
        env = SupplyGraphWarEnv(max_rounds=request.max_rounds).reset(
            seed=request.seed,
            map_id=request.map_id,
            first_player=request.first_player,
        )
        assert env.state is not None
        session = WebSession(
            session_id=str(uuid4()),
            env=env,
            agents=(
                _make_agent(request.player0_agent),
                _make_agent(request.player1_agent),
            ),
            agent_ids=(request.player0_agent, request.player1_agent),
            seed=request.seed,
            map_id=env.map_id,
            map_name=env.map_name,
            max_rounds=request.max_rounds,
            first_player=request.first_player,
            positions=dict(env.map_positions),
        )
        try:
            _start_agents(session)
        except Exception as exc:  # noqa: BLE001 - surface external agent startup failures.
            _end_agents(session)
            raise HTTPException(status_code=400, detail=f"agent startup failed: {exc}") from exc
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> WebSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc

    def step(self, session: WebSession) -> None:
        if session.env.is_terminal():
            return
        player = session.env.current_player
        agent = session.agents[player]
        action = agent.select_action(session.env, player)
        round_index = session.env.round_index
        session.env.step(action)
        session.action_log.append(
            {
                "index": len(session.action_log) + 1,
                "round": round_index,
                "player": player,
                "agent": session.agent_ids[player],
                "action": str(action),
                "structured_action": _serialize_action(action),
            }
        )
        if session.env.is_terminal():
            _end_agents(session)

    def step_round(self, session: WebSession) -> None:
        if session.env.is_terminal():
            return
        start_round = session.env.round_index
        while not session.env.is_terminal() and session.env.round_index == start_round:
            self.step(session)


def create_app() -> FastAPI:
    static_dir = files("strategic_agent_arena.web").joinpath("static")
    store = SessionStore()

    app = FastAPI(title="Strategic Agent Arena")
    app.state.sessions = store
    app.mount("/static", NoCacheStaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(
            str(static_dir.joinpath("index.html")),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/agents")
    def agents() -> dict[str, Any]:
        return {
            "agents": agent_infos(),
            "maps": [asdict(map_info) for map_info in MAP_INFOS],
        }

    @app.post("/api/sessions")
    def create_session(request: SessionCreateRequest) -> dict[str, Any]:
        return _serialize_session(store.create(request))

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        return _serialize_session(store.get(session_id))

    @app.post("/api/sessions/{session_id}/step")
    def step_session(session_id: str) -> dict[str, Any]:
        session = store.get(session_id)
        store.step(session)
        return _serialize_session(session)

    @app.post("/api/sessions/{session_id}/round")
    def step_round(session_id: str) -> dict[str, Any]:
        session = store.get(session_id)
        store.step_round(session)
        return _serialize_session(session)

    @app.post("/api/lab/batch")
    def run_batch(request: BatchRunRequest) -> dict[str, Any]:
        _validate_batch_request(request)
        return _run_batch(request)

    return app


app = create_app()


def _validate_request(request: SessionCreateRequest) -> None:
    if request.map_id not in MAP_IDS:
        raise HTTPException(status_code=400, detail=f"unknown map_id: {request.map_id}")
    for agent_id in (request.player0_agent, request.player1_agent):
        if agent_id not in _agent_ids():
            raise HTTPException(status_code=400, detail=f"unknown agent: {agent_id}")


def _validate_batch_request(request: BatchRunRequest) -> None:
    map_ids = _unique_map_ids(request.map_ids)
    if not map_ids:
        raise HTTPException(status_code=400, detail="at least one map_id is required")

    unknown_maps = [map_id for map_id in map_ids if map_id not in MAP_IDS]
    if unknown_maps:
        raise HTTPException(status_code=400, detail=f"unknown map_id: {unknown_maps[0]}")

    for agent_id in (request.agent_a, request.agent_b):
        if agent_id not in _agent_ids():
            raise HTTPException(status_code=400, detail=f"unknown agent: {agent_id}")

    total_games = (
        len(map_ids)
        * request.games_per_map
        * (2 if request.side_swap else 1)
        * len(_first_players_for_mode(request.initiative_mode))
    )
    if total_games > MAX_BATCH_GAMES:
        raise HTTPException(
            status_code=400,
            detail=f"batch too large: {total_games} games requested, max is {MAX_BATCH_GAMES}",
        )


def _make_agent(agent_id: str) -> BaseAgent:
    try:
        return make_agent(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _agent_ids() -> set[str]:
    return {spec.id for spec in available_agent_specs()}


def _run_batch(request: BatchRunRequest) -> dict[str, Any]:
    started = perf_counter()
    map_ids = _unique_map_ids(request.map_ids)
    total = _empty_batch_accumulator()
    by_map = {map_id: _empty_batch_accumulator() for map_id in map_ids}
    side_breakdown = {
        ("agent_a", 0): _empty_side_accumulator(),
        ("agent_a", 1): _empty_side_accumulator(),
        ("agent_b", 0): _empty_side_accumulator(),
        ("agent_b", 1): _empty_side_accumulator(),
    }
    games: list[dict[str, Any]] = []

    for map_id in map_ids:
        for seed in range(request.seed_start, request.seed_start + request.games_per_map):
            pairings = [0, 1] if request.side_swap else [0]
            for agent_a_player in pairings:
                player_agents = (
                    (request.agent_a, request.agent_b)
                    if agent_a_player == 0
                    else (request.agent_b, request.agent_a)
                )
                for first_player in _first_players_for_mode(request.initiative_mode):
                    raw = _play_lab_game(
                        player_agents=player_agents,
                        seed=seed,
                        map_id=map_id,
                        max_rounds=request.max_rounds,
                        first_player=first_player,
                    )
                    normalized = _normalize_lab_game(raw, agent_a_player, first_player)
                    games.append(normalized)
                    _record_batch_game(total, normalized)
                    _record_batch_game(by_map[map_id], normalized)
                    _record_side_game(
                        side_breakdown[("agent_a", agent_a_player)],
                        normalized,
                        "agent_a",
                    )
                    _record_side_game(
                        side_breakdown[("agent_b", 1 - agent_a_player)],
                        normalized,
                        "agent_b",
                    )

    runtime_ms = round((perf_counter() - started) * 1000, 2)
    return {
        "config": {
            "agent_a": request.agent_a,
            "agent_b": request.agent_b,
            "agent_a_name": _agent_name(request.agent_a),
            "agent_b_name": _agent_name(request.agent_b),
            "map_ids": map_ids,
            "seed_start": request.seed_start,
            "games_per_map": request.games_per_map,
            "max_rounds": request.max_rounds,
            "side_swap": request.side_swap,
            "initiative_mode": request.initiative_mode,
            "total_games": total["games"],
            "runtime_ms": runtime_ms,
        },
        "summary": _finalize_batch_accumulator(total),
        "by_map": [
            {
                "map_id": map_id,
                "map_name": MAP_NAMES[map_id],
                **_finalize_batch_accumulator(by_map[map_id]),
            }
            for map_id in map_ids
        ],
        "side_breakdown": [
            {
                "agent": agent_key,
                "agent_name": _agent_name(
                    request.agent_a if agent_key == "agent_a" else request.agent_b
                ),
                "as_player": player,
                **_finalize_side_accumulator(accumulator),
            }
            for (agent_key, player), accumulator in side_breakdown.items()
        ],
        "games": games,
    }


def _play_lab_game(
    player_agents: tuple[str, str],
    seed: int,
    map_id: str,
    max_rounds: int,
    first_player: int,
) -> dict[str, Any]:
    env = SupplyGraphWarEnv(max_rounds=max_rounds).reset(
        seed=seed,
        map_id=map_id,
        first_player=first_player,
    )
    agents = (_make_agent(player_agents[0]), _make_agent(player_agents[1]))

    for player, agent in enumerate(agents):
        agent.on_game_start(env, player)

    try:
        while not env.is_terminal():
            player = env.current_player
            action = agents[player].select_action(env, player)
            env.step(action)
    finally:
        result_summary = {"winner": env.winner(), "seed": seed, "map_id": env.map_id}
        for player, agent in enumerate(agents):
            agent.on_game_end(env, player, result_summary)
            agent.close()

    state = env.state
    assert state is not None
    supplied = compute_supply(state.graph, state.owners, state.bases)
    return {
        "winner": env.winner(),
        "scores": {player: env.score(player) for player in (0, 1)},
        "rounds": env.round_index,
        "captured_base": env.captured_base,
        "final_owned": {player: int((state.owners == player).sum()) for player in (0, 1)},
        "final_supplied": {
            player: int(((state.owners == player) & supplied[player]).sum()) for player in (0, 1)
        },
        "final_units": {
            player: int(state.units[state.owners == player].sum()) for player in (0, 1)
        },
        "seed": seed,
        "map_id": env.map_id,
        "map_name": env.map_name,
        "first_player": first_player,
    }


def _normalize_lab_game(
    raw: dict[str, Any],
    agent_a_player: int,
    first_player: int,
) -> dict[str, Any]:
    agent_b_player = 1 - agent_a_player
    winner = raw["winner"]
    winner_agent = None
    if winner is not None:
        winner_agent = "agent_a" if winner == agent_a_player else "agent_b"

    score_a = raw["scores"][agent_a_player]
    score_b = raw["scores"][agent_b_player]
    return {
        "seed": raw["seed"],
        "map_id": raw["map_id"],
        "map_name": raw["map_name"],
        "agent_a_player": agent_a_player,
        "first_player": first_player,
        "winner": winner_agent,
        "score_a": score_a,
        "score_b": score_b,
        "score_delta": score_a - score_b,
        "rounds": raw["rounds"],
        "captured_base": raw["captured_base"],
        "final_owned_a": raw["final_owned"][agent_a_player],
        "final_owned_b": raw["final_owned"][agent_b_player],
        "final_supplied_a": raw["final_supplied"][agent_a_player],
        "final_supplied_b": raw["final_supplied"][agent_b_player],
        "final_units_a": raw["final_units"][agent_a_player],
        "final_units_b": raw["final_units"][agent_b_player],
    }


def _empty_batch_accumulator() -> dict[str, float | int]:
    return {
        "games": 0,
        "agent_a_wins": 0,
        "agent_b_wins": 0,
        "draws": 0,
        "score_a_total": 0,
        "score_b_total": 0,
        "score_delta_total": 0,
        "rounds_total": 0,
        "base_captures": 0,
        "owned_a_total": 0,
        "owned_b_total": 0,
        "supplied_a_total": 0,
        "supplied_b_total": 0,
        "units_a_total": 0,
        "units_b_total": 0,
    }


def _record_batch_game(accumulator: dict[str, float | int], game: dict[str, Any]) -> None:
    accumulator["games"] += 1
    if game["winner"] == "agent_a":
        accumulator["agent_a_wins"] += 1
    elif game["winner"] == "agent_b":
        accumulator["agent_b_wins"] += 1
    else:
        accumulator["draws"] += 1

    accumulator["score_a_total"] += game["score_a"]
    accumulator["score_b_total"] += game["score_b"]
    accumulator["score_delta_total"] += game["score_delta"]
    accumulator["rounds_total"] += game["rounds"]
    accumulator["base_captures"] += int(game["captured_base"])
    accumulator["owned_a_total"] += game["final_owned_a"]
    accumulator["owned_b_total"] += game["final_owned_b"]
    accumulator["supplied_a_total"] += game["final_supplied_a"]
    accumulator["supplied_b_total"] += game["final_supplied_b"]
    accumulator["units_a_total"] += game["final_units_a"]
    accumulator["units_b_total"] += game["final_units_b"]


def _finalize_batch_accumulator(accumulator: dict[str, float | int]) -> dict[str, Any]:
    games = int(accumulator["games"])
    return {
        "games": games,
        "wins": {
            "agent_a": int(accumulator["agent_a_wins"]),
            "agent_b": int(accumulator["agent_b_wins"]),
            "draws": int(accumulator["draws"]),
        },
        "win_rates": {
            "agent_a": _rate(accumulator["agent_a_wins"], games),
            "agent_b": _rate(accumulator["agent_b_wins"], games),
            "draw": _rate(accumulator["draws"], games),
        },
        "avg_score": {
            "agent_a": _average(accumulator["score_a_total"], games),
            "agent_b": _average(accumulator["score_b_total"], games),
            "delta": _average(accumulator["score_delta_total"], games),
        },
        "avg_rounds": _average(accumulator["rounds_total"], games),
        "base_capture_rate": _rate(accumulator["base_captures"], games),
        "avg_final": {
            "owned": {
                "agent_a": _average(accumulator["owned_a_total"], games),
                "agent_b": _average(accumulator["owned_b_total"], games),
            },
            "supplied": {
                "agent_a": _average(accumulator["supplied_a_total"], games),
                "agent_b": _average(accumulator["supplied_b_total"], games),
            },
            "units": {
                "agent_a": _average(accumulator["units_a_total"], games),
                "agent_b": _average(accumulator["units_b_total"], games),
            },
        },
    }


def _empty_side_accumulator() -> dict[str, float | int]:
    return {
        "games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "score_total": 0,
        "starts_first": 0,
    }


def _record_side_game(
    accumulator: dict[str, float | int],
    game: dict[str, Any],
    agent_key: str,
) -> None:
    accumulator["games"] += 1
    if game["winner"] is None:
        accumulator["draws"] += 1
    elif game["winner"] == agent_key:
        accumulator["wins"] += 1
    else:
        accumulator["losses"] += 1
    accumulator["score_total"] += game["score_a" if agent_key == "agent_a" else "score_b"]
    agent_player = game["agent_a_player"] if agent_key == "agent_a" else 1 - game["agent_a_player"]
    accumulator["starts_first"] += int(agent_player == game["first_player"])


def _finalize_side_accumulator(accumulator: dict[str, float | int]) -> dict[str, Any]:
    games = int(accumulator["games"])
    return {
        "games": games,
        "wins": int(accumulator["wins"]),
        "losses": int(accumulator["losses"]),
        "draws": int(accumulator["draws"]),
        "win_rate": _rate(accumulator["wins"], games),
        "avg_score": _average(accumulator["score_total"], games),
        "first_rate": _rate(accumulator["starts_first"], games),
    }


def _unique_map_ids(map_ids: list[str]) -> list[str]:
    return list(dict.fromkeys(map_ids))


def _agent_name(agent_id: str) -> str:
    for spec in available_agent_specs():
        if spec.id == agent_id:
            return spec.name
    return agent_id


def _start_agents(session: WebSession) -> None:
    for player, agent in enumerate(session.agents):
        agent.on_game_start(session.env, player)


def _end_agents(session: WebSession) -> None:
    if session.agents_closed:
        return
    result = {
        "winner": session.env.winner(),
        "seed": session.seed,
        "map_id": session.map_id,
        "rounds": session.env.round_index,
    }
    for player, agent in enumerate(session.agents):
        agent.on_game_end(session.env, player, result)
        agent.close()
    session.agents_closed = True


def _first_players_for_mode(mode: str) -> tuple[int, ...]:
    if mode == "balanced":
        return (0, 1)
    if mode == "p1":
        return (1,)
    return (0,)


def _rate(value: float | int, games: int) -> float:
    if games == 0:
        return 0.0
    return round(float(value) / games, 4)


def _average(value: float | int, games: int) -> float:
    if games == 0:
        return 0.0
    return round(float(value) / games, 2)


def _serialize_session(session: WebSession) -> dict[str, Any]:
    env = session.env
    state = env.state
    assert state is not None
    supplied = compute_supply(state.graph, state.owners, state.bases)

    nodes = []
    for node in range(state.n_nodes):
        owner = int(state.owners[node])
        base_player = _base_player(node, state.bases)
        x, y = session.positions[node]
        nodes.append(
            {
                "id": node,
                "owner": owner,
                "units": int(state.units[node]),
                "production": int(state.production[node]),
                "defense": int(state.defense[node]),
                "supplied": bool(owner in (0, 1) and supplied[owner, node]),
                "base_player": base_player,
                "x": x,
                "y": y,
            }
        )

    current_player = None if env.is_terminal() else env.current_player
    legal_actions = [] if current_player is None else env.legal_actions(current_player)

    return {
        "session_id": session.session_id,
        "config": {
            "seed": session.seed,
            "map_id": session.map_id,
            "map_name": session.map_name,
            "node_count": state.n_nodes,
            "max_rounds": session.max_rounds,
            "first_player": session.first_player,
            "agents": {
                "0": session.agent_ids[0],
                "1": session.agent_ids[1],
            },
        },
        "status": {
            "round_index": env.round_index,
            "current_player": current_player,
            "terminal": env.is_terminal(),
            "winner": env.winner(),
            "captured_base": env.captured_base,
            "production_pending": env._production_pending,
            "first_player": state.first_player,
        },
        "scores": {
            "0": env.score(0),
            "1": env.score(1),
        },
        "summary": {
            "owned": {
                "0": int((state.owners == 0).sum()),
                "1": int((state.owners == 1).sum()),
                "neutral": int((state.owners == -1).sum()),
            },
            "supplied": {
                "0": int(((state.owners == 0) & supplied[0]).sum()),
                "1": int(((state.owners == 1) & supplied[1]).sum()),
            },
            "units": {
                "0": int(state.units[state.owners == 0].sum()),
                "1": int(state.units[state.owners == 1].sum()),
                "neutral": int(state.units[state.owners == -1].sum()),
            },
        },
        "graph": {
            "nodes": nodes,
            "edges": [
                {"source": int(source), "target": int(target)}
                for source, target in sorted(state.graph.edges())
            ],
            "bases": {
                "0": int(state.bases[0]),
                "1": int(state.bases[1]),
            },
        },
        "legal_actions": [
            {"index": index, **_serialize_action(action)}
            for index, action in enumerate(legal_actions)
        ],
        "action_log": session.action_log,
    }


def _serialize_action(action: Action) -> dict[str, Any]:
    kind = action.kind if isinstance(action.kind, ActionKind) else ActionKind(action.kind)
    return {
        "kind": kind.value,
        "source": action.source,
        "target": action.target,
        "ratio": action.ratio,
        "label": str(action),
    }


def _base_player(node: int, bases: tuple[int, int]) -> int | None:
    if node == bases[0]:
        return 0
    if node == bases[1]:
        return 1
    return None

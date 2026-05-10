"""FastAPI app for the local Supply Graph War frontend."""

from __future__ import annotations

import subprocess
import threading
from dataclasses import asdict, dataclass, field
from importlib.resources import files
from pathlib import Path
from time import perf_counter, time
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from strategic_agent_arena.agents import BaseAgent
from strategic_agent_arena.agents.external_process_agent import ExternalProcessAgent
from strategic_agent_arena.agents.registry import (
    REPO_ROOT,
    AgentSpec,
    agent_infos,
    available_agent_specs,
    load_external_agent_specs,
    make_agent,
)
from strategic_agent_arena.envs.supply_graph_war.actions import Action, ActionKind
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv
from strategic_agent_arena.envs.supply_graph_war.mapgen import available_maps
from strategic_agent_arena.envs.supply_graph_war.maps import DEFAULT_MAP_ID
from strategic_agent_arena.envs.supply_graph_war.rules import compute_supply

MAP_INFOS = tuple(available_maps())
MAP_IDS = tuple(map_info.id for map_info in MAP_INFOS)
MAP_NAMES = {map_info.id: map_info.name for map_info in MAP_INFOS}
MAX_BATCH_GAMES = 2_000
CPP_UI_AGENT_IDS = frozenset({"cpp_random_agent", "cpp_greedy_expansion_agent"})
CPP_DEV_AGENT_ID = "cpp_mcts_v1"
CPP_DEV_SOURCE = REPO_ROOT / "algos" / "cpp" / "agents" / "mcts_v1.cpp"
CPP_DEV_EXECUTABLE = REPO_ROOT / "algos" / "cpp" / "build" / "cpp_mcts_v1"
BUILD_TIMEOUT_SECONDS = 60


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
    games_per_map: int = Field(default=10, ge=1, le=500)
    max_rounds: int = Field(default=80, ge=1, le=500)
    side_swap: bool = True
    initiative_mode: Literal["balanced", "p0", "p1"] = "balanced"


class DevSessionCreateRequest(BaseModel):
    seed: int | None = 7
    map_id: str = DEFAULT_MAP_ID
    max_rounds: int = Field(default=80, ge=1, le=500)
    first_player: int = Field(default=0, ge=0, le=1)
    mcts_player: int = Field(default=0, ge=0, le=1)
    opponent_agent: str = "cpp_greedy_expansion_agent"


@dataclass(slots=True)
class BuildCommandResult:
    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    runtime_ms: float


@dataclass(slots=True)
class DevBuildState:
    state: str = "not_started"
    source_mtime: float | None = None
    executable_mtime: float | None = None
    build_id: str | None = None
    last_started_at: float | None = None
    last_finished_at: float | None = None
    commands: list[BuildCommandResult] = field(default_factory=list)
    error: str | None = None


class DevBuildService:
    """Small synchronous build watcher for the local C++ development target."""

    def __init__(
        self,
        *,
        source_path: Path = CPP_DEV_SOURCE,
        executable_path: Path = CPP_DEV_EXECUTABLE,
    ) -> None:
        self.source_path = source_path
        self.executable_path = executable_path
        self._state = DevBuildState()
        self._lock = threading.Lock()

    def status(self, *, auto_build: bool = True) -> dict[str, Any]:
        with self._lock:
            source_mtime = _path_mtime(self.source_path)
            should_build = (
                auto_build
                and source_mtime is not None
                and (self._state.source_mtime is None or source_mtime > self._state.source_mtime)
            )
            if should_build:
                self._build_locked(source_mtime)
            return self._serialize_locked()

    def build(self) -> dict[str, Any]:
        with self._lock:
            self._build_locked(_path_mtime(self.source_path))
            return self._serialize_locked()

    def current_build_id(self) -> str | None:
        with self._lock:
            return self._state.build_id

    def _build_locked(self, source_mtime: float | None) -> None:
        self._state.state = "running"
        self._state.source_mtime = source_mtime
        self._state.last_started_at = time()
        self._state.last_finished_at = None
        self._state.commands = []
        self._state.error = None

        commands = (
            ["cmake", "-S", "algos/cpp", "-B", "algos/cpp/build"],
            ["cmake", "--build", "algos/cpp/build", "--target", "cpp_mcts_v1"],
        )

        for command in commands:
            result = _run_build_command(command)
            self._state.commands.append(result)
            if result.return_code != 0:
                self._state.state = "failed"
                self._state.error = f"command failed: {' '.join(command)}"
                self._state.last_finished_at = time()
                self._state.executable_mtime = _path_mtime(self.executable_path)
                return

        self._state.state = "success"
        self._state.last_finished_at = time()
        self._state.executable_mtime = _path_mtime(self.executable_path)
        self._state.build_id = _build_id(self._state.source_mtime, self._state.executable_mtime)

    def _serialize_locked(self) -> dict[str, Any]:
        source_mtime = _path_mtime(self.source_path)
        executable_mtime = _path_mtime(self.executable_path)
        stale = (
            source_mtime is not None
            and self._state.source_mtime is not None
            and source_mtime > self._state.source_mtime
        )
        return {
            "agent_id": CPP_DEV_AGENT_ID,
            "source": {
                "path": str(self.source_path.relative_to(REPO_ROOT)),
                "exists": self.source_path.exists(),
                "mtime": source_mtime,
            },
            "executable": {
                "path": str(self.executable_path.relative_to(REPO_ROOT)),
                "exists": self.executable_path.exists(),
                "mtime": executable_mtime,
            },
            "build": {
                "state": self._state.state,
                "stale": stale,
                "build_id": self._state.build_id,
                "last_started_at": self._state.last_started_at,
                "last_finished_at": self._state.last_finished_at,
                "error": self._state.error,
                "commands": [
                    {
                        "command": result.command,
                        "return_code": result.return_code,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "runtime_ms": result.runtime_ms,
                    }
                    for result in self._state.commands
                ],
            },
        }


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
    mode: str = "play"
    build_id: str | None = None


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

    def add(self, session: WebSession) -> WebSession:
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> WebSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc

    def close(self, session_id: str) -> WebSession:
        session = self.get(session_id)
        _end_agents(session)
        self._sessions.pop(session_id, None)
        return session

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
    dev_builds = DevBuildService()

    app = FastAPI(title="Strategic Agent Arena")
    app.state.sessions = store
    app.state.dev_builds = dev_builds
    app.mount("/static", NoCacheStaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return _static_page(static_dir, "play.html")

    @app.get("/play")
    def play_page() -> FileResponse:
        return _static_page(static_dir, "play.html")

    @app.get("/analysis")
    def analysis_page() -> FileResponse:
        return _static_page(static_dir, "analysis.html")

    @app.get("/develop")
    def develop_page() -> FileResponse:
        return _static_page(static_dir, "develop.html")

    @app.get("/api/agents")
    def agents() -> dict[str, Any]:
        return {
            "agents": _web_agent_infos(),
            "unavailable_agents": _web_agent_infos(available=False),
            "development_agent": _development_agent_info(),
            "internal_agents": agent_infos(),
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

    @app.post("/api/sessions/{session_id}/close")
    def close_session(session_id: str) -> dict[str, Any]:
        store.close(session_id)
        return {"closed": True, "session_id": session_id}

    @app.post("/api/lab/batch")
    def run_batch(request: BatchRunRequest) -> dict[str, Any]:
        _validate_batch_request(request)
        return _run_batch(request)

    @app.get("/api/dev/status")
    def dev_status() -> dict[str, Any]:
        return dev_builds.status(auto_build=True)

    @app.post("/api/dev/build")
    def dev_build() -> dict[str, Any]:
        return dev_builds.build()

    @app.post("/api/dev/session")
    def create_dev_session(request: DevSessionCreateRequest) -> dict[str, Any]:
        _validate_dev_request(request)
        build_status = dev_builds.status(auto_build=True)
        if not build_status["executable"]["exists"] or build_status["build"]["state"] != "success":
            raise HTTPException(status_code=400, detail="cpp_mcts_v1 is not built successfully")
        return _serialize_session(_create_dev_session(store, request, dev_builds.current_build_id()))

    return app


app = create_app()


def _static_page(static_dir: Any, filename: str) -> FileResponse:
    return FileResponse(
        str(static_dir.joinpath(filename)),
        headers={"Cache-Control": "no-store"},
    )


def _path_mtime(path: Path) -> float | None:
    if not path.exists():
        return None
    return path.stat().st_mtime


def _build_id(source_mtime: float | None, executable_mtime: float | None) -> str | None:
    if source_mtime is None or executable_mtime is None:
        return None
    return f"{source_mtime:.6f}:{executable_mtime:.6f}"


def _run_build_command(command: list[str]) -> BuildCommandResult:
    started = perf_counter()
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=BUILD_TIMEOUT_SECONDS,
        )
        return BuildCommandResult(
            command=command,
            return_code=result.returncode,
            stdout=result.stdout[-20_000:],
            stderr=result.stderr[-20_000:],
            runtime_ms=round((perf_counter() - started) * 1000, 2),
        )
    except OSError as exc:
        return BuildCommandResult(
            command=command,
            return_code=127,
            stdout="",
            stderr=str(exc),
            runtime_ms=round((perf_counter() - started) * 1000, 2),
        )
    except subprocess.TimeoutExpired as exc:
        return BuildCommandResult(
            command=command,
            return_code=124,
            stdout=_text_output(exc.stdout)[-20_000:],
            stderr=(_text_output(exc.stderr) + "\nbuild timed out")[-20_000:],
            runtime_ms=round((perf_counter() - started) * 1000, 2),
        )


def _text_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _web_agent_infos(*, available: bool = True) -> list[dict[str, Any]]:
    return [
        _web_agent_info(spec)
        for spec in _web_agent_specs()
        if _command_available(spec) is available
    ]


def _web_agent_specs() -> list[AgentSpec]:
    return [
        spec
        for spec in load_external_agent_specs()
        if spec.enabled and spec.id in CPP_UI_AGENT_IDS
    ]


def _web_agent_info(spec: AgentSpec) -> dict[str, Any]:
    executable = _command_path(spec)
    return {
        "id": spec.id,
        "name": spec.name,
        "kind": spec.kind,
        "enabled": spec.enabled,
        "available": _command_available(spec),
        "command": list(spec.command),
        "executable": str(executable.relative_to(REPO_ROOT)) if executable is not None else None,
    }


def _development_agent_info() -> dict[str, Any] | None:
    spec = _external_spec(CPP_DEV_AGENT_ID)
    if spec is None:
        return None
    return _web_agent_info(spec)


def _external_spec(agent_id: str) -> AgentSpec | None:
    for spec in load_external_agent_specs():
        if spec.id == agent_id:
            return spec
    return None


def _command_path(spec: AgentSpec) -> Path | None:
    if not spec.command:
        return None
    path = Path(spec.command[0])
    return path if path.is_absolute() else REPO_ROOT / path


def _command_available(spec: AgentSpec) -> bool:
    path = _command_path(spec)
    return path is not None and path.exists() and path.is_file()


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


def _validate_dev_request(request: DevSessionCreateRequest) -> None:
    if request.map_id not in MAP_IDS:
        raise HTTPException(status_code=400, detail=f"unknown map_id: {request.map_id}")
    if request.opponent_agent not in {spec.id for spec in _web_agent_specs()}:
        raise HTTPException(status_code=400, detail=f"unknown C++ opponent: {request.opponent_agent}")
    spec = _external_spec(request.opponent_agent)
    if spec is None or not _command_available(spec):
        raise HTTPException(status_code=400, detail=f"opponent is not built: {request.opponent_agent}")


def _make_agent(agent_id: str) -> BaseAgent:
    try:
        return make_agent(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _make_external_agent(agent_id: str) -> ExternalProcessAgent:
    spec = _external_spec(agent_id)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"unknown external agent: {agent_id}")
    return ExternalProcessAgent(
        spec.command,
        agent_id=spec.id,
        name=spec.name,
        protocol=spec.protocol,
        timeout_ms=spec.timeout_ms,
        startup_timeout_ms=spec.startup_timeout_ms,
        cwd=REPO_ROOT,
    )


def _create_dev_session(
    store: SessionStore,
    request: DevSessionCreateRequest,
    build_id: str | None,
) -> WebSession:
    env = SupplyGraphWarEnv(max_rounds=request.max_rounds).reset(
        seed=request.seed,
        map_id=request.map_id,
        first_player=request.first_player,
    )
    assert env.state is not None

    mcts_agent = _make_external_agent(CPP_DEV_AGENT_ID)
    opponent = _make_agent(request.opponent_agent)
    agents = (mcts_agent, opponent) if request.mcts_player == 0 else (opponent, mcts_agent)
    agent_ids = (
        (CPP_DEV_AGENT_ID, request.opponent_agent)
        if request.mcts_player == 0
        else (request.opponent_agent, CPP_DEV_AGENT_ID)
    )
    session = WebSession(
        session_id=str(uuid4()),
        env=env,
        agents=agents,
        agent_ids=agent_ids,
        seed=request.seed,
        map_id=env.map_id,
        map_name=env.map_name,
        max_rounds=request.max_rounds,
        first_player=request.first_player,
        positions=dict(env.map_positions),
        mode="develop",
        build_id=build_id,
    )
    try:
        _start_agents(session)
    except Exception as exc:  # noqa: BLE001 - surface external startup failures.
        _end_agents(session)
        raise HTTPException(status_code=400, detail=f"agent startup failed: {exc}") from exc
    return store.add(session)


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
    agent_pool: dict[tuple[str, int], BaseAgent] = {}

    try:
        for map_id in map_ids:
            for seed in range(request.seed_start, request.seed_start + request.games_per_map):
                pairings = [0, 1] if request.side_swap else [0]
                for agent_a_player in pairings:
                    player_agents = (
                        (request.agent_a, request.agent_b)
                        if agent_a_player == 0
                        else (request.agent_b, request.agent_a)
                    )
                    agents = (
                        _batch_agent(agent_pool, player_agents[0], 0),
                        _batch_agent(agent_pool, player_agents[1], 1),
                    )
                    for first_player in _first_players_for_mode(request.initiative_mode):
                        raw = _play_lab_game(
                            player_agents=player_agents,
                            seed=seed,
                            map_id=map_id,
                            max_rounds=request.max_rounds,
                            first_player=first_player,
                            agents=agents,
                            close_agents=False,
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
    finally:
        for agent in agent_pool.values():
            agent.close()

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
    agents: tuple[BaseAgent, BaseAgent] | None = None,
    close_agents: bool = True,
) -> dict[str, Any]:
    env = SupplyGraphWarEnv(max_rounds=max_rounds).reset(
        seed=seed,
        map_id=map_id,
        first_player=first_player,
    )
    match_agents = agents or (_make_agent(player_agents[0]), _make_agent(player_agents[1]))

    for player, agent in enumerate(match_agents):
        agent.on_game_start(env, player)

    try:
        while not env.is_terminal():
            player = env.current_player
            action = match_agents[player].select_action(env, player)
            env.step(action)
    finally:
        result_summary = {"winner": env.winner(), "seed": seed, "map_id": env.map_id}
        for player, agent in enumerate(match_agents):
            agent.on_game_end(env, player, result_summary)
            if close_agents:
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


def _batch_agent(
    agent_pool: dict[tuple[str, int], BaseAgent],
    agent_id: str,
    player: int,
) -> BaseAgent:
    key = (agent_id, player)
    if key not in agent_pool:
        agent_pool[key] = _make_agent(agent_id)
    return agent_pool[key]


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
            "mode": session.mode,
            "build_id": session.build_id,
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
        "agent_diagnostics": {
            str(player): _agent_diagnostics(agent)
            for player, agent in enumerate(session.agents)
        },
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


def _agent_diagnostics(agent: BaseAgent) -> dict[str, Any]:
    snapshot = getattr(agent, "diagnostics_snapshot", None)
    if callable(snapshot):
        return snapshot()
    return {
        "fallbacks": 0,
        "timeouts": 0,
        "invalid_responses": 0,
        "crashes": 0,
        "last_error": None,
        "stderr_tail": [],
        "running": False,
    }


def _base_player(node: int, bases: tuple[int, int]) -> int | None:
    if node == bases[0]:
        return 0
    if node == bases[1]:
        return 1
    return None

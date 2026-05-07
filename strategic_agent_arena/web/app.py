"""FastAPI app for the local Supply Graph War frontend."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from importlib.resources import files
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from strategic_agent_arena.agents import BaseAgent, GreedyExpansionAgent, RandomAgent
from strategic_agent_arena.envs.supply_graph_war.actions import Action, ActionKind
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv
from strategic_agent_arena.envs.supply_graph_war.mapgen import available_maps
from strategic_agent_arena.envs.supply_graph_war.maps import DEFAULT_MAP_ID
from strategic_agent_arena.envs.supply_graph_war.rules import compute_supply

AGENT_FACTORIES: dict[str, tuple[str, type[BaseAgent]]] = {
    "random": ("RandomAgent", RandomAgent),
    "greedy_expansion": ("GreedyExpansionAgent", GreedyExpansionAgent),
}
MAP_IDS = tuple(map_info.id for map_info in available_maps())


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict[str, Any]) -> Any:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


class SessionCreateRequest(BaseModel):
    seed: int | None = 7
    map_id: str = DEFAULT_MAP_ID
    max_rounds: int = Field(default=80, ge=1, le=500)
    player0_agent: str = "random"
    player1_agent: str = "greedy_expansion"


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
    positions: dict[int, tuple[float, float]]
    action_log: list[dict[str, Any]] = field(default_factory=list)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, WebSession] = {}

    def create(self, request: SessionCreateRequest) -> WebSession:
        _validate_request(request)
        env = SupplyGraphWarEnv(max_rounds=request.max_rounds).reset(
            seed=request.seed,
            map_id=request.map_id,
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
            positions=dict(env.map_positions),
        )
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
            "agents": [
                {"id": agent_id, "name": display_name}
                for agent_id, (display_name, _) in AGENT_FACTORIES.items()
            ],
            "maps": [asdict(map_info) for map_info in available_maps()],
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

    return app


app = create_app()


def _validate_request(request: SessionCreateRequest) -> None:
    if request.map_id not in MAP_IDS:
        raise HTTPException(status_code=400, detail=f"unknown map_id: {request.map_id}")
    for agent_id in (request.player0_agent, request.player1_agent):
        if agent_id not in AGENT_FACTORIES:
            raise HTTPException(status_code=400, detail=f"unknown agent: {agent_id}")


def _make_agent(agent_id: str) -> BaseAgent:
    return AGENT_FACTORIES[agent_id][1]()


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

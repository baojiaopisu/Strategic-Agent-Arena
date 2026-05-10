from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from strategic_agent_arena.web.app import create_app


def test_create_session_returns_graph_state_and_agents() -> None:
    client = TestClient(create_app())

    agents_response = client.get("/api/agents")
    assert agents_response.status_code == 200
    agents_body = agents_response.json()
    agent_ids = {agent["id"] for agent in agents_body["agents"]}
    unavailable_ids = {agent["id"] for agent in agents_body["unavailable_agents"]}
    assert "random" not in agent_ids
    assert "greedy_expansion" not in agent_ids
    assert agent_ids <= {"cpp_random_agent", "cpp_greedy_expansion_agent"}
    assert {"cpp_random_agent", "cpp_greedy_expansion_agent"} <= agent_ids | unavailable_ids
    assert {agent["id"] for agent in agents_body["internal_agents"]} >= {
        "random",
        "greedy_expansion",
    }
    assert agents_body["development_agent"]["id"] == "cpp_mcts_v1"
    assert [map_info["id"] for map_info in agents_body["maps"]] == [
        "twin_pass",
        "island_ring",
        "trident_front",
    ]

    response = client.post(
        "/api/sessions",
        json={
            "seed": 10,
            "map_id": "twin_pass",
            "max_rounds": 20,
            "player0_agent": "random",
            "player1_agent": "greedy_expansion",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["config"]["map_id"] == "twin_pass"
    assert body["config"]["map_name"] == "Twin Pass"
    assert body["config"]["first_player"] == 0
    assert body["status"]["round_index"] == 1
    assert body["status"]["current_player"] == 0
    assert body["status"]["first_player"] == 0
    assert len(body["graph"]["nodes"]) == 21
    assert body["graph"]["edges"]
    assert body["legal_actions"]
    assert body["action_log"] == []


def test_pages_use_split_static_assets() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert '<div id="root"></div>' in response.text
    assert "/static/spa/assets/" in response.text

    analysis = client.get("/analysis")
    develop = client.get("/develop")

    assert analysis.status_code == 200
    assert '<div id="root"></div>' in analysis.text
    assert develop.status_code == 200
    assert '<div id="root"></div>' in develop.text


def test_create_session_can_start_with_player_one() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/sessions",
        json={"seed": 10, "map_id": "twin_pass", "first_player": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["config"]["first_player"] == 1
    assert body["status"]["first_player"] == 1
    assert body["status"]["current_player"] == 1


def test_same_seed_produces_deterministic_initial_state_and_layout() -> None:
    client = TestClient(create_app())
    payload = {
        "seed": 12,
        "map_id": "island_ring",
        "max_rounds": 20,
        "player0_agent": "random",
        "player1_agent": "greedy_expansion",
    }

    first = client.post("/api/sessions", json=payload).json()
    second = client.post("/api/sessions", json=payload).json()

    assert first["graph"] == second["graph"]
    assert first["scores"] == second["scores"]
    assert first["legal_actions"] == second["legal_actions"]


def test_step_advances_one_action_and_appends_log() -> None:
    client = TestClient(create_app())
    session = client.post(
        "/api/sessions",
        json={"seed": 3, "map_id": "twin_pass", "max_rounds": 10},
    ).json()

    response = client.post(f"/api/sessions/{session['session_id']}/step")

    assert response.status_code == 200
    body = response.json()
    assert len(body["action_log"]) == 1
    assert body["action_log"][0]["round"] == 1
    assert body["action_log"][0]["player"] == 0
    assert body["status"]["current_player"] == 1


def test_close_session_ends_session() -> None:
    client = TestClient(create_app())
    session = client.post(
        "/api/sessions",
        json={"seed": 3, "map_id": "twin_pass", "max_rounds": 10},
    ).json()

    response = client.post(f"/api/sessions/{session['session_id']}/close")
    missing = client.get(f"/api/sessions/{session['session_id']}")

    assert response.status_code == 200
    assert response.json()["closed"] is True
    assert missing.status_code == 404


def test_round_advances_to_next_round_or_terminal() -> None:
    client = TestClient(create_app())
    session = client.post(
        "/api/sessions",
        json={"seed": 4, "map_id": "trident_front", "max_rounds": 10},
    ).json()

    response = client.post(f"/api/sessions/{session['session_id']}/round")

    assert response.status_code == 200
    body = response.json()
    assert len(body["action_log"]) >= 1
    assert body["status"]["terminal"] or body["status"]["round_index"] == 2


def test_lab_batch_runs_headless_games_and_returns_statistics() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/lab/batch",
        json={
            "agent_a": "random",
            "agent_b": "greedy_expansion",
            "map_ids": ["twin_pass"],
            "seed_start": 1,
            "games_per_map": 2,
            "max_rounds": 20,
            "side_swap": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["config"]["initiative_mode"] == "balanced"
    assert body["config"]["total_games"] == 8
    assert body["summary"]["games"] == 8
    assert sum(body["summary"]["wins"].values()) == 8
    assert body["by_map"][0]["map_id"] == "twin_pass"
    assert body["by_map"][0]["games"] == 8
    assert len(body["side_breakdown"]) == 4
    assert len(body["games"]) == 8
    assert {game["agent_a_player"] for game in body["games"]} == {0, 1}
    assert {game["first_player"] for game in body["games"]} == {0, 1}
    assert {row["first_rate"] for row in body["side_breakdown"]} == {0.5}


def test_lab_batch_is_deterministic_for_same_request() -> None:
    client = TestClient(create_app())
    payload = {
        "agent_a": "random",
        "agent_b": "greedy_expansion",
        "map_ids": ["island_ring", "trident_front"],
        "seed_start": 5,
        "games_per_map": 2,
        "max_rounds": 20,
        "side_swap": False,
    }

    first = client.post("/api/lab/batch", json=payload).json()
    second = client.post("/api/lab/batch", json=payload).json()

    assert first["summary"] == second["summary"]
    assert first["by_map"] == second["by_map"]
    assert first["side_breakdown"] == second["side_breakdown"]
    assert first["games"] == second["games"]


def test_lab_batch_rejects_too_many_games() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/lab/batch",
        json={
            "map_ids": ["twin_pass", "island_ring", "trident_front"],
            "games_per_map": 500,
            "side_swap": True,
        },
    )

    assert response.status_code == 400
    assert "batch too large" in response.json()["detail"]


def test_lab_batch_job_runs_in_memory() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/lab/jobs",
        json={
            "agent_a": "random",
            "agent_b": "greedy_expansion",
            "map_ids": ["twin_pass"],
            "seed_start": 1,
            "games_per_map": 1,
            "max_rounds": 10,
            "side_swap": False,
            "initiative_mode": "p0",
        },
    )

    assert response.status_code == 200
    job = response.json()
    assert job["job_id"]
    assert job["progress"]["total_games"] == 1

    for _ in range(20):
        job = client.get(f"/api/lab/jobs/{job['job_id']}").json()
        if job["state"] in {"success", "failed", "cancelled"}:
            break

    assert job["state"] == "success"
    assert job["result"]["summary"]["games"] == 1


def test_dev_status_reports_build_target() -> None:
    client = TestClient(create_app())

    response = client.get("/api/dev/status")

    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == "cpp_mcts_v1"
    assert body["source"]["path"] == "algos/cpp/agents/mcts_v1.cpp"
    assert "algos/cpp/include/saa_protocol.hpp" in body["source"]["watched"]
    assert body["executable"]["path"] == "algos/cpp/build/cpp_mcts_v1"
    assert body["build"]["state"] in {"success", "failed", "not_started"}
    assert "commands" in body["build"]


def test_dev_files_are_whitelisted() -> None:
    client = TestClient(create_app())

    listing = client.get("/api/dev/files")

    assert listing.status_code == 200
    file_paths = {file_info["path"] for file_info in listing.json()["files"]}
    assert "algos/cpp/agents/mcts_v1.cpp" in file_paths
    assert "algos/cpp/include/saa_protocol.hpp" in file_paths

    valid = client.get("/api/dev/files/algos/cpp/agents/mcts_v1.cpp")
    traversal = client.get("/api/dev/files/%2E%2E/pyproject.toml")
    outside = client.put("/api/dev/files/README.md", json={"content": "bad"})

    assert valid.status_code == 200
    assert "content" in valid.json()
    assert traversal.status_code == 400
    assert outside.status_code == 400


def test_dev_session_runs_cpp_mcts_against_cpp_agent() -> None:
    client = TestClient(create_app())
    agents = client.get("/api/agents").json()["agents"]
    if "cpp_greedy_expansion_agent" not in {agent["id"] for agent in agents}:
        pytest.skip("C++ greedy agent binary is not built")
    build_status = client.get("/api/dev/status").json()
    if build_status["build"]["state"] != "success" or not build_status["executable"]["exists"]:
        pytest.skip("C++ MCTS development target is not built")

    response = client.post(
        "/api/dev/session",
        json={
            "seed": 3,
            "map_id": "twin_pass",
            "max_rounds": 5,
            "mcts_player": 0,
            "opponent_agent": "cpp_greedy_expansion_agent",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["config"]["mode"] == "develop"
    assert body["config"]["agents"]["0"] == "cpp_mcts_v1"
    assert body["config"]["agents"]["1"] == "cpp_greedy_expansion_agent"
    assert body["config"]["build_id"]
    assert body["agent_diagnostics"]["0"]["fallbacks"] == 0

    client.post(f"/api/sessions/{body['session_id']}/close")


def test_invalid_ids_return_clear_http_errors() -> None:
    client = TestClient(create_app())

    bad_agent = client.post("/api/sessions", json={"player0_agent": "missing"})
    assert bad_agent.status_code == 400
    assert "unknown agent" in bad_agent.json()["detail"]

    bad_map = client.post("/api/sessions", json={"map_id": "random_sparse"})
    assert bad_map.status_code == 400
    assert "unknown map_id" in bad_map.json()["detail"]

    missing_session = client.get("/api/sessions/not-a-session")
    assert missing_session.status_code == 404
    assert missing_session.json()["detail"] == "session not found"

from __future__ import annotations

from fastapi.testclient import TestClient

from strategic_agent_arena.web.app import create_app


def test_create_session_returns_graph_state_and_agents() -> None:
    client = TestClient(create_app())

    agents_response = client.get("/api/agents")
    assert agents_response.status_code == 200
    agents_body = agents_response.json()
    assert {agent["id"] for agent in agents_body["agents"]} == {
        "random",
        "greedy_expansion",
    }
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
    assert body["status"]["round_index"] == 1
    assert body["status"]["current_player"] == 0
    assert len(body["graph"]["nodes"]) == 21
    assert body["graph"]["edges"]
    assert body["legal_actions"]
    assert body["action_log"] == []


def test_index_uses_versioned_static_assets() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "/static/app.js?v=20260508-fixed-maps" in response.text
    assert "/static/styles.css?v=20260508-fixed-maps" in response.text


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

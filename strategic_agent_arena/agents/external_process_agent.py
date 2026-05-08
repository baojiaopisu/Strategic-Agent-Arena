"""External process agent adapter using the JSON Lines contract."""

from __future__ import annotations

import json
import queue
import subprocess
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from strategic_agent_arena.agents.base import BaseAgent
from strategic_agent_arena.agents.protocol import PROTOCOL_VERSION, serialize_observation
from strategic_agent_arena.envs.supply_graph_war.actions import Action
from strategic_agent_arena.envs.supply_graph_war.env import SupplyGraphWarEnv


class ExternalProcessError(RuntimeError):
    """Raised when an external process cannot be started or initialized."""


class ExternalProcessAgent(BaseAgent):
    """Agent adapter for JSONL-speaking external executables."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        agent_id: str,
        name: str | None = None,
        protocol: str = PROTOCOL_VERSION,
        timeout_ms: int = 200,
        startup_timeout_ms: int = 1_000,
        cwd: str | Path | None = None,
    ) -> None:
        super().__init__(name=name)
        if not command:
            raise ValueError("external agent command must not be empty")
        self.agent_id = agent_id
        self.command = tuple(command)
        self.protocol = protocol
        self.timeout_s = timeout_ms / 1000
        self.startup_timeout_s = startup_timeout_ms / 1000
        self.cwd = Path(cwd).resolve() if cwd is not None else None
        self.diagnostics: dict[str, Any] = {
            "fallbacks": 0,
            "timeouts": 0,
            "invalid_responses": 0,
            "crashes": 0,
            "last_error": None,
        }
        self._process: subprocess.Popen[str] | None = None
        self._stdout_queue: queue.Queue[str | None] = queue.Queue()
        self._stderr_lines: list[str] = []
        self._request_counter = 0
        self._game_active = False

    def on_game_start(self, env: SupplyGraphWarEnv, player: int) -> None:
        self._ensure_started()
        self._send(
            {
                "type": "game_start",
                "protocol": self.protocol,
                "agent_id": self.agent_id,
                "player_id": player,
                "map_id": env.map_id,
                "seed": None,
            }
        )
        self._game_active = True

    def select_action(self, env: SupplyGraphWarEnv, player: int) -> Action:
        legal_actions = env.legal_actions(player)
        fallback = _pass_action(legal_actions)
        if not self._ensure_started_for_action():
            return fallback

        self._request_counter += 1
        request_id = f"{self.agent_id}-{self._request_counter}"
        try:
            self._drain_stdout_queue()
            self._send(serialize_observation(env, player, request_id, legal_actions))
            response = self._read_json_line(self.timeout_s)
            action_index = self._parse_action_index(response, request_id, len(legal_actions))
            return legal_actions[action_index]
        except Exception as exc:  # noqa: BLE001 - all external failures fall back.
            self._record_fallback(exc)
            return fallback

    def on_game_end(
        self,
        env: SupplyGraphWarEnv,
        player: int,
        result: dict[str, Any] | None = None,
    ) -> None:
        if self._process is None or not self._game_active:
            return
        payload = {
            "type": "game_end",
            "protocol": self.protocol,
            "agent_id": self.agent_id,
            "player_id": player,
            "winner": env.winner(),
            "result": result or {},
        }
        try:
            self._send(payload)
        except BrokenPipeError:
            self.diagnostics["crashes"] += 1
        finally:
            self._game_active = False

    def close(self) -> None:
        process = self._process
        if process is None:
            return

        if process.poll() is None:
            try:
                self._send(
                    {
                        "type": "shutdown",
                        "protocol": self.protocol,
                        "agent_id": self.agent_id,
                    }
                )
            except BrokenPipeError:
                pass

            try:
                process.terminate()
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=0.5)

        self._process = None
        self._game_active = False

    def _ensure_started_for_action(self) -> bool:
        try:
            self._ensure_started()
        except ExternalProcessError as exc:
            self._record_fallback(exc)
            return False
        return True

    def _ensure_started(self) -> None:
        if self.protocol != PROTOCOL_VERSION:
            raise ExternalProcessError(f"unsupported protocol: {self.protocol}")

        if self._process is not None and self._process.poll() is None:
            return

        try:
            self._process = subprocess.Popen(
                list(self.command),
                cwd=str(self.cwd) if self.cwd is not None else None,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise ExternalProcessError(f"failed to start external agent: {exc}") from exc

        self._stdout_queue = queue.Queue()
        self._stderr_lines = []
        assert self._process.stdout is not None
        assert self._process.stderr is not None
        threading.Thread(
            target=self._read_stdout,
            args=(self._process.stdout,),
            daemon=True,
        ).start()
        threading.Thread(
            target=self._read_stderr,
            args=(self._process.stderr,),
            daemon=True,
        ).start()

        self._send(
            {
                "type": "init",
                "protocol": self.protocol,
                "agent_id": self.agent_id,
            }
        )
        response = self._read_json_line(self.startup_timeout_s)
        if response.get("type") != "ready":
            self.close()
            raise ExternalProcessError("external agent did not reply with ready")

    def _send(self, payload: dict[str, Any]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise BrokenPipeError("external agent process is not running")
        if process.poll() is not None:
            raise BrokenPipeError("external agent process exited")

        process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def _read_json_line(self, timeout_s: float) -> dict[str, Any]:
        try:
            line = self._stdout_queue.get(timeout=timeout_s)
        except queue.Empty as exc:
            self.diagnostics["timeouts"] += 1
            raise TimeoutError("external agent response timed out") from exc

        if line is None:
            self.diagnostics["crashes"] += 1
            raise BrokenPipeError("external agent process exited")

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            self.diagnostics["invalid_responses"] += 1
            raise ValueError(f"external agent returned invalid JSON: {line!r}") from exc
        if not isinstance(payload, dict):
            self.diagnostics["invalid_responses"] += 1
            raise ValueError("external agent response must be a JSON object")
        return payload

    def _parse_action_index(
        self,
        response: dict[str, Any],
        request_id: str,
        legal_action_count: int,
    ) -> int:
        if response.get("type") != "action":
            self.diagnostics["invalid_responses"] += 1
            raise ValueError("external agent response type must be action")
        if response.get("request_id") != request_id:
            self.diagnostics["invalid_responses"] += 1
            raise ValueError("external agent response request_id mismatch")

        action_index = response.get("action_index")
        if not isinstance(action_index, int):
            self.diagnostics["invalid_responses"] += 1
            raise ValueError("external agent action_index must be an integer")
        if action_index < 0 or action_index >= legal_action_count:
            self.diagnostics["invalid_responses"] += 1
            raise ValueError("external agent action_index is outside legal action range")
        return action_index

    def _record_fallback(self, exc: Exception) -> None:
        self.diagnostics["fallbacks"] += 1
        self.diagnostics["last_error"] = str(exc)

    def _drain_stdout_queue(self) -> None:
        while True:
            try:
                self._stdout_queue.get_nowait()
            except queue.Empty:
                return

    def _read_stdout(self, stream: Any) -> None:
        try:
            for line in stream:
                self._stdout_queue.put(line.strip())
        finally:
            self._stdout_queue.put(None)

    def _read_stderr(self, stream: Any) -> None:
        for line in stream:
            self._stderr_lines.append(line.rstrip())
            if len(self._stderr_lines) > 200:
                del self._stderr_lines[:50]


def _pass_action(actions: list[Action]) -> Action:
    for action in actions:
        if action.kind.value == "PASS":
            return action
    return actions[-1]

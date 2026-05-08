"""Environment API for Supply Graph War."""

from __future__ import annotations

import math

import numpy as np

from strategic_agent_arena.envs.supply_graph_war.actions import (
    PASS_ACTION,
    VALID_RATIOS,
    Action,
    ActionKind,
)
from strategic_agent_arena.envs.supply_graph_war.mapgen import generate_map
from strategic_agent_arena.envs.supply_graph_war.maps import DEFAULT_MAP_ID
from strategic_agent_arena.envs.supply_graph_war.rules import (
    MAX_DEFENSE,
    MAX_PRODUCTION,
    NEUTRAL,
    apply_production,
    calculate_sent_units,
    compute_supply,
    current_player_for_turn,
    enemy,
    score_state,
)
from strategic_agent_arena.envs.supply_graph_war.state import SupplyGraphWarState


class SupplyGraphWarEnv:
    """Minimal deterministic simulator for Supply Graph War."""

    def __init__(self, max_rounds: int = 80) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        self.max_rounds = max_rounds
        self.rng = np.random.default_rng()
        self.state: SupplyGraphWarState | None = None
        self._terminal = False
        self._winner: int | None = None
        self._captured_base = False
        self._production_pending = True
        self.map_id = DEFAULT_MAP_ID
        self.map_name = ""
        self.map_description = ""
        self.map_positions: dict[int, tuple[float, float]] = {}
        self.map_mirror: dict[int, int] = {}

    def reset(
        self,
        seed: int | None = None,
        map_id: str = DEFAULT_MAP_ID,
        first_player: int = 0,
    ) -> "SupplyGraphWarEnv":
        if first_player not in (0, 1):
            raise ValueError(f"invalid first player: {first_player}")
        self.rng = np.random.default_rng(seed)
        map_spec = generate_map(map_id=map_id)
        supplied = compute_supply(map_spec.graph, map_spec.owners, map_spec.bases)
        self.state = SupplyGraphWarState(
            graph=map_spec.graph,
            owners=map_spec.owners,
            units=map_spec.units,
            production=map_spec.production,
            defense=map_spec.defense,
            bases=map_spec.bases,
            supplied=supplied,
            round_index=1,
            turn_index=0,
            first_player=first_player,
        )
        self._terminal = False
        self._winner = None
        self._captured_base = False
        self._production_pending = True
        self.map_id = map_spec.map_id
        self.map_name = map_spec.map_name
        self.map_description = map_spec.description
        self.map_positions = dict(map_spec.positions)
        self.map_mirror = dict(map_spec.mirror)
        return self

    @property
    def current_player(self) -> int:
        state = self._require_state()
        return current_player_for_turn(state.round_index, state.turn_index, state.first_player)

    @property
    def round_index(self) -> int:
        return self._require_state().round_index

    @property
    def captured_base(self) -> bool:
        return self._captured_base

    def legal_actions(self, player: int) -> list[Action]:
        state = self._require_state()
        if self._terminal:
            return [PASS_ACTION]
        if player not in (0, 1):
            raise ValueError(f"invalid player: {player}")

        units = self._units_after_pending_production()
        actions: list[Action] = []

        for source in np.flatnonzero(state.owners == player):
            source = int(source)
            if units[source] > 1:
                for target in sorted(state.graph.neighbors(source)):
                    for ratio in VALID_RATIOS:
                        if calculate_sent_units(int(units[source]), ratio) > 0:
                            actions.append(Action.move_attack(source, int(target), ratio))

            if state.defense[source] < MAX_DEFENSE:
                actions.append(Action.fortify(source))

            if state.supplied[player, source] and state.production[source] < MAX_PRODUCTION:
                actions.append(Action.upgrade(source))

        actions.append(PASS_ACTION)
        return actions

    def step(self, action: Action) -> "SupplyGraphWarEnv":
        state = self._require_state()
        if self._terminal:
            raise RuntimeError("cannot step a terminal environment")

        player = self.current_player
        self._start_round_if_needed()
        self._validate_action(action, player)

        kind = self._kind(action)
        if kind == ActionKind.MOVE_ATTACK:
            self._apply_move_attack(player, int(action.source), int(action.target), float(action.ratio))
        elif kind == ActionKind.FORTIFY:
            state.defense[int(action.source)] += 1
        elif kind == ActionKind.UPGRADE:
            state.production[int(action.source)] += 1
        elif kind == ActionKind.PASS:
            pass
        else:
            raise ValueError(f"unsupported action kind: {kind}")

        if not self._terminal:
            self._advance_turn()
        return self

    def clone(self) -> "SupplyGraphWarEnv":
        clone = SupplyGraphWarEnv(max_rounds=self.max_rounds)
        clone.state = self._require_state().clone()
        clone._terminal = self._terminal
        clone._winner = self._winner
        clone._captured_base = self._captured_base
        clone._production_pending = self._production_pending
        clone.map_id = self.map_id
        clone.map_name = self.map_name
        clone.map_description = self.map_description
        clone.map_positions = dict(self.map_positions)
        clone.map_mirror = dict(self.map_mirror)
        clone.rng = np.random.default_rng()
        clone.rng.bit_generator.state = self.rng.bit_generator.state
        return clone

    def is_terminal(self) -> bool:
        return self._terminal

    def winner(self) -> int | None:
        if not self._terminal:
            return None
        return self._winner

    def score(self, player: int) -> int:
        return score_state(self._require_state(), player)

    def render_text(self) -> str:
        state = self._require_state()
        lines = [
            f"Round {state.round_index} | current_player={self.current_player} "
            f"| first_player={state.first_player} | pending_production={self._production_pending}",
            f"Bases: P0={state.bases[0]} P1={state.bases[1]}",
        ]

        live_supply = compute_supply(state.graph, state.owners, state.bases)
        for player in (0, 1):
            owned = state.owners == player
            lines.append(
                f"P{player}: owned={int(np.count_nonzero(owned))} "
                f"supplied={int(np.count_nonzero(live_supply[player] & owned))} "
                f"units={int(np.sum(state.units[owned]))} score={self.score(player)}"
            )

        lines.append("Nodes:")
        for node in range(state.n_nodes):
            owner = state.owners[node]
            owner_text = "N" if owner == NEUTRAL else f"P{owner}"
            supply_text = ""
            if owner in (0, 1):
                supply_text = " supplied" if live_supply[owner, node] else " unsupplied"
            lines.append(
                f"  {node:02d}: owner={owner_text}{supply_text} units={int(state.units[node])} "
                f"prod={int(state.production[node])} def={int(state.defense[node])} "
                f"neighbors={sorted(state.graph.neighbors(node))}"
            )
        return "\n".join(lines)

    def _require_state(self) -> SupplyGraphWarState:
        if self.state is None:
            raise RuntimeError("environment has not been reset")
        return self.state

    def _units_after_pending_production(self) -> np.ndarray:
        state = self._require_state()
        units = state.units.copy()
        if not self._production_pending:
            return units

        preview = state.clone()
        apply_production(preview)
        return preview.units

    def _start_round_if_needed(self) -> None:
        if not self._production_pending:
            return
        apply_production(self._require_state())
        self._production_pending = False

    def _validate_action(self, action: Action, player: int) -> None:
        state = self._require_state()
        kind = self._kind(action)

        if kind == ActionKind.PASS:
            return

        if action.source is None:
            raise ValueError(f"{kind.value} requires a source node")
        source = int(action.source)
        if source < 0 or source >= state.n_nodes:
            raise ValueError(f"invalid source node: {source}")
        if state.owners[source] != player:
            raise ValueError(f"source node {source} is not owned by player {player}")

        if kind == ActionKind.FORTIFY:
            if state.defense[source] >= MAX_DEFENSE:
                raise ValueError(f"node {source} is already at max defense")
            return

        if kind == ActionKind.UPGRADE:
            if not state.supplied[player, source]:
                raise ValueError(f"node {source} is not supplied")
            if state.production[source] >= MAX_PRODUCTION:
                raise ValueError(f"node {source} is already at max production")
            return

        if kind != ActionKind.MOVE_ATTACK:
            raise ValueError(f"unsupported action kind: {kind}")

        if action.target is None:
            raise ValueError("MOVE_ATTACK requires a target node")
        if action.ratio is None:
            raise ValueError("MOVE_ATTACK requires a ratio")
        target = int(action.target)
        if target < 0 or target >= state.n_nodes:
            raise ValueError(f"invalid target node: {target}")
        if not state.graph.has_edge(source, target):
            raise ValueError(f"nodes {source} and {target} are not adjacent")
        if not any(math.isclose(float(action.ratio), ratio) for ratio in VALID_RATIOS):
            raise ValueError(f"invalid move ratio: {action.ratio}")
        if state.units[source] <= 1:
            raise ValueError(f"node {source} does not have enough units to move or attack")
        if calculate_sent_units(int(state.units[source]), float(action.ratio)) <= 0:
            raise ValueError("MOVE_ATTACK would send no units")

    def _apply_move_attack(self, player: int, source: int, target: int, ratio: float) -> None:
        state = self._require_state()
        sent_units = calculate_sent_units(int(state.units[source]), ratio)
        state.units[source] -= sent_units

        if state.owners[target] == player:
            state.units[target] += sent_units
            return

        attack_power = sent_units
        if not state.supplied[player, source]:
            attack_power = math.floor(attack_power * 0.75)

        defense_power = int(state.units[target] + 2 * state.defense[target])
        if attack_power > defense_power:
            state.owners[target] = player
            state.units[target] = attack_power - defense_power
            state.defense[target] = 0
            if target == state.bases[enemy(player)]:
                self._terminal = True
                self._winner = player
                self._captured_base = True
        else:
            state.units[target] = max(0, int(state.units[target] - attack_power))

    def _advance_turn(self) -> None:
        state = self._require_state()
        if state.turn_index == 0:
            state.turn_index = 1
            return

        state.supplied = compute_supply(state.graph, state.owners, state.bases)
        if state.round_index >= self.max_rounds:
            self._terminal = True
            score_0 = self.score(0)
            score_1 = self.score(1)
            if score_0 > score_1:
                self._winner = 0
            elif score_1 > score_0:
                self._winner = 1
            else:
                self._winner = None
            return

        state.round_index += 1
        state.turn_index = 0
        self._production_pending = True

    @staticmethod
    def _kind(action: Action) -> ActionKind:
        return action.kind if isinstance(action.kind, ActionKind) else ActionKind(action.kind)

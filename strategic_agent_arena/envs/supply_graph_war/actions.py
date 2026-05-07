"""Action definitions for Supply Graph War."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

VALID_RATIOS: tuple[float, ...] = (0.25, 0.50, 0.75, 1.00)


class ActionKind(str, Enum):
    """Supported action kinds."""

    MOVE_ATTACK = "MOVE_ATTACK"
    FORTIFY = "FORTIFY"
    UPGRADE = "UPGRADE"
    PASS = "PASS"


@dataclass(frozen=True, slots=True)
class Action:
    """A single player action.

    MOVE_ATTACK uses source, target, and ratio. FORTIFY and UPGRADE use source only.
    PASS uses no fields.
    """

    kind: ActionKind
    source: int | None = None
    target: int | None = None
    ratio: float | None = None

    @staticmethod
    def move_attack(source: int, target: int, ratio: float) -> "Action":
        return Action(ActionKind.MOVE_ATTACK, source=source, target=target, ratio=ratio)

    @staticmethod
    def fortify(source: int) -> "Action":
        return Action(ActionKind.FORTIFY, source=source)

    @staticmethod
    def upgrade(source: int) -> "Action":
        return Action(ActionKind.UPGRADE, source=source)

    @staticmethod
    def pass_turn() -> "Action":
        return Action(ActionKind.PASS)

    def __str__(self) -> str:
        if self.kind == ActionKind.MOVE_ATTACK:
            return f"MOVE_ATTACK({self.source}->{self.target}, ratio={self.ratio:.2f})"
        if self.kind in {ActionKind.FORTIFY, ActionKind.UPGRADE}:
            return f"{self.kind.value}({self.source})"
        return "PASS"


PASS_ACTION = Action.pass_turn()


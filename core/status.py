"""Shared status labels and helpers for all data types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StatusLabel(str, Enum):
    GOOD = "good"
    INTERMITTENT = "intermittent"
    BAD = "bad"
    NO_DATA = "no_data"
    COMPROMISED = "compromised"
    ERROR = "error"


STATUS_COLORS = {
    StatusLabel.GOOD: "#28a745",
    StatusLabel.INTERMITTENT: "#ffc107",
    StatusLabel.BAD: "#fd7e14",
    StatusLabel.NO_DATA: "#dc3545",
    StatusLabel.COMPROMISED: "#6f42c1",
    StatusLabel.ERROR: "#6c757d",
}

STATUS_ICONS = {
    StatusLabel.GOOD: "✓",
    StatusLabel.INTERMITTENT: "~",
    StatusLabel.BAD: "⚠",
    StatusLabel.NO_DATA: "✗",
    StatusLabel.COMPROMISED: "⊘",
    StatusLabel.ERROR: "!",
}


@dataclass(frozen=True)
class EntityStatus:
    label: StatusLabel
    message: str = ""

    @property
    def color(self) -> str:
        return STATUS_COLORS.get(self.label, STATUS_COLORS[StatusLabel.ERROR])

    @property
    def icon(self) -> str:
        return STATUS_ICONS.get(self.label, STATUS_ICONS[StatusLabel.ERROR])

    @property
    def display(self) -> str:
        return self.label.value.replace("_", " ").title()

    def to_dict(self) -> dict:
        return {
            "label": self.label.value,
            "display": self.display,
            "message": self.message,
            "color": self.color,
            "icon": self.icon,
        }


def worst_status(statuses: list[EntityStatus]) -> EntityStatus:
    priority = [
        StatusLabel.ERROR,
        StatusLabel.NO_DATA,
        StatusLabel.COMPROMISED,
        StatusLabel.BAD,
        StatusLabel.INTERMITTENT,
        StatusLabel.GOOD,
    ]
    rank = {s: i for i, s in enumerate(priority)}
    if not statuses:
        return EntityStatus(StatusLabel.NO_DATA, "No devices")
    return min(statuses, key=lambda s: rank.get(s.label, len(priority)))

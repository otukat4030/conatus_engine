"""Core data models for the provisional Conatus Engine."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Affect(str, Enum):
    """A provisional affect classified from a change in power."""

    JOY = "joy"
    SADNESS = "sadness"
    NEUTRAL = "neutral"


class Mode(str, Enum):
    """Whether an event is active or passive in the current model."""

    ACTIVE = "active"
    PASSIVE = "passive"


class CausalAdequacy(str, Enum):
    """Whether the result is sufficiently explained by the agent's own power."""

    ADEQUATE = "adequate"
    PARTIAL = "partial"


class IdeaAdequacy(str, Enum):
    """Whether the agent sufficiently understands the event's causes."""

    ADEQUATE = "adequate"
    INADEQUATE = "inadequate"


def _require_text(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} must not be empty")


def _require_finite(value: float, field_name: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be a finite number")


@dataclass(frozen=True)
class AgentState:
    """A person's state at one point in the simulation."""

    agent_id: str
    name: str
    power: float

    def __post_init__(self) -> None:
        _require_text(self.agent_id, "agent_id")
        _require_text(self.name, "name")
        _require_finite(self.power, "power")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary."""

        return {"agent_id": self.agent_id, "name": self.name, "power": self.power}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentState:
        """Restore an agent state from a dictionary."""

        return cls(
            agent_id=str(data["agent_id"]),
            name=str(data["name"]),
            power=float(data["power"]),
        )

    def to_json(self) -> str:
        """Serialize the state to a JSON string."""

        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str) -> AgentState:
        """Restore an agent state from a JSON string."""

        return cls.from_dict(json.loads(value))


@dataclass(frozen=True)
class WorldEvent:
    """An event that changes an agent's power in this provisional model."""

    event_id: str
    description: str
    power_delta: float
    causal_adequacy: CausalAdequacy
    idea_adequacy: IdeaAdequacy

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        _require_text(self.description, "description")
        _require_finite(self.power_delta, "power_delta")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary."""

        return {
            "event_id": self.event_id,
            "description": self.description,
            "power_delta": self.power_delta,
            "causal_adequacy": self.causal_adequacy.value,
            "idea_adequacy": self.idea_adequacy.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldEvent:
        """Restore a world event from a dictionary."""

        return cls(
            event_id=str(data["event_id"]),
            description=str(data["description"]),
            power_delta=float(data["power_delta"]),
            causal_adequacy=CausalAdequacy(data["causal_adequacy"]),
            idea_adequacy=IdeaAdequacy(data["idea_adequacy"]),
        )

    def to_json(self) -> str:
        """Serialize the event to a JSON string."""

        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str) -> WorldEvent:
        """Restore a world event from a JSON string."""

        return cls.from_dict(json.loads(value))


@dataclass(frozen=True)
class Derivation:
    """A single rule application in a transition trace."""

    rule_id: str
    premises: tuple[str, ...]
    conclusion: str
    explanation: str

    def __post_init__(self) -> None:
        _require_text(self.rule_id, "rule_id")
        _require_text(self.conclusion, "conclusion")
        _require_text(self.explanation, "explanation")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary."""

        return {
            "rule_id": self.rule_id,
            "premises": list(self.premises),
            "conclusion": self.conclusion,
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Derivation:
        """Restore a derivation from a dictionary."""

        return cls(
            rule_id=str(data["rule_id"]),
            premises=tuple(str(item) for item in data["premises"]),
            conclusion=str(data["conclusion"]),
            explanation=str(data["explanation"]),
        )


@dataclass(frozen=True)
class Transition:
    """The result of applying one world event to one agent state."""

    before: AgentState
    after: AgentState
    event: WorldEvent
    affect: Affect
    mode: Mode
    idea_adequacy: IdeaAdequacy
    derivations: tuple[Derivation, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary."""

        return {
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "event": self.event.to_dict(),
            "affect": self.affect.value,
            "mode": self.mode.value,
            "idea_adequacy": self.idea_adequacy.value,
            "derivations": [item.to_dict() for item in self.derivations],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transition:
        """Restore a transition from a dictionary."""

        return cls(
            before=AgentState.from_dict(data["before"]),
            after=AgentState.from_dict(data["after"]),
            event=WorldEvent.from_dict(data["event"]),
            affect=Affect(data["affect"]),
            mode=Mode(data["mode"]),
            idea_adequacy=IdeaAdequacy(data["idea_adequacy"]),
            derivations=tuple(
                Derivation.from_dict(item) for item in data["derivations"]
            ),
        )

    def to_json(self) -> str:
        """Serialize the transition to a JSON string."""

        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str) -> Transition:
        """Restore a transition from a JSON string."""

        return cls.from_dict(json.loads(value))

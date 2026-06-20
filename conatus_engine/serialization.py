"""JSON helpers for Conatus Engine models."""

from __future__ import annotations

from typing import Any, TypeVar

from conatus_engine.models import AgentState, Transition, WorldEvent

SerializableModel = TypeVar("SerializableModel", AgentState, WorldEvent, Transition)


def to_dict(model: AgentState | WorldEvent | Transition) -> dict[str, Any]:
    """Convert a supported model to a JSON-compatible dictionary."""

    return model.to_dict()


def to_json(model: AgentState | WorldEvent | Transition) -> str:
    """Convert a supported model to a JSON string."""

    return model.to_json()


def agent_state_from_json(value: str) -> AgentState:
    """Restore an agent state from JSON."""

    return AgentState.from_json(value)


def world_event_from_json(value: str) -> WorldEvent:
    """Restore a world event from JSON."""

    return WorldEvent.from_json(value)


def transition_from_json(value: str) -> Transition:
    """Restore a transition from JSON."""

    return Transition.from_json(value)

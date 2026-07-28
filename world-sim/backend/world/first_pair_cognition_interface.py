"""Phase 10FN — First Pair Cognition Interface.

Abstract base classes defining the cognitive operations available to First Pair
agents. This module establishes the pure, testable interface that any model
backend (or deterministic stub) must implement. It deliberately excludes all
runtime, persistence, network, and world-state mutation concerns.

Implementations must be pure functions of their inputs and must not perform
I/O, mutation, or external calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentContext:
    """Read-only context provided to the agent at each heartbeat."""

    agent_id: str
    canonical_name: str
    canonical_ref: str
    heartbeat_number: int
    position: str
    observation: dict
    memory: list
    goals: list
    unanswered_questions: list
    world_public_objects: dict
    habitat_allowed_tiles: list
    habitat_movement_allowed: bool
    previous_action: dict | None
    timestamp_utc: str
    # Dynamic pair identity (not hard-coded in model module)
    other_agent_id: str = ""
    other_agent_name: str = ""
    other_agent_ref: str = ""
    # Answered question history for this agent
    answered_questions: list = field(default_factory=list)
    # Dynamic context fields for movement grant era
    available_moves: list = field(default_factory=list)
    current_runtime_capabilities: list = field(default_factory=list)
    current_tile_occupants: list = field(default_factory=list)
    visible_public_messages: list = field(default_factory=list)
    relevant_human_answers: list = field(default_factory=list)
    # Bounded memory selection fields
    selected_private_memories: list = field(default_factory=list)
    derived_memory_summaries: list = field(default_factory=list)
    public_relationship_events: list = field(default_factory=list)
    memory_selection_manifest: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CognitionOutput:
    """Structured output from a single cognition cycle."""

    action: dict | None
    memory_write: list | None
    goal_updates: list | None
    questions_raised: list | None
    internal_reasoning: str
    confidence: float
    observation_summary: str = ""
    decision_summary: str = ""
    uncertainty: str = ""


class CognitionBackend(ABC):
    """Abstract base class for First Pair cognition backends.

    All methods are pure functions of their inputs. No I/O, mutation, network,
    or external state access is permitted. Implementations must be deterministic
    for given inputs (or provide a seed for stochastic behavior).

    A concrete implementation is provided by the test stub in
    `first_pair_cognition_stub.py` and by the model-backed implementation in
    `first_pair_cognition_model.py`.
    """

    @abstractmethod
    def observe_and_orient(self, context: AgentContext) -> CognitionOutput:
        """Single cognition cycle: observe, orient, decide, plan.

        Args:
            context: Complete read-only snapshot of agent state and world view.

        Returns:
            CognitionOutput containing the chosen action (if any), memory
            writes, goal updates, questions for human, and internal reasoning.
        """
        ...

    @abstractmethod
    def propose_goal(self, context: AgentContext) -> dict | None:
        """Propose a new goal based on current state and observations.

        Returns a goal dict or None if no new goal is warranted.
        """
        ...

    @abstractmethod
    def evaluate_questions(self, context: AgentContext) -> list[dict]:
        """Evaluate whether to raise questions for human assistance.

        Returns a list of question dicts with fields:
        - question_id: str
        - question: str
        - reason_for_asking: str
        - related_goal_id: str | None
        - requested_human_capability: str
        - urgency: str ("low" | "medium" | "high")
        """
        ...

    @abstractmethod
    def reflect_on_outcome(
        self,
        context: AgentContext,
        previous_action: dict | None,
        outcome: dict,
    ) -> str:
        """Produce a brief internal reflection on the outcome of the last action.

        Returns a reasoning string for memory storage.
        """
        ...


@dataclass(frozen=True)
class ModelBackendConfig:
    """Configuration for model-backed cognition."""

    model_name: str
    temperature: float = 0.3
    max_tokens: int = 2048
    system_prompt: str | None = None
    seed: int | None = None


class CognitiveCycle:
    """Orchestrates a single deterministic cognitive cycle for an agent.

    This class composes the cognition backend with the persistence layer and
    world interface. It handles the mechanical flow; the backend handles the
    actual reasoning.
    """

    def __init__(self, backend: CognitionBackend):
        self._backend = backend

    def run_cycle(self, context: AgentContext) -> CognitionOutput:
        """Execute one complete cognition cycle."""
        return self._backend.observe_and_orient(context)

    def maybe_propose_goal(self, context: AgentContext) -> dict | None:
        return self._backend.propose_goal(context)

    def maybe_raise_questions(self, context: AgentContext) -> list[dict]:
        return self._backend.evaluate_questions(context)

    def reflect(self, context: AgentContext, previous_action: dict | None, outcome: dict) -> str:
        return self._backend.reflect_on_outcome(context, previous_action, outcome)
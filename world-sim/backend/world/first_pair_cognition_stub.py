"""Phase 10FO — First Pair Cognition Stub Implementation.

Deterministic, testable cognition backend for First Pair agents. This stub
provides predictable, rule-based behavior suitable for integration testing
and CI. It implements the CognitionBackend interface without any external
dependencies.
"""

from __future__ import annotations

import hashlib
from typing import Any

from backend.world.first_pair_cognition_interface import (
    AgentContext,
    CognitionBackend,
    CognitionOutput,
)


class DeterministicStubBackend(CognitionBackend):
    """Deterministic, rule-based cognition backend for testing.

    Behavior:
    - Alternates between moving, observing, and proposing goals
    - Raises questions when goals cannot be resolved locally
    - Maintains internal state via context-only reasoning
    """

    def __init__(self, seed: int | None = None):
        self._cycle_count = 0
        self._seed = seed or 0

    def _deterministic_choice(self, context: AgentContext, options: list[Any]) -> Any:
        """Make a deterministic choice based on context hash."""
        h = hashlib.sha256(f"{context.agent_id}{context.heartbeat_number}{self._seed}".encode()).hexdigest()
        idx = int(h, 16) % len(options)
        return options[idx]

    def observe_and_orient(self, context: AgentContext) -> CognitionOutput:
        self._cycle_count += 1

        # Determine available tiles for movement
        allowed_tiles = context.habitat_allowed_tiles
        current_pos = context.position
        can_move = context.habitat_movement_allowed

        action = None
        memory_write = None
        goal_updates = None
        questions_raised = None

        # Simple state machine: if no goals, propose one; else act on it
        if not context.goals:
            # Propose a goal: explore the other tile
            other_tiles = [t for t in allowed_tiles if t != current_pos]
            if other_tiles:
                target = other_tiles[0]
                goal_updates = [{
                    "goal_id": f"goal-{context.agent_id}-{context.heartbeat_number}",
                    "agent_id": context.agent_id,
                    "description": f"Explore {target}",
                    "status": "active",
                    "created_heartbeat": context.heartbeat_number,
                }]
        elif can_move and allowed_tiles:
            # Try to move toward goal
            active_goals = [g for g in context.goals if g.get("status") == "active"]
            if active_goals:
                goal = active_goals[0]
                # Extract target tile from goal description
                target = None
                for t in allowed_tiles:
                    if t in goal.get("description", ""):
                        target = t
                        break
                if target and target != current_pos:
                    action = {
                        "action_type": "move",
                        "target_tile": target,
                        "reason": f"Pursuing goal: {goal.get('description')}",
                    }
                    goal_updates = [{
                        "goal_id": goal.get("goal_id"),
                        "agent_id": context.agent_id,
                        "description": goal.get("description"),
                        "status": "in_progress",
                        "created_heartbeat": goal.get("created_heartbeat", context.heartbeat_number),
                    }]

        reasoning = f"Cycle {self._cycle_count} for {context.canonical_name}: evaluated {len(context.goals)} goals, can_move={can_move}"

        return CognitionOutput(
            action=action,
            memory_write=memory_write,
            goal_updates=goal_updates,
            questions_raised=questions_raised,
            internal_reasoning=reasoning,
            confidence=0.8,
        )

    def propose_goal(self, context: AgentContext) -> dict | None:
        if not context.goals:
            allowed = context.habitat_allowed_tiles
            current = context.position
            other = [t for t in allowed if t != current]
            if other:
                return {
                    "goal_id": f"goal-{context.agent_id}-{context.heartbeat_number}",
                    "agent_id": context.agent_id,
                    "description": f"Explore {other[0]}",
                    "status": "active",
                    "created_heartbeat": context.heartbeat_number,
                }
        return None

    def evaluate_questions(self, context: AgentContext) -> list[dict]:
        questions = []
        # Raise a question if stuck with no movement allowed and no goals
        if not context.habitat_movement_allowed and not context.goals:
            questions.append({
                "question_id": f"q-{context.agent_id}-{context.heartbeat_number}-{'d' + hashlib.sha256(f'{context.agent_id}{context.heartbeat_number}movement-stuck'.encode()).hexdigest()[:7]}",
                "question": f"Movement is currently disabled. May I request permission to enable movement for exploration?",
                "reason_for_asking": "Cannot pursue exploration goals while movement is prohibited by habitat boundary.",
                "related_goal_id": None,
                "requested_human_capability": "modify_habitat_movement_allowed",
                "urgency": "low",
            })
        return questions

    def reflect_on_outcome(self, context: AgentContext, previous_action: dict | None, outcome: dict) -> str:
        if previous_action is None:
            return f"No previous action to reflect on. Outcome: {outcome.get('status', 'unknown')}"
        action_type = previous_action.get("action_type", "unknown")
        success = outcome.get("status") == "success"
        return f"Action '{action_type}' {'succeeded' if success else 'failed'}. Outcome detail: {outcome}"


class AlternatingStubBackend(CognitionBackend):
    """Stub that alternates behavior between Adam and Eve for diverse test coverage."""

    def __init__(self, agent_ref: str):
        self._agent_ref = agent_ref
        self._cycle = 0

    def observe_and_orient(self, context: AgentContext) -> CognitionOutput:
        self._cycle += 1

        if self._agent_ref == "east_adam":
            return self._adam_cycle(context)
        else:
            return self._eve_cycle(context)

    def _adam_cycle(self, context: AgentContext) -> CognitionOutput:
        # Adam: methodical explorer, proposes goals, asks for permissions
        if not context.goals:
            return CognitionOutput(
                action=None,
                memory_write=[{"type": "observation", "content": "Initial position noted"}],
                goal_updates=[{
                    "goal_id": "adam-goal-1",
                    "agent_id": context.agent_id,
                    "description": "Map local habitat boundaries",
                    "status": "active",
                    "created_heartbeat": context.heartbeat_number,
                }],
                questions_raised=[],
                internal_reasoning="First cycle: establishing baseline goal to map habitat.",
                confidence=0.9,
            )
        elif not context.habitat_movement_allowed:
            return CognitionOutput(
                action=None,
                memory_write=[{"type": "reflection", "content": "Movement disabled, requesting permission"}],
                goal_updates=None,
                questions_raised=[{
                    "question_id": f"adam-q-{context.heartbeat_number}",
                    "question": "May I have movement enabled to map the habitat?",
                    "reason_for_asking": "Cannot explore without movement permission.",
                    "related_goal_id": "adam-goal-1",
                    "requested_human_capability": "modify_habitat_movement_allowed",
                    "urgency": "medium",
                }],
                internal_reasoning="Second+ cycle: blocked by movement restriction, raising question.",
                confidence=0.8,
            )
        else:
            return CognitionOutput(
                action=None,
                memory_write=[{"type": "observation", "content": f"Cycle {self._cycle} complete"}],
                goal_updates=None,
                questions_raised=None,
                internal_reasoning=f"Cognitive cycle {context.heartbeat_number}.",
                confidence=0.5,
            )

    def _eve_cycle(self, context: AgentContext) -> CognitionOutput:
        # Eve: reflective observer, builds memory, synthesizes
        if not context.goals:
            return CognitionOutput(
                action=None,
                memory_write=[{"type": "observation", "content": "Initial observation recorded"}],
                goal_updates=[{
                    "goal_id": "eve-goal-1",
                    "agent_id": context.agent_id,
                    "description": "Synthesize observations into memory patterns",
                    "status": "active",
                    "created_heartbeat": context.heartbeat_number,
                }],
                questions_raised=[],
                internal_reasoning="First cycle: establishing synthesis goal.",
                confidence=0.9,
            )
        elif context.heartbeat_number == 2:
            return CognitionOutput(
                action={
                    "action_type": "create_public_object",
                    "object_id": "eve-marker-stone-1",
                    "object_type": "stone_marker",
                    "description": "A small stone placed at the starting position to mark Eve's presence.",
                    "tile_id": context.position,
                },
                memory_write=[{"type": "action", "content": "Placed public stone marker"}],
                goal_updates=None,
                questions_raised=None,
                internal_reasoning="Second heartbeat: creating a public object to establish agent presence.",
                confidence=0.9,
            )
        else:
            return CognitionOutput(
                action=None,
                memory_write=[{"type": "synthesis", "content": f"Continuing synthesis at heartbeat {context.heartbeat_number}"}],
                goal_updates=None,
                questions_raised=None,
                internal_reasoning=f"Heartbeat {context.heartbeat_number}: continuing synthesis.",
                confidence=0.7,
            )

    def propose_goal(self, context: AgentContext) -> dict | None:
        return None  # Goals proposed in observe_and_orient

    def evaluate_questions(self, context: AgentContext) -> list[dict]:
        return []  # Questions raised in observe_and_orient

    def reflect_on_outcome(self, context: AgentContext, previous_action: dict | None, outcome: dict) -> str:
        return f"Reflection on {previous_action}: {outcome}"
"""Focused tests for movement-grant prompt truthfulness."""

from __future__ import annotations

from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import build_system_prompt


class TestSystemPromptMovementGrant:
    def test_no_capability_no_moves_no_false_grant_claim(self):
        ctx = AgentContext(
            agent_id="genesis-agent-test-adam-0000000000000000000000000000000000000000000000000000",
            canonical_name="Adam",
            canonical_ref="east_adam",
            heartbeat_number=1,
            position="tile-alpha",
            observation={"tile_id": "tile-alpha", "visible_tiles": ["tile-alpha"], "objects_here": []},
            memory=[],
            goals=[],
            unanswered_questions=[],
            world_public_objects={},
            habitat_allowed_tiles=["tile-alpha"],
            habitat_movement_allowed=False,
            previous_action=None,
            timestamp_utc="2026-07-27T12:00:00Z",
            other_agent_id="",
            other_agent_name="",
            other_agent_ref="",
            answered_questions=[],
            available_moves=[],
            current_runtime_capabilities=[],
        )
        prompt = build_system_prompt(ctx)
        assert "superseded" not in prompt
        assert "runtime movement grant" not in prompt.lower() or "no active runtime movement grant" in prompt.lower()

    def test_no_capability_no_moves_clear_no_grant(self):
        ctx = AgentContext(
            agent_id="genesis-agent-test-adam-0000000000000000000000000000000000000000000000000000",
            canonical_name="Adam",
            canonical_ref="east_adam",
            heartbeat_number=1,
            position="tile-alpha",
            observation={"tile_id": "tile-alpha", "visible_tiles": ["tile-alpha"], "objects_here": []},
            memory=[],
            goals=[],
            unanswered_questions=[],
            world_public_objects={},
            habitat_allowed_tiles=["tile-alpha"],
            habitat_movement_allowed=False,
            previous_action=None,
            timestamp_utc="2026-07-27T12:00:00Z",
            other_agent_id="",
            other_agent_name="",
            other_agent_ref="",
            answered_questions=[],
            available_moves=[],
            current_runtime_capabilities=[],
        )
        prompt = build_system_prompt(ctx)
        assert "No active runtime movement grant" in prompt or "no active runtime movement grant" in prompt

    def test_active_capability_with_moves(self):
        ctx = AgentContext(
            agent_id="genesis-agent-test-adam-0000000000000000000000000000000000000000000000000000",
            canonical_name="Adam",
            canonical_ref="east_adam",
            heartbeat_number=1,
            position="tile-alpha",
            observation={"tile_id": "tile-alpha", "visible_tiles": ["tile-alpha"], "objects_here": []},
            memory=[],
            goals=[],
            unanswered_questions=[],
            world_public_objects={},
            habitat_allowed_tiles=["tile-alpha"],
            habitat_movement_allowed=False,
            previous_action=None,
            timestamp_utc="2026-07-27T12:00:00Z",
            other_agent_id="",
            other_agent_name="",
            other_agent_ref="",
            answered_questions=[],
            available_moves=["tile-beta"],
            current_runtime_capabilities=["movement_grant"],
        )
        prompt = build_system_prompt(ctx)
        assert "bounded runtime movement grant is active" in prompt or "runtime movement grant is active" in prompt
        assert "tile-beta" in prompt
        assert "only to tiles listed in available_moves" in prompt or "only to tiles listed" in prompt

    def test_active_capability_no_moves(self):
        ctx = AgentContext(
            agent_id="genesis-agent-test-adam-0000000000000000000000000000000000000000000000000000",
            canonical_name="Adam",
            canonical_ref="east_adam",
            heartbeat_number=1,
            position="tile-alpha",
            observation={"tile_id": "tile-alpha", "visible_tiles": ["tile-alpha"], "objects_here": []},
            memory=[],
            goals=[],
            unanswered_questions=[],
            world_public_objects={},
            habitat_allowed_tiles=["tile-alpha"],
            habitat_movement_allowed=False,
            previous_action=None,
            timestamp_utc="2026-07-27T12:00:00Z",
            other_agent_id="",
            other_agent_name="",
            other_agent_ref="",
            answered_questions=[],
            available_moves=[],
            current_runtime_capabilities=["movement_grant"],
        )
        prompt = build_system_prompt(ctx)
        assert "no movement destination is currently available" in prompt or "no movement destinations are currently available" in prompt
        assert "available_moves" in prompt

    def test_existing_material_intact(self):
        ctx = AgentContext(
            agent_id="genesis-agent-test-adam-0000000000000000000000000000000000000000000000000000",
            canonical_name="Adam",
            canonical_ref="east_adam",
            heartbeat_number=1,
            position="tile-alpha",
            observation={"tile_id": "tile-alpha", "visible_tiles": ["tile-alpha"], "objects_here": []},
            memory=[
                {"type": "observation", "content": "I see an empty room.", "heartbeat": 1},
            ],
            goals=[
                {"goal_id": "goal-explore", "agent_id": "genesis-agent-test-adam-...", "description": "Explore the world", "status": "active"},
            ],
            unanswered_questions=[],
            world_public_objects={},
            habitat_allowed_tiles=["tile-alpha", "tile-beta"],
            habitat_movement_allowed=False,
            previous_action=None,
            timestamp_utc="2026-07-27T12:00:00Z",
            other_agent_id="genesis-agent-test-eve-...",
            other_agent_name="Eve",
            other_agent_ref="east_eve",
            answered_questions=[{"question_id": "q1", "answer": "42"}],
            available_moves=[],
            current_runtime_capabilities=[],
        )
        prompt = build_system_prompt(ctx)
        assert "42" in prompt
        assert "q1" in prompt
        assert "Explore the world" in prompt
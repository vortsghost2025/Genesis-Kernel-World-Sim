"""Speaking must not cost the heartbeat.

`docs/free_messaging_spec.md`. The mechanism: they talked for 360 messages
early on, then stopped dead — not because the capability went away, but
because speaking occupied the single action slot and acting outbid it. At
HB1297 Adam wrote "Eve is unresponsive, so solo exploration is the
reason", correctly diagnosing a budget problem as a relationship problem.

The claim under test is precise: an agent may act AND speak in one
heartbeat. Everything here is about that conjunction holding, and about
nothing else changing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m  # noqa: E402
from backend.world.first_pair_cognition_interface import (  # noqa: E402
    AgentContext,
)


def _output(**overrides) -> dict:
    base = {
        "observation_summary": "sees grass",
        "self_model_update": None,
        "decision_summary": "walk west",
        "uncertainty": "unknown",
        "confidence": 0.7,
        "proposed_action": {"action_type": "move", "target_tile": "t-2",
                            "reason": "frontier"},
        "memory_candidates": [],
        "goal_updates": [],
        "questions_for_humans": [],
    }
    base.update(overrides)
    return base


class TestContractAcceptsAMessage:
    def test_message_alongside_an_action_validates(self):
        v = m.validate_model_output(_output(message={
            "recipient": "east_eve", "message": "I am at -34. where are you?"}),
            "genesis-agent-test-adam-" + "0" * 48)
        assert v.is_valid, v.validation_errors

    def test_message_is_parsed_out(self):
        v = m.validate_model_output(_output(message={
            "recipient": "east_eve", "message": "hello"}),
            "genesis-agent-test-adam-" + "0" * 48)
        assert v.message == {"recipient": "east_eve", "message": "hello"}

    def test_absent_message_is_unchanged_behaviour(self):
        v = m.validate_model_output(_output(), "genesis-agent-test-adam-" + "0" * 48)
        assert v.is_valid
        assert v.message is None


class TestContractRejectsNonsense:
    def test_wrong_shape_fails_validation(self):
        v = m.validate_model_output(_output(message="just a string"),
                                    "genesis-agent-test-adam-" + "0" * 48)
        assert not v.is_valid
        assert any("message" in e for e in v.validation_errors)

    def test_missing_recipient_fails_validation(self):
        v = m.validate_model_output(_output(message={"message": "hi"}),
                                    "genesis-agent-test-adam-" + "0" * 48)
        assert not v.is_valid

    def test_empty_message_text_fails_validation(self):
        v = m.validate_model_output(
            _output(message={"recipient": "east_eve", "message": "   "}),
            "genesis-agent-test-adam-" + "0" * 48)
        assert not v.is_valid


class TestNoCost:
    def test_prompt_documents_the_field_without_advising_when_to_use_it(self):
        """Contract documentation, not coaching. The world states rules."""
        ctx = AgentContext(
            agent_id="genesis-agent-test-adam-" + "0" * 48,
            canonical_name="Adam", canonical_ref="east_adam", heartbeat_number=3,
            position="tile-alpha",
            observation={"tile_id": "tile-alpha",
                         "visible_tiles": ["tile-alpha"], "objects_here": []},
            memory=[], goals=[], unanswered_questions=[],
            world_public_objects={},
            habitat_allowed_tiles=["tile-alpha"],
            habitat_movement_allowed=False, previous_action=None,
            timestamp_utc="2026-07-27T12:00:00Z",
            other_agent_id="genesis-agent-test-eve-...",
            other_agent_name="Eve", other_agent_ref="east_eve",
            answered_questions=[],
        )
        prompt = m.build_system_prompt(ctx)
        assert "message" in prompt.lower()
        # The coaching we are refusing to write.
        for directive in ("you should message", "you must message",
                          "in order to communicate", "try to contact",
                          "reach out to"):
            assert directive not in prompt.lower(), (
                f"prompt gives advice about messaging: {directive!r}")

    def test_message_does_not_replace_the_action(self):
        """One action per heartbeat, unchanged. Speech rides alongside."""
        v = m.validate_model_output(
            _output(message={"recipient": "all", "message": "still walking"}),
            "genesis-agent-test-adam-" + "0" * 48)
        assert v.proposed_action["action_type"] == "move"

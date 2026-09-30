"""The conjunction: one heartbeat, one action AND one message.

`docs/free_messaging_spec.md` §2. The contract tests prove the field
parses. These prove the thing that actually matters — that delivering a
message does not consume, delay, or disturb the action it rides with, and
that a dropped message is harmless.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
)


class _Out:
    """Minimal stand-in for a CognitionOutput."""

    def __init__(self, message=None):
        self.goal_updates = []
        self.questions_raised = None
        self.memory_write = None
        self.continuity_update = None
        self.message = message


def _runtime(tmp_path):
    store = FirstPairPersistenceStore(root=tmp_path)
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt._load_or_initialize()
    return rt


class TestMessageRidesWithTheAction:
    def test_message_is_delivered(self, tmp_path):
        rt = _runtime(tmp_path)
        before = len(rt._world_state.public_messages)
        rt._apply_cognition_output(
            "east_adam",
            _Out(message={"recipient": "east_eve", "message": "I am at -34."}),
            1350)
        assert len(rt._world_state.public_messages) == before + 1
        rec = rt._world_state.public_messages[-1]
        assert "at -34" in rec["message"]
        assert rec["heartbeat"] == 1350

    def test_message_does_not_disturb_the_action_slot(self, tmp_path):
        """The whole point. One heartbeat, one action, plus speech."""
        rt = _runtime(tmp_path)
        out = _Out(message={"recipient": "all", "message": "walking west"})
        out.action = {"action_type": "move", "target_tile": "x",
                      "reason": "frontier"}
        before_actions = len(rt._world_state.public_messages)
        rt._apply_cognition_output("east_adam", out, 1350)
        # Action untouched, message delivered, no coupling.
        assert out.action["action_type"] == "move"
        assert len(rt._world_state.public_messages) == before_actions + 1

    def test_absent_message_delivers_nothing(self, tmp_path):
        rt = _runtime(tmp_path)
        before = len(rt._world_state.public_messages)
        rt._apply_cognition_output("east_adam", _Out(), 1350)
        assert len(rt._world_state.public_messages) == before

    def test_message_defaults_recipient_to_all(self, tmp_path):
        rt = _runtime(tmp_path)
        rt._apply_cognition_output(
            "east_eve", _Out(message={"message": "anyone?"}), 1351)
        rec = rt._world_state.public_messages[-1]
        assert rec["recipient"] == "all"


class TestBadMessagesAreHarmless:
    def test_malformed_message_is_dropped_silently(self, tmp_path):
        """Validation catches shape errors; the runtime never raises on
        one, and never lets it disturb the action."""
        rt = _runtime(tmp_path)
        before = len(rt._world_state.public_messages)
        for bad in ({"message": ""}, {"message": "   "},
                    {"message": None}, "a bare string", {"nope": 1}):
            rt._apply_cognition_output(
                "east_adam", _Out(message=bad), 1350)
        assert len(rt._world_state.public_messages) == before

    def test_message_is_sanitized_like_any_public_text(self, tmp_path):
        """Same gate as leave_public_message - no private paths or control
        characters reach the public record through the new door."""
        rt = _runtime(tmp_path)
        rt._apply_cognition_output(
            "east_adam",
            _Out(message={"recipient": "east_eve",
                          "message": "meet me at S:\\secret\\place"}),
            1350)
        rec = rt._world_state.public_messages[-1]
        assert "S:\\secret\\place" not in rec["message"]


class TestOneMessagePerHeartbeat:
    def test_repeat_sends_produce_repeat_records(self, tmp_path):
        """Bounded by the cycle, not by a hidden counter: one call, one
        message, and it is visible in the world state like any other."""
        rt = _runtime(tmp_path)
        before = len(rt._world_state.public_messages)
        for hb in (1350, 1351, 1352):
            rt._apply_cognition_output(
                "east_adam", _Out(message={"message": f"beat {hb}"}), hb)
        assert len(rt._world_state.public_messages) == before + 3
        assert [m["heartbeat"] for m in rt._world_state.public_messages[-3:]] == \
            [1350, 1351, 1352]

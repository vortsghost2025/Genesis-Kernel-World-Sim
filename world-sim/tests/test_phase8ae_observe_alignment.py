"""
Phase 8AE tests: Observe decision alignment prompt patch.

Tests that build_reflection_prompt() includes the observe-preference instruction
when current_goal asks to observe/refresh world facts, and excludes it for
normal verification goals.

No runtime, no provider calls, no daemon mode.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from unittest.mock import MagicMock

from backend.daemon.agent_daemon import AgentDaemon


OBSERVE_PREFERENCE_TEXT = 'Prefer `decision="observe"` to gather fresh world facts before deciding'


def _build_prompt_with_goal(goal: str) -> str:
    """Build a reflection prompt with the given current_goal."""
    daemon = AgentDaemon(no_llm=True)
    agent_obj = MagicMock()
    agent_obj.persistent_memory.get_unread_whispers.return_value = []
    agent_obj.persistent_memory.get_recent.return_value = []

    state = {
        "agent_id": "east_adam",
        "name": "East Adam",
        "current_goal": goal,
        "current_topic": "none",
        "fatigue": {"topic": "none", "level": 0.0, "cooldown_active": False},
        "__canonical_id": "east_adam",
        "__display_name": "East Adam",
    }

    return daemon.build_reflection_prompt("Adam", agent_obj, state)


class TestObserveAlignmentPrompt:
    """Test that the observe-preference instruction appears only for observe/refresh goals."""

    def test_observe_preferred_when_goal_contains_observe(self):
        """goal='observe the world' should add observe-preference instruction."""
        prompt = _build_prompt_with_goal("observe the world")
        assert OBSERVE_PREFERENCE_TEXT in prompt

    def test_observe_preferred_when_goal_contains_refresh(self):
        """goal='refresh canonical world facts' should add observe-preference instruction."""
        prompt = _build_prompt_with_goal("refresh canonical world facts")
        assert OBSERVE_PREFERENCE_TEXT in prompt

    def test_observe_preferred_when_goal_contains_current_world_state(self):
        """goal='refresh current world state before choosing any goal' should add observe-preference instruction."""
        prompt = _build_prompt_with_goal("refresh current world state before choosing any goal")
        assert OBSERVE_PREFERENCE_TEXT in prompt

    def test_goal_preferred_when_goal_is_normal_verification(self):
        """goal='verify whether a hidden water source exists' should NOT add observe-preference."""
        prompt = _build_prompt_with_goal("verify whether a hidden water source exists")
        assert OBSERVE_PREFERENCE_TEXT not in prompt

    def test_goal_preferred_when_goal_is_find_water(self):
        """goal='find water source' should NOT add observe-preference."""
        prompt = _build_prompt_with_goal("find water source")
        assert OBSERVE_PREFERENCE_TEXT not in prompt

    def test_goal_preferred_when_goal_is_gather_water(self):
        """goal='gather water from a source' should NOT add observe-preference."""
        prompt = _build_prompt_with_goal("gather water from a source")
        assert OBSERVE_PREFERENCE_TEXT not in prompt

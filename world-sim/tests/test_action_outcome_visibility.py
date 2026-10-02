"""Failed actions must be legible, or they will be invented.

Eve's HB1655 diagnostic: "GATHER IS UNIVERSALLY BROKEN — 23 failed stone
gathers." The store verifies otherwise: in the window she consulted
(1640-1700) every gather attempt succeeded. Nineteen recorded failures
are a fiction she manufactured from memory and then used as proof.

This is the prompt's fault, not hers. The world had an answer, and never
delivered it. A heartbeat that knows what it just did needs to be inside
the record so anyone who reads the record can see what actually happened.
Absent that voice, the pair are left to invent failure patterns.

The answer here is one prompt line: outcomes from the window's actions,
labeled from the store, not invented. Facts, not advice. That's all.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m  # noqa: E402
from backend.world.first_pair_cognition_interface import (  # noqa: E402
    AgentContext,
)


def _ctx(**over) -> AgentContext:
    b = dict(
        agent_id="genesis-agent-test-adam-" + "0" * 48,
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=1700,
        position="tile-alpha",
        observation={"tile_id": "tile-alpha",
                     "visible_tiles": ["tile-alpha"], "objects_here": []},
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["tile-alpha"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-07-27T12:00:00Z",
        other_agent_id="genesis-agent-test-eve-...",
        other_agent_name="Eve",
        other_agent_ref="east_eve",
        answered_questions=[],
    )
    b.update(over)
    return AgentContext(**b)


class TestReliabilityIsVisible:
    def test_failures_within_the_recent_window_are_declared(self):
        """An action that failed must be visible in the prompt, sourced —
        if the record never defends them, they can invent one."""
        ctx = _ctx(recent_action_failures=[
            {"heartbeat": 1690, "action": "gather",
             "outcome": {"status": "failure"}},
        ])
        prompt = m.build_system_prompt(ctx)
        assert "heartbeat 1690" in prompt.lower()
        assert "failure" in prompt.lower()

    def test_success_only_means_nothing_to_report(self):
        """If no failed actions, the line omits itself - zero is never an
        event. A failure-erased-state is cleared from the message."""
        ctx = _ctx(recent_action_failures=[])
        prompt = m.build_system_prompt(ctx)
        assert "recent outcomes" not in prompt.lower()

    def test_sink_of_the_record_not_a_guess(self):
        """The prompt is rendering a count, not inventing it - the plain
        phrasing policy applies."""
        ctx = _ctx(recent_action_failures=[
            {"heartbeat": 1651, "action": "gather",
             "outcome": {"status": "failure"}},
            {"heartbeat": 1652, "action": "gather",
             "outcome": {"status": "failure"}},
        ])
        prompt = m.build_system_prompt(ctx)
        assert "heartbeat 1651" in prompt and "heartbeat 1652" in prompt

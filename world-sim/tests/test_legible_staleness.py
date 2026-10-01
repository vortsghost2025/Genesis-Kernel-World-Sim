"""The record must be able to say how quiet it has gotten.

`docs/legible_staleness_spec.md`. A free channel shipped at HB1347 and
produced 0 messages in 100 heartbeats, while Adam's HB1436 reasoning still
carried "Eve is unresponsive" as the cause of his own solo path. The
relationship ledger has 252 co-location events down to HB939 and the
prompt rendered them all with no age on any of it. The last thing in the
frame that couldn't be seen was the piece that mattered.

What is under test: a line that states the record's age from the record,
every heartbeat, with no advice and no invented data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m  # noqa: E402
from backend.world.first_pair_cognition_interface import (  # noqa: E402
    AgentContext,
)


def _ctx(**overrides) -> AgentContext:
    base = dict(
        agent_id="genesis-agent-test-adam-" + "0" * 48,
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=1500,
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
    base.update(overrides)
    return AgentContext(**base)


class TestTheLineIsComputedFromTheRecord:
    def test_states_message_age_from_the_record_itself(self):
        ctx = _ctx(public_record_age={
            "now": 1500,
            "message_count": 4,
            "last_message_hb": 1200,
            "last_colocation_hb": 1300,
        })
        prompt = m.build_system_prompt(ctx)
        assert "4 messages" in prompt
        assert "1200" in prompt
        assert "300 heartbeats ago" in prompt
        assert "1300" in prompt

    def test_states_co_location_age_the_same_way(self):
        ctx = _ctx(public_record_age={
            "now": 1500, "message_count": 1,
            "last_message_hb": 1200, "last_colocation_hb": 1300,
        })
        prompt = m.build_system_prompt(ctx)
        assert "co-location" in prompt
        assert "200 heartbeats ago" in prompt

    def test_the_ages_are_arithmetic_not_persuasion(self):
        """now=1000, last message at 700: the line must read 300, the
        record's own age - not a weighed verdict."""
        ctx = _ctx(public_record_age={
            "now": 1000, "message_count": 3,
            "last_message_hb": 700, "last_colocation_hb": 400,
        })
        prompt = m.build_system_prompt(ctx)
        assert "300 heartbeats ago" in prompt
        assert "600 heartbeats ago" in prompt


class TestAbsenceIsStatedNotInvented:
    def test_no_messages_says_no_messages(self):
        ctx = _ctx(public_record_age={
            "now": 1500, "message_count": 0,
            "last_message_hb": None, "last_colocation_hb": 900,
        })
        prompt = m.build_system_prompt(ctx)
        assert "no messages" in prompt.lower()

    def test_no_colocation_events_omits_the_clause(self):
        """When the record has never recorded a co-location, the line
        absent - there is nothing to age, and a zero is not a fact."""
        ctx = _ctx(public_record_age={
            "now": 1500, "message_count": 2,
            "last_message_hb": 1400, "last_colocation_hb": None,
        })
        prompt = m.build_system_prompt(ctx)
        assert "co-location" not in prompt

    def test_no_data_renders_nothing(self):
        """A session with no record at all (a fresh run) must not carry
        a fabricated shape."""
        ctx = _ctx()
        prompt = m.build_system_prompt(ctx)
        assert "heartbeats ago" not in prompt


class TestNoAdvice:
    def test_the_line_states_facts_never_instructions(self):
        ctx = _ctx(public_record_age={
            "now": 1500, "message_count": 4,
            "last_message_hb": 1200, "last_colocation_hb": 1300,
        })
        line = m._public_record_age_line(ctx.public_record_age)
        for directive in ("you should", "you must", "try to",
                          "in order to", "consider", "why not",
                          "reach out", "respond to"):
            assert directive not in line.lower(), (
                f"the line advises: {directive!r}")

    def test_the_record_never_carries_agent_ids(self):
        """A public-record line is public. Agent ids are hashes that must
        not appear - the section renders names, never ids."""
        ctx = _ctx(public_record_age={
            "now": 1500, "message_count": 4,
            "last_message_hb": 1200, "last_colocation_hb": 1300,
        })
        prompt = m.build_system_prompt(ctx)
        assert "9c37c102" not in prompt
        assert "genesis-agent" not in prompt.split(
            "Public record")[1].split("actions")[0].lower().split(
            "the most recent")[0] if "Public record" in prompt else ""

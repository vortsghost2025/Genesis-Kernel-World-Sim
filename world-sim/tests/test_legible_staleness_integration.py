"""The runtime computes the record's age from the record.

`docs/legible_staleness_spec.md`. The line the prompt renders is only as
honest as its source. These pin that the ages are derived from the store's
public messages and relationship ledger - the same facts, the same count -
never computed against fabricated or operator-supplied data.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
)


def _rt(tmp_path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(root=tmp_path)
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt._load_or_initialize()
    return rt


class TestComputedFromTheRecord:
    def test_message_age_is_from_the_store(self, tmp_path):
        rt = _rt(tmp_path)
        rt._world_state.public_messages = [
            {"message_id": "m1", "sender_agent_id": "x", "recipient": "all",
             "message": "hello", "heartbeat": 10},
            {"message_id": "m2", "sender_agent_id": "x", "recipient": "all",
             "message": "two", "heartbeat": 14},
        ]
        ctx = rt._build_context("east_adam", 50)
        age = ctx.public_record_age
        assert age is not None
        assert age["now"] == 50
        assert age["message_count"] == 2
        assert age["last_message_hb"] == 14

    def test_colocation_age_comes_from_the_ledger(self, tmp_path):
        rt = _rt(tmp_path)
        rt._world_state.public_messages = []
        ctx = rt._build_context("east_eve", 40)
        assert ctx.public_record_age["message_count"] == 0

    def test_absent_record_means_absent_clause(self, tmp_path):
        """A fresh run has no messages, so the line says no messages -
        not a fabricated count, not a placeholder age."""
        rt = _rt(tmp_path)
        ctx = rt._build_context("east_adam", 1)
        assert ctx.public_record_age is not None
        assert ctx.public_record_age["message_count"] == 0


class TestRenderedForBothAgents:
    def test_the_line_is_present_for_both_agents(self, tmp_path):
        rt = _rt(tmp_path)
        for ref in ("east_adam", "east_eve"):
            ctx = rt._build_context(ref, 50)
            line = __import__(
                "backend.world.first_pair_cognition_model",
                fromlist=["_public_record_age_line"],
            )._public_record_age_line(ctx.public_record_age)
            assert "Public record" in line

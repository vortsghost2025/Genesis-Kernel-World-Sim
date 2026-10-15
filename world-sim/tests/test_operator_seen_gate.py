"""Operator messages fire once, like the physics changelog.

West Eve at HB2441: "The operator's announcement has repeated verbatim
for 90 consecutive heartbeats." West Adam: "A sixth answer would be
noise." They correctly identified the structural problem — every
operator message stays in the prompt until 5 newer ones exist, so a
single message repeats for hundreds of heartbeats.

The physics changelog already solved this: it fires once per agent
(new_to_agent), the agent reads it, it enters memory, the prompt stops
repeating it. Operator messages should behave identically.

The mechanism: an `operator_seen.json` store tracks which message IDs
each agent has been shown. The runtime only passes UNSEEN messages to
the prompt. After building the context, all shown messages are marked
seen. The next heartbeat shows nothing (or the next new message).

The agent's memory carries the content forward — the prompt doesn't
need to repeat what the agent already read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
)
from backend.world.first_pair_cognition_model import (  # noqa: E402
    build_system_prompt,
)
from backend.world.first_pair_cognition_interface import (  # noqa: E402
    AgentContext,
)


def _rt(tmp_path):
    store = FirstPairPersistenceStore(root=tmp_path)
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt._load_or_initialize()
    return rt


def _seed_operator_message(rt, msg_id="op-test-1", text="test message"):
    from backend.world.first_pair_persistence import (
        append_operator_message, load_operator_messages,
    )
    append_operator_message(rt._store, {
        "message_id": msg_id,
        "author": "the operator",
        "addressed_to": "all",
        "text": text,
        "created_at_utc": "2026-10-14T00:00:00Z",
        "provenance": "operator-authored",
    })


class TestOperatorMessagesFireOnce:
    def test_new_message_appears_in_prompt(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_operator_message(rt, "op-1", "the world changed")
        ctx = rt._build_context("east_adam", 1)
        prompt = build_system_prompt(ctx)
        assert "the world changed" in prompt

    def test_seen_message_does_not_repeat(self, tmp_path):
        """The second heartbeat must NOT show the same message again.
        The agent read it; their memory carries it; the prompt moves on."""
        rt = _rt(tmp_path)
        _seed_operator_message(rt, "op-1", "the world changed")
        # First heartbeat: the message appears
        ctx1 = rt._build_context("east_adam", 1)
        prompt1 = build_system_prompt(ctx1)
        assert "the world changed" in prompt1
        # Second heartbeat: it must NOT appear
        ctx2 = rt._build_context("east_adam", 2)
        prompt2 = build_system_prompt(ctx2)
        assert "the world changed" not in prompt2, (
            "operator message repeated on the second heartbeat — "
            "the 90-heartbeat spam bug")

    def test_each_agent_sees_it_once_independently(self, tmp_path):
        """Adam and Eve each get their own 'seen' gate. If Adam reads
        the message at HB1, Eve should still see it at her HB1."""
        rt = _rt(tmp_path)
        _seed_operator_message(rt, "op-1", "the world changed")
        # Adam sees it
        ctx_a = rt._build_context("east_adam", 1)
        assert "the world changed" in build_system_prompt(ctx_a)
        # Eve also sees it (her first exposure)
        ctx_e = rt._build_context("east_eve", 1)
        assert "the world changed" in build_system_prompt(ctx_e)
        # Neither sees it again
        ctx_a2 = rt._build_context("east_adam", 2)
        assert "the world changed" not in build_system_prompt(ctx_a2)
        ctx_e2 = rt._build_context("east_eve", 2)
        assert "the world changed" not in build_system_prompt(ctx_e2)

    def test_a_new_message_shows_again(self, tmp_path):
        """A genuinely new operator message appears even after old ones
        are marked seen."""
        rt = _rt(tmp_path)
        _seed_operator_message(rt, "op-1", "first message")
        rt._build_context("east_adam", 1)  # seen
        _seed_operator_message(rt, "op-2", "second message")
        ctx = rt._build_context("east_adam", 2)
        prompt = build_system_prompt(ctx)
        assert "second message" in prompt
        assert "first message" not in prompt, (
            "old message still showing; only the new one should appear")

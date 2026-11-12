"""Bounded Context Integrity (Genesis Phase Path A).

Verifies the constitutional properties of bounded selection:
1. Strict selection caps (messages <= 35, relationship events <= 25)
2. Historical evidence integrity (fields, IDs, timestamps untampered)
3. Correct agent visibility (no cross-agent private message leaks)
4. Stable chronological ordering (ascending heartbeat order)
5. Preservation of important older events (first contact, creations, questions)
6. Unchanged full history on disk (no disk mutation from selection)
7. No alteration to cognition action semantics (validate_model_output unchanged)

Historically this suite read a scratch store under a hard-coded absolute
path from a prior tooling session, so it could only ever run on one
machine. The selection functions it exercises are pure, and the invariants
it asserts are about THOSE functions, not about that particular store --
so a committed fixture stands in for the scratch store and the suite is
now portable.
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

import pytest

REPO_SIM = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_SIM) not in sys.path:
    sys.path.insert(0, str(REPO_SIM))

from backend.world.first_pair_persistence import (
    select_bounded_public_messages,
    select_bounded_relationship_events,
)
from backend.world.first_pair_cognition_model import validate_model_output

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
FIXTURE_STORE = FIXTURES / "bounded_context_store"

ADAM_ID = "genesis-agent-" + "a" * 56
EVE_ID = "genesis-agent-" + "b" * 56

# A committed stand-in for the scratch store this suite used to require.
# Shaped exactly like the real store's files: an envelope with a `data`
# key holding the records. The assertions below target specific landmark
# records, so the fixture carries the same ones by ID.
_WORLD_STATE = {
    "type": "world_state_record",
    "schema_version": "world_state.1",
    "data": {
        "tick": 4000,
        "public_messages": [
            # Founding exchange at HB 2 (both directions).
            {"message_id": "msg-92a268d86c38", "heartbeat": 2, "recipient": "east_eve",
             "sender_agent_id": ADAM_ID, "message": "I see you.",
             "sent_at_utc": "2026-10-01T00:00:02+00:00"},
            {"message_id": "msg-b5105215af59", "heartbeat": 2, "recipient": "east_adam",
             "sender_agent_id": EVE_ID, "message": "I see you too.",
             "sent_at_utc": "2026-10-01T00:00:02+00:00"},
            # Historical operator appeals: private to their authoring agent.
            {"message_id": "msg-fee573ae1fb7", "heartbeat": 830, "recipient": "the operator",
             "sender_agent_id": ADAM_ID, "message": "How do I make fire?",
             "sent_at_utc": "2026-10-01T00:00:00+00:00"},
            {"message_id": "msg-bac436451ea9", "heartbeat": 937, "recipient": "the operator",
             "sender_agent_id": EVE_ID, "message": "Where is stone?",
             "sent_at_utc": "2026-10-01T00:00:00+00:00"},
            # The crucial partner inquiry at HB 3594.
            {"message_id": "msg-6051b436bac5", "heartbeat": 3594, "recipient": "east_adam",
             "sender_agent_id": EVE_ID, "message": "Can you see the river?",
             "sent_at_utc": "2026-10-01T00:00:00+00:00"},
            # Filler so the 35-message cap is genuinely exercised. Addressed
            # BOTH ways so each agent's selection has enough to fill its cap.
            *[
                {"message_id": f"msg-fill-a-{i:04d}", "heartbeat": 100 + i,
                 "recipient": "east_adam", "sender_agent_id": ADAM_ID,
                 "message": f"adam note {i}", "sent_at_utc": "2026-10-01T00:00:00+00:00"}
                for i in range(40)
            ],
            *[
                {"message_id": f"msg-fill-e-{i:04d}", "heartbeat": 100 + i,
                 "recipient": "east_eve", "sender_agent_id": EVE_ID,
                 "message": f"eve note {i}", "sent_at_utc": "2026-10-01T00:00:00+00:00"}
                for i in range(40)
            ],
        ],
    },
}

_RELATIONSHIP_LEDGER = {
    "type": "relationship_ledger",
    "schema_version": "relationship_ledger.1",
    "data": [
        # Foundational meeting co-location at HB 1.
        {"event_id": "16463155fcdf7275", "heartbeat": 1, "event_type": "co_location",
         "actor_agent_id": ADAM_ID, "other_agent_id": EVE_ID,
         "created_at_utc": "2026-10-01T00:00:01+00:00"},
        # Meeting stone creation at HB 10. The real event type is
        # `public_object_creation` (see first_pair_persistence.py ~1150):
        # `select_bounded_relationship_events` preserves founders by TYPE, so
        # a fixture using plain "creation" would be correctly ignored and the
        # preservation test would fail for the wrong reason.
        {"event_id": "38afea75f195f40c", "heartbeat": 10, "event_type": "public_object_creation",
         "actor_agent_id": ADAM_ID, "other_agent_id": EVE_ID,
         "created_at_utc": "2026-10-01T00:00:10+00:00"},
        # Filler so the 25-event cap is genuinely exercised. These sit at
        # HIGHER heartbeats than the founders, and `select_bounded_relationship_events`
        # prefers recent events -- so the preservation test below is what
        # proves the founders survive the cap rather than being crowded out.
        *[
            {"event_id": f"evt-fill-{i:04d}", "heartbeat": 3000 + i,
             "event_type": "co_location", "actor_agent_id": ADAM_ID,
             "other_agent_id": EVE_ID, "created_at_utc": "2026-10-01T00:00:00+00:00"}
            for i in range(40)
        ],
    ],
}

_IDENTITY = {
    "type": "identity_record",
    "schema_version": "first_pair_identity.1",
    "data": {
        "adam_agent_id": ADAM_ID,
        "eve_agent_id": EVE_ID,
        "birth_candidate": {
            "adam_identity": {"canonical_name": "Adam", "canonical_agent_ref": "east_adam"},
            "eve_identity": {"canonical_name": "Eve", "canonical_agent_ref": "east_eve"},
        },
    },
}


@pytest.fixture(scope="module")
def isolated_store(tmp_path_factory):
    """Materialize the fixture store once. Uses a platform-native temp dir,
    never a hardcoded path."""
    root = tmp_path_factory.mktemp("bounded_context_store")
    (root / "world_state.json").write_text(
        json.dumps(_WORLD_STATE), encoding="utf-8", newline="\n")
    (root / "relationship_ledger.json").write_text(
        json.dumps(_RELATIONSHIP_LEDGER), encoding="utf-8", newline="\n")
    (root / "identity.json").write_text(
        json.dumps(_IDENTITY), encoding="utf-8", newline="\n")
    return root


@pytest.fixture
def isolated_data(isolated_store):
    with open(isolated_store / "world_state.json", "r", encoding="utf-8") as f:
        ws = json.load(f)
    msgs = ws.get("data", {}).get("public_messages", [])

    with open(isolated_store / "relationship_ledger.json", "r", encoding="utf-8") as f:
        rel_data = json.load(f)
    events = rel_data.get("data", [])

    with open(isolated_store / "identity.json", "r", encoding="utf-8") as f:
        ident = json.load(f).get("data", {})
    return msgs, events, ident

def test_strict_selection_caps(isolated_data):
    msgs, events, ident = isolated_data
    adam_id = ident.get("adam_agent_id")
    eve_id = ident.get("eve_agent_id")

    # 1. Real data check
    for ref, aid in [("east_adam", adam_id), ("east_eve", eve_id)]:
        sel_msgs = select_bounded_public_messages(msgs, agent_ref=ref, max_total_messages=35)
        sel_events = select_bounded_relationship_events(events, agent_id=aid, max_total_events=25)
        assert len(sel_msgs) <= 35, f"Expected <= 35 messages for {ref}, got {len(sel_msgs)}"
        assert len(sel_events) <= 25, f"Expected <= 25 events for {ref}, got {len(sel_events)}"
        assert len(sel_msgs) == 35
        assert len(sel_events) == 25

    # 2. Stress check on 1,000 synthetic items
    synthetic_msgs = [
        {"message_id": f"syn-msg-{i}", "heartbeat": i, "recipient": "east_eve", "message": f"note {i}"}
        for i in range(1000)
    ]
    synthetic_events = [
        {"event_id": f"syn-evt-{i}", "heartbeat": i, "event_type": "co_location", "actor_agent_id": eve_id, "other_agent_id": adam_id}
        for i in range(1000)
    ]
    bounded_syn_msgs = select_bounded_public_messages(synthetic_msgs, agent_ref="east_eve", max_total_messages=35)
    bounded_syn_evts = select_bounded_relationship_events(synthetic_events, agent_id=eve_id, max_total_events=25)
    assert len(bounded_syn_msgs) == 35, f"Expected exactly 35 synthetic messages, got {len(bounded_syn_msgs)}"
    assert len(bounded_syn_evts) == 25, f"Expected exactly 25 synthetic events, got {len(bounded_syn_evts)}"


def test_historical_evidence_integrity(isolated_data):
    msgs, events, ident = isolated_data
    eve_id = ident.get("eve_agent_id")

    msg_map = {m["message_id"]: m for m in msgs}
    evt_map = {e["event_id"]: e for e in events}

    sel_msgs = select_bounded_public_messages(msgs, agent_ref="east_eve", max_total_messages=35)
    sel_events = select_bounded_relationship_events(events, agent_id=eve_id, max_total_events=25)

    for sm in sel_msgs:
        orig = msg_map[sm["message_id"]]
        assert sm == orig, f"Message {sm['message_id']} was modified during selection!"
        assert sm["message"] == orig["message"]
        assert sm["sent_at_utc"] == orig["sent_at_utc"]

    for se in sel_events:
        orig = evt_map[se["event_id"]]
        assert se == orig, f"Event {se['event_id']} was modified during selection!"
        assert se["event_type"] == orig["event_type"]
        assert se["created_at_utc"] == orig["created_at_utc"]


def test_correct_agent_visibility(isolated_data):
    msgs, _, ident = isolated_data
    adam_id = ident.get("adam_agent_id")
    eve_id = ident.get("eve_agent_id")

    # Add private messages and operator inquiries
    test_msgs = copy.deepcopy(msgs)
    test_msgs.append({
        "message_id": "secret-adam-msg",
        "heartbeat": 9999,
        "recipient": "east_adam",
        "sender_agent_id": "operator",
        "message": "Top secret for Adam only"
    })
    test_msgs.append({
        "message_id": "secret-eve-msg",
        "heartbeat": 9999,
        "recipient": "east_eve",
        "sender_agent_id": "operator",
        "message": "Top secret for Eve only"
    })
    test_msgs.append({
        "message_id": "operator-appeal-from-adam",
        "heartbeat": 9998,
        "recipient": "the operator",
        "sender_agent_id": adam_id,
        "message": "Adam asking operator a private question"
    })
    test_msgs.append({
        "message_id": "operator-appeal-from-eve",
        "heartbeat": 9998,
        "recipient": "operator",
        "sender_agent_id": eve_id,
        "message": "Eve asking operator a private question"
    })

    eve_selected = select_bounded_public_messages(
        test_msgs, agent_ref="east_eve", canonical_agent_ref=eve_id, max_total_messages=35
    )
    adam_selected = select_bounded_public_messages(
        test_msgs, agent_ref="east_adam", canonical_agent_ref=adam_id, max_total_messages=35
    )

    eve_ids = {m["message_id"] for m in eve_selected}
    adam_ids = {m["message_id"] for m in adam_selected}

    # 1. Inbound private messages addressed to a specific agent
    assert "secret-adam-msg" not in eve_ids, "Private message for Adam leaked into Eve's context!"
    assert "secret-eve-msg" not in adam_ids, "Private message for Eve leaked into Adam's context!"

    # 2. Outbound operator inquiries: visible only to authoring agent
    assert "operator-appeal-from-adam" in adam_ids, "Adam's inquiry to operator missing from Adam's context!"
    assert "operator-appeal-from-adam" not in eve_ids, "Adam's inquiry to operator leaked to Eve!"

    assert "operator-appeal-from-eve" in eve_ids, "Eve's inquiry to operator missing from Eve's context!"
    assert "operator-appeal-from-eve" not in adam_ids, "Eve's inquiry to operator leaked to Adam!"

    # 3. Real historical operator inquiries in canon: no cross-agent leakage
    assert "msg-fee573ae1fb7" not in eve_ids, "Historical Adam operator appeal (HB 830) leaked to Eve!"
    assert "msg-bac436451ea9" not in adam_ids, "Historical Eve operator appeal (HB 937) leaked to Adam!"


def test_stable_chronological_ordering(isolated_data):
    msgs, events, ident = isolated_data
    adam_id = ident.get("adam_agent_id")

    sel_msgs = select_bounded_public_messages(msgs, agent_ref="east_adam", max_total_messages=35)
    sel_events = select_bounded_relationship_events(events, agent_id=adam_id, max_total_events=25)

    # Strictly ascending heartbeats
    for i in range(len(sel_msgs) - 1):
        assert sel_msgs[i]["heartbeat"] <= sel_msgs[i+1]["heartbeat"], "Messages not sorted by heartbeat!"

    for i in range(len(sel_events) - 1):
        assert sel_events[i]["heartbeat"] <= sel_events[i+1]["heartbeat"], "Events not sorted by heartbeat!"


def test_preservation_of_important_older_events(isolated_data):
    msgs, events, ident = isolated_data
    adam_id = ident.get("adam_agent_id")
    eve_id = ident.get("eve_agent_id")

    sel_adam_msgs = select_bounded_public_messages(msgs, agent_ref="east_adam", max_total_messages=35)
    sel_eve_msgs = select_bounded_public_messages(msgs, agent_ref="east_eve", max_total_messages=35)
    sel_events = select_bounded_relationship_events(events, agent_id=adam_id, max_total_events=25)

    adam_msg_ids = {m["message_id"] for m in sel_adam_msgs}
    eve_msg_ids = {m["message_id"] for m in sel_eve_msgs}
    event_ids = {e["event_id"] for e in sel_events}

    # First meeting co-location at HB 1 must be present
    assert "16463155fcdf7275" in event_ids, "Foundational meeting HB 1 missing from relationship events!"
    # Meeting stone creation at HB 10 must be present
    assert "38afea75f195f40c" in event_ids, "Meeting stone creation at HB 10 missing from relationship events!"
    # First message to Eve at HB 2 must be present in Eve's context
    assert "msg-92a268d86c38" in eve_msg_ids, "Foundational first message at HB 2 missing from Eve's public messages!"
    # First message to Adam at HB 2 must be present in Adam's context
    assert "msg-b5105215af59" in adam_msg_ids, "Foundational first message at HB 2 missing from Adam's public messages!"
    # Crucial inquiry at HB 3594 must be present in Adam's context
    assert "msg-6051b436bac5" in adam_msg_ids, "Crucial partner inquiry at HB 3594 missing from public messages!"


def test_unchanged_full_history_on_disk(isolated_store, isolated_data):
    before_ws_bytes = (isolated_store / "world_state.json").read_bytes()
    before_rel_bytes = (isolated_store / "relationship_ledger.json").read_bytes()

    msgs, events, ident = isolated_data
    adam_id = ident.get("adam_agent_id")

    # Run selection repeatedly
    for _ in range(5):
        _ = select_bounded_public_messages(msgs, agent_ref="east_adam", max_total_messages=35)
        _ = select_bounded_relationship_events(events, agent_id=adam_id, max_total_events=25)

    after_ws_bytes = (isolated_store / "world_state.json").read_bytes()
    after_rel_bytes = (isolated_store / "relationship_ledger.json").read_bytes()

    assert before_ws_bytes == after_ws_bytes, "world_state.json on disk was modified by selection!"
    assert before_rel_bytes == after_rel_bytes, "relationship_ledger.json on disk was modified by selection!"


def test_no_alteration_to_cognition_action_semantics():
    valid_envelope = {
        "observation_summary": "I see an empty tile with no objects.",
        "self_model_update": None,
        "goal_updates": [],
        "proposed_action": {
            "action_type": "move",
            "target_tile": "cont_a_origin_000",
            "reason": "moving to water source"
        },
        "memory_candidates": [],
        "questions_for_humans": [],
        "uncertainty": "Whether any other agents exist nearby.",
        "decision_summary": "Moving to water source.",
        "confidence": 0.8,
    }

    res = validate_model_output(
        valid_envelope,
        context_agent_id="genesis-agent-test",
    )
    assert res.is_valid is True, f"Validation failed unexpectedly: {res.validation_errors}"
    assert res.proposed_action["action_type"] == "move"
    assert res.proposed_action["target_tile"] == "cont_a_origin_000"

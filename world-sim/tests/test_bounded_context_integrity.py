"""Unit and Integration Tests for Bounded Context Integrity (Genesis Phase Path A).

Verifies all seven constitutional properties mandated by the Operator:
1. Strict selection caps (messages <= 35, relationship events <= 25)
2. Historical evidence integrity (fields, IDs, timestamps untampered)
3. Correct agent visibility (no cross-agent private message leaks)
4. Stable chronological ordering (ascending heartbeat order)
5. Preservation of important older events (first contact, creations, questions)
6. Unchanged full history on disk (no disk mutation from selection)
7. No alteration to cognition action semantics (validate_model_output unchanged)
"""
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

ISOLATED_STORE = pathlib.Path(r"C:\Users\seand\.gemini\antigravity\brain\ef6607e4-f06f-4d3a-af0b-67d2ea6e848a\scratch\isolated_east_store")


@pytest.fixture
def isolated_data():
    with open(ISOLATED_STORE / "world_state.json", "r", encoding="utf-8") as f:
        ws = json.load(f)
    msgs = ws.get("data", {}).get("public_messages", [])

    with open(ISOLATED_STORE / "relationship_ledger.json", "r", encoding="utf-8") as f:
        rel_data = json.load(f)
    events = rel_data.get("data", [])

    with open(ISOLATED_STORE / "identity.json", "r", encoding="utf-8") as f:
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

    # Add private messages
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

    eve_selected = select_bounded_public_messages(test_msgs, agent_ref="east_eve", max_total_messages=35)
    adam_selected = select_bounded_public_messages(test_msgs, agent_ref="east_adam", max_total_messages=35)

    eve_ids = {m["message_id"] for m in eve_selected}
    adam_ids = {m["message_id"] for m in adam_selected}

    assert "secret-adam-msg" not in eve_ids, "Private message for Adam leaked into Eve's context!"
    assert "secret-eve-msg" not in adam_ids, "Private message for Eve leaked into Adam's context!"


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


def test_unchanged_full_history_on_disk(isolated_data):
    before_ws_bytes = (ISOLATED_STORE / "world_state.json").read_bytes()
    before_rel_bytes = (ISOLATED_STORE / "relationship_ledger.json").read_bytes()

    msgs, events, ident = isolated_data
    adam_id = ident.get("adam_agent_id")

    # Run selection repeatedly
    for _ in range(5):
        _ = select_bounded_public_messages(msgs, agent_ref="east_adam", max_total_messages=35)
        _ = select_bounded_relationship_events(events, agent_id=adam_id, max_total_events=25)

    after_ws_bytes = (ISOLATED_STORE / "world_state.json").read_bytes()
    after_rel_bytes = (ISOLATED_STORE / "relationship_ledger.json").read_bytes()

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

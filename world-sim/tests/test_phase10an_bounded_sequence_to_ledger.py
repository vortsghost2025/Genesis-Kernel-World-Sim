"""Phase 10AN - bounded sequence to ledger proof.

These tests prove that public 10AM sequence output can be transformed into
verified temp-ledger events and sanitized export proof without becoming runtime.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(TESTS_ROOT))

from backend.world.local_heartbeat_ledger_bridge import (
    bridge_heartbeat_sequence_to_ledger,
)
from backend.world.local_heartbeat_sequence import run_local_heartbeat_sequence
from backend.world.world_event_ledger import read_events

from test_phase10am_bounded_heartbeat_sequence import (
    AGENT_ID,
    HIDDEN_TERMS,
    _empty_known_map,
    _make_true_map,
    _start_position,
)


def _sequence_ok() -> dict:
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-2", "directions": ["southeast"]},
    ]
    return run_local_heartbeat_sequence(
        true_map=_make_true_map(),
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
        sequence_id="seq-10an",
    )


def _sequence_blocked() -> dict:
    plan = [{"heartbeat_id": "hb-blocked", "directions": ["south"]}]
    return run_local_heartbeat_sequence(
        true_map=_make_true_map(),
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
        sequence_id="seq-blocked",
    )


def _bridge(sequence: dict, tmp_path: Path) -> dict:
    return bridge_heartbeat_sequence_to_ledger(
        sequence,
        ledger_dir=tmp_path,
        actor_id=AGENT_ID,
    )


def _assert_temp_path(path_text: str) -> None:
    root = Path(tempfile.gettempdir()).resolve()
    path = Path(path_text).resolve()
    path.relative_to(root)


def _assert_no_hidden_payload(value: object) -> None:
    text = json.dumps(value, sort_keys=True)
    for term in HIDDEN_TERMS:
        assert term not in text, f"hidden term leaked: {term}"


def test_happy_path_sequence_produces_verified_ledger_events(tmp_path):
    sequence = _sequence_ok()
    result = _bridge(sequence, tmp_path)

    assert result["ok"] is True
    assert result["sequence_ok"] is True
    assert result["event_count"] == len(sequence["timeline"])
    assert result["rejected_count"] == 0
    assert result["errors"] == []
    assert result["failure"] is None

    ledger_path = Path(result["ledger_path"])
    assert ledger_path.exists()
    _assert_temp_path(result["ledger_path"])

    events = read_events(ledger_path)
    assert len(events) == result["event_count"]
    assert all(event["verification_status"] == "accepted" for event in events)
    assert [event["action_type"] for event in events] == [
        entry["action"] for entry in sequence["timeline"]
    ]


def test_observe_and_move_timeline_entries_map_correctly(tmp_path):
    sequence = _sequence_ok()
    result = _bridge(sequence, tmp_path)
    events = read_events(result["ledger_path"])

    observe_entries = [e for e in sequence["timeline"] if e["action"] == "observe"]
    move_entries = [e for e in sequence["timeline"] if e["action"] == "move_local"]
    observe_events = [e for e in events if e["action_type"] == "observe"]
    move_events = [e for e in events if e["action_type"] == "move_local"]

    assert len(observe_events) == len(observe_entries)
    assert len(move_events) == len(move_entries)

    first_observe = observe_events[0]
    assert first_observe["claim_scope"] == "observed"
    assert first_observe["territory_ref"] == observe_entries[0]["territory_ref"]
    assert first_observe["evidence_refs"][0]["category"] == "observed_world_fact"

    first_move = move_events[0]
    first_move_entry = move_entries[0]
    assert first_move["claim_scope"] == "observed"
    assert first_move["territory_ref"] == first_move_entry["territory_ref"]
    assert first_move["before_ref"] == f"tile:{first_move_entry['from_tile_id']}"
    assert first_move["after_ref"] == f"tile:{first_move_entry['to_tile_id']}"
    assert first_move["evidence_refs"][0]["category"] == "agent_action"


def test_invalid_or_rejected_candidate_is_counted_and_does_not_poison_ledger(tmp_path):
    sequence = _sequence_ok()
    sequence["timeline"].append({"action": "unknown", "tick": 999})
    sequence["timeline"].append({
        "action": "move_local",
        "tick": 1000,
        "ok": False,
        "from_tile_id": "tile_a",
        "to_tile_id": "tile_b",
        "territory_ref": "reg_a",
        "error": "blocked",
    })

    result = _bridge(sequence, tmp_path)
    events = read_events(result["ledger_path"])

    assert result["ok"] is True
    assert result["event_count"] == len(_sequence_ok()["timeline"])
    assert result["rejected_count"] == 2
    assert len(events) == result["event_count"]
    assert all(event["verification_status"] == "accepted" for event in events)


def test_tempdir_only_ledger_boundary_is_enforced():
    sequence = _sequence_ok()

    result = bridge_heartbeat_sequence_to_ledger(
        sequence,
        ledger_dir=PROJECT_ROOT,
        actor_id=AGENT_ID,
    )

    assert result["ok"] is False
    assert result["sequence_ok"] is None
    assert result["event_count"] == 0
    assert result["ledger_path"] is None
    assert result["failure"]["error"] == "unsafe ledger_dir"
    assert "temp folder" in result["errors"][0]


def test_sanitized_export_contains_no_hidden_substrate(tmp_path):
    sequence = _sequence_ok()
    result = _bridge(sequence, tmp_path)

    assert result["sanitized_export"]
    parsed = json.loads(result["sanitized_export"])
    assert len(parsed) == result["event_count"]
    _assert_no_hidden_payload(result["sanitized_export"])

    exported_text = result["sanitized_export"]
    assert "true_map" not in exported_text
    assert "travel_edges" not in exported_text
    assert ("world-sim" + "/data") not in exported_text


def test_true_map_is_never_returned_or_exported(tmp_path):
    sequence = _sequence_ok()
    result = _bridge(sequence, tmp_path)

    assert "true_map" not in result
    assert "true_map" not in result["sanitized_export"]

    events = read_events(result["ledger_path"])
    for event in events:
        assert "true_map" not in event
        assert "true_map" not in json.dumps(event, sort_keys=True)


def test_caller_owned_sequence_input_is_not_mutated(tmp_path):
    sequence = _sequence_ok()
    before = copy.deepcopy(sequence)

    result = _bridge(sequence, tmp_path)

    assert result["ok"] is True
    assert sequence == before


def test_deterministic_replay_with_same_sequence(tmp_path):
    sequence = _sequence_ok()

    first = bridge_heartbeat_sequence_to_ledger(
        sequence,
        ledger_dir=tmp_path / "one",
        actor_id=AGENT_ID,
    )
    second = bridge_heartbeat_sequence_to_ledger(
        sequence,
        ledger_dir=tmp_path / "two",
        actor_id=AGENT_ID,
    )

    assert first["ok"] is True
    assert second["ok"] is True
    assert first["event_count"] == second["event_count"]

    first_events = read_events(first["ledger_path"])
    second_events = read_events(second["ledger_path"])

    assert [
        (event["event_id"], event["tick"], event["action_type"], event["summary"])
        for event in first_events
    ] == [
        (event["event_id"], event["tick"], event["action_type"], event["summary"])
        for event in second_events
    ]
    assert first["sanitized_export"] == second["sanitized_export"]


def test_blocked_sequence_failure_is_represented_safely(tmp_path):
    sequence = _sequence_blocked()
    assert sequence["ok"] is False

    result = _bridge(sequence, tmp_path)

    assert result["ok"] is False
    assert result["sequence_ok"] is False
    assert result["failure"] is not None
    assert result["failed_tick"] == sequence["failed_tick"]
    assert result["failed_direction"] == sequence["failed_direction"]
    assert result["failed_heartbeat_id"] == sequence["failed_heartbeat_id"]
    assert result["event_count"] >= 1
    assert result["rejected_count"] >= 1
    assert result["sanitized_export"]

    _assert_no_hidden_payload(result)
    assert "true_map" not in json.dumps(result, sort_keys=True)


def test_sequence_timeline_must_be_a_list(tmp_path):
    sequence = _sequence_ok()
    sequence["timeline"] = {"bad": "not-list"}

    result = _bridge(sequence, tmp_path)

    assert result["ok"] is False
    assert result["event_count"] == 0
    assert result["rejected_count"] == 0
    assert "timeline must be a list" in result["errors"][0]


def test_runtime_marker_scan_passes():
    module_path = PROJECT_ROOT / "backend/world/local_heartbeat_ledger_bridge.py"
    test_path = PROJECT_ROOT / "tests/test_phase10an_bounded_sequence_to_ledger.py"

    text = module_path.read_text(encoding="utf-8") + test_path.read_text(encoding="utf-8")

    forbidden_markers = [
        "while " + "True",
        "async" + "io",
        "thread" + "ing",
        "sub" + "process",
        "sock" + "et",
        "requests" + ".",
        "http" + "://",
        "https" + "://",
        "dock" + "er",
        "pro" + "vider",
        "API" + "_KEY",
        "TOKEN" + "=",
    ]

    for marker in forbidden_markers:
        assert marker not in text

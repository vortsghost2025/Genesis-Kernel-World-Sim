"""Phase 10CV - minimal gate-7-free dry-run adapter tests."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from backend.world.local_gate7_free_dry_run_adapter import (
    create_gate7_free_dry_run_adapter_decision,
    export_gate7_free_dry_run_adapter_decision,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_gate7_free_dry_run_adapter.py"
)

KNOWN_SIGNAL_TYPES = (
    "snapshot_id_equality",
    "snapshot_hash_equality",
    "current_tile_id_equality",
    "route_intent_id_equality",
    "known_tile_ids_set_equality",
    "route_destination_tile_id_equality",
)

GATE_FLAGS = (
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

ALLOWED_INPUT_FIELDS = {
    "ok",
    "adapter_schema_version",
    "adapter_type",
    "adapter_scope",
    "adapter_decision_id",
    "source_decision_id",
    "source_consumer_scope",
    "source_signal_seen",
    "recognized_signal_type",
    "planned_action",
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
}

OUTPUT_FIELDS = {
    "ok",
    "gate7_adapter_schema_version",
    "gate7_adapter_type",
    "gate7_adapter_scope",
    "gate7_adapter_decision_id",
    "source_adapter_decision_id",
    "source_decision_id",
    "source_consumer_scope",
    "source_signal_seen",
    "recognized_signal_type",
    "planned_action",
    "candidate_action",
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
    "ledger_write_attempted",
    "claim_boundary",
    "errors",
}

FORBIDDEN_OUTPUT_FIELDS = {
    "equality_signal_value",
    "equality_signal_type",
    "agent_id",
    "tile",
    "route",
    "path",
    "destination",
    "timing",
    "co_presence",
    "awareness",
    "relationship",
    "interaction",
    "movement",
    "map_lookup",
    "emit_event",
    "create_event",
    "npc_behavior",
}


def _valid_10cj_decision(
    signal_type: str = "snapshot_id_equality",
) -> dict:
    return {
        "ok": True,
        "adapter_schema_version": "10CJ.1",
        "adapter_type": "runtime_adapter_dry_run_decision",
        "adapter_scope": "dry_run_only",
        "adapter_decision_id": "10CJ-test-adapter-decision",
        "source_decision_id": "10BT-test-decision",
        "source_consumer_scope": "record_public_equality_signal_only",
        "source_signal_seen": True,
        "recognized_signal_type": signal_type,
        "planned_action": "log_only",
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
    }


def _assert_inert(result: dict) -> None:
    assert result["executed"] is False
    for flag in GATE_FLAGS:
        assert result[flag] is False
    assert result["ledger_write_attempted"] is False
    assert result["planned_action"] in {"none", "log_only"}
    assert result["candidate_action"] in {
        "none",
        "eligible_for_inert_ledger_log",
    }


def test_non_dict_input_returns_false_and_inert():
    result = create_gate7_free_dry_run_adapter_decision("not-a-dict")

    assert result["ok"] is False
    assert result["candidate_action"] == "none"
    assert result["errors"]
    _assert_inert(result)


def test_non_ok_input_returns_false():
    decision = _valid_10cj_decision()
    decision["ok"] = False

    result = create_gate7_free_dry_run_adapter_decision(decision)

    assert result["ok"] is False
    assert result["candidate_action"] == "none"
    _assert_inert(result)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("adapter_schema_version", "10CJ.2"),
        ("adapter_type", "not-a-10cj-decision"),
        ("adapter_scope", "not-dry-run"),
        ("planned_action", "none"),
        ("executed", True),
        ("runtime_allowed", True),
        ("daemon_allowed", True),
        ("scheduler_allowed", True),
        ("network_allowed", True),
        ("world_sim_data_accessed", True),
    ],
)
def test_invalid_required_field_is_rejected(field: str, value: object):
    decision = _valid_10cj_decision()
    decision[field] = value

    result = create_gate7_free_dry_run_adapter_decision(decision)

    assert result["ok"] is False
    assert result["planned_action"] == "none"
    assert result["candidate_action"] == "none"
    assert result["errors"]
    _assert_inert(result)


def test_source_signal_not_seen_has_no_candidate_action():
    decision = _valid_10cj_decision()
    decision["source_signal_seen"] = False

    result = create_gate7_free_dry_run_adapter_decision(decision)

    assert result["ok"] is False
    assert result["candidate_action"] == "none"
    _assert_inert(result)


@pytest.mark.parametrize("signal_type", KNOWN_SIGNAL_TYPES)
def test_each_known_signal_type_is_eligible_for_inert_ledger_log(
    signal_type: str,
):
    result = create_gate7_free_dry_run_adapter_decision(
        _valid_10cj_decision(signal_type)
    )

    assert result["ok"] is True
    assert result["recognized_signal_type"] == signal_type
    assert result["planned_action"] == "log_only"
    assert result["candidate_action"] == "eligible_for_inert_ledger_log"
    assert result["errors"] == []
    _assert_inert(result)


def test_unknown_signal_type_has_no_candidate_action():
    result = create_gate7_free_dry_run_adapter_decision(
        _valid_10cj_decision("future_unknown_signal")
    )

    assert result["ok"] is False
    assert result["candidate_action"] == "none"
    _assert_inert(result)


def test_output_has_exactly_the_inert_envelope_fields():
    cases = [
        create_gate7_free_dry_run_adapter_decision("not-a-dict"),
        create_gate7_free_dry_run_adapter_decision(_valid_10cj_decision()),
        create_gate7_free_dry_run_adapter_decision(
            _valid_10cj_decision("future_unknown_signal")
        ),
    ]

    for result in cases:
        assert set(result) == OUTPUT_FIELDS
        assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(result)
        _assert_inert(result)


def test_forbidden_extra_input_fields_are_ignored_and_not_emitted():
    first_input = _valid_10cj_decision()
    first_input.update(
        {
            "equality_signal_value": "opaque-one",
            "route": "route-one",
            "co_presence": True,
            "npc_behavior": "act",
        }
    )
    second_input = dict(first_input)
    second_input.update(
        {
            "equality_signal_value": "opaque-two",
            "route": "route-two",
            "co_presence": False,
            "npc_behavior": "other",
        }
    )

    first = create_gate7_free_dry_run_adapter_decision(first_input)
    second = create_gate7_free_dry_run_adapter_decision(second_input)

    assert first == second
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(first)


def test_all_gate_flags_and_ledger_attempt_are_false_on_every_path():
    invalid_gate = _valid_10cj_decision()
    invalid_gate["network_allowed"] = True
    cases = [
        create_gate7_free_dry_run_adapter_decision(None),
        create_gate7_free_dry_run_adapter_decision(invalid_gate),
        create_gate7_free_dry_run_adapter_decision(_valid_10cj_decision()),
    ]

    for result in cases:
        _assert_inert(result)


def test_export_is_deterministic_sorted_json():
    result = create_gate7_free_dry_run_adapter_decision(
        _valid_10cj_decision("current_tile_id_equality")
    )

    first = export_gate7_free_dry_run_adapter_decision(result)
    second = export_gate7_free_dry_run_adapter_decision(result)

    assert first == second
    assert first == json.dumps(result, sort_keys=True, ensure_ascii=False)
    assert json.loads(first) == result


def test_decision_id_is_deterministic_for_same_input():
    decision = _valid_10cj_decision("route_intent_id_equality")

    first = create_gate7_free_dry_run_adapter_decision(decision)
    second = create_gate7_free_dry_run_adapter_decision(dict(decision))

    assert first == second
    assert first["gate7_adapter_decision_id"].startswith("10CV-")


def test_module_has_only_allowed_imports():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    allowed_import_roots = {"__future__", "hashlib", "json", "typing"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed_import_roots
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] in allowed_import_roots


def test_module_does_not_call_file_or_scanning_apis():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    forbidden_calls = {
        "open",
        "read",
        "write",
        "glob",
        "rglob",
        "listdir",
        "walk",
        "scandir",
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_calls
        elif isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_calls


def test_module_does_not_import_or_call_10cp_or_10bt():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    forbidden_modules = {
        "local_runtime_adapter_inert_ledger_writer",
        "local_shared_public_contract_consumer_harness",
    }
    forbidden_calls = {
        "append_inert_ledger_record",
        "create_shared_public_contract_consumer_decision",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert forbidden_modules.isdisjoint(alias.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            assert forbidden_modules.isdisjoint((node.module or "").split("."))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls
            elif isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls


def test_module_reads_only_allowlisted_10cj_fields():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "adapter_decision"
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            assert node.args[0].value in ALLOWED_INPUT_FIELDS
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "adapter_decision"
            and isinstance(node.slice, ast.Constant)
        ):
            assert node.slice.value in ALLOWED_INPUT_FIELDS

"""Phase 10DL - minimal authorized runtime adapter integration tests."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from backend.world.local_minimal_runtime_adapter_integration_harness import (
    export_minimal_runtime_adapter_integration_result,
    run_minimal_runtime_adapter_integration,
)
from backend.world.local_runtime_adapter_dry_run_harness import (
    create_runtime_adapter_dry_run_decision,
)
from backend.world.local_runtime_adapter_inert_ledger_writer import (
    append_inert_ledger_record,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_runtime_adapter_integration_harness.py"
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
)

OUTPUT_FIELDS = {
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
    "claim_boundary",
    "errors",
}

FORBIDDEN_OUTPUT_FIELDS = {
    "equality_signal_value",
    "equality_signal_type",
    "candidate_action",
    "gate7_activity_allowed",
    "ledger_write_requested",
    "ledger_write_attempted",
    "ledger_record_written",
    "ledger_path_authorized",
    "ledger_record_hash",
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
    "daemon_output",
    "scheduler_output",
    "network_output",
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
    assert result["planned_action"] in {"none", "log_only"}


def test_valid_10cj_decision_returns_exact_10cj_shape():
    result = run_minimal_runtime_adapter_integration(
        _valid_10cj_decision()
    )

    assert result["ok"] is True
    assert result["adapter_schema_version"] == "10CJ.1"
    assert result["adapter_type"] == "runtime_adapter_dry_run_decision"
    assert result["adapter_scope"] == "dry_run_only"
    assert result["adapter_decision_id"] == "10CJ-test-adapter-decision"
    assert result["planned_action"] == "log_only"
    assert result["errors"] == []
    assert set(result) == OUTPUT_FIELDS
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(result)
    _assert_inert(result)


def test_actual_10cj_generated_decision_composes_without_contract_drift():
    source = create_runtime_adapter_dry_run_decision(
        {
            "ok": True,
            "decision_id": "10BT-generated-source",
            "consumer_scope": "record_public_equality_signal_only",
            "equality_signal_type": "snapshot_hash_equality",
            "equality_signal_present": True,
        }
    )

    result = run_minimal_runtime_adapter_integration(source)

    assert source["ok"] is True
    assert result["ok"] is True
    assert set(result) == set(source) == OUTPUT_FIELDS
    assert result["adapter_decision_id"] == source["adapter_decision_id"]
    assert result["source_decision_id"] == source["source_decision_id"]
    assert result["recognized_signal_type"] == "snapshot_hash_equality"
    _assert_inert(result)


@pytest.mark.parametrize("signal_type", KNOWN_SIGNAL_TYPES)
def test_each_known_10cj_signal_stays_inert(signal_type: str):
    result = run_minimal_runtime_adapter_integration(
        _valid_10cj_decision(signal_type)
    )

    assert result["ok"] is True
    assert result["recognized_signal_type"] == signal_type
    assert result["planned_action"] == "log_only"
    _assert_inert(result)


def test_invalid_10cj_decision_fails_closed():
    decision = _valid_10cj_decision()
    decision["network_allowed"] = True

    result = run_minimal_runtime_adapter_integration(decision)

    assert result["ok"] is False
    assert result["planned_action"] == "none"
    assert result["errors"]
    assert set(result) == OUTPUT_FIELDS
    _assert_inert(result)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("adapter_decision_id", ""),
        ("source_decision_id", None),
        ("source_consumer_scope", "unexpected_scope"),
    ],
)
def test_incomplete_10cj_identity_fails_closed(field: str, value: object):
    decision = _valid_10cj_decision()
    decision[field] = value

    result = run_minimal_runtime_adapter_integration(decision)

    assert result["ok"] is False
    assert result["planned_action"] == "none"
    assert result["errors"]
    _assert_inert(result)


def test_equality_signal_value_is_ignored_and_never_emitted():
    first = _valid_10cj_decision()
    first["equality_signal_value"] = "opaque-one"
    second = dict(first)
    second["equality_signal_value"] = "opaque-two"

    first_result = run_minimal_runtime_adapter_integration(first)
    second_result = run_minimal_runtime_adapter_integration(second)

    assert first_result == second_result
    assert first_result["ok"] is True
    assert "equality_signal_value" not in first_result
    assert "equality_signal_value" not in json.dumps(first_result)


def test_result_remains_compatible_with_existing_10cp_writer(tmp_path: Path):
    result = run_minimal_runtime_adapter_integration(
        _valid_10cj_decision("route_intent_id_equality")
    )
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    writer_result = append_inert_ledger_record(
        result,
        ledger_path,
        ledger_path,
        recorded_at_utc="2026-07-12T12:00:00Z",
    )

    assert writer_result["ok"] is True
    assert writer_result["ledger_record_written"] is True
    assert ledger_path.read_text(encoding="utf-8").count("\n") == 1


def test_result_and_export_are_deterministic():
    decision = _valid_10cj_decision("current_tile_id_equality")

    first = run_minimal_runtime_adapter_integration(decision)
    second = run_minimal_runtime_adapter_integration(dict(decision))
    assert first == second

    exported = export_minimal_runtime_adapter_integration_result(first)
    assert exported == json.dumps(first, sort_keys=True, ensure_ascii=False)
    assert json.loads(exported) == first


def test_module_imports_only_10cv_from_backend_and_has_no_direct_io():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    backend_imports: list[str] = []
    allowed_import_roots = {
        "__future__",
        "hashlib",
        "json",
        "typing",
        "backend",
    }
    forbidden_calls = {
        "open",
        "read",
        "write",
        "glob",
        "rglob",
        "listdir",
        "walk",
        "scandir",
        "append_inert_ledger_record",
        "emit_event",
        "create_event",
        "map_lookup",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed_import_roots
                if alias.name.startswith("backend."):
                    backend_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module.split(".")[0] in allowed_import_roots
            if module.startswith("backend."):
                backend_imports.append(module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls
            elif isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls

    assert backend_imports == [
        "backend.world.local_gate7_free_dry_run_adapter"
    ]
    assert "world-sim/data" not in source
    assert "equality_signal_value" not in source

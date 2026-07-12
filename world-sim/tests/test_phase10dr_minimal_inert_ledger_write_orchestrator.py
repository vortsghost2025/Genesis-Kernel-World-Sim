"""Phase 10DR - minimal inert ledger write orchestrator tests."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

import backend.world.local_minimal_inert_ledger_write_orchestrator as orchestrator_module
from backend.world.local_minimal_inert_ledger_write_orchestrator import (
    export_minimal_inert_ledger_write_result,
    run_minimal_inert_ledger_write_orchestration,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_ledger_write_orchestrator.py"
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
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

OUTPUT_FIELDS = {
    "ok",
    "orchestrator_schema_version",
    "orchestrator_type",
    "orchestrator_scope",
    "orchestrator_decision_id",
    "source_consumer_decision_id",
    "source_adapter_decision_id",
    "recognized_signal_type",
    "planned_action",
    "ledger_write_requested",
    "ledger_write_attempted",
    "ledger_record_written",
    "ledger_path_authorized",
    "ledger_record_hash",
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
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
    "daemon_output",
    "scheduler_output",
    "network_output",
    "bytes_appended",
}


def _valid_10bt_decision(
    signal_type: str = "snapshot_id_equality",
) -> dict:
    return {
        "ok": True,
        "decision_schema_version": "10BT.1",
        "decision_type": "shared_public_contract_consumer_decision",
        "decision_id": "10BT-test-consumer-decision",
        "source_contract_id": "10BP-test-contract",
        "source_contract_type": "shared_public_snapshot_id_equality_contract",
        "source_contract_schema_version": "10BP.1",
        "source_claim_scope": "shared_public_snapshot_id_equality_only",
        "source_merge_hash": "a" * 64,
        "consumer_scope": "record_public_equality_signal_only",
        "contract_seen": True,
        "contract_ok": True,
        "equality_signal_present": True,
        "equality_signal_type": signal_type,
        "equality_signal_value": "opaque-public-value",
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "claim_boundary": "public equality signal only",
        "errors": [],
    }


def _run(
    decision: object,
    ledger_path: object = None,
    authorized_ledger_path: object = None,
) -> dict:
    return run_minimal_inert_ledger_write_orchestration(
        decision,
        ledger_path=ledger_path,
        authorized_ledger_path=authorized_ledger_path,
        recorded_at_utc="2026-07-12T12:00:00Z",
    )


def _assert_inert(result: dict) -> None:
    for flag in GATE_FLAGS:
        assert result[flag] is False, flag
    assert result["planned_action"] in {"none", "log_only"}


def _assert_rejected_without_write(result: dict, ledger_path: Path) -> None:
    assert result["ok"] is False
    assert result["ledger_record_written"] is False
    assert result["ledger_record_hash"] is None
    assert result["errors"]
    assert not ledger_path.exists()
    _assert_inert(result)


def test_valid_inert_path_writes_exactly_one_ndjson_line_through_10cp(
    tmp_path: Path,
):
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run(_valid_10bt_decision(), ledger_path, ledger_path)

    assert result["ok"] is True
    assert result["orchestrator_schema_version"] == "10DR.1"
    assert result["orchestrator_type"] == (
        "minimal_inert_ledger_write_orchestrator_result"
    )
    assert result["orchestrator_scope"] == "inert_ledger_write_only"
    assert result["orchestrator_decision_id"].startswith("10DR-")
    assert result["source_consumer_decision_id"].startswith("10BT-")
    assert result["source_adapter_decision_id"].startswith("10CJ-")
    assert result["recognized_signal_type"] == "snapshot_id_equality"
    assert result["planned_action"] == "log_only"
    assert result["ledger_write_requested"] is True
    assert result["ledger_write_attempted"] is True
    assert result["ledger_record_written"] is True
    assert result["ledger_path_authorized"] is True
    assert result["ledger_record_hash"]
    assert result["errors"] == []
    assert set(result) == OUTPUT_FIELDS
    _assert_inert(result)

    payload = ledger_path.read_bytes()
    assert payload.endswith(b"\n")
    assert payload.count(b"\n") == 1
    record = json.loads(payload)
    assert record["record_hash"] == result["ledger_record_hash"]
    assert record["adapter_decision_id"] == result["source_adapter_decision_id"]


@pytest.mark.parametrize("signal_type", KNOWN_SIGNAL_TYPES)
def test_each_known_inert_signal_can_write_through_existing_chain(
    signal_type: str,
    tmp_path: Path,
):
    ledger_path = tmp_path / f"{signal_type}.ndjson"

    result = _run(
        _valid_10bt_decision(signal_type),
        ledger_path,
        ledger_path,
    )

    assert result["ok"] is True
    assert result["recognized_signal_type"] == signal_type
    assert result["ledger_record_written"] is True
    assert ledger_path.read_bytes().count(b"\n") == 1
    _assert_inert(result)


def test_no_write_occurs_by_default():
    result = _run(_valid_10bt_decision())

    assert result["ok"] is False
    assert result["ledger_write_requested"] is False
    assert result["ledger_write_attempted"] is False
    assert result["ledger_record_written"] is False
    assert result["ledger_path_authorized"] is False
    assert result["ledger_record_hash"] is None
    _assert_inert(result)


@pytest.mark.parametrize("missing", ["ledger", "authorized"])
def test_missing_path_fails_closed(missing: str, tmp_path: Path):
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"
    candidate = None if missing == "ledger" else ledger_path
    authorized = None if missing == "authorized" else ledger_path

    result = _run(_valid_10bt_decision(), candidate, authorized)

    assert result["ledger_write_requested"] is False
    assert result["ledger_write_attempted"] is False
    _assert_rejected_without_write(result, ledger_path)


def test_unauthorized_path_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "candidate.ndjson"
    authorized_path = tmp_path / "authorized.ndjson"

    result = _run(_valid_10bt_decision(), ledger_path, authorized_path)

    assert result["ledger_write_requested"] is True
    assert result["ledger_write_attempted"] is True
    assert result["ledger_path_authorized"] is False
    _assert_rejected_without_write(result, ledger_path)
    assert not authorized_path.exists()


def test_missing_parent_is_rejected_by_10cp_without_directory_creation(
    tmp_path: Path,
):
    ledger_path = tmp_path / "missing" / "runtime_adapter_decisions.ndjson"

    result = _run(_valid_10bt_decision(), ledger_path, ledger_path)

    assert result["ledger_write_requested"] is True
    assert result["ledger_write_attempted"] is True
    assert result["ledger_path_authorized"] is True
    _assert_rejected_without_write(result, ledger_path)
    assert not ledger_path.parent.exists()


@pytest.mark.parametrize(
    "flag",
    (
        "runtime_allowed",
        "daemon_allowed",
        "scheduler_allowed",
        "network_allowed",
        "world_sim_data_accessed",
        "gate7_activity_allowed",
        "provider_allowed",
        "launcher_allowed",
        "container_allowed",
        "docker_allowed",
    ),
)
def test_gate_true_input_fails_closed(flag: str, tmp_path: Path):
    decision = _valid_10bt_decision()
    decision[flag] = True
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run(decision, ledger_path, ledger_path)

    assert result["ledger_write_requested"] is True
    assert result["ledger_write_attempted"] is False
    _assert_rejected_without_write(result, ledger_path)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", False),
        ("ok", 1),
        ("decision_schema_version", "10BT.2"),
        ("decision_type", "not-a-10bt-decision"),
        ("decision_id", ""),
        ("consumer_scope", "unexpected_scope"),
        ("equality_signal_present", False),
        ("equality_signal_present", 1),
        ("equality_signal_type", "future_unknown_signal"),
    ),
)
def test_malformed_10bt_chain_fails_closed(
    field: str,
    value: object,
    tmp_path: Path,
):
    decision = _valid_10bt_decision()
    decision[field] = value
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run(decision, ledger_path, ledger_path)

    assert result["ledger_write_attempted"] is False
    _assert_rejected_without_write(result, ledger_path)


@pytest.mark.parametrize(
    ("stage", "field", "value"),
    (
        ("10CJ", "source_decision_id", "10BT-substituted"),
        ("10CJ", "recognized_signal_type", "snapshot_hash_equality"),
        ("10DL", "source_decision_id", "10BT-substituted"),
        ("10DL", "adapter_decision_id", "10CJ-substituted"),
        ("10DL", "recognized_signal_type", "snapshot_hash_equality"),
    ),
)
def test_dependency_provenance_mismatch_fails_closed(
    stage: str,
    field: str,
    value: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    dependency_name = (
        "create_runtime_adapter_dry_run_decision"
        if stage == "10CJ"
        else "run_minimal_runtime_adapter_integration"
    )
    original = getattr(orchestrator_module, dependency_name)

    def tampered_dependency(source: dict) -> dict:
        result = original(source)
        result[field] = value
        return result

    monkeypatch.setattr(orchestrator_module, dependency_name, tampered_dependency)
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run(_valid_10bt_decision(), ledger_path, ledger_path)

    assert result["ledger_write_attempted"] is False
    _assert_rejected_without_write(result, ledger_path)


@pytest.mark.parametrize(
    ("stage", "field", "value"),
    (
        ("10CJ", "ok", 1),
        ("10CJ", "executed", 0),
        ("10DL", "source_signal_seen", 1),
        ("10DL", "runtime_allowed", 0),
    ),
)
def test_dependency_boolean_type_drift_fails_closed(
    stage: str,
    field: str,
    value: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    dependency_name = (
        "create_runtime_adapter_dry_run_decision"
        if stage == "10CJ"
        else "run_minimal_runtime_adapter_integration"
    )
    original = getattr(orchestrator_module, dependency_name)

    def tampered_dependency(source: dict) -> dict:
        result = original(source)
        result[field] = value
        return result

    monkeypatch.setattr(orchestrator_module, dependency_name, tampered_dependency)
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run(_valid_10bt_decision(), ledger_path, ledger_path)

    assert result["ledger_write_attempted"] is False
    _assert_rejected_without_write(result, ledger_path)


@pytest.mark.parametrize("stage", ["10CJ", "10DL"])
def test_malformed_dependency_error_envelope_fails_closed(
    stage: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    dependency_name = (
        "create_runtime_adapter_dry_run_decision"
        if stage == "10CJ"
        else "run_minimal_runtime_adapter_integration"
    )
    original = getattr(orchestrator_module, dependency_name)

    def malformed_dependency(source: dict) -> dict:
        result = original(source)
        result["errors"] = [{"malformed": True}]
        return result

    monkeypatch.setattr(orchestrator_module, dependency_name, malformed_dependency)
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run(_valid_10bt_decision(), ledger_path, ledger_path)

    assert result["ledger_write_attempted"] is False
    _assert_rejected_without_write(result, ledger_path)


def test_malformed_10cp_error_envelope_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def malformed_writer(*args: object, **kwargs: object) -> dict:
        return {
            "ok": True,
            "ledger_record_written": True,
            "ledger_path_authorized": True,
            "record_hash": "b" * 64,
            "errors": [{"malformed": True}],
        }

    monkeypatch.setattr(
        orchestrator_module,
        "append_inert_ledger_record",
        malformed_writer,
    )
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run(_valid_10bt_decision(), ledger_path, ledger_path)

    assert result["ok"] is False
    assert result["ledger_write_attempted"] is True
    assert result["ledger_record_written"] is True
    assert result["ledger_record_hash"] == "b" * 64
    assert result["errors"]
    _assert_inert(result)


def test_writer_confirmed_append_is_reported_even_when_writer_rejects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def inconsistent_writer(*args: object, **kwargs: object) -> dict:
        return {
            "ok": False,
            "ledger_record_written": True,
            "ledger_path_authorized": True,
            "record_hash": "a" * 64,
            "errors": ["post-write confirmation failed"],
        }

    monkeypatch.setattr(
        orchestrator_module,
        "append_inert_ledger_record",
        inconsistent_writer,
    )
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run(_valid_10bt_decision(), ledger_path, ledger_path)

    assert result["ok"] is False
    assert result["ledger_write_attempted"] is True
    assert result["ledger_record_written"] is True
    assert result["ledger_path_authorized"] is True
    assert result["ledger_record_hash"] == "a" * 64
    assert result["errors"]
    _assert_inert(result)


def test_unencodable_consumer_id_fails_closed_without_raising(tmp_path: Path):
    decision = _valid_10bt_decision()
    decision["decision_id"] = "\ud800"
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run(decision, ledger_path, ledger_path)

    assert result["ledger_write_attempted"] is False
    _assert_rejected_without_write(result, ledger_path)


def test_unencodable_recorded_time_fails_closed_without_write(tmp_path: Path):
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = run_minimal_inert_ledger_write_orchestration(
        _valid_10bt_decision(),
        ledger_path=ledger_path,
        authorized_ledger_path=ledger_path,
        recorded_at_utc="\ud800",
    )

    assert result["ledger_write_attempted"] is True
    _assert_rejected_without_write(result, ledger_path)


def test_non_dict_input_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run("not-a-dict", ledger_path, ledger_path)

    assert result["source_consumer_decision_id"] is None
    assert result["source_adapter_decision_id"] is None
    assert result["ledger_write_attempted"] is False
    _assert_rejected_without_write(result, ledger_path)


@pytest.mark.parametrize(
    "field",
    (
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
    ),
)
def test_forbidden_input_field_fails_closed(field: str, tmp_path: Path):
    decision = _valid_10bt_decision()
    decision[field] = "forbidden"
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run(decision, ledger_path, ledger_path)

    assert result["ledger_write_attempted"] is False
    _assert_rejected_without_write(result, ledger_path)


class _UnreadableSignalValueDecision(dict):
    def get(self, key: object, default: object = None) -> object:
        if key == "equality_signal_value":
            raise AssertionError("10DR read equality_signal_value")
        return super().get(key, default)

    def __getitem__(self, key: object) -> object:
        if key == "equality_signal_value":
            raise AssertionError("10DR read equality_signal_value")
        return super().__getitem__(key)


def test_equality_signal_value_is_never_read_or_emitted(tmp_path: Path):
    decision = _UnreadableSignalValueDecision(_valid_10bt_decision())
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    result = _run(decision, ledger_path, ledger_path)

    assert result["ok"] is True
    assert "equality_signal_value" not in result
    assert "equality_signal_value" not in json.dumps(result)
    assert "equality_signal_value" not in MODULE_PATH.read_text(encoding="utf-8")


def test_output_contains_only_safe_status_fields(tmp_path: Path):
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"
    success = _run(_valid_10bt_decision(), ledger_path, ledger_path)
    failure = _run({}, ledger_path, ledger_path)

    for result in (success, failure):
        assert set(result) == OUTPUT_FIELDS
        assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(result)
        _assert_inert(result)


def test_input_is_not_mutated(tmp_path: Path):
    decision = _valid_10bt_decision()
    original = copy.deepcopy(decision)
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"

    _run(decision, ledger_path, ledger_path)

    assert decision == original


def test_export_is_deterministic_sorted_json():
    result = _run(_valid_10bt_decision())

    first = export_minimal_inert_ledger_write_result(result)
    second = export_minimal_inert_ledger_write_result(dict(result))

    assert first == second
    assert first == json.dumps(result, sort_keys=True, ensure_ascii=False)
    assert json.loads(first) == result


def test_gate_flags_are_false_on_success_and_failure(tmp_path: Path):
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"
    bad_gate = _valid_10bt_decision()
    bad_gate["network_allowed"] = True
    cases = (
        _run(_valid_10bt_decision(), ledger_path, ledger_path),
        _run(_valid_10bt_decision()),
        _run(bad_gate, tmp_path / "other.ndjson", tmp_path / "other.ndjson"),
        _run(None, tmp_path / "third.ndjson", tmp_path / "third.ndjson"),
    )

    for result in cases:
        _assert_inert(result)


def test_module_uses_only_public_10cj_10dl_10cp_surfaces():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    backend_imports: list[tuple[str, tuple[str, ...]]] = []
    allowed_import_roots = {
        "__future__",
        "hashlib",
        "json",
        "typing",
        "backend",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed_import_roots
                if alias.name.startswith("backend."):
                    backend_imports.append((alias.name, ()))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module.split(".")[0] in allowed_import_roots
            if module.startswith("backend."):
                backend_imports.append(
                    (module, tuple(alias.name for alias in node.names))
                )

    assert backend_imports == [
        (
            "backend.world.local_minimal_runtime_adapter_integration_harness",
            ("run_minimal_runtime_adapter_integration",),
        ),
        (
            "backend.world.local_runtime_adapter_dry_run_harness",
            ("create_runtime_adapter_dry_run_decision",),
        ),
        (
            "backend.world.local_runtime_adapter_inert_ledger_writer",
            ("append_inert_ledger_record",),
        ),
    ]


def test_module_has_no_direct_io_scanning_or_runtime_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = {
        "open",
        "read",
        "read_text",
        "read_bytes",
        "write",
        "write_text",
        "write_bytes",
        "mkdir",
        "makedirs",
        "glob",
        "rglob",
        "listdir",
        "walk",
        "scandir",
        "unlink",
        "remove",
        "rename",
        "replace",
        "emit_event",
        "create_event",
        "map_lookup",
    }
    allowed_chain_calls = {
        "create_runtime_adapter_dry_run_decision",
        "run_minimal_runtime_adapter_integration",
        "append_inert_ledger_record",
    }
    seen_chain_calls: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_calls
        elif isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_calls
            if node.func.id in allowed_chain_calls:
                seen_chain_calls.add(node.func.id)

    assert seen_chain_calls == allowed_chain_calls
    assert "world-sim/data" not in source
    assert "runtime_adapter_decisions.ndjson" not in source

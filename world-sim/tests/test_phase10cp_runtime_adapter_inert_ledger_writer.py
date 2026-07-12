"""Phase 10CP - minimal inert ledger adapter writer tests."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

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
    / "local_runtime_adapter_inert_ledger_writer.py"
)

ALLOWED_RECORD_FIELDS = {
    "ledger_schema_version",
    "source_adapter_schema_version",
    "adapter_decision_id",
    "source_decision_id",
    "source_consumer_scope",
    "source_signal_seen",
    "recognized_signal_type",
    "planned_action",
    "recorded_at_utc",
    "record_hash",
}

GATE_FLAGS = (
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
)

FORBIDDEN_INPUT_FIELDS = (
    "equality_signal_value",
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
)


def _valid_10cj_decision(
    signal_type: str = "snapshot_id_equality",
) -> dict:
    return create_runtime_adapter_dry_run_decision(
        {
            "ok": True,
            "decision_id": "10BT-test-decision",
            "consumer_scope": "record_public_equality_signal_only",
            "equality_signal_type": signal_type,
            "equality_signal_present": True,
        }
    )


def _append(
    adapter_decision: object,
    ledger_path: Path,
    authorized_ledger_path: Path | None = None,
) -> dict:
    return append_inert_ledger_record(
        adapter_decision,
        ledger_path,
        authorized_ledger_path or ledger_path,
        recorded_at_utc="2026-07-12T12:00:00Z",
    )


def _assert_rejected_without_write(
    adapter_decision: object,
    tmp_path: Path,
) -> dict:
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"
    result = _append(adapter_decision, ledger_path)
    assert result["ok"] is False
    assert result["ledger_record_written"] is False
    assert result["bytes_appended"] == 0
    assert result["errors"]
    assert not ledger_path.exists()
    return result


def test_valid_10cj_decision_writes_exactly_one_ndjson_line(tmp_path: Path):
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"
    result = _append(_valid_10cj_decision(), ledger_path)

    assert result["ok"] is True
    assert result["ledger_record_written"] is True
    assert result["ledger_path_authorized"] is True
    assert result["source_adapter_decision_id"].startswith("10CJ-")
    assert result["record_hash"]
    payload = ledger_path.read_bytes()
    assert payload.endswith(b"\n")
    assert payload.count(b"\n") == 1
    assert result["bytes_appended"] == len(payload)


def test_written_record_has_exactly_allowed_fields(tmp_path: Path):
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"
    _append(_valid_10cj_decision(), ledger_path)

    record = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert set(record) == ALLOWED_RECORD_FIELDS
    assert record["ledger_schema_version"] == "10CP.1"
    assert record["source_adapter_schema_version"] == "10CJ.1"
    assert record["planned_action"] == "log_only"


def test_record_hash_verifies_canonical_record_content(tmp_path: Path):
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"
    result = _append(_valid_10cj_decision(), ledger_path)
    record = json.loads(ledger_path.read_text(encoding="utf-8"))
    expected_hash = record.pop("record_hash")
    canonical = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == expected_hash
    assert result["record_hash"] == expected_hash


def test_existing_content_is_preserved_and_record_is_appended(tmp_path: Path):
    ledger_path = tmp_path / "runtime_adapter_decisions.ndjson"
    existing = '{"existing":true}\n'
    ledger_path.write_text(existing, encoding="utf-8", newline="\n")

    result = _append(_valid_10cj_decision(), ledger_path)

    content = ledger_path.read_text(encoding="utf-8")
    assert result["ok"] is True
    assert content.startswith(existing)
    assert len(content.splitlines()) == 2


def test_non_dict_input_does_not_write(tmp_path: Path):
    _assert_rejected_without_write("not-a-dict", tmp_path)


def test_non_ok_decision_does_not_write(tmp_path: Path):
    decision = _valid_10cj_decision()
    decision["ok"] = False
    _assert_rejected_without_write(decision, tmp_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("adapter_schema_version", "10CJ.2"),
        ("adapter_type", "not-a-dry-run-decision"),
        ("adapter_scope", "not-dry-run"),
        ("planned_action", "none"),
        ("executed", True),
    ],
)
def test_wrong_required_field_does_not_write(
    field: str,
    value: object,
    tmp_path: Path,
):
    decision = _valid_10cj_decision()
    decision[field] = value
    _assert_rejected_without_write(decision, tmp_path)


@pytest.mark.parametrize("flag", GATE_FLAGS)
def test_any_gate_flag_true_does_not_write(flag: str, tmp_path: Path):
    decision = _valid_10cj_decision()
    decision[flag] = True
    _assert_rejected_without_write(decision, tmp_path)


def test_unknown_recognized_signal_type_does_not_write(tmp_path: Path):
    decision = _valid_10cj_decision()
    decision["recognized_signal_type"] = "future_unknown_signal"
    _assert_rejected_without_write(decision, tmp_path)


def test_equality_signal_value_present_does_not_write(tmp_path: Path):
    decision = _valid_10cj_decision()
    decision["equality_signal_value"] = "opaque-value"
    _assert_rejected_without_write(decision, tmp_path)


@pytest.mark.parametrize("field", FORBIDDEN_INPUT_FIELDS)
def test_every_forbidden_input_field_causes_no_write(
    field: str,
    tmp_path: Path,
):
    decision = _valid_10cj_decision()
    decision[field] = "forbidden"
    _assert_rejected_without_write(decision, tmp_path)


def test_unauthorized_ledger_path_does_not_write(tmp_path: Path):
    authorized_path = tmp_path / "authorized.ndjson"
    unauthorized_path = tmp_path / "unauthorized.ndjson"

    result = _append(
        _valid_10cj_decision(),
        unauthorized_path,
        authorized_path,
    )

    assert result["ok"] is False
    assert result["ledger_path_authorized"] is False
    assert result["ledger_record_written"] is False
    assert not unauthorized_path.exists()
    assert not authorized_path.exists()


def test_missing_parent_directory_does_not_write(tmp_path: Path):
    ledger_path = tmp_path / "missing" / "runtime_adapter_decisions.ndjson"
    result = _append(_valid_10cj_decision(), ledger_path)

    assert result["ok"] is False
    assert result["ledger_path_authorized"] is True
    assert result["ledger_record_written"] is False
    assert not ledger_path.parent.exists()
    assert not ledger_path.exists()


def test_module_does_not_read_equality_signal_value_from_decision():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    writer = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "append_inert_ledger_record"
    )

    for node in ast.walk(writer):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "adapter_decision"
                and node.func.attr == "get"
            ):
                assert not any(
                    isinstance(arg, ast.Constant)
                    and arg.value == "equality_signal_value"
                    for arg in node.args
                )
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "adapter_decision"
            and isinstance(node.slice, ast.Constant)
        ):
            assert node.slice.value != "equality_signal_value"


def test_module_has_only_safe_imports_and_no_scanning_apis():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    allowed_import_roots = {
        "__future__",
        "datetime",
        "hashlib",
        "json",
        "pathlib",
        "typing",
    }
    forbidden_calls = {"glob", "rglob", "listdir", "walk", "scandir"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed_import_roots
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] in allowed_import_roots
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls
            elif isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls


def test_module_opens_files_in_append_mode_only():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    open_calls = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "open":
                open_calls.append(node)
            elif isinstance(node.func, ast.Name) and node.func.id == "open":
                open_calls.append(node)

    assert open_calls
    for call in open_calls:
        if call.args:
            mode = call.args[0]
        else:
            mode = next(
                keyword.value
                for keyword in call.keywords
                if keyword.arg == "mode"
            )
        assert isinstance(mode, ast.Constant)
        assert mode.value == "a"

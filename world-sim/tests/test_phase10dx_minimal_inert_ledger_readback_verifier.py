"""Phase 10DX - minimal inert ledger read-back verifier tests."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

import backend.world.local_minimal_inert_ledger_readback_verifier as verifier_module
from backend.world.local_minimal_inert_ledger_readback_verifier import (
    export_minimal_inert_ledger_readback_result,
    verify_minimal_inert_ledger_readback,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_ledger_readback_verifier.py"
)

KNOWN_SIGNAL_TYPES = (
    "snapshot_id_equality",
    "snapshot_hash_equality",
    "current_tile_id_equality",
    "route_intent_id_equality",
    "known_tile_ids_set_equality",
    "route_destination_tile_id_equality",
)

RECORD_FIELDS = {
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

OUTPUT_FIELDS = {
    "ok",
    "verifier_schema_version",
    "verifier_type",
    "verifier_scope",
    "verifier_decision_id",
    "ledger_path_supplied",
    "ledger_file_seen",
    "records_seen",
    "records_valid",
    "invalid_record_count",
    "verified_record_hashes",
    "recognized_signal_types_seen",
    "append_only_line_format_valid",
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

GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

FORBIDDEN_RECORD_FIELDS = (
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
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _valid_record(
    signal_type: str = "snapshot_id_equality",
    *,
    suffix: str = "one",
) -> dict:
    record = {
        "ledger_schema_version": "10CP.1",
        "source_adapter_schema_version": "10CJ.1",
        "adapter_decision_id": f"10CJ-test-{suffix}",
        "source_decision_id": f"10BT-test-{suffix}",
        "source_consumer_scope": "record_public_equality_signal_only",
        "source_signal_seen": True,
        "recognized_signal_type": signal_type,
        "planned_action": "log_only",
        "recorded_at_utc": "2026-07-12T12:00:00Z",
    }
    record["record_hash"] = hashlib.sha256(
        _canonical_json(record).encode("utf-8")
    ).hexdigest()
    return record


def _rehash(record: dict) -> dict:
    record = dict(record)
    record.pop("record_hash", None)
    record["record_hash"] = hashlib.sha256(
        _canonical_json(record).encode("utf-8")
    ).hexdigest()
    return record


def _write_records(path: Path, records: list[object], *, final_newline: bool = True):
    payload = "\n".join(_canonical_json(record) for record in records)
    if final_newline:
        payload += "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")


def _assert_inert(result: dict) -> None:
    for field in GATE_FLAGS:
        assert result[field] is False, field


def _assert_failed(result: dict) -> None:
    assert result["ok"] is False
    assert result["errors"]
    _assert_inert(result)


def test_missing_path_fails_closed():
    result = verify_minimal_inert_ledger_readback(None)

    assert result["ledger_path_supplied"] is False
    assert result["ledger_file_seen"] is False
    assert result["records_seen"] == 0
    _assert_failed(result)


def test_nonexistent_path_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "missing.ndjson"

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["ledger_path_supplied"] is True
    assert result["ledger_file_seen"] is False
    assert not ledger_path.exists()
    _assert_failed(result)


def test_directory_path_fails_closed(tmp_path: Path):
    result = verify_minimal_inert_ledger_readback(tmp_path)

    assert result["ledger_path_supplied"] is True
    assert result["ledger_file_seen"] is False
    _assert_failed(result)


def test_empty_file_is_invalid(tmp_path: Path):
    ledger_path = tmp_path / "empty.ndjson"
    ledger_path.write_bytes(b"")

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["ledger_file_seen"] is True
    assert result["records_seen"] == 0
    assert result["append_only_line_format_valid"] is False
    _assert_failed(result)


def test_valid_single_record_ledger_passes(tmp_path: Path):
    ledger_path = tmp_path / "single.ndjson"
    record = _valid_record()
    _write_records(ledger_path, [record])

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["ok"] is True
    assert result["verifier_schema_version"] == "10DX.1"
    assert result["verifier_type"] == "minimal_inert_ledger_readback_result"
    assert result["verifier_scope"] == "inert_ledger_readback_only"
    assert result["verifier_decision_id"].startswith("10DX-")
    assert result["ledger_path_supplied"] is True
    assert result["ledger_file_seen"] is True
    assert result["records_seen"] == 1
    assert result["records_valid"] == 1
    assert result["invalid_record_count"] == 0
    assert result["verified_record_hashes"] == [record["record_hash"]]
    assert result["recognized_signal_types_seen"] == [
        "snapshot_id_equality"
    ]
    assert result["append_only_line_format_valid"] is True
    assert result["errors"] == []
    assert set(result) == OUTPUT_FIELDS
    _assert_inert(result)


def test_valid_multi_record_ledger_passes(tmp_path: Path):
    ledger_path = tmp_path / "multi.ndjson"
    records = [
        _valid_record("snapshot_hash_equality", suffix="one"),
        _valid_record("snapshot_id_equality", suffix="two"),
        _valid_record("snapshot_hash_equality", suffix="three"),
    ]
    _write_records(ledger_path, records)

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["ok"] is True
    assert result["records_seen"] == 3
    assert result["records_valid"] == 3
    assert result["invalid_record_count"] == 0
    assert result["verified_record_hashes"] == [
        record["record_hash"] for record in records
    ]
    assert result["recognized_signal_types_seen"] == [
        "snapshot_hash_equality",
        "snapshot_id_equality",
    ]
    _assert_inert(result)


@pytest.mark.parametrize("signal_type", KNOWN_SIGNAL_TYPES)
def test_each_known_inert_signal_type_passes(signal_type: str, tmp_path: Path):
    ledger_path = tmp_path / f"{signal_type}.ndjson"
    _write_records(ledger_path, [_valid_record(signal_type)])

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["ok"] is True
    assert result["recognized_signal_types_seen"] == [signal_type]


def test_malformed_json_line_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "malformed.ndjson"
    ledger_path.write_bytes(b'{"bad":\n')

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_seen"] == 1
    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    assert result["append_only_line_format_valid"] is False
    _assert_failed(result)


@pytest.mark.parametrize("value", (["not", "object"], "string", 7, True, None))
def test_non_object_json_line_fails_closed(value: object, tmp_path: Path):
    ledger_path = tmp_path / "non-object.ndjson"
    _write_records(ledger_path, [value])

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_seen"] == 1
    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    assert result["append_only_line_format_valid"] is False
    _assert_failed(result)


@pytest.mark.parametrize("field", sorted(RECORD_FIELDS))
def test_missing_required_field_fails_closed(field: str, tmp_path: Path):
    ledger_path = tmp_path / f"missing-{field}.ndjson"
    record = _valid_record()
    record.pop(field)
    if field != "record_hash":
        record = _rehash(record)
    _write_records(ledger_path, [record])

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    _assert_failed(result)


def test_unexpected_field_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "unexpected.ndjson"
    record = _valid_record()
    record["future_field"] = "not-authorized"
    _write_records(ledger_path, [_rehash(record)])

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    _assert_failed(result)


@pytest.mark.parametrize("field", FORBIDDEN_RECORD_FIELDS)
def test_forbidden_record_field_fails_closed(field: str, tmp_path: Path):
    ledger_path = tmp_path / "forbidden.ndjson"
    record = _valid_record()
    record[field] = "opaque-forbidden-value"
    _write_records(ledger_path, [_rehash(record)])

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    assert "opaque-forbidden-value" not in json.dumps(result)
    _assert_failed(result)


def test_forbidden_field_rejection_is_value_and_hash_independent(tmp_path: Path):
    first_path = tmp_path / "first-forbidden.ndjson"
    second_path = tmp_path / "second-forbidden.ndjson"
    first = _valid_record()
    second = _valid_record()
    first["equality_signal_value"] = "first-opaque-value"
    second["equality_signal_value"] = "second-opaque-value"
    _write_records(first_path, [_rehash(first)])
    _write_records(second_path, [second])

    first_result = verify_minimal_inert_ledger_readback(first_path)
    second_result = verify_minimal_inert_ledger_readback(second_path)

    assert first_result == second_result
    assert "first-opaque-value" not in json.dumps(first_result)
    assert "second-opaque-value" not in json.dumps(second_result)
    _assert_failed(first_result)


def test_invalid_nested_value_is_not_hashed_or_reflected(tmp_path: Path):
    first_path = tmp_path / "first-nested.ndjson"
    second_path = tmp_path / "second-nested.ndjson"
    first = _valid_record()
    second = _valid_record()
    first["adapter_decision_id"] = {
        "equality_signal_value": "first-nested-value"
    }
    second["adapter_decision_id"] = {
        "equality_signal_value": "second-nested-value"
    }
    _write_records(first_path, [_rehash(first)])
    _write_records(second_path, [second])

    first_result = verify_minimal_inert_ledger_readback(first_path)
    second_result = verify_minimal_inert_ledger_readback(second_path)

    assert first_result == second_result
    assert "first-nested-value" not in json.dumps(first_result)
    assert "second-nested-value" not in json.dumps(second_result)
    _assert_failed(first_result)


def test_bad_record_hash_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "bad-hash.ndjson"
    record = _valid_record()
    record["record_hash"] = "0" * 64
    _write_records(ledger_path, [record])

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["verified_record_hashes"] == []
    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    _assert_failed(result)


def test_integer_bool_drift_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "integer-bool.ndjson"
    record = _valid_record()
    record["source_signal_seen"] = 1
    _write_records(ledger_path, [_rehash(record)])

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    _assert_failed(result)


def test_unknown_recognized_signal_type_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "unknown-signal.ndjson"
    record = _valid_record()
    record["recognized_signal_type"] = "future_unknown_signal"
    _write_records(ledger_path, [_rehash(record)])

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["recognized_signal_types_seen"] == []
    assert result["records_valid"] == 0
    _assert_failed(result)


def test_planned_action_other_than_log_only_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "wrong-action.ndjson"
    record = _valid_record()
    record["planned_action"] = "execute"
    _write_records(ledger_path, [_rehash(record)])

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_valid"] == 0
    _assert_failed(result)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ledger_schema_version", "10CP.2"),
        ("source_adapter_schema_version", "10CJ.2"),
        ("source_consumer_scope", "unexpected_scope"),
        ("adapter_decision_id", ""),
        ("source_decision_id", ""),
        ("recorded_at_utc", ""),
        ("record_hash", 7),
    ),
)
def test_invalid_required_value_fails_closed(
    field: str,
    value: object,
    tmp_path: Path,
):
    ledger_path = tmp_path / f"invalid-{field}.ndjson"
    record = _valid_record()
    record[field] = value
    if field != "record_hash":
        record = _rehash(record)
    _write_records(ledger_path, [record])

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    _assert_failed(result)


def test_partial_non_newline_terminated_record_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "partial.ndjson"
    _write_records(ledger_path, [_valid_record()], final_newline=False)

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_seen"] == 1
    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    assert result["append_only_line_format_valid"] is False
    _assert_failed(result)


def test_blank_line_fails_append_only_format(tmp_path: Path):
    ledger_path = tmp_path / "blank-line.ndjson"
    record = _canonical_json(_valid_record()).encode("utf-8")
    ledger_path.write_bytes(record + b"\n\n")

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_seen"] == 2
    assert result["records_valid"] == 1
    assert result["invalid_record_count"] == 1
    assert result["append_only_line_format_valid"] is False
    _assert_failed(result)


def test_crlf_line_ending_fails_append_only_format(tmp_path: Path):
    ledger_path = tmp_path / "crlf.ndjson"
    ledger_path.write_bytes(
        _canonical_json(_valid_record()).encode("utf-8") + b"\r\n"
    )

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_seen"] == 1
    assert result["records_valid"] == 0
    assert result["append_only_line_format_valid"] is False
    _assert_failed(result)


def test_duplicate_json_object_key_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "duplicate-key.ndjson"
    ledger_path.write_bytes(b'{"record_hash":"a","record_hash":"b"}\n')

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_seen"] == 1
    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    assert result["append_only_line_format_valid"] is False
    _assert_failed(result)


def test_invalid_utf8_line_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "invalid-utf8.ndjson"
    ledger_path.write_bytes(b"\xff\n")

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_seen"] == 1
    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    assert result["append_only_line_format_valid"] is False
    _assert_failed(result)


def test_excessively_nested_json_fails_closed(tmp_path: Path):
    ledger_path = tmp_path / "nested-json.ndjson"
    ledger_path.write_bytes(b"[" * 2000 + b"0" + b"]" * 2000 + b"\n")

    result = verify_minimal_inert_ledger_readback(ledger_path)

    assert result["records_seen"] == 1
    assert result["records_valid"] == 0
    assert result["invalid_record_count"] == 1
    assert result["append_only_line_format_valid"] is False
    _assert_failed(result)


@pytest.mark.parametrize("max_records", (0, -1, True, 1.0, "1"))
def test_invalid_max_records_fails_closed(max_records: object, tmp_path: Path):
    ledger_path = tmp_path / "limit.ndjson"
    _write_records(ledger_path, [_valid_record()])

    result = verify_minimal_inert_ledger_readback(
        ledger_path,
        max_records=max_records,
    )

    assert result["ledger_file_seen"] is False
    assert result["records_seen"] == 0
    _assert_failed(result)


def test_max_records_is_a_fail_closed_ceiling(tmp_path: Path):
    ledger_path = tmp_path / "over-limit.ndjson"
    _write_records(
        ledger_path,
        [_valid_record(suffix="one"), _valid_record(suffix="two")],
    )

    result = verify_minimal_inert_ledger_readback(ledger_path, max_records=1)

    assert result["ok"] is False
    assert result["records_seen"] == 2
    assert result["records_valid"] == 1
    assert result["invalid_record_count"] == 1
    assert len(result["verified_record_hashes"]) == 1
    assert result["append_only_line_format_valid"] is False
    assert result["errors"] == ["ledger record limit exceeded"]
    _assert_failed(result)


def test_exact_max_records_boundary_passes(tmp_path: Path):
    ledger_path = tmp_path / "exact-limit.ndjson"
    records = [_valid_record(suffix="one"), _valid_record(suffix="two")]
    _write_records(ledger_path, records)

    result = verify_minimal_inert_ledger_readback(ledger_path, max_records=2)

    assert result["ok"] is True
    assert result["records_seen"] == 2
    assert result["records_valid"] == 2
    assert result["verified_record_hashes"] == [
        record["record_hash"] for record in records
    ]


def test_unc_path_is_rejected_before_filesystem_inspection(
    monkeypatch: pytest.MonkeyPatch,
):
    def unexpected_path(value: object) -> Path:
        raise AssertionError("UNC path reached Path construction")

    monkeypatch.setattr(verifier_module, "Path", unexpected_path)

    result = verify_minimal_inert_ledger_readback(
        r"\\server\share\runtime_adapter_decisions.ndjson"
    )

    assert result["ledger_path_supplied"] is True
    assert result["ledger_file_seen"] is False
    assert result["records_seen"] == 0
    _assert_failed(result)


def test_pathlike_unc_path_is_rejected_before_path_construction(
    monkeypatch: pytest.MonkeyPatch,
):
    class _DisguisedUncPath:
        def __str__(self) -> str:
            return "benign-local-name.ndjson"

        def __fspath__(self) -> str:
            return r"\\server\share\runtime_adapter_decisions.ndjson"

    def unexpected_path(value: object) -> Path:
        raise AssertionError("PathLike UNC path reached Path construction")

    monkeypatch.setattr(verifier_module, "Path", unexpected_path)

    result = verify_minimal_inert_ledger_readback(_DisguisedUncPath())

    assert result["ledger_path_supplied"] is True
    assert result["ledger_file_seen"] is False
    assert result["records_seen"] == 0
    _assert_failed(result)


@pytest.mark.parametrize("exception", (OSError("path failure"), RuntimeError("path failure")))
def test_pathlike_conversion_exception_fails_closed(exception: Exception):
    class _BrokenPath:
        def __fspath__(self) -> str:
            raise exception

    result = verify_minimal_inert_ledger_readback(_BrokenPath())

    assert result["ledger_path_supplied"] is True
    assert result["ledger_file_seen"] is False
    assert result["records_seen"] == 0
    _assert_failed(result)


def test_readback_does_not_modify_ledger(tmp_path: Path):
    ledger_path = tmp_path / "unchanged.ndjson"
    _write_records(ledger_path, [_valid_record()])
    before = ledger_path.read_bytes()

    verify_minimal_inert_ledger_readback(ledger_path)

    assert ledger_path.read_bytes() == before


def test_output_contains_only_safe_status_and_no_path_or_record_fields(
    tmp_path: Path,
):
    ledger_path = tmp_path / "private-ledger-name.ndjson"
    _write_records(ledger_path, [_valid_record()])
    success = verify_minimal_inert_ledger_readback(ledger_path)
    failure = verify_minimal_inert_ledger_readback(None)

    for result in (success, failure):
        serialized = json.dumps(result)
        assert set(result) == OUTPUT_FIELDS
        assert RECORD_FIELDS.isdisjoint(result)
        assert set(FORBIDDEN_RECORD_FIELDS).isdisjoint(result)
        assert "private-ledger-name" not in serialized
        assert "opaque-forbidden-value" not in serialized
        _assert_inert(result)


def test_export_is_deterministic_sorted_json(tmp_path: Path):
    ledger_path = tmp_path / "deterministic.ndjson"
    _write_records(ledger_path, [_valid_record()])
    result = verify_minimal_inert_ledger_readback(ledger_path)

    first = export_minimal_inert_ledger_readback_result(result)
    second = export_minimal_inert_ledger_readback_result(dict(result))

    assert first == second
    assert first == json.dumps(result, sort_keys=True, ensure_ascii=False)
    assert json.loads(first) == result


def test_export_rejects_non_verifier_fields(tmp_path: Path):
    ledger_path = tmp_path / "tainted-export.ndjson"
    _write_records(ledger_path, [_valid_record()])
    result = verify_minimal_inert_ledger_readback(ledger_path)
    result["equality_signal_value"] = "must-not-export"

    with pytest.raises(ValueError, match="exact 10DX result shape"):
        export_minimal_inert_ledger_readback_result(result)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", 1),
        ("ledger_path_supplied", 1),
        ("records_seen", True),
        ("verified_record_hashes", ["not-a-hash"]),
        ("recognized_signal_types_seen", ["future_unknown_signal"]),
        ("errors", ["opaque-equality-value"]),
    ),
)
def test_export_rejects_tainted_allowed_fields(
    field: str,
    value: object,
    tmp_path: Path,
):
    ledger_path = tmp_path / "tainted-allowed-export.ndjson"
    _write_records(ledger_path, [_valid_record()])
    result = verify_minimal_inert_ledger_readback(ledger_path)
    result[field] = value

    with pytest.raises(ValueError, match="exact 10DX result shape"):
        export_minimal_inert_ledger_readback_result(result)


def test_gate_flags_are_false_on_success_and_failure(tmp_path: Path):
    ledger_path = tmp_path / "gates.ndjson"
    _write_records(ledger_path, [_valid_record()])

    for result in (
        verify_minimal_inert_ledger_readback(ledger_path),
        verify_minimal_inert_ledger_readback(None),
        verify_minimal_inert_ledger_readback(tmp_path / "missing.ndjson"),
    ):
        _assert_inert(result)


def test_module_has_no_10cp_or_other_backend_imports_or_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed_import_roots = {
        "__future__",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "typing",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed_import_roots
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] in allowed_import_roots

    assert "append_inert_ledger_record" not in source
    assert "local_runtime_adapter_inert_ledger_writer" not in source


def test_module_opens_only_one_explicit_file_in_binary_read_mode():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    open_calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr == "open":
            open_calls.append(node)
        elif isinstance(node.func, ast.Name) and node.func.id == "open":
            open_calls.append(node)

    assert len(open_calls) == 1
    call = open_calls[0]
    assert isinstance(call.func, ast.Attribute)
    assert isinstance(call.func.value, ast.Name)
    assert call.func.value.id == "explicit_path"
    mode = call.args[0] if call.args else next(
        keyword.value for keyword in call.keywords if keyword.arg == "mode"
    )
    assert isinstance(mode, ast.Constant)
    assert mode.value == "rb"


def test_module_has_no_mutating_scanning_or_runtime_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = {
        "write",
        "writelines",
        "write_text",
        "write_bytes",
        "touch",
        "truncate",
        "mkdir",
        "makedirs",
        "unlink",
        "remove",
        "rename",
        "replace",
        "repair",
        "glob",
        "rglob",
        "listdir",
        "walk",
        "scandir",
        "iterdir",
        "chmod",
        "rmdir",
        "symlink_to",
        "hardlink_to",
        "emit_event",
        "create_event",
        "map_lookup",
        "append_inert_ledger_record",
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_calls
        elif isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_calls

    assert "world-sim/data" not in source
    assert "runtime_adapter_decisions.ndjson" not in source

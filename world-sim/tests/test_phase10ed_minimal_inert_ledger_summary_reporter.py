"""Phase 10ED - minimal inert ledger summary reporter tests."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from backend.world.local_minimal_inert_ledger_summary_reporter import (
    create_minimal_inert_ledger_summary_report,
    export_minimal_inert_ledger_summary_report,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_ledger_summary_reporter.py"
)

KNOWN_SIGNAL_TYPES = (
    "snapshot_id_equality",
    "snapshot_hash_equality",
    "current_tile_id_equality",
    "route_intent_id_equality",
    "known_tile_ids_set_equality",
    "route_destination_tile_id_equality",
)

SOURCE_FIELDS = {
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

REPORT_FIELDS = {
    "ok",
    "reporter_schema_version",
    "reporter_type",
    "reporter_scope",
    "reporter_decision_id",
    "source_verifier_schema_version",
    "source_verifier_decision_id",
    "source_ok",
    "ledger_path_supplied",
    "ledger_file_seen",
    "records_seen",
    "records_valid",
    "invalid_record_count",
    "verified_record_hash_count",
    "recognized_signal_types_seen",
    "recognized_signal_type_count",
    "append_only_line_format_valid",
    "source_error_count",
    "summary_status",
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

FORBIDDEN_REPORT_FIELDS = {
    "verified_record_hashes",
    "source_errors",
    "ledger_path",
    "path",
    "record_hash",
    "equality_signal_value",
    "equality_signal_type",
    "agent_id",
    "tile",
    "route",
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
    "event",
    "npc_behavior",
}

SOURCE_CLAIM_BOUNDARY = (
    "read-only inert ledger verification only; no write, repair, runtime "
    "action, daemon, scheduler, network, world-data promotion, movement, "
    "map lookup, route execution, event emission, NPC behavior, "
    "co-presence, awareness, relationship, interaction, or timing"
)


def _valid_source_success() -> dict:
    return {
        "ok": True,
        "verifier_schema_version": "10DX.1",
        "verifier_type": "minimal_inert_ledger_readback_result",
        "verifier_scope": "inert_ledger_readback_only",
        "verifier_decision_id": "10DX-" + "a" * 32,
        "ledger_path_supplied": True,
        "ledger_file_seen": True,
        "records_seen": 2,
        "records_valid": 2,
        "invalid_record_count": 0,
        "verified_record_hashes": ["1" * 64, "2" * 64],
        "recognized_signal_types_seen": [
            "snapshot_hash_equality",
            "snapshot_id_equality",
        ],
        "append_only_line_format_valid": True,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": SOURCE_CLAIM_BOUNDARY,
        "errors": [],
    }


def _valid_source_failure() -> dict:
    source = _valid_source_success()
    source.update(
        {
            "ok": False,
            "verifier_decision_id": "10DX-" + "b" * 32,
            "ledger_file_seen": False,
            "records_seen": 0,
            "records_valid": 0,
            "invalid_record_count": 0,
            "verified_record_hashes": [],
            "recognized_signal_types_seen": [],
            "append_only_line_format_valid": False,
            "errors": [
                "source verification failed at C:\\private\\ledger.ndjson",
                "opaque source detail",
            ],
        }
    )
    return source


def _assert_inert(report: dict) -> None:
    for field in GATE_FLAGS:
        assert report[field] is False, field


def _assert_invalid_source(report: dict) -> None:
    assert report["ok"] is False
    assert report["source_ok"] is False
    assert report["summary_status"] == "invalid_source"
    assert report["errors"] == ["verification_result is not a valid 10DX result"]
    assert set(report) == REPORT_FIELDS
    _assert_inert(report)


def test_missing_result_fails_closed():
    _assert_invalid_source(create_minimal_inert_ledger_summary_report(None))


@pytest.mark.parametrize("value", ([], "10DX", 7, True, object()))
def test_non_dict_result_fails_closed(value: object):
    _assert_invalid_source(create_minimal_inert_ledger_summary_report(value))


def test_source_dict_subclass_fails_closed_without_invoking_overrides():
    class _HostileDict(dict):
        def get(self, key: object, default: object = None) -> object:
            raise RuntimeError("caller-controlled get")

    source = _HostileDict(_valid_source_success())

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("records_seen", type("IntSubclass", (int,), {})(2)),
        ("verified_record_hashes", type("ListSubclass", (list,), {})(["1" * 64, "2" * 64])),
        ("errors", type("ListSubclass", (list,), {})([])),
        ("verifier_decision_id", type("StrSubclass", (str,), {})("10DX-" + "a" * 32)),
    ),
)
def test_source_container_and_primitive_subclasses_fail_closed(
    field: str,
    value: object,
):
    source = _valid_source_success()
    source[field] = value

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


def test_valid_10dx_success_produces_safe_summary():
    report = create_minimal_inert_ledger_summary_report(_valid_source_success())

    assert report == {
        "ok": True,
        "reporter_schema_version": "10ED.1",
        "reporter_type": "minimal_inert_ledger_summary_report",
        "reporter_scope": "inert_ledger_summary_only",
        "reporter_decision_id": report["reporter_decision_id"],
        "source_verifier_schema_version": "10DX.1",
        "source_verifier_decision_id": "10DX-" + "a" * 32,
        "source_ok": True,
        "ledger_path_supplied": True,
        "ledger_file_seen": True,
        "records_seen": 2,
        "records_valid": 2,
        "invalid_record_count": 0,
        "verified_record_hash_count": 2,
        "recognized_signal_types_seen": [
            "snapshot_hash_equality",
            "snapshot_id_equality",
        ],
        "recognized_signal_type_count": 2,
        "append_only_line_format_valid": True,
        "source_error_count": 0,
        "summary_status": "verified",
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": report["claim_boundary"],
        "errors": [],
    }
    assert report["reporter_decision_id"].startswith("10ED-")
    _assert_inert(report)


def test_valid_10dx_failure_produces_safe_failed_summary():
    source = _valid_source_failure()

    report = create_minimal_inert_ledger_summary_report(source)
    serialized = json.dumps(report)

    assert report["ok"] is False
    assert report["source_ok"] is False
    assert report["summary_status"] == "verification_failed"
    assert report["source_error_count"] == 2
    assert report["errors"] == ["source 10DX verification did not pass"]
    assert "private" not in serialized
    assert "opaque source detail" not in serialized
    _assert_inert(report)


@pytest.mark.parametrize("field", sorted(SOURCE_FIELDS))
def test_missing_required_10dx_field_fails_closed(field: str):
    source = _valid_source_success()
    source.pop(field)

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


def test_unexpected_10dx_field_fails_closed():
    source = _valid_source_success()
    source["future_field"] = "not authorized"

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("verifier_schema_version", "10DX.2"),
        ("verifier_type", "future_verifier"),
        ("verifier_scope", "future_scope"),
        ("claim_boundary", "expanded boundary"),
    ),
)
def test_wrong_10dx_identity_field_fails_closed(field: str, value: object):
    source = _valid_source_success()
    source[field] = value

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


@pytest.mark.parametrize(
    "decision_id",
    (None, 7, "", "10DZ-" + "a" * 32, "10DX-", "10DX-" + "a" * 31, "10DX-" + "A" * 32),
)
def test_malformed_verifier_decision_id_fails_closed(decision_id: object):
    source = _valid_source_success()
    source["verifier_decision_id"] = decision_id

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


@pytest.mark.parametrize(
    "field",
    ("ok", "ledger_path_supplied", "ledger_file_seen", "append_only_line_format_valid"),
)
def test_source_integer_bool_drift_fails_closed(field: str):
    source = _valid_source_success()
    source[field] = 1

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


@pytest.mark.parametrize("field", GATE_FLAGS)
def test_source_gate_flag_integer_drift_fails_closed(field: str):
    source = _valid_source_success()
    source[field] = 0

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("records_seen", -1),
        ("records_valid", -1),
        ("invalid_record_count", -1),
        ("records_seen", True),
        ("records_valid", False),
        ("invalid_record_count", True),
        ("records_seen", 1.0),
        ("records_valid", "2"),
    ),
)
def test_invalid_source_count_fails_closed(field: str, value: object):
    source = _valid_source_success()
    source[field] = value

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


@pytest.mark.parametrize(
    "hashes",
    (
        None,
        "1" * 64,
        ["short"],
        ["A" * 64],
        ["g" * 64],
        [1],
    ),
)
def test_invalid_verified_record_hashes_fails_closed(hashes: object):
    source = _valid_source_success()
    source["verified_record_hashes"] = hashes

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


@pytest.mark.parametrize(
    "signal_types",
    (
        None,
        "snapshot_id_equality",
        ["future_unknown_signal"],
        [1],
        ["snapshot_id_equality", "snapshot_id_equality"],
        ["snapshot_id_equality", "snapshot_hash_equality"],
    ),
)
def test_invalid_recognized_signal_types_fails_closed(signal_types: object):
    source = _valid_source_success()
    source["recognized_signal_types_seen"] = signal_types

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


@pytest.mark.parametrize("signal_type", KNOWN_SIGNAL_TYPES)
def test_each_known_signal_type_is_summarized(signal_type: str):
    source = _valid_source_success()
    source["recognized_signal_types_seen"] = [signal_type]

    report = create_minimal_inert_ledger_summary_report(source)

    assert report["ok"] is True
    assert report["recognized_signal_types_seen"] == [signal_type]
    assert report["recognized_signal_type_count"] == 1


@pytest.mark.parametrize(
    "errors",
    (None, "error", [7], [""], ["valid", 7]),
)
def test_invalid_source_errors_fails_closed(errors: object):
    source = _valid_source_failure()
    source["errors"] = errors

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


def test_non_utf8_source_error_fails_closed():
    source = _valid_source_failure()
    source["errors"] = ["\ud800"]

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("records_seen", 3),
        ("records_valid", 1),
        ("invalid_record_count", 1),
        ("verified_record_hashes", ["1" * 64]),
        ("ok", False),
    ),
)
def test_internally_inconsistent_10dx_result_fails_closed(field: str, value: object):
    source = _valid_source_success()
    source[field] = value

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ledger_path_supplied", False),
        ("recognized_signal_types_seen", []),
    ),
)
def test_impossible_success_provenance_fails_closed(field: str, value: object):
    source = _valid_source_success()
    source[field] = value

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


def test_records_without_seen_file_fail_closed():
    source = _valid_source_failure()
    source.update(
        {
            "records_seen": 1,
            "records_valid": 0,
            "invalid_record_count": 1,
        }
    )

    _assert_invalid_source(create_minimal_inert_ledger_summary_report(source))


def test_source_errors_are_counted_but_not_emitted_raw():
    source = _valid_source_failure()

    report = create_minimal_inert_ledger_summary_report(source)
    serialized = json.dumps(report)

    assert report["source_error_count"] == len(source["errors"])
    assert all(error not in serialized for error in source["errors"])
    assert "source_errors" not in report


def test_verified_hashes_are_counted_but_not_emitted_raw():
    source = _valid_source_success()

    report = create_minimal_inert_ledger_summary_report(source)
    serialized = json.dumps(report)

    assert report["verified_record_hash_count"] == 2
    assert "verified_record_hashes" not in report
    assert all(record_hash not in serialized for record_hash in source["verified_record_hashes"])


def test_output_contains_only_safe_aggregate_fields():
    for source in (_valid_source_success(), _valid_source_failure()):
        report = create_minimal_inert_ledger_summary_report(source)

        assert set(report) == REPORT_FIELDS
        assert FORBIDDEN_REPORT_FIELDS.isdisjoint(report)
        _assert_inert(report)


def test_sensitive_source_values_cannot_be_emitted():
    source = _valid_source_failure()
    source["errors"] = [
        "C:\\private\\runtime_adapter_decisions.ndjson",
        "equality_signal_value=secret-value",
        "raw_record={agent_id: private-agent}",
    ]

    first = create_minimal_inert_ledger_summary_report(source)
    source["errors"] = ["entirely different opaque values"]
    second = create_minimal_inert_ledger_summary_report(source)
    first_serialized = json.dumps(first)

    assert "private" not in first_serialized
    assert "secret-value" not in first_serialized
    assert "private-agent" not in first_serialized
    assert "runtime_adapter_decisions.ndjson" not in first_serialized
    assert first["source_error_count"] == 3
    assert second["source_error_count"] == 1


def test_invalid_source_values_are_not_reflected_or_hashed():
    first_source = _valid_source_success()
    second_source = _valid_source_success()
    first_source["equality_signal_value"] = "first secret"
    second_source["equality_signal_value"] = "second secret"

    first = create_minimal_inert_ledger_summary_report(first_source)
    second = create_minimal_inert_ledger_summary_report(second_source)

    assert first == second
    assert "first secret" not in json.dumps(first)
    assert "second secret" not in json.dumps(second)
    _assert_invalid_source(first)


def test_export_is_deterministic_sorted_json():
    report = create_minimal_inert_ledger_summary_report(_valid_source_success())

    first = export_minimal_inert_ledger_summary_report(report)
    second = export_minimal_inert_ledger_summary_report(dict(report))

    assert first == second
    assert first == json.dumps(report, sort_keys=True, ensure_ascii=False)
    assert json.loads(first) == report


def test_export_rejects_unexpected_or_forbidden_fields():
    report = create_minimal_inert_ledger_summary_report(_valid_source_success())
    report["equality_signal_value"] = "must not export"

    with pytest.raises(ValueError, match="exact 10ED report shape"):
        export_minimal_inert_ledger_summary_report(report)


def test_export_rejects_dict_subclass_without_serializing_override():
    class _TaintedReport(dict):
        def items(self):
            tainted = dict(super().items())
            tainted["errors"] = ["raw secret"]
            return tainted.items()

    report = _TaintedReport(
        create_minimal_inert_ledger_summary_report(_valid_source_success())
    )

    with pytest.raises(ValueError, match="exact 10ED report shape"):
        export_minimal_inert_ledger_summary_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", 1),
        ("source_ok", 1),
        ("ledger_file_seen", 1),
        ("records_seen", True),
        ("verified_record_hash_count", -1),
        ("recognized_signal_types_seen", ["future_unknown_signal"]),
        ("recognized_signal_type_count", 99),
        ("source_error_count", -1),
        ("summary_status", "runtime_started"),
        ("runtime_allowed", 0),
        ("errors", ["raw source error"]),
        ("reporter_decision_id", "10ED-tainted"),
    ),
)
def test_export_rejects_tainted_allowed_fields(field: str, value: object):
    report = create_minimal_inert_ledger_summary_report(_valid_source_success())
    report[field] = value

    with pytest.raises(ValueError, match="exact 10ED report shape"):
        export_minimal_inert_ledger_summary_report(report)


def test_gate_flags_are_false_on_success_and_failure():
    for result in (
        create_minimal_inert_ledger_summary_report(_valid_source_success()),
        create_minimal_inert_ledger_summary_report(_valid_source_failure()),
        create_minimal_inert_ledger_summary_report(None),
    ):
        _assert_inert(result)


def test_module_imports_only_allowed_standard_library_modules():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed_import_roots = {"__future__", "hashlib", "json", "typing"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed_import_roots
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] in allowed_import_roots


def test_module_has_no_10dx_verifier_or_10cp_writer_import_or_call():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "verify_minimal_inert_ledger_readback" not in source
    assert "export_minimal_inert_ledger_readback_result" not in source
    assert "append_inert_ledger_record" not in source
    assert "local_minimal_inert_ledger_readback_verifier" not in source
    assert "local_runtime_adapter_inert_ledger_writer" not in source
    assert "backend." not in source


def test_module_has_no_file_mutation_scanning_or_runtime_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = {
        "open",
        "read",
        "read_text",
        "read_bytes",
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
        "delete",
        "rename",
        "replace",
        "repair",
        "glob",
        "rglob",
        "listdir",
        "walk",
        "scandir",
        "iterdir",
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


def test_caller_owned_lists_are_detached_before_content_validation():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    source_validator = functions["_validated_source_snapshot"]
    assert source_validator is not None
    assert source_validator.index(
        "verified_hashes = list(verified_hashes)"
    ) < source_validator.index("not _is_lower_hex(record_hash, 64)")
    assert source_validator.index(
        "signal_types = list(signal_types)"
    ) < source_validator.index("signal_type not in _KNOWN_SIGNAL_TYPES")
    assert source_validator.index(
        "source_errors = list(source_errors)"
    ) < source_validator.index("not _is_utf8_string(error)")

    exporter = functions["export_minimal_inert_ledger_summary_report"]
    assert exporter is not None
    assert exporter.index("signal_types = list(signal_types)") < exporter.index(
        "signal_type not in _KNOWN_SIGNAL_TYPES"
    )
    assert exporter.index("report_errors = list(report_errors)") < exporter.index(
        "type(error) is not str"
    )

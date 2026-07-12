"""Phase 10CJ - pure dry-run runtime adapter harness tests.

These tests exercise the sibling adapter to 10BT. The adapter consumes
already-built 10BT consumer decision objects and emits an inert dry-run
adapter decision. It must never read ``equality_signal_value``, never
execute anything, and keep every runtime gate flag hard-coded False.
"""

from __future__ import annotations

import ast
import json
import pathlib

from backend.world.local_runtime_adapter_dry_run_harness import (
    create_runtime_adapter_dry_run_decision,
    export_runtime_adapter_dry_run_decision,
)
from backend.world.local_shared_public_contract_consumer_harness import (
    create_shared_public_contract_consumer_decision,
)

_KNOWN_SIGNAL_TYPES = [
    "snapshot_id_equality",
    "snapshot_hash_equality",
    "current_tile_id_equality",
    "route_intent_id_equality",
    "known_tile_ids_set_equality",
    "route_destination_tile_id_equality",
]

_CONTRACT_BUILDERS = {
    "snapshot_id_equality": (
        "shared_public_snapshot_id_equality_contract",
        {"same_snapshot_id": True, "shared_snapshot_id": "snap1"},
    ),
    "snapshot_hash_equality": (
        "shared_snapshot_hash_equality_contract",
        {"same_snapshot_hash": True, "shared_snapshot_hash": "hash1"},
    ),
    "current_tile_id_equality": (
        "shared_public_current_tile_id_equality_contract",
        {"same_current_tile_id": True, "shared_current_tile_id": "tile1"},
    ),
    "route_intent_id_equality": (
        "shared_public_route_intent_id_equality_contract",
        {"same_route_intent_id": True, "shared_route_intent_id": "intent1"},
    ),
    "known_tile_ids_set_equality": (
        "shared_public_known_tile_ids_set_equality_contract",
        {"same_known_tile_ids": True, "shared_known_tile_ids": ["t1", "t2"]},
    ),
    "route_destination_tile_id_equality": (
        "shared_public_route_destination_contract",
        {"shared_route_destination_tile_id": "dest1"},
    ),
}


def _build_bt_decision(signal_type: str) -> dict:
    contract_type, signal_fields = _CONTRACT_BUILDERS[signal_type]
    contract = {
        "ok": True,
        "contract_id": "c-" + contract_type,
        "contract_type": contract_type,
        "claim_scope": "public_equality_only",
        "source_merge_hash": "abc123",
        **signal_fields,
    }
    decision = create_shared_public_contract_consumer_decision(contract)
    assert decision["ok"] is True
    assert decision["equality_signal_present"] is True
    assert decision["equality_signal_type"] == signal_type
    return decision


def test_non_dict_input_returns_false_none_unexecuted():
    result = create_runtime_adapter_dry_run_decision("not-a-dict")
    assert result["ok"] is False
    assert result["planned_action"] == "none"
    assert result["executed"] is False
    assert result["errors"]


def test_non_ok_decision_returns_false_none_unexecuted():
    bt = _build_bt_decision("snapshot_id_equality")
    bt["ok"] = False
    result = create_runtime_adapter_dry_run_decision(bt)
    assert result["ok"] is False
    assert result["planned_action"] == "none"
    assert result["executed"] is False
    assert result["errors"]


def test_wrong_consumer_scope_returns_false_none_unexecuted():
    bt = _build_bt_decision("snapshot_id_equality")
    bt["consumer_scope"] = "something_else"
    result = create_runtime_adapter_dry_run_decision(bt)
    assert result["ok"] is False
    assert result["planned_action"] == "none"
    assert result["executed"] is False
    assert result["errors"]


def test_signal_not_present_returns_true_none_unexecuted():
    bt = _build_bt_decision("snapshot_id_equality")
    bt["equality_signal_present"] = False
    result = create_runtime_adapter_dry_run_decision(bt)
    assert result["ok"] is True
    assert result["source_signal_seen"] is False
    assert result["planned_action"] == "none"
    assert result["executed"] is False
    assert result["errors"] == []


def test_each_known_signal_type_returns_log_only_unexecuted():
    for signal_type in _KNOWN_SIGNAL_TYPES:
        bt = _build_bt_decision(signal_type)
        result = create_runtime_adapter_dry_run_decision(bt)
        assert result["ok"] is True
        assert result["source_signal_seen"] is True
        assert result["recognized_signal_type"] == signal_type
        assert result["planned_action"] == "log_only"
        assert result["executed"] is False


def test_unknown_signal_type_returns_none_unexecuted():
    bt = _build_bt_decision("snapshot_id_equality")
    bt["equality_signal_type"] = "some_future_signal"
    result = create_runtime_adapter_dry_run_decision(bt)
    assert result["ok"] is True
    assert result["recognized_signal_type"] is None
    assert result["planned_action"] == "none"
    assert result["executed"] is False


def test_output_envelope_is_deterministic_and_stable():
    bt = _build_bt_decision("current_tile_id_equality")
    first = create_runtime_adapter_dry_run_decision(bt)
    second = create_runtime_adapter_dry_run_decision(bt)
    assert first == second
    assert first["adapter_decision_id"] == second["adapter_decision_id"]
    exported = export_runtime_adapter_dry_run_decision(first)
    assert isinstance(exported, str)
    assert "10CJ-" in exported


def test_all_runtime_flags_always_false():
    cases = [
        create_runtime_adapter_dry_run_decision("not-a-dict"),
        create_runtime_adapter_dry_run_decision(
            _build_bt_decision("snapshot_id_equality")
        ),
        create_runtime_adapter_dry_run_decision(
            _build_bt_decision("route_destination_tile_id_equality")
        ),
    ]
    for result in cases:
        assert result["runtime_allowed"] is False
        assert result["daemon_allowed"] is False
        assert result["scheduler_allowed"] is False
        assert result["network_allowed"] is False
        assert result["world_sim_data_accessed"] is False
        assert result["executed"] is False


def test_no_output_includes_equality_signal_value():
    bt = _build_bt_decision("known_tile_ids_set_equality")
    result = create_runtime_adapter_dry_run_decision(bt)
    assert "equality_signal_value" not in result
    exported = export_runtime_adapter_dry_run_decision(result)
    assert "equality_signal_value" not in exported


# Top-level output keys that are forbidden behavior/action surfaces.
FORBIDDEN_OUTPUT_KEYS = {
    "equality_signal_value",
    "movement",
    "map_lookup",
    "emit_event",
    "create_event",
    "npc_behavior",
    "co_presence",
    "awareness",
    "relationship",
    "runtime_action",
    "daemon_action",
    "scheduler_action",
    "network_action",
    "world_data_write",
    "world_data_read",
}

# The complete fixed 10CJ output schema. The mandated inert gate flags
# (runtime_allowed / daemon_allowed / scheduler_allowed / network_allowed /
# world_sim_data_accessed) are allowed keys, not forbidden behavior.
ALLOWED_OUTPUT_KEYS = {
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


def test_no_forbidden_keys_in_output():
    bt = _build_bt_decision("route_destination_tile_id_equality")
    result = create_runtime_adapter_dry_run_decision(bt)
    for key in FORBIDDEN_OUTPUT_KEYS:
        assert key not in result, f"forbidden key present: {key}"
    assert set(result.keys()) == ALLOWED_OUTPUT_KEYS
    exported = export_runtime_adapter_dry_run_decision(result)
    parsed = json.loads(exported)
    assert parsed == result


def test_module_source_has_no_forbidden_imports_or_calls():
    source = pathlib.Path(
        "backend/world/local_runtime_adapter_dry_run_harness.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden_imports = {
        "socket",
        "requests",
        "urllib",
        "http",
        "subprocess",
        "os",
    }
    forbidden_calls = {"emit_event", "create_event", "map_lookup"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert (
                    root not in forbidden_imports
                ), f"forbidden import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            assert (
                root not in forbidden_imports
            ), f"forbidden import: {node.module}"
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                assert (
                    func.attr not in forbidden_calls
                ), f"forbidden call: {func.attr}"
            elif isinstance(func, ast.Name):
                assert (
                    func.id not in forbidden_calls
                ), f"forbidden call: {func.id}"

    assert "world-sim/data" not in source
    assert "open(" not in source


def test_module_does_not_read_equality_signal_value():
    source = pathlib.Path(
        "backend/world/local_runtime_adapter_dry_run_harness.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    func = None
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "create_runtime_adapter_dry_run_decision"
        ):
            func = node
            break
    assert func is not None

    param_names = {a.arg for a in func.args.args}

    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            func_node = node.func
            if (
                isinstance(func_node, ast.Attribute)
                and func_node.attr == "get"
            ):
                value = func_node.value
                if isinstance(value, ast.Name) and value.id in param_names:
                    for arg in node.args:
                        if (
                            isinstance(arg, ast.Constant)
                            and arg.value == "equality_signal_value"
                        ):
                            raise AssertionError(
                                "adapter reads equality_signal_value from decision"
                            )
        elif isinstance(node, ast.Subscript):
            value = node.value
            if isinstance(value, ast.Name) and value.id in param_names:
                sl = node.slice
                if isinstance(sl, ast.Constant) and sl.value == "equality_signal_value":
                    raise AssertionError(
                        "adapter subscripts equality_signal_value from decision"
                    )

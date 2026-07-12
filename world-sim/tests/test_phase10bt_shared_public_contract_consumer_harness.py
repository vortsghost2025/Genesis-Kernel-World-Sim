"""Phase 10BT - first shared public contract consumer harness tests.

These tests prove that a Phase 10BP shared-public snapshot-id equality
contract artifact can be wrapped in a deterministic, sanitized
"consumer decision" object, without ever lifting runtime/daemon/
scheduler/network flags, and without ever inferring same map, same
observation, co-presence, awareness, relationship, trust, proximity,
distance, ETA, route, or timing.

10BT is the first consumer harness.  It:

    - consumes already-built shared-public contract artifacts,
    - does not create equality claims,
    - does not perform runtime wiring,
    - does not write a ledger/event,
    - does not touch world-sim/data.

The module's import discipline is asserted explicitly: the new module
must not import or call any phase creator (10AS, 10AQ, 10AR, 10AP,
10BP, or earlier).  Tests may use 10AS/10BP **fixtures** but the module
itself must be safe in isolation.

These tests follow the established Genesis discipline: tempdir-only,
no daemon, no scheduler, no provider, no Docker, no network, no live
data, no ``world-sim/data`` access.
"""

from __future__ import annotations

import ast
import copy
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(TESTS_ROOT))

from backend.world.local_shared_public_contract_consumer_harness import (
    consume_shared_public_contract_file,
    create_shared_public_contract_consumer_decision,
    export_shared_public_contract_consumer_decision,
)
from backend.world.local_shared_public_snapshot_hash_equality_contract import (
    create_shared_snapshot_hash_equality_contract,
)
from backend.world.local_shared_public_snapshot_id_equality_contract import (
    create_shared_snapshot_id_equality_contract,
)
from backend.world.local_two_agent_public_merge import (
    create_two_agent_public_merge,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping


AGENT_A_ID = "agent_adam"
AGENT_B_ID = "agent_eve"
TILE_A = "tile_start"
TILE_B = "tile_east"
TILE_C = "tile_north"
TILE_SHARED = "tile_central"
TILE_OTHER = "tile_far"
SNAP_HASH_A = "a" * 64
SNAP_HASH_B = "b" * 64
SNAP_HASH_SHARED = "s" * 64
SNAP_ID_A = "10AQ-" + "a" * 32
SNAP_ID_B = "10AQ-" + "b" * 32
SNAP_ID_SHARED = "10AQ-" + "s" * 32


def _strip_python_prose(text: str) -> str:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    lines: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else start + 1
            block = text.splitlines()[start:end]
            cleaned: list[str] = []
            in_docstring = False
            for line in block:
                stripped = line.strip()
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    in_docstring = not in_docstring
                    continue
                if in_docstring:
                    continue
                if "#" in line:
                    line = line.split("#")[0]
                cleaned.append(line)
            lines.extend(cleaned)
    return "\n".join(lines)


def _public_state_dict(
    *,
    agent_id: str,
    current_tile_id: str,
    observed: list[str],
    visited: list[str],
) -> dict:
    return {
        "ok": True,
        "agent_id": agent_id,
        "current_tile_id": current_tile_id,
        "current_territory_ref": "reg_" + agent_id.split("_")[-1],
        "observed_tile_ids": observed,
        "visited_tile_ids": visited,
        "movement_count": 1,
        "observation_count": len(observed),
        "first_tick": 1,
        "last_tick": 4,
        "last_event_id": "ev-" + agent_id,
        "accepted_event_count": 3,
        "ignored_event_count": 0,
        "errors": [],
    }


def _snapshot_dict(
    *,
    agent_id: str,
    current_tile_id: str,
    observed: list[str],
    visited: list[str],
) -> dict:
    known = sorted(set(observed) | set(visited))
    return {
        "ok": True,
        "snapshot_schema_version": "10AQ.1",
        "snapshot_type": "known_map_snapshot",
        "snapshot_id": (
            "10AQ-" + agent_id.replace("agent_", "") + "_" + "a" * 29
        ),
        "source_phase": "10AP",
        "source_projection_hash": "a" * 64,
        "agent_id": agent_id,
        "current_tile_id": current_tile_id,
        "current_territory_ref": "reg_" + agent_id.split("_")[-1],
        "observed_tile_ids": sorted(observed),
        "visited_tile_ids": sorted(visited),
        "known_tile_ids": known,
        "movement_count": 1,
        "observation_count": len(observed),
        "first_tick": 1,
        "last_tick": 4,
        "last_event_id": "ev-" + agent_id,
        "accepted_event_count": 3,
        "ignored_event_count": 0,
        "errors": [],
    }


def _build_merge(
    *,
    a_current: str = TILE_A,
    a_observed: list[str] | None = None,
    a_visited: list[str] | None = None,
    b_current: str = TILE_B,
    b_observed: list[str] | None = None,
    b_visited: list[str] | None = None,
    a_snapshot_id: str | None = None,
    b_snapshot_id: str | None = None,
) -> dict:
    """Build a real 10AS merge via the 10AS creator."""

    a_obs = a_observed if a_observed is not None else [TILE_A, TILE_SHARED, TILE_C]
    a_vis = a_visited if a_visited is not None else [TILE_A, TILE_SHARED]
    b_obs = b_observed if b_observed is not None else [TILE_B, TILE_SHARED]
    b_vis = b_visited if b_visited is not None else [TILE_B, TILE_SHARED]

    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=a_current,
        observed=a_obs,
        visited=a_vis,
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=b_current,
        observed=b_obs,
        visited=b_vis,
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=a_current,
        observed=a_obs,
        visited=a_vis,
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=b_current,
        observed=b_obs,
        visited=b_vis,
    )

    if a_snapshot_id is not None:
        snap_a["snapshot_id"] = a_snapshot_id
    if b_snapshot_id is not None:
        snap_b["snapshot_id"] = b_snapshot_id
    else:
        snap_b["snapshot_id"] = snap_a["snapshot_id"]

    merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b
    )
    assert merge["ok"] is True, "fixture merge must be ok=True; got: " + repr(
        merge.get("errors")
    )
    return merge


def _build_10bp_contract(
    *,
    a_snapshot_id: str | None = None,
    b_snapshot_id: str | None = None,
) -> dict:
    merge = _build_merge(
        a_snapshot_id=a_snapshot_id,
        b_snapshot_id=b_snapshot_id,
    )
    contract = create_shared_snapshot_id_equality_contract(merge)
    assert contract["ok"] is True, (
        "fixture 10BP contract must be ok=True; got: "
        + repr(contract.get("errors"))
    )
    return contract


def _build_merge_for_10ay(
    *,
    a_snapshot_hash: str = SNAP_HASH_A,
    b_snapshot_hash: str = SNAP_HASH_B,
    a_snapshot_id: str = SNAP_ID_A,
    b_snapshot_id: str = SNAP_ID_B,
) -> dict:
    merge = _build_merge()
    merge["agent_a"]["snapshot_hash"] = a_snapshot_hash
    merge["agent_a"]["snapshot_id"] = a_snapshot_id
    merge["agent_b"]["snapshot_hash"] = b_snapshot_hash
    merge["agent_b"]["snapshot_id"] = b_snapshot_id
    return merge


def _build_10ay_contract(
    *,
    a_snapshot_hash: str = SNAP_HASH_A,
    b_snapshot_hash: str = SNAP_HASH_B,
) -> dict:
    merge = _build_merge_for_10ay(
        a_snapshot_hash=a_snapshot_hash,
        b_snapshot_hash=b_snapshot_hash,
    )
    contract = create_shared_snapshot_hash_equality_contract(merge)
    assert contract["ok"] is True, (
        "fixture 10AY contract must be ok=True; got: "
        + repr(contract.get("errors"))
    )
    return contract


_EXPECTED_DECISION_FIELDS = frozenset(
    {
        "ok",
        "decision_schema_version",
        "decision_type",
        "decision_id",
        "source_contract_id",
        "source_contract_type",
        "source_contract_schema_version",
        "source_claim_scope",
        "source_merge_hash",
        "consumer_scope",
        "contract_seen",
        "contract_ok",
        "equality_signal_present",
        "equality_signal_type",
        "equality_signal_value",
        "runtime_allowed",
        "daemon_allowed",
        "scheduler_allowed",
        "network_allowed",
        "claim_boundary",
        "errors",
    }
)


class TestHappyPath:
    """Tests 1-2: 10BP happy path + different snapshot_id paths."""

    def test_happy_path_consume_10bp_same_snapshot_id(self):
        contract = _build_10bp_contract()
        decision = create_shared_public_contract_consumer_decision(contract)
        assert decision["ok"] is True
        assert decision["decision_schema_version"] == "10BT.1"
        assert (
            decision["decision_type"]
            == "shared_public_contract_consumer_decision"
        )
        assert decision["decision_id"].startswith("10BT-")
        assert decision["source_contract_id"] == contract["contract_id"]
        assert (
            decision["source_contract_type"]
            == contract["contract_type"]
        )
        assert (
            decision["source_contract_schema_version"]
            == contract["contract_schema_version"]
        )
        assert decision["source_claim_scope"] == contract["claim_scope"]
        assert (
            decision["source_merge_hash"] == contract["source_merge_hash"]
        )
        assert decision["consumer_scope"] == "record_public_equality_signal_only"
        assert decision["contract_seen"] is True
        assert decision["contract_ok"] is True
        assert decision["equality_signal_present"] is True
        assert decision["equality_signal_type"] == "snapshot_id_equality"
        assert decision["equality_signal_value"] == contract["shared_snapshot_id"]
        for flag in (
            "runtime_allowed",
            "daemon_allowed",
            "scheduler_allowed",
            "network_allowed",
        ):
            assert decision[flag] is False, flag + " must be False"
        assert "co-presence" in decision["claim_boundary"]
        assert decision["errors"] == []

    def test_different_snapshot_ids_produces_no_signal(self):
        contract = _build_10bp_contract(
            a_snapshot_id="10AQ-adam_" + "a" * 29,
            b_snapshot_id="10AQ-eve_" + "a" * 29,
        )
        assert contract["same_snapshot_id"] is False
        decision = create_shared_public_contract_consumer_decision(contract)
        assert decision["ok"] is True
        assert decision["contract_seen"] is True
        assert decision["contract_ok"] is True
        assert decision["equality_signal_present"] is False
        assert decision["equality_signal_type"] == "snapshot_id_equality"
        assert decision["equality_signal_value"] is None
        for flag in (
            "runtime_allowed",
            "daemon_allowed",
            "scheduler_allowed",
            "network_allowed",
        ):
            assert decision[flag] is False


class TestUnknownContractType:
    """Test 3: structurally-valid but unknown contract types."""

    def test_unknown_valid_contract_type(self):
        synthetic = {
            "ok": True,
            "contract_id": "X-custom-future-rung",
            "contract_type": "shared_public_unknown_future_contract",
            "contract_schema_version": "999.0",
            "claim_scope": "public_only",
            "source_merge_hash": "f" * 64,
        }
        decision = create_shared_public_contract_consumer_decision(synthetic)
        assert decision["ok"] is True
        assert decision["contract_seen"] is True
        assert decision["contract_ok"] is True
        assert decision["source_contract_id"] == synthetic["contract_id"]
        assert (
            decision["source_contract_type"]
            == synthetic["contract_type"]
        )
        assert decision["equality_signal_present"] is False
        assert decision["equality_signal_type"] == "unknown_contract_type"
        assert decision["equality_signal_value"] is None
        for flag in (
            "runtime_allowed",
            "daemon_allowed",
            "scheduler_allowed",
            "network_allowed",
        ):
            assert decision[flag] is False


class TestInvalidInputs:
    """Tests 4-5: invalid non-dict + missing required fields."""

    def test_invalid_non_dict_input(self):
        decision = create_shared_public_contract_consumer_decision("not a dict")
        assert decision["ok"] is False
        assert decision["decision_schema_version"] == "10BT.1"
        assert decision["decision_id"] is None
        assert decision["contract_seen"] is False
        assert decision["contract_ok"] is False
        for flag in (
            "runtime_allowed",
            "daemon_allowed",
            "scheduler_allowed",
            "network_allowed",
        ):
            assert decision[flag] is False
        assert decision["errors"]
        assert "contract must be a dict" in decision["errors"]

    def test_missing_required_contract_fields(self):
        partial = {
            "ok": True,
            "contract_id": "10BP-deadbeefdeadbeefdeadbeefdeadbeef",
            "contract_type": "shared_public_snapshot_id_equality_contract",
        }
        decision = create_shared_public_contract_consumer_decision(partial)
        assert decision["ok"] is False
        assert decision["decision_id"] is None
        assert decision["contract_seen"] is False
        assert decision["contract_ok"] is False
        for flag in (
            "runtime_allowed",
            "daemon_allowed",
            "scheduler_allowed",
            "network_allowed",
        ):
            assert decision[flag] is False
        joined = " | ".join(decision["errors"])
        assert "claim_scope is missing or empty" in joined
        assert "source_merge_hash is missing or empty" in joined

    def test_output_envelope_shape_on_failure(self):
        envelopes = [
            create_shared_public_contract_consumer_decision(None),
            create_shared_public_contract_consumer_decision(123),
            create_shared_public_contract_consumer_decision({}),
            create_shared_public_contract_consumer_decision(
                {"ok": False, "contract_id": "x", "contract_type": "y",
                 "claim_scope": "z", "source_merge_hash": "q"}
            ),
        ]
        for decision in envelopes:
            assert set(decision.keys()) == _EXPECTED_DECISION_FIELDS
            assert decision["ok"] is False
            assert decision["decision_id"] is None
            assert decision["contract_seen"] is False
            assert decision["contract_ok"] is False
            for flag in (
                "runtime_allowed",
                "daemon_allowed",
                "scheduler_allowed",
                "network_allowed",
            ):
                assert decision[flag] is False
            assert isinstance(decision["errors"], list)


class TestDeterminism:
    """Tests 6-8: input-not-mutated, deterministic, decision_id sensitive."""

    def test_input_contract_not_mutated(self):
        contract = _build_10bp_contract()
        original = copy.deepcopy(contract)
        create_shared_public_contract_consumer_decision(contract)
        assert contract == original

    def test_decision_id_is_deterministic(self):
        contract = _build_10bp_contract()
        d1 = create_shared_public_contract_consumer_decision(contract)
        d2 = create_shared_public_contract_consumer_decision(contract)
        assert d1["decision_id"] == d2["decision_id"]
        assert d1["decision_id"] is not None
        assert d1["decision_id"].startswith("10BT-")

    def test_decision_id_changes_with_source_contract_id(self):
        c1 = _build_10bp_contract(
            a_snapshot_id="10AQ-same_" + "a" * 29,
            b_snapshot_id="10AQ-same_" + "a" * 29,
        )
        assert c1["same_snapshot_id"] is True
        c2 = _build_10bp_contract(
            a_snapshot_id="10AQ-adam_" + "a" * 29,
            b_snapshot_id="10AQ-eve_" + "a" * 29,
        )
        assert c2["same_snapshot_id"] is False
        d1 = create_shared_public_contract_consumer_decision(c1)
        d2 = create_shared_public_contract_consumer_decision(c2)
        assert d1["decision_id"] != d2["decision_id"]
        assert d1["source_contract_id"] != d2["source_contract_id"]


class TestExportAndFileHelper:
    """Tests 9-10: export stable + tempdir-only file helper."""

    def test_exported_json_stable_and_sanitized(self):
        contract = _build_10bp_contract()
        decision = create_shared_public_contract_consumer_decision(contract)
        exported = export_shared_public_contract_consumer_decision(decision)
        parsed = json.loads(exported)
        assert parsed["decision_id"] == decision["decision_id"]
        exported2 = export_shared_public_contract_consumer_decision(parsed)
        assert exported == exported2

    def test_file_helper_tempdir_only(self):
        contract = _build_10bp_contract()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "contract.json"
            path.write_text(
                json.dumps(contract), encoding="utf-8"
            )
            decision = consume_shared_public_contract_file(path)
        assert decision["ok"] is True
        assert decision["contract_seen"] is True
        assert decision["equality_signal_present"] is True
        assert (
            decision["source_contract_id"] == contract["contract_id"]
        )


class TestSanitization:
    """Tests 11-12: redacted strings + forbidden inference tokens."""

    def test_private_redacted_strings_do_not_leak(self):
        secret = "/home/user/secret"
        contract = _build_10bp_contract()
        contract["source_merge_hash"] = secret
        decision = create_shared_public_contract_consumer_decision(contract)
        exported = export_shared_public_contract_consumer_decision(decision)
        assert secret not in exported

    def test_forbidden_inference_words_absent_from_keys(self):
        contract = _build_10bp_contract()
        decision = create_shared_public_contract_consumer_decision(contract)
        forbidden_keys = [
            "co_presence",
            "met",
            "trust",
            "cooperation",
            "conflict",
            "awareness",
            "communication",
            "relationship",
            "same_event",
            "same_time",
            "same_sequence",
            "same_map",
            "same_knowledge",
            "same_observation",
            "temporal_overlap",
            "active_at_same_time",
            "tick_window",
            "route_path",
            "travel_timing",
            "eta",
            "same_state",
        ]
        for key in forbidden_keys:
            assert key not in decision, (
                "forbidden key in 10BT decision: " + key
            )
        allowed = {"co-presence", "awareness", "relationship", "timing"}
        lowered = decision["claim_boundary"].lower()
        for word in allowed:
            assert word in lowered, (
                "claim_boundary must mention forbidden concept "
                + word
                + " by name"
            )


class TestRuntimeFlags:
    """Test 13: all four runtime flags always False."""

    def test_runtime_flags_always_false_on_every_path(self):
        happy = create_shared_public_contract_consumer_decision(
            _build_10bp_contract()
        )
        unknown = create_shared_public_contract_consumer_decision(
            {
                "ok": True,
                "contract_id": "10BP-zzzzzzzzz",
                "contract_type": "some_future_rung",
                "contract_schema_version": "999.0",
                "claim_scope": "public_only",
                "source_merge_hash": "0" * 64,
            }
        )
        invalid = create_shared_public_contract_consumer_decision({})
        bad_type = create_shared_public_contract_consumer_decision("nope")
        for decision, label in (
            (happy, "happy"),
            (unknown, "unknown"),
            (invalid, "invalid"),
            (bad_type, "bad_type"),
        ):
            for flag in (
                "runtime_allowed",
                "daemon_allowed",
                "scheduler_allowed",
                "network_allowed",
            ):
                assert decision[flag] is False, (
                    label + " path: " + flag + " must be False"
                )


class TestModuleDiscipline:
    """Tests 14-15: import discipline + no upstream creator calls."""

    def test_module_has_no_forbidden_imports(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_contract_consumer_harness.py"
        )
        source = module_path.read_text(encoding="utf-8")
        prose = _strip_python_prose(source)
        forbidden = [
            "import runtime",
            "import daemon",
            "import scheduler",
            "import docker",
            "import network",
            "import requests",
            "import urllib",
            "import asyncio",
            "import socket",
            "import threading",
            "import subprocess",
            "from runtime",
            "from daemon",
            "from scheduler",
            "from docker",
            "world-sim/data",
        ]
        for token in forbidden:
            assert token not in prose, (
                "forbidden token in 10BT module source: " + token
            )

    def test_module_does_not_call_upstream_creators(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_contract_consumer_harness.py"
        )
        source = module_path.read_text(encoding="utf-8")
        prose = _strip_python_prose(source)
        creators = [
            "create_two_agent_public_merge(",
            "create_known_map_snapshot(",
            "project_public_state(",
            "create_route_intent_contract(",
            "create_shared_snapshot_id_equality_contract(",
            "create_shared_snapshot_hash_equality_contract(",
            "create_shared_current_tile_id_equality_contract(",
            "create_shared_route_intent_id_equality_contract(",
            "create_shared_known_tile_ids_set_equality_contract(",
            "create_shared_merge_id_equality_contract(",
            "create_shared_first_event_id_equality_contract(",
            "create_shared_last_event_id_equality_contract(",
            "create_shared_public_state_hash_equality_contract(",
        ]
        for creator in creators:
            assert creator not in prose, (
                "10BT module must not call upstream creator: " + creator
            )


class Test10AYExpansion:
    """10BV expansion: consumer recognizes snapshot_hash equality too."""

    def test_happy_path_consume_10ay_same_snapshot_hash(self):
        contract = _build_10ay_contract(
            a_snapshot_hash=SNAP_HASH_SHARED,
            b_snapshot_hash=SNAP_HASH_SHARED,
        )
        assert contract["same_snapshot_hash"] is True
        decision = create_shared_public_contract_consumer_decision(contract)
        assert decision["ok"] is True
        assert decision["decision_schema_version"] == "10BT.1"
        assert (
            decision["decision_type"]
            == "shared_public_contract_consumer_decision"
        )
        assert decision["decision_id"].startswith("10BT-")
        assert decision["source_contract_id"] == contract["contract_id"]
        assert (
            decision["source_contract_type"]
            == "shared_snapshot_hash_equality_contract"
        )
        assert (
            decision["source_contract_schema_version"]
            == contract["contract_schema_version"]
        )
        assert (
            decision["source_claim_scope"]
            == "shared_snapshot_hash_equality_only"
        )
        assert (
            decision["source_merge_hash"]
            == contract["source_merge_hash"]
        )
        assert decision["consumer_scope"] == "record_public_equality_signal_only"
        assert decision["contract_seen"] is True
        assert decision["contract_ok"] is True
        assert decision["equality_signal_present"] is True
        assert decision["equality_signal_type"] == "snapshot_hash_equality"
        assert (
            decision["equality_signal_value"]
            == contract["shared_snapshot_hash"]
        )
        for flag in (
            "runtime_allowed",
            "daemon_allowed",
            "scheduler_allowed",
            "network_allowed",
        ):
            assert decision[flag] is False, flag + " must be False"
        assert decision["errors"] == []

    def test_different_snapshot_hashes_produces_no_signal(self):
        contract = _build_10ay_contract(
            a_snapshot_hash=SNAP_HASH_A,
            b_snapshot_hash=SNAP_HASH_B,
        )
        assert contract["same_snapshot_hash"] is False
        decision = create_shared_public_contract_consumer_decision(contract)
        assert decision["ok"] is True
        assert decision["contract_seen"] is True
        assert decision["contract_ok"] is True
        assert decision["equality_signal_present"] is False
        assert decision["equality_signal_type"] == "snapshot_hash_equality"
        assert decision["equality_signal_value"] is None
        for flag in (
            "runtime_allowed",
            "daemon_allowed",
            "scheduler_allowed",
            "network_allowed",
        ):
            assert decision[flag] is False

    def test_10ay_missing_snapshot_hash_produces_no_signal(self):
        contract = _build_10ay_contract(
            a_snapshot_hash="",
            b_snapshot_hash="",
        )
        assert contract["same_snapshot_hash"] is False
        decision = create_shared_public_contract_consumer_decision(contract)
        assert decision["ok"] is True
        assert decision["equality_signal_present"] is False
        assert decision["equality_signal_type"] == "snapshot_hash_equality"
        assert decision["equality_signal_value"] is None

    def test_decision_id_changes_with_10ay_contract_id(self):
        c_shared = _build_10ay_contract(
            a_snapshot_hash=SNAP_HASH_SHARED,
            b_snapshot_hash=SNAP_HASH_SHARED,
        )
        c_diff = _build_10ay_contract(
            a_snapshot_hash=SNAP_HASH_A,
            b_snapshot_hash=SNAP_HASH_B,
        )
        d_shared = create_shared_public_contract_consumer_decision(c_shared)
        d_diff = create_shared_public_contract_consumer_decision(c_diff)
        assert d_shared["ok"] is True
        assert d_diff["ok"] is True
        assert (
            d_shared["equality_signal_present"]
            != d_diff["equality_signal_present"]
        )
        assert d_shared["decision_id"] != d_diff["decision_id"]
        assert (
            d_shared["source_contract_id"] != d_diff["source_contract_id"]
        )


class TestPublicFunctionCoverage:
    """Test 16: all public functions exercised."""

    def test_all_public_functions_exercised(self):
        bp_contract = _build_10bp_contract()
        ay_contract = _build_10ay_contract(
            a_snapshot_hash=SNAP_HASH_SHARED,
            b_snapshot_hash=SNAP_HASH_SHARED,
        )

        d_bp = create_shared_public_contract_consumer_decision(bp_contract)
        assert d_bp["ok"] is True
        assert d_bp["contract_seen"] is True
        assert d_bp["equality_signal_type"] == "snapshot_id_equality"

        d_ay = create_shared_public_contract_consumer_decision(ay_contract)
        assert d_ay["ok"] is True
        assert d_ay["contract_seen"] is True
        assert d_ay["equality_signal_type"] == "snapshot_hash_equality"

        exported = export_shared_public_contract_consumer_decision(d_bp)
        assert isinstance(exported, str)
        parsed = json.loads(exported)
        assert parsed["decision_id"] == d_bp["decision_id"]
        re = export_shared_public_contract_consumer_decision(parsed)
        assert re == exported

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "contract.json"
            path.write_text(
                json.dumps(bp_contract), encoding="utf-8"
            )
            d2 = consume_shared_public_contract_file(path)
        assert d2["ok"] is True
        assert d2["decision_id"] == d_bp["decision_id"]

        sanitizer_check = sanitize_public_mapping(d_bp)
        assert isinstance(sanitizer_check, dict)

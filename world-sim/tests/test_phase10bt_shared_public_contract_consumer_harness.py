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
from backend.world.local_shared_public_current_tile_id_equality_contract import (
    create_shared_current_tile_id_equality_contract,
)
from backend.world.local_shared_public_known_tile_ids_set_equality_contract import (
    create_shared_known_tile_ids_set_equality_contract,
)
from backend.world.local_shared_public_route_destination_contract import (
    create_shared_public_route_destination_contract,
)
from backend.world.local_shared_public_route_intent_id_equality_contract import (
    create_shared_route_intent_id_equality_contract,
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
INTENT_A = "10AR-" + "a" * 32
INTENT_B = "10AR-" + "b" * 32
INTENT_SHARED = "10AR-" + "c" * 32


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
    a_intent_id: str | None = None,
    b_intent_id: str | None = None,
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

    route_intent_a = None
    route_intent_b = None
    if a_intent_id is not None:
        route_intent_a = _route_intent_dict(
            agent_id=AGENT_A_ID,
            source_snapshot_id=snap_a["snapshot_id"],
            intent_id=a_intent_id,
            destination_tile_id=TILE_SHARED,
        )
    if b_intent_id is not None:
        route_intent_b = _route_intent_dict(
            agent_id=AGENT_B_ID,
            source_snapshot_id=snap_b["snapshot_id"],
            intent_id=b_intent_id,
            destination_tile_id=TILE_SHARED,
        )

    merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b,
        route_intent_a=route_intent_a,
        route_intent_b=route_intent_b,
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


def _build_merge_for_10bj(
    *,
    a_current: str = TILE_A,
    b_current: str = TILE_B,
) -> dict:
    merge = _build_merge(
        a_current=a_current,
        b_current=b_current,
    )
    return merge


def _build_10bj_contract(
    *,
    a_current: str = TILE_A,
    b_current: str = TILE_B,
) -> dict:
    merge = _build_merge_for_10bj(
        a_current=a_current,
        b_current=b_current,
    )
    contract = create_shared_current_tile_id_equality_contract(merge)
    assert contract["ok"] is True, (
        "fixture 10BJ contract must be ok=True; got: "
        + repr(contract.get("errors"))
    )
    return contract


def _route_intent_dict(
    *,
    agent_id: str,
    source_snapshot_id: str,
    intent_id: str,
    destination_tile_id: str,
) -> dict:
    return {
        "ok": True,
        "intent_type": "route_intent_contract",
        "intent_id": intent_id,
        "source_phase": "10AQ",
        "source_snapshot_id": source_snapshot_id,
        "agent_id": agent_id,
        "destination_tile_id": destination_tile_id,
        "destination_known": True,
        "claim_scope": "intent_only",
        "errors": [],
    }


def _build_merge_for_10bk(
    *,
    a_intent_id: str = INTENT_A,
    b_intent_id: str = INTENT_B,
) -> dict:
    return _build_merge(
        a_intent_id=a_intent_id,
        b_intent_id=b_intent_id,
    )


def _build_10bk_contract(
    *,
    a_intent_id: str = INTENT_A,
    b_intent_id: str = INTENT_B,
) -> dict:
    merge = _build_merge_for_10bk(
        a_intent_id=a_intent_id,
        b_intent_id=b_intent_id,
    )
    contract = create_shared_route_intent_id_equality_contract(merge)
    assert contract["ok"] is True, (
        "fixture 10BK contract must be ok=True; got: "
        + repr(contract.get("errors"))
    )
    return contract


def _build_merge_for_10bl(
    *,
    a_known: list[str] | None = None,
    b_known: list[str] | None = None,
) -> dict:
    merge = _build_merge()
    if a_known is not None:
        merge["agent_a"]["known_tile_ids"] = list(a_known)
    if b_known is not None:
        merge["agent_b"]["known_tile_ids"] = list(b_known)
    return merge


def _build_10bl_contract(
    *,
    a_known: list[str] | None = None,
    b_known: list[str] | None = None,
) -> dict:
    merge = _build_merge_for_10bl(
        a_known=a_known,
        b_known=b_known,
    )
    contract = create_shared_known_tile_ids_set_equality_contract(merge)
    assert contract["ok"] is True, (
        "fixture 10BL contract must be ok=True; got: "
        + repr(contract.get("errors"))
    )
    return contract


def _build_merge_for_10aw(
    *,
    a_dest: str = "tile_central",
    b_dest: str = "tile_central",
    a_known: bool = True,
    b_known: bool = True,
) -> dict:
    merge = _build_merge()
    merge["agent_a"]["route_destination_tile_id"] = a_dest
    merge["agent_a"]["route_destination_known"] = a_known
    merge["agent_b"]["route_destination_tile_id"] = b_dest
    merge["agent_b"]["route_destination_known"] = b_known
    return merge


def _build_10aw_contract(
    *,
    a_dest: str = "tile_central",
    b_dest: str = "tile_central",
    a_known: bool = True,
    b_known: bool = True,
) -> dict:
    merge = _build_merge_for_10aw(
        a_dest=a_dest,
        b_dest=b_dest,
        a_known=a_known,
        b_known=b_known,
    )
    contract = create_shared_public_route_destination_contract(merge)
    assert contract["ok"] is True, (
        "fixture 10AW contract must be ok=True; got: "
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


class Test10BXExpansion:
    """10BX expansion: consumer recognizes current_tile_id equality too.

    NOTE: a same current_tile_id signal alone is NOT co-presence, NOT
    proximity, NOT same-time, NOT awareness, NOT interaction,
    NOT meeting, NOT collision, NOT relationship.  These tests
    enforce that boundary at all observable surfaces.
    """

    def test_happy_path_consume_10bj_same_current_tile_id(self):
        contract = _build_10bj_contract(
            a_current=TILE_SHARED,
            b_current=TILE_SHARED,
        )
        assert contract["same_current_tile_id"] is True
        assert contract["shared_current_tile_id"] == TILE_SHARED
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
            == "shared_public_current_tile_id_equality_contract"
        )
        assert (
            decision["source_contract_schema_version"] == "10BJ.1"
        )
        assert decision["source_claim_scope"] == (
            "shared_public_current_tile_id_equality_only"
        )
        assert (
            decision["source_merge_hash"]
            == contract["source_merge_hash"]
        )
        assert decision["consumer_scope"] == "record_public_equality_signal_only"
        assert decision["contract_seen"] is True
        assert decision["contract_ok"] is True
        assert decision["equality_signal_present"] is True
        assert decision["equality_signal_type"] == "current_tile_id_equality"
        assert (
            decision["equality_signal_value"] == TILE_SHARED
        )
        for flag in (
            "runtime_allowed",
            "daemon_allowed",
            "scheduler_allowed",
            "network_allowed",
        ):
            assert decision[flag] is False, flag + " must be False"
        assert decision["errors"] == []

    def test_different_current_tile_ids_produces_no_signal(self):
        contract = _build_10bj_contract(
            a_current=TILE_A,
            b_current=TILE_B,
        )
        assert contract["same_current_tile_id"] is False
        assert contract["shared_current_tile_id"] is None
        decision = create_shared_public_contract_consumer_decision(contract)
        assert decision["ok"] is True
        assert decision["contract_seen"] is True
        assert decision["contract_ok"] is True
        assert decision["equality_signal_present"] is False
        assert decision["equality_signal_type"] == "current_tile_id_equality"
        assert decision["equality_signal_value"] is None
        for flag in (
            "runtime_allowed",
            "daemon_allowed",
            "scheduler_allowed",
            "network_allowed",
        ):
            assert decision[flag] is False

    def test_10bx_signal_does_not_change_21_field_envelope(self):
        contract = _build_10bj_contract(
            a_current=TILE_SHARED, b_current=TILE_SHARED
        )
        decision = create_shared_public_contract_consumer_decision(contract)
        assert set(decision.keys()) == _EXPECTED_DECISION_FIELDS
        assert len(_EXPECTED_DECISION_FIELDS) == 21
        assert set(decision.keys()) == {
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

    def test_10bx_signal_does_not_change_runtime_flag_block(self):
        happy = create_shared_public_contract_consumer_decision(
            _build_10bj_contract(a_current=TILE_SHARED, b_current=TILE_SHARED)
        )
        different = create_shared_public_contract_consumer_decision(
            _build_10bj_contract(a_current=TILE_A, b_current=TILE_B)
        )
        for label, decision in (("happy", happy), ("different", different)):
            assert decision["runtime_allowed"] is False, label
            assert decision["daemon_allowed"] is False, label
            assert decision["scheduler_allowed"] is False, label
            assert decision["network_allowed"] is False, label

    def test_10bx_signal_does_not_introduce_co_presence_or_proximity_keys(self):
        contract = _build_10bj_contract(
            a_current=TILE_SHARED, b_current=TILE_SHARED
        )
        decision = create_shared_public_contract_consumer_decision(contract)
        exported = export_shared_public_contract_consumer_decision(decision)
        forbidden_keys = [
            "co_presence",
            "proximate",
            "proximity",
            "met",
            "meeting",
            "collision",
            "interaction",
            "active_at_same_time",
            "temporal_overlap",
            "same_event",
            "same_time",
            "same_sequence",
            "same_observation",
            "same_place_at_same_time",
            "same_trip",
            "together",
            "shared_visit",
            "shared_journey",
            "navigated_to_each_other",
            "aware",
            "awareness",
            "relationship",
            "trust",
        ]
        for key in forbidden_keys:
            assert key not in decision, (
                "10BX must not introduce co-presence / proximity key: "
                + key
            )
        lowered = exported.lower()
        for token in (
            "co_presence",
            "proximity",
            "met",
            "meeting",
            "collision",
            "interaction",
            "temporal_overlap",
            "active_at_same_time",
            "same_event",
            "same_time",
            "same_sequence",
            "navigated_to_each_other",
            "shared_visit",
            "shared_journey",
            "together",
        ):
            assert token not in lowered, (
                "forbidden co-presence token in exported 10BX decision: "
                + token
            )
        forbidden_phrases = [
            "are co-present",
            "are aware",
            "have met",
            "interacted",
            "are proximate",
            "same time",
            "share an event",
            "navigated to each other",
            "share a journey",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in lowered, (
                "forbidden co-presence phrase in exported 10BX decision: "
                + phrase
            )

    def test_10bx_claim_boundary_names_co_presence_as_forbidden_concept(self):
        contract = _build_10bj_contract(
            a_current=TILE_SHARED, b_current=TILE_SHARED
        )
        decision = create_shared_public_contract_consumer_decision(contract)
        boundary = decision["claim_boundary"]
        must_be_named_as_forbidden = [
            "co-presence",
            "awareness",
            "relationship",
            "timing",
        ]
        lowered = boundary.lower()
        for word in must_be_named_as_forbidden:
            assert word in lowered, (
                "10BX claim_boundary must name co-presence/awareness/"
                "relationship/timing as forbidden concepts; missing: "
                + word
            )

    def test_10bx_decision_id_changes_with_contract_id(self):
        c_shared = _build_10bj_contract(
            a_current=TILE_SHARED, b_current=TILE_SHARED
        )
        c_diff = _build_10bj_contract(
            a_current=TILE_A, b_current=TILE_B
        )
        d_shared = create_shared_public_contract_consumer_decision(c_shared)
        d_diff = create_shared_public_contract_consumer_decision(c_diff)
        assert d_shared["decision_id"] != d_diff["decision_id"]
        assert (
            d_shared["source_contract_id"] != d_diff["source_contract_id"]
        )
        assert (
            d_shared["equality_signal_present"]
            != d_diff["equality_signal_present"]
        )

    def test_10bx_private_strings_do_not_leak(self):
        contract = _build_10bj_contract(
            a_current=TILE_SHARED, b_current=TILE_SHARED
        )
        contract["source_merge_hash"] = "/home/user/secret"
        decision = create_shared_public_contract_consumer_decision(contract)
        exported = export_shared_public_contract_consumer_decision(decision)
        assert "/home/user/secret" not in exported


class Test10BZExpansion:
    # 10BZ: consumer recognizes 10BK
    # (shared_public_route_intent_id_equality_contract) and exports
    # route_intent_id_equality without inferring co-presence / co-journey /
    # coordination.

    def test_happy_path_shared_intent_exports_equality(self) -> None:
        merge = _build_merge_for_10bk(
            a_intent_id=INTENT_SHARED,
            b_intent_id=INTENT_SHARED,
        )
        contract = create_shared_route_intent_id_equality_contract(merge)
        assert contract["ok"] is True
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["ok"] is True
        assert result["contract_seen"] is True
        assert result["equality_signal_type"] == "route_intent_id_equality"
        assert result["equality_signal_present"] is True
        assert result["equality_signal_value"] == INTENT_SHARED
        assert result["source_contract_type"] == (
            "shared_public_route_intent_id_equality_contract"
        )

    def test_different_intent_id_exports_false(self) -> None:
        merge = _build_merge_for_10bk(
            a_intent_id=INTENT_A,
            b_intent_id=INTENT_B,
        )
        contract = create_shared_route_intent_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract.get("same_route_intent_id") is False
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["ok"] is True
        assert result["contract_seen"] is True
        assert result["equality_signal_type"] == "route_intent_id_equality"
        assert result["equality_signal_present"] is False
        assert result["equality_signal_value"] is None

    def test_envelope_fields_are_unchanged(self) -> None:
        merge = _build_merge_for_10bk(
            a_intent_id=INTENT_SHARED,
            b_intent_id=INTENT_SHARED,
        )
        contract = create_shared_route_intent_id_equality_contract(merge)
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["decision_schema_version"] == "10BT.1"
        assert result["runtime_allowed"] is False
        assert result["daemon_allowed"] is False
        assert result["scheduler_allowed"] is False
        assert result["network_allowed"] is False
        assert result["source_contract_type"] == (
            "shared_public_route_intent_id_equality_contract"
        )
        assert result["claim_boundary"]

    def test_no_forbidden_keys_present(self) -> None:
        merge = _build_merge_for_10bk(
            a_intent_id=INTENT_A,
            b_intent_id=INTENT_B,
        )
        contract = create_shared_route_intent_id_equality_contract(merge)
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["ok"] is True
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
            "co_journey",
            "coordination",
            "shared_visit",
            "shared_journey",
            "proximity",
        ]
        for key in forbidden_keys:
            assert key not in result, (
                "forbidden key in 10BZ decision: " + key
            )

    def test_module_discipline_no_contract_creator_import(self) -> None:
        path = (
            Path(__file__).resolve().parent.parent
            / "backend"
            / "world"
            / "local_shared_public_contract_consumer_harness.py"
        )
        text = path.read_text(encoding="utf-8")
        assert "create_shared_route_intent_id_equality_contract" not in text

    def test_existing_10bp_10ay_10bj_contracts_still_pass(self) -> None:
        contracts = [
            _build_10bp_contract(),
            _build_10ay_contract(),
            _build_10bj_contract(),
        ]
        results = [
            create_shared_public_contract_consumer_decision(c)
            for c in contracts
        ]
        assert all(r["ok"] is True for r in results)
        assert results[0]["equality_signal_type"] == "snapshot_id_equality"
        assert results[1]["equality_signal_type"] == "snapshot_hash_equality"
        assert results[2]["equality_signal_type"] == "current_tile_id_equality"


class Test10CBExpansion:
    # 10CB: consumer recognizes 10BL
    # (shared_public_known_tile_ids_set_equality_contract) and exports
    # known_tile_ids_set_equality WITHOUT inferring same observation
    # depth, same route path, same travel history, same memory, same
    # map, same experience, same time, co-presence, awareness,
    # interaction, relationship, or coordination.

    KNOWN_SHARED = ["tile_a", "tile_b", "tile_central", "tile_north"]
    KNOWN_A_ONLY = ["tile_a", "tile_b", "tile_central"]
    KNOWN_B_ONLY = ["tile_b", "tile_central", "tile_south"]

    def test_happy_path_shared_set_exports_equality(self) -> None:
        contract = _build_10bl_contract(
            a_known=list(self.KNOWN_SHARED),
            b_known=list(self.KNOWN_SHARED),
        )
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["ok"] is True
        assert result["contract_seen"] is True
        assert result["equality_signal_type"] == (
            "known_tile_ids_set_equality"
        )
        assert result["equality_signal_present"] is True
        assert result["equality_signal_value"] == sorted(self.KNOWN_SHARED)
        assert result["source_contract_type"] == (
            "shared_public_known_tile_ids_set_equality_contract"
        )

    def test_different_sets_export_false(self) -> None:
        contract = _build_10bl_contract(
            a_known=list(self.KNOWN_A_ONLY),
            b_known=list(self.KNOWN_B_ONLY),
        )
        assert contract["ok"] is True
        assert contract.get("same_known_tile_ids") is False
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["ok"] is True
        assert result["equality_signal_type"] == (
            "known_tile_ids_set_equality"
        )
        assert result["equality_signal_present"] is False
        assert result["equality_signal_value"] is None

    def test_set_value_is_deterministic_and_sanitized(self) -> None:
        contract = _build_10bl_contract(
            a_known=["tile_a", "tile_b", "tile_central"],
            b_known=["tile_central", "tile_b", "tile_a"],
        )
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["equality_signal_present"] is True
        assert result["equality_signal_value"] == [
            "tile_a",
            "tile_b",
            "tile_central",
        ]
        assert result["equality_signal_value"] == sorted(
            result["equality_signal_value"]
        )

    def test_envelope_fields_are_unchanged(self) -> None:
        contract = _build_10bl_contract(
            a_known=list(self.KNOWN_SHARED),
            b_known=list(self.KNOWN_SHARED),
        )
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["decision_schema_version"] == "10BT.1"
        assert result["runtime_allowed"] is False
        assert result["daemon_allowed"] is False
        assert result["scheduler_allowed"] is False
        assert result["network_allowed"] is False
        assert result["source_contract_type"] == (
            "shared_public_known_tile_ids_set_equality_contract"
        )
        assert result["claim_boundary"]

    def test_no_inference_keys_present(self) -> None:
        contract = _build_10bl_contract(
            a_known=list(self.KNOWN_A_ONLY),
            b_known=list(self.KNOWN_B_ONLY),
        )
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["ok"] is True
        forbidden_keys = [
            "same_observation_depth",
            "same_knowledge_depth",
            "same_path",
            "same_route",
            "same_travel",
            "same_travel_history",
            "same_memory",
            "same_map",
            "same_experience",
            "same_time",
            "co_presence",
            "awareness",
            "interaction",
            "relationship",
            "coordination",
            "cooperation",
            "shared_visit",
            "shared_journey",
            "proximity",
            "route_path",
            "travel_timing",
            "eta",
        ]
        for key in forbidden_keys:
            assert key not in result, (
                "forbidden key in 10CB decision: " + key
            )

    def test_module_discipline_no_contract_creator_import(self) -> None:
        path = (
            Path(__file__).resolve().parent.parent
            / "backend"
            / "world"
            / "local_shared_public_contract_consumer_harness.py"
        )
        text = path.read_text(encoding="utf-8")
        assert "create_shared_known_tile_ids_set_equality_contract" not in text

    def test_existing_10bp_10ay_10bj_10bk_contracts_still_pass(self) -> None:
        contracts = [
            _build_10bp_contract(),
            _build_10ay_contract(),
            _build_10bj_contract(),
            _build_10bk_contract(),
        ]
        results = [
            create_shared_public_contract_consumer_decision(c)
            for c in contracts
        ]
        assert all(r["ok"] is True for r in results)
        assert results[0]["equality_signal_type"] == "snapshot_id_equality"
        assert results[1]["equality_signal_type"] == "snapshot_hash_equality"
        assert results[2]["equality_signal_type"] == "current_tile_id_equality"
        assert results[3]["equality_signal_type"] == "route_intent_id_equality"


class Test10CDExpansion:
    # 10CD: consumer recognizes 10AW
    # (shared_public_route_destination_contract) and exports
    # route_destination_tile_id_equality WITHOUT inferring same route
    # path, movement, arrival, timing, plan, coordination,
    # cooperation, awareness, trip, proximity, co-presence, or
    # relationship.

    def test_happy_path_shared_destination_exports_equality(self) -> None:
        contract = _build_10aw_contract(
            a_dest="tile_central",
            b_dest="tile_central",
        )
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["ok"] is True
        assert result["contract_seen"] is True
        assert result["equality_signal_type"] == (
            "route_destination_tile_id_equality"
        )
        assert result["equality_signal_present"] is True
        assert result["equality_signal_value"] == "tile_central"
        assert result["source_contract_type"] == (
            "shared_public_route_destination_contract"
        )

    def test_different_destination_exports_false(self) -> None:
        contract = _build_10aw_contract(
            a_dest="tile_central",
            b_dest="tile_far",
        )
        assert contract["ok"] is True
        assert contract.get("shared_route_destination_tile_id") is None
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["ok"] is True
        assert result["equality_signal_type"] == (
            "route_destination_tile_id_equality"
        )
        assert result["equality_signal_present"] is False
        assert result["equality_signal_value"] is None

    def test_unknown_destination_exports_false(self) -> None:
        contract = _build_10aw_contract(
            a_dest="tile_central",
            b_dest="tile_central",
            b_known=False,
        )
        assert contract["ok"] is True
        assert contract.get("shared_route_destination_tile_id") is None
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["equality_signal_present"] is False
        assert result["equality_signal_value"] is None

    def test_envelope_fields_are_unchanged(self) -> None:
        contract = _build_10aw_contract(
            a_dest="tile_central",
            b_dest="tile_central",
        )
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["decision_schema_version"] == "10BT.1"
        assert result["runtime_allowed"] is False
        assert result["daemon_allowed"] is False
        assert result["scheduler_allowed"] is False
        assert result["network_allowed"] is False
        assert result["source_contract_type"] == (
            "shared_public_route_destination_contract"
        )
        assert result["claim_boundary"]

    def test_no_inference_keys_present(self) -> None:
        contract = _build_10aw_contract(
            a_dest="tile_central",
            b_dest="tile_far",
        )
        result = create_shared_public_contract_consumer_decision(contract)
        assert result["ok"] is True
        forbidden_keys = [
            "route_path",
            "movement",
            "arrival",
            "arrived",
            "destination_reached",
            "same_time",
            "timing",
            "plan",
            "planning",
            "coordination",
            "cooperation",
            "co_presence",
            "proximity",
            "awareness",
            "interaction",
            "relationship",
            "trip",
            "shared_journey",
            "co_journey",
            "shared_visit",
        ]
        for key in forbidden_keys:
            assert key not in result, (
                "forbidden key in 10CD decision: " + key
            )

    def test_module_discipline_no_contract_creator_import(self) -> None:
        path = (
            Path(__file__).resolve().parent.parent
            / "backend"
            / "world"
            / "local_shared_public_contract_consumer_harness.py"
        )
        text = path.read_text(encoding="utf-8")
        assert "create_shared_public_route_destination_contract" not in text

    def test_existing_10bp_10ay_10bj_10bk_10bl_contracts_still_pass(
        self,
    ) -> None:
        contracts = [
            _build_10bp_contract(),
            _build_10ay_contract(),
            _build_10bj_contract(),
            _build_10bk_contract(),
            _build_10bl_contract(),
        ]
        results = [
            create_shared_public_contract_consumer_decision(c)
            for c in contracts
        ]
        assert all(r["ok"] is True for r in results)
        assert results[0]["equality_signal_type"] == "snapshot_id_equality"
        assert results[1]["equality_signal_type"] == "snapshot_hash_equality"
        assert results[2]["equality_signal_type"] == "current_tile_id_equality"
        assert results[3]["equality_signal_type"] == "route_intent_id_equality"
        assert results[4]["equality_signal_type"] == "known_tile_ids_set_equality"


class TestPublicFunctionCoverage:
    """Test 16: all public functions exercised."""

    def test_all_public_functions_exercised(self):
        bp_contract = _build_10bp_contract()
        ay_contract = _build_10ay_contract(
            a_snapshot_hash=SNAP_HASH_SHARED,
            b_snapshot_hash=SNAP_HASH_SHARED,
        )
        bj_contract = _build_10bj_contract(
            a_current=TILE_SHARED,
            b_current=TILE_SHARED,
        )
        bk_contract = _build_10bk_contract(
            a_intent_id=INTENT_SHARED,
            b_intent_id=INTENT_SHARED,
        )
        bl_contract = _build_10bl_contract(
            a_known=["tile_a", "tile_b", "tile_central"],
            b_known=["tile_central", "tile_b", "tile_a"],
        )

        d_bp = create_shared_public_contract_consumer_decision(bp_contract)
        assert d_bp["ok"] is True
        assert d_bp["contract_seen"] is True
        assert d_bp["equality_signal_type"] == "snapshot_id_equality"

        d_ay = create_shared_public_contract_consumer_decision(ay_contract)
        assert d_ay["ok"] is True
        assert d_ay["contract_seen"] is True
        assert d_ay["equality_signal_type"] == "snapshot_hash_equality"

        d_bj = create_shared_public_contract_consumer_decision(bj_contract)
        assert d_bj["ok"] is True
        assert d_bj["contract_seen"] is True
        assert d_bj["equality_signal_type"] == "current_tile_id_equality"

        d_bk = create_shared_public_contract_consumer_decision(bk_contract)
        assert d_bk["ok"] is True
        assert d_bk["contract_seen"] is True
        assert d_bk["equality_signal_type"] == "route_intent_id_equality"
        d_bl = create_shared_public_contract_consumer_decision(bl_contract)
        assert d_bl["ok"] is True
        assert d_bl["contract_seen"] is True
        assert d_bl["equality_signal_type"] == "known_tile_ids_set_equality"

        aw_contract = _build_10aw_contract(
            a_dest="tile_central",
            b_dest="tile_central",
        )
        d_aw = create_shared_public_contract_consumer_decision(aw_contract)
        assert d_aw["ok"] is True
        assert d_aw["contract_seen"] is True
        assert d_aw["equality_signal_type"] == (
            "route_destination_tile_id_equality"
        )

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

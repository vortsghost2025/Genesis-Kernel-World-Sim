"""Phase 10BP - shared public snapshot id equality contract proof.

These tests prove that a Phase 10AS two-agent public merge artifact can
be wrapped in a deterministic, sanitized shared-public-snapshot-id-
equality contract that formalizes whether two agents' public snapshot
IDs are identical, without ever inferring same snapshot content, same
map, same observation, same knowledge, or same relationship.

Snapshot IDs are read from 10AS bundles.  Missing, non-string, or
empty-after-sanitize snapshot IDs are treated as ``None``.

10BP may say:

    "Agent A's public snapshot_id is X."

    "Agent B's public snapshot_id is Y."

    "Both agents report the same public snapshot_id value."
    (public-surface equality only)

10BP may not say:

    "Both agents used the same map snapshot." (snapshot-content inference)

    "Both agents observed the same things." (observation content inference)

    "Both agents have the same knowledge." (knowledge-state inference)

    "The agents have a relationship." (relationship inference)

    Anything about awareness, communication, cooperation, conflict,
    trust, proximity, distance, ETA, route, or timing.

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

from backend.world.local_shared_public_snapshot_id_equality_contract import (
    contract_snapshot_id_equality_file,
    create_shared_snapshot_id_equality_contract,
    export_shared_snapshot_id_equality_contract,
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


def _strip_python_prose(text: str) -> str:
    import ast

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
        "snapshot_id": "10AQ-" + agent_id.replace("agent_", "") + "_" + "a" * 29,
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
        public_a,
        snap_a,
        public_b,
        snap_b,
    )
    assert merge["ok"] is True, "fixture merge must be ok=True; got: " + repr(
        merge.get("errors")
    )
    return merge


class TestCreateSharedSnapshotIdEqualityContract:
    """Tests 1-21 from the 10BP spec test plan."""

    def test_happy_path_equal_snapshot_ids(self):
        merge = _build_merge()
        contract = create_shared_snapshot_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["contract_schema_version"] == "10BP.1"
        assert contract["contract_type"] == "shared_public_snapshot_id_equality_contract"
        assert contract["contract_id"].startswith("10BP-")
        assert contract["claim_scope"] == "shared_public_snapshot_id_equality_only"
        assert contract["errors"] == []
        assert contract["same_snapshot_id"] is True
        assert contract["shared_snapshot_id"] is not None
        assert contract["agent_a_snapshot_id"] == contract["agent_b_snapshot_id"]

    def test_different_snapshot_ids(self):
        merge = _build_merge(
            a_snapshot_id="10AQ-adam_" + "a" * 29,
            b_snapshot_id="10AQ-eve_" + "a" * 29,
        )
        contract = create_shared_snapshot_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["same_snapshot_id"] is False
        assert contract["shared_snapshot_id"] is None
        assert contract["agent_a_snapshot_id"] != contract["agent_b_snapshot_id"]

    def test_one_bundle_missing_snapshot_id(self):
        merge = _build_merge()
        merge["agent_a"]["snapshot_id"] = None
        contract = create_shared_snapshot_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_snapshot_id"] is None
        assert contract["agent_b_snapshot_id"] is not None
        assert contract["same_snapshot_id"] is False
        assert contract["shared_snapshot_id"] is None

    def test_both_bundles_missing_snapshot_id(self):
        merge = _build_merge()
        merge["agent_a"]["snapshot_id"] = None
        merge["agent_b"]["snapshot_id"] = None
        contract = create_shared_snapshot_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_snapshot_id"] is None
        assert contract["agent_b_snapshot_id"] is None
        assert contract["same_snapshot_id"] is False
        assert contract["shared_snapshot_id"] is None

    def test_output_has_exact_fields(self):
        merge = _build_merge()
        contract = create_shared_snapshot_id_equality_contract(merge)
        expected_fields = {
            "ok",
            "contract_schema_version",
            "contract_type",
            "contract_id",
            "source_phase",
            "source_merge_id",
            "source_merge_hash",
            "source_merge_schema_version",
            "agent_a_id",
            "agent_b_id",
            "agent_a_snapshot_id",
            "agent_b_snapshot_id",
            "same_snapshot_id",
            "shared_snapshot_id",
            "claim_scope",
            "errors",
        }
        assert sorted(contract.keys()) == sorted(expected_fields)
        forbidden = [
            "co_presence",
            "met",
            "trust",
            "cooperation",
            "conflict",
            "awareness",
            "communication",
            "relationship",
            "private_state",
            "shared_private_state",
            "tick_window",
            "active_at_same_time",
            "temporal_overlap",
            "same_event",
            "same_time",
            "same_sequence",
            "same_interaction",
            "same_relationship",
            "event_content",
            "route_path",
            "travel_timing",
            "eta",
            "same_state",
            "temporal_overlap",
            "co_presence",
            "meeting",
            "interaction",
            "same_map",
            "same_knowledge",
            "same_snapshot",
            "same_observation",
        ]
        for token in forbidden:
            assert token not in contract

    def test_contract_id_deterministic(self):
        merge = _build_merge()
        c1 = create_shared_snapshot_id_equality_contract(merge)
        c2 = create_shared_snapshot_id_equality_contract(merge)
        assert c1["contract_id"] == c2["contract_id"]
        assert c1["contract_id"] is not None

    def test_contract_id_changes_with_id(self):
        merge1 = _build_merge(
            a_snapshot_id="10AQ-same_" + "a" * 29,
            b_snapshot_id="10AQ-same_" + "a" * 29,
        )
        merge2 = _build_merge(
            a_snapshot_id="10AQ-adam_" + "a" * 29,
            b_snapshot_id="10AQ-eve_" + "a" * 29,
        )
        c1 = create_shared_snapshot_id_equality_contract(merge1)
        c2 = create_shared_snapshot_id_equality_contract(merge2)
        assert c1["same_snapshot_id"] != c2["same_snapshot_id"]
        assert c1["contract_id"] != c2["contract_id"]

    def test_input_not_mutated(self):
        merge = _build_merge()
        original = copy.deepcopy(merge)
        create_shared_snapshot_id_equality_contract(merge)
        assert merge == original

    def test_structural_failures(self):
        c = create_shared_snapshot_id_equality_contract("not a dict")
        assert c["ok"] is False
        assert "merge must be a dict" in c["errors"]

        bad_merge = {"ok": False, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_snapshot_id_equality_contract(bad_merge)
        assert c["ok"] is False

        bad_merge = {"ok": True, "merge_type": "wrong",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_snapshot_id_equality_contract(bad_merge)
        assert c["ok"] is False

        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "9X.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_snapshot_id_equality_contract(bad_merge)
        assert c["ok"] is False

        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_b": {}}
        c = create_shared_snapshot_id_equality_contract(bad_merge)
        assert c["ok"] is False

        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {}}
        c = create_shared_snapshot_id_equality_contract(bad_merge)
        assert c["ok"] is False

        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": ""},
                     "agent_b": {"agent_id": ""}}
        c = create_shared_snapshot_id_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id is missing or empty" in c["errors"]

        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": "same_id"},
                     "agent_b": {"agent_id": "same_id"}}
        c = create_shared_snapshot_id_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id and agent_b_id must be distinct" in c["errors"]

    def test_private_markers_redacted(self):
        merge = _build_merge()
        merge["agent_a"]["snapshot_id"] = "/home/user/secret"
        merge["agent_b"]["snapshot_id"] = "/home/user/secret"
        contract = create_shared_snapshot_id_equality_contract(merge)
        assert contract["agent_a_snapshot_id"] is None
        assert contract["agent_b_snapshot_id"] is None
        assert contract["same_snapshot_id"] is False
        assert contract["shared_snapshot_id"] is None
        exported = export_shared_snapshot_id_equality_contract(contract)
        assert "/home/user/secret" not in exported

    def test_graceful_missing_snapshot_ids(self):
        merge = _build_merge()
        merge["agent_a"]["snapshot_id"] = None
        merge["agent_b"]["snapshot_id"] = "10AQ-other"
        contract = create_shared_snapshot_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_snapshot_id"] is None
        assert contract["agent_b_snapshot_id"] == "10AQ-other"
        assert contract["same_snapshot_id"] is False
        assert contract["shared_snapshot_id"] is None

    def test_export_stable_json(self):
        merge = _build_merge()
        contract = create_shared_snapshot_id_equality_contract(merge)
        exported = export_shared_snapshot_id_equality_contract(contract)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == contract["contract_id"]
        exported2 = export_shared_snapshot_id_equality_contract(parsed)
        assert exported == exported2

    def test_contract_snapshot_id_equality_file(self):
        merge = _build_merge()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            result = contract_snapshot_id_equality_file(path)
        assert result["ok"] is True
        assert result["same_snapshot_id"] is True

    def test_all_public_functions_exercised(self):
        merge = _build_merge()
        c1 = create_shared_snapshot_id_equality_contract(merge)
        assert c1["ok"] is True

        exported = export_shared_snapshot_id_equality_contract(c1)
        assert isinstance(exported, str)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == c1["contract_id"]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            c2 = contract_snapshot_id_equality_file(path)
        assert c2["ok"] is True
        assert c2["same_snapshot_id"] is True

    def test_module_has_no_forbidden_imports(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_snapshot_id_equality_contract.py"
        )
        source = module_path.read_text(encoding="utf-8")
        prose = _strip_python_prose(source)
        forbidden = [
            "create_two_agent_public_merge(",
            "create_known_map_snapshot(",
            "project_public_state(",
            "create_route_intent_contract(",
            "world-sim/data",
        ]
        for token in forbidden:
            assert token not in prose, (
                "forbidden token in 10BP module source: " + token
            )

    def test_module_does_not_call_upstream_creators(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_snapshot_id_equality_contract.py"
        )
        source = module_path.read_text(encoding="utf-8")
        prose = _strip_python_prose(source)
        creators = [
            "create_two_agent_public_merge",
            "create_known_map_snapshot",
            "project_public_state",
            "create_route_intent_contract",
        ]
        for creator in creators:
            assert creator not in prose, (
                "10BP module must not call upstream creator: " + creator
            )

    def test_happy_path_contains_no_forbidden_tokens(self):
        merge = _build_merge()
        contract = create_shared_snapshot_id_equality_contract(merge)
        exported = export_shared_snapshot_id_equality_contract(contract)
        forbidden_tokens = [
            "same_event",
            "same_time",
            "same_sequence",
            "same_interaction",
            "same_relationship",
            "temporal_overlap",
            "co_presence",
            "meeting",
            "interaction",
            "relationship",
            "trust",
            "cooperation",
            "conflict",
            "awareness",
            "communication",
            "shared_private",
            "private_knowledge",
            "tick_window",
            "active_at_same_time",
            "route_path",
            "travel_timing",
            "eta",
            "same_state",
            "same_map",
            "same_knowledge",
            "same_observation",
        ]
        lowered = exported.lower()
        for token in forbidden_tokens:
            assert token not in lowered, (
                "forbidden token in exported contract: " + token
            )


class TestSnapshotIdBoundaries:
    """Additional boundary cases for 10BP."""

    def test_private_marker_like_snapshot_id_never_leaks(self):
        merge = _build_merge()
        merge["agent_a"]["snapshot_id"] = "/home/user/secret"
        merge["agent_b"]["snapshot_id"] = "/home/user/secret"
        contract = create_shared_snapshot_id_equality_contract(merge)
        assert contract["agent_a_snapshot_id"] is None
        assert contract["agent_b_snapshot_id"] is None
        assert contract["same_snapshot_id"] is False
        exported = export_shared_snapshot_id_equality_contract(contract)
        assert "/home/user/secret" not in exported

    def test_empty_string_snapshot_id_treated_as_none(self):
        merge = _build_merge()
        merge["agent_a"]["snapshot_id"] = ""
        merge["agent_b"]["snapshot_id"] = ""
        contract = create_shared_snapshot_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_snapshot_id"] is None
        assert contract["agent_b_snapshot_id"] is None
        assert contract["same_snapshot_id"] is False

    def test_contract_id_preserves_ab_orientation(self):
        merge1 = _build_merge(
            a_snapshot_id="10AQ-1_" + "a" * 29,
            b_snapshot_id="10AQ-2_" + "a" * 29,
        )
        c1 = create_shared_snapshot_id_equality_contract(merge1)
        public_a = _public_state_dict(
            agent_id=AGENT_B_ID,
            current_tile_id=TILE_B,
            observed=[TILE_B, TILE_SHARED],
            visited=[TILE_B, TILE_SHARED],
        )
        public_b = _public_state_dict(
            agent_id=AGENT_A_ID,
            current_tile_id=TILE_A,
            observed=[TILE_A, TILE_SHARED, TILE_C],
            visited=[TILE_A, TILE_SHARED],
        )
        snap_a = _snapshot_dict(
            agent_id=AGENT_B_ID,
            current_tile_id=TILE_B,
            observed=[TILE_B, TILE_SHARED],
            visited=[TILE_B, TILE_SHARED],
        )
        snap_b = _snapshot_dict(
            agent_id=AGENT_A_ID,
            current_tile_id=TILE_A,
            observed=[TILE_A, TILE_SHARED, TILE_C],
            visited=[TILE_A, TILE_SHARED],
        )
        swap_merge = create_two_agent_public_merge(public_a, snap_a, public_b, snap_b)
        c2 = create_shared_snapshot_id_equality_contract(swap_merge)
        assert c1["contract_id"] != c2["contract_id"]
        assert c2["agent_a_id"] == AGENT_B_ID
        assert c2["agent_b_id"] == AGENT_A_ID


class TestSnapshotIdScalarOnly:
    """Additional scalar-only boundary cases for 10BP."""

    def test_no_list_fields_in_output(self):
        merge = _build_merge()
        contract = create_shared_snapshot_id_equality_contract(merge)
        for key, value in contract.items():
            if key in ("errors",):
                continue
            assert not isinstance(value, list), (
                "10BP is scalar-only; field " + key + " must not be a list"
            )

    def test_snapshot_ids_not_present_beyond_id_fields(self):
        merge = _build_merge()
        contract = create_shared_snapshot_id_equality_contract(merge)
        forbidden_fields = [
            "agent_a_snapshot_id_count",
            "agent_b_snapshot_id_count",
            "shared_snapshot_id_count",
        ]
        for field in forbidden_fields:
            assert field not in contract, (
                "10BP is scalar-only; id field " + field + " must not exist"
            )
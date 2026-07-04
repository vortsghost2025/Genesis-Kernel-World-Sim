"""Phase 10AY - shared public snapshot hash equality contract proof.

These tests prove that a Phase 10AS two-agent public merge artifact can
be wrapped in a deterministic, sanitized shared-snapshot-hash-equality
contract that formalizes whether two agents' known-map snapshots have
identical content fingerprints, without ever inferring private
knowledge, co-presence, awareness, trust, cooperation, conflict,
communication, temporal overlap, coordination, planning, proximity, or
any kind of relationship.

10AY may say:

    "Both agents' known-map snapshots have identical content hashes."

    "Both agents' public known-map snapshots are byte-for-byte equal."
    (a public-surface match; no claim of shared private knowledge,
    communication, or awareness)

    "Both agents declare the same snapshot hash."
    (a public-surface match; no claim of how they acquired identical
    knowledge)

10AY may not say:

    "The agents have the same knowledge."

    "The agents communicated or shared information."

    "The agents coordinated their exploration."

    "The agents are aware of each other."

    "The agents are or were co-present, nearby, or in the same
    location."

    "The agents' identical snapshots imply they have a relationship."

These tests follow the established Genesis discipline: tempdir-only,
no daemon, no scheduler, no provider, no Docker, no network, no live
data, no ``world-sim/data`` access.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(TESTS_ROOT))

from backend.world.local_shared_public_snapshot_hash_equality_contract import (  # noqa: E402
    contract_snapshot_hash_equality_file,
    create_shared_snapshot_hash_equality_contract,
    export_shared_snapshot_hash_equality_contract,
)
from backend.world.local_two_agent_public_merge import (  # noqa: E402
    create_two_agent_public_merge,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping  # noqa: E402

# NOTE: We import the 10AS creator here in the TEST file ONLY, to
# fabricate valid 10AS merge inputs.  The 10AY MODULE under test
# (local_shared_public_snapshot_hash_equality_contract.py) does not
# import any of these — that boundary is asserted below by a
# source-scan test.  Importing it here is the standard pattern used
# by test_phase10as_two_agent_public_merge.py,
# test_phase10au_shared_public_anchor_contract.py,
# test_phase10av_shared_public_event_ref_contract.py,
# test_phase10aw_shared_public_route_destination_contract.py, and
# test_phase10ax_shared_public_territory_ref_contract.py.


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


# ---------------------------------------------------------------------------
# Fixtures: build real 10AS merges to feed 10AY
# ---------------------------------------------------------------------------


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
    snapshot_id: str = "10AQ-" + "a" * 32,
    snapshot_hash: str = SNAP_HASH_A,
) -> dict:
    known = sorted(set(observed) | set(visited))
    return {
        "ok": True,
        "snapshot_schema_version": "10AQ.1",
        "snapshot_type": "known_map_snapshot",
        "snapshot_id": snapshot_id,
        "source_phase": "10AP",
        "source_projection_hash": snapshot_hash,
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


def _build_merge_with_snapshot_hashes(
    *,
    a_current: str = TILE_A,
    a_observed: list[str] | None = None,
    a_visited: list[str] | None = None,
    b_current: str = TILE_B,
    b_observed: list[str] | None = None,
    b_visited: list[str] | None = None,
    a_snapshot_hash: str = SNAP_HASH_A,
    b_snapshot_hash: str = SNAP_HASH_B,
    a_snapshot_id: str = SNAP_ID_A,
    b_snapshot_id: str = SNAP_ID_B,
) -> dict:
    """Build a real 10AS merge and inject snapshot hash/id fields into bundles."""

    merge = _build_merge(
        a_current=a_current,
        a_observed=a_observed,
        a_visited=a_visited,
        b_current=b_current,
        b_observed=b_observed,
        b_visited=b_visited,
    )
    merge["agent_a"]["snapshot_hash"] = a_snapshot_hash
    merge["agent_a"]["snapshot_id"] = a_snapshot_id
    merge["agent_b"]["snapshot_hash"] = b_snapshot_hash
    merge["agent_b"]["snapshot_id"] = b_snapshot_id
    return merge


_REQUIRED_TOP_LEVEL_FIELDS = [
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
    "shared_known_tile_ids",
    "shared_known_tile_count",
    "same_current_tile",
    "shared_current_tile_id",
    "agent_a_snapshot_hash",
    "agent_b_snapshot_hash",
    "agent_a_snapshot_id",
    "agent_b_snapshot_id",
    "same_snapshot_hash",
    "shared_snapshot_hash",
    "claim_scope",
    "errors",
]

_FORBIDDEN_TOP_LEVEL_FIELDS = [
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
    "route_path",
    "travel_timing",
    "eta",
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateSharedSnapshotHashEqualityContract:
    """Tests 1-21 from the 10AY spec test plan."""

    # 1. Happy path: both bundles carry equal snapshot_hash
    def test_happy_path_equal_snapshot_hashes(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_SHARED,
            b_snapshot_hash=SNAP_HASH_SHARED,
            a_snapshot_id=SNAP_ID_SHARED,
            b_snapshot_id=SNAP_ID_SHARED,
        )
        contract = create_shared_snapshot_hash_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["contract_schema_version"] == "10AY.1"
        assert contract["contract_type"] == "shared_snapshot_hash_equality_contract"
        assert contract["contract_id"].startswith("10AY-")
        assert contract["claim_scope"] == "shared_snapshot_hash_equality_only"
        assert contract["errors"] == []
        assert contract["same_snapshot_hash"] is True
        assert contract["shared_snapshot_hash"] == SNAP_HASH_SHARED

    # 2. Different snapshot hashes
    def test_different_snapshot_hashes(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_A,
            b_snapshot_hash=SNAP_HASH_B,
        )
        contract = create_shared_snapshot_hash_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["same_snapshot_hash"] is False
        assert contract["shared_snapshot_hash"] is None
        assert contract["agent_a_snapshot_hash"] == SNAP_HASH_A
        assert contract["agent_b_snapshot_hash"] == SNAP_HASH_B

    # 3. Output has exactly required top-level fields
    def test_output_has_exact_fields(self):
        merge = _build_merge()
        contract = create_shared_snapshot_hash_equality_contract(merge)
        assert sorted(contract.keys()) == sorted(_REQUIRED_TOP_LEVEL_FIELDS)
        for forbidden in _FORBIDDEN_TOP_LEVEL_FIELDS:
            assert forbidden not in contract

    # 4. same_current_tile and shared_current_tile_id propagated
    def test_current_tile_propagation(self):
        merge = _build_merge(
            a_current=TILE_SHARED,
            b_current=TILE_SHARED,
        )
        contract = create_shared_snapshot_hash_equality_contract(merge)
        assert contract["same_current_tile"] is True
        assert contract["shared_current_tile_id"] == TILE_SHARED

    # 5. shared_known_tile_ids and count lifted
    def test_shared_known_tiles_propagation(self):
        merge = _build_merge()
        contract = create_shared_snapshot_hash_equality_contract(merge)
        assert contract["shared_known_tile_ids"] == merge["shared_known_tile_ids"]
        assert contract["shared_known_tile_count"] == len(
            merge["shared_known_tile_ids"]
        )

    # 6. agent_a_snapshot_hash and agent_b_snapshot_hash propagated
    def test_snapshot_hashes_propagated(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_A,
            b_snapshot_hash=SNAP_HASH_B,
        )
        contract = create_shared_snapshot_hash_equality_contract(merge)
        assert contract["agent_a_snapshot_hash"] == SNAP_HASH_A
        assert contract["agent_b_snapshot_hash"] == SNAP_HASH_B

    # 7. agent_a_snapshot_id and agent_b_snapshot_id propagated
    def test_snapshot_ids_propagated(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_id=SNAP_ID_A,
            b_snapshot_id=SNAP_ID_B,
        )
        contract = create_shared_snapshot_hash_equality_contract(merge)
        assert contract["agent_a_snapshot_id"] == SNAP_ID_A
        assert contract["agent_b_snapshot_id"] == SNAP_ID_B

    # 8. contract_id deterministic
    def test_contract_id_deterministic(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_SHARED,
            b_snapshot_hash=SNAP_HASH_SHARED,
        )
        c1 = create_shared_snapshot_hash_equality_contract(merge)
        c2 = create_shared_snapshot_hash_equality_contract(merge)
        assert c1["contract_id"] == c2["contract_id"]
        assert c1["contract_id"] is not None

    # 9. contract_id changes when snapshot hash changes
    def test_contract_id_changes_with_snapshot_hash(self):
        merge1 = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_A,
            b_snapshot_hash=SNAP_HASH_A,
        )
        c1 = create_shared_snapshot_hash_equality_contract(merge1)

        merge2 = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_A,
            b_snapshot_hash=SNAP_HASH_B,
        )
        c2 = create_shared_snapshot_hash_equality_contract(merge2)

        assert c1["same_snapshot_hash"] != c2["same_snapshot_hash"]
        assert c1["contract_id"] != c2["contract_id"]

    # 10. Input mutation guard
    def test_input_not_mutated(self):
        merge = _build_merge()
        original = copy.deepcopy(merge)
        create_shared_snapshot_hash_equality_contract(merge)
        assert merge == original

    # 11. Non-dict / ok=False / wrong types / empty ids / same ids
    def test_structural_failures(self):
        # Non-dict
        c = create_shared_snapshot_hash_equality_contract("not a dict")
        assert c["ok"] is False
        assert "merge must be a dict" in c["errors"]

        # ok=False merge
        bad_merge = {"ok": False, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_snapshot_hash_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_type
        bad_merge = {"ok": True, "merge_type": "wrong",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_snapshot_hash_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_schema_version
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "9X.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_snapshot_hash_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_a
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_b": {}}
        c = create_shared_snapshot_hash_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_b
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {}}
        c = create_shared_snapshot_hash_equality_contract(bad_merge)
        assert c["ok"] is False

        # Empty agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": ""},
                     "agent_b": {"agent_id": ""}}
        c = create_shared_snapshot_hash_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id is missing or empty" in c["errors"]

        # Same agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": "same_id"},
                     "agent_b": {"agent_id": "same_id"}}
        c = create_shared_snapshot_hash_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id and agent_b_id must be distinct" in c["errors"]

    # 12. shared_known_tile_ids not a list / same_current_tile not bool
    def test_type_validation_failures(self):
        merge = _build_merge()
        merge["shared_known_tile_ids"] = "not a list"
        c = create_shared_snapshot_hash_equality_contract(merge)
        assert c["ok"] is False

        merge = _build_merge()
        merge["same_current_tile"] = "yes"
        c = create_shared_snapshot_hash_equality_contract(merge)
        assert c["ok"] is False

    # 13. same_current_tile True but bundle current tiles differ
    def test_same_current_tile_internal_consistency_guard(self):
        merge = _build_merge(
            a_current=TILE_A,
            b_current=TILE_B,
        )
        merge["same_current_tile"] = True
        c = create_shared_snapshot_hash_equality_contract(merge)
        assert c["ok"] is False
        assert "same_current_tile is True but agent current_tile_ids differ" in c[
            "errors"
        ]

    # 14. Private markers redacted
    def test_private_markers_redacted(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_hash="/home/user/secret.txt",
            a_snapshot_id="10AQ-secret",
            b_snapshot_hash="192.168.1.1",
            b_snapshot_id="10AQ-other",
        )
        contract = create_shared_snapshot_hash_equality_contract(merge)
        exported = export_shared_snapshot_hash_equality_contract(contract)
        assert "/home/user/secret.txt" not in exported
        assert "192.168.1.1" not in exported

    # 15. Graceful handling of missing snapshot_hash
    def test_graceful_missing_snapshot_hash(self):
        merge = _build_merge()
        # Remove snapshot_hash fields to simulate older 10AS merge
        merge["agent_a"]["snapshot_hash"] = ""
        merge["agent_b"]["snapshot_hash"] = ""
        merge["agent_a"]["snapshot_id"] = ""
        merge["agent_b"]["snapshot_id"] = ""
        contract = create_shared_snapshot_hash_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_snapshot_hash"] is None
        assert contract["agent_b_snapshot_hash"] is None
        assert contract["agent_a_snapshot_id"] is None
        assert contract["agent_b_snapshot_id"] is None
        assert contract["same_snapshot_hash"] is False
        assert contract["shared_snapshot_hash"] is None

    # 16. export_shared_snapshot_hash_equality_contract stable JSON
    def test_export_stable_json(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_SHARED,
            b_snapshot_hash=SNAP_HASH_SHARED,
        )
        contract = create_shared_snapshot_hash_equality_contract(merge)
        exported = export_shared_snapshot_hash_equality_contract(contract)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == contract["contract_id"]
        # Round-trip: re-export is identical
        exported2 = export_shared_snapshot_hash_equality_contract(parsed)
        assert exported == exported2

    # 17. contract_snapshot_hash_equality_file reads and builds
    def test_contract_snapshot_hash_equality_file(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_hash="ha",
            b_snapshot_hash="hb",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            result = contract_snapshot_hash_equality_file(path)
        assert result["ok"] is True
        assert result["agent_a_snapshot_hash"] == "ha"
        assert result["agent_b_snapshot_hash"] == "hb"

    # 18. Saturation: all three public functions exercised
    def test_all_public_functions_exercised(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_SHARED,
            b_snapshot_hash=SNAP_HASH_SHARED,
        )
        c1 = create_shared_snapshot_hash_equality_contract(merge)
        assert c1["ok"] is True

        exported = export_shared_snapshot_hash_equality_contract(c1)
        assert isinstance(exported, str)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == c1["contract_id"]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            c2 = contract_snapshot_hash_equality_file(path)
        assert c2["ok"] is True
        assert c2["same_snapshot_hash"] is True

    # 19. Boundary scan: no forbidden imports in the 10AY module
    def test_module_has_no_forbidden_imports(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_snapshot_hash_equality_contract.py"
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
                "forbidden token in 10AY module source: " + token
            )

    # 20. Module source does not call upstream creators
    def test_module_does_not_call_upstream_creators(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_snapshot_hash_equality_contract.py"
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
                "10AY module must not call upstream creator: " + creator
            )

    # 21. Boundary smoke: no relationship/trust/etc tokens in happy path
    def test_happy_path_contains_no_forbidden_tokens(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_SHARED,
            b_snapshot_hash=SNAP_HASH_SHARED,
        )
        contract = create_shared_snapshot_hash_equality_contract(merge)
        exported = export_shared_snapshot_hash_equality_contract(contract)
        forbidden_tokens = [
            "relationship",
            "trust",
            "cooperation",
            "conflict",
            "awareness",
            "co-presence",
            "communication",
            "shared_private",
            "private_knowledge",
            "tick_window",
            "active_at_same_time",
            "temporal_overlap",
            "route_path",
            "travel_timing",
            "eta",
        ]
        lowered = exported.lower()
        for token in forbidden_tokens:
            assert token not in lowered, (
                "forbidden token in exported contract: " + token
            )


class TestSnapshotHashSetOperations:
    """Additional set-operation edge cases for snapshot hash fields."""

    def test_one_empty_hash_no_shared(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_A,
            b_snapshot_hash="",
        )
        contract = create_shared_snapshot_hash_equality_contract(merge)
        assert contract["same_snapshot_hash"] is False
        assert contract["shared_snapshot_hash"] is None

    def test_both_empty_hashes_no_shared(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_hash="",
            b_snapshot_hash="",
        )
        contract = create_shared_snapshot_hash_equality_contract(merge)
        assert contract["same_snapshot_hash"] is False
        assert contract["shared_snapshot_hash"] is None

    def test_same_snapshot_id_but_different_hash_not_shared(self):
        merge = _build_merge_with_snapshot_hashes(
            a_snapshot_id=SNAP_ID_SHARED,
            b_snapshot_id=SNAP_ID_SHARED,
            a_snapshot_hash=SNAP_HASH_A,
            b_snapshot_hash=SNAP_HASH_B,
        )
        contract = create_shared_snapshot_hash_equality_contract(merge)
        assert contract["same_snapshot_hash"] is False
        assert contract["shared_snapshot_hash"] is None
        assert contract["agent_a_snapshot_id"] == SNAP_ID_SHARED
        assert contract["agent_b_snapshot_id"] == SNAP_ID_SHARED

    def test_contract_id_changes_when_hash_changes(self):
        merge1 = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_A,
            b_snapshot_hash=SNAP_HASH_A,
        )
        c1 = create_shared_snapshot_hash_equality_contract(merge1)

        merge2 = _build_merge_with_snapshot_hashes(
            a_snapshot_hash=SNAP_HASH_A,
            b_snapshot_hash=SNAP_HASH_B,
        )
        c2 = create_shared_snapshot_hash_equality_contract(merge2)

        assert c1["shared_snapshot_hash"] != c2["shared_snapshot_hash"]
        assert c1["contract_id"] != c2["contract_id"]

"""Phase 10BE - shared public accepted event count equality contract proof.

These tests prove that a Phase 10AS two-agent public merge artifact can
be wrapped in a deterministic, sanitized shared-public-accepted-event-
count-equality contract that formalizes whether two agents' public
accepted event counts are identical, without ever inferring same accepted
events, temporal overlap, co-presence, awareness, trust, cooperation,
conflict, communication, coordination, planning, proximity, or any kind
of relationship.

Accepted event counts are supplied as optional caller arguments; 10BE
does not read them from 10AS bundles.  Missing, non-integer, or negative
accepted event counts are treated as ``None``.

10BE may say:

    "Agent A's public accepted_event_count is N."

    "Agent B's public accepted_event_count is M."

    "Both agents report the same public accepted_event_count value."
    (public-surface equality only)

10BE may not say:

    "Both agents accepted the same events." (event-content inference)

    "Both agents accepted events at the same time." (temporal overlap inference)

    "Both agents were in the same place." (spatial inference)

    "The agents could have met or interacted." (meeting/interaction inference)

    "The agents have a temporal window in common." (window inference)

    "The agents' accepted event counts imply a relationship." (relationship inference)

    Anything about awareness, communication, cooperation, conflict,
    relationship, trust, proximity, distance, ETA, or route inference.

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

from backend.world.local_shared_public_accepted_event_count_equality_contract import (  # noqa: E402
    contract_accepted_event_count_equality_file,
    create_shared_accepted_event_count_equality_contract,
    export_shared_accepted_event_count_equality_contract,
)
from backend.world.local_two_agent_public_merge import (  # noqa: E402
    create_two_agent_public_merge,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping  # noqa: E402

# NOTE: We import the 10AS creator here in the TEST file ONLY, to
# fabricate valid 10AS merge inputs.  The 10BE MODULE under test
# (local_shared_public_accepted_event_count_equality_contract.py) does not
# import any of these — that boundary is asserted below by a
# source-scan test.  Importing it here is the standard pattern used
# by test_phase10as_two_agent_public_merge.py,
# test_phase10au_shared_public_anchor_contract.py,
# test_phase10av_shared_public_event_ref_contract.py,
# test_phase10aw_shared_public_route_destination_contract.py,
# test_phase10ax_shared_public_territory_ref_contract.py,
# test_phase10ay_shared_public_snapshot_hash_equality_contract.py,
# test_phase10az_shared_public_tick_range_equality_contract.py,
# test_phase10ba_shared_public_tick_label_contract.py,
# test_phase10bb_shared_public_state_hash_equality_contract.py,
# test_phase10bc_shared_public_observation_count_equality_contract.py, and
# test_phase10bd_shared_public_movement_count_equality_contract.py.


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


# ---------------------------------------------------------------------------
# Fixtures: build real 10AS merges to feed 10BE
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
) -> dict:
    known = sorted(set(observed) | set(visited))
    return {
        "ok": True,
        "snapshot_schema_version": "10AQ.1",
        "snapshot_type": "known_map_snapshot",
        "snapshot_id": "10AQ-" + "a" * 32,
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateSharedAcceptedEventCountEqualityContract:
    """Tests 1-21 from the 10BE spec test plan."""

    # 1. Happy path: both bundles carry equal accepted_event_count
    def test_happy_path_equal_counts(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
        assert contract["ok"] is True
        assert contract["contract_schema_version"] == "10BE.1"
        assert contract["contract_type"] == "shared_public_accepted_event_count_equality_contract"
        assert contract["contract_id"].startswith("10BE-")
        assert contract["claim_scope"] == "shared_public_accepted_event_count_equality_only"
        assert contract["errors"] == []
        assert contract["same_accepted_event_count"] is True
        assert contract["shared_accepted_event_count"] == 3

    # 2. Different accepted event counts
    def test_different_accepted_event_counts(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=5,
        )
        assert contract["ok"] is True
        assert contract["same_accepted_event_count"] is False
        assert contract["shared_accepted_event_count"] is None
        assert contract["agent_a_accepted_event_count"] == 3
        assert contract["agent_b_accepted_event_count"] == 5

    # 3. One bundle missing accepted_event_count
    def test_one_bundle_missing_accepted_event_count(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=None,
            agent_b_accepted_event_count=3,
        )
        assert contract["ok"] is True
        assert contract["agent_a_accepted_event_count"] is None
        assert contract["agent_b_accepted_event_count"] == 3
        assert contract["same_accepted_event_count"] is False
        assert contract["shared_accepted_event_count"] is None

    # 4. Both bundles missing accepted_event_count
    def test_both_bundles_missing_accepted_event_count(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=None,
            agent_b_accepted_event_count=None,
        )
        assert contract["ok"] is True
        assert contract["agent_a_accepted_event_count"] is None
        assert contract["agent_b_accepted_event_count"] is None
        assert contract["same_accepted_event_count"] is False
        assert contract["shared_accepted_event_count"] is None

    # 5. Output has exactly required top-level fields; no forbidden fields
    def test_output_has_exact_fields(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
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
            "agent_a_accepted_event_count",
            "agent_b_accepted_event_count",
            "same_accepted_event_count",
            "shared_accepted_event_count",
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
            "same_accepted_events",
            "event_content",
            "route_path",
            "travel_timing",
            "eta",
            "same_state",
            "temporal_overlap",
            "co_presence",
            "meeting",
            "interaction",
        ]
        for token in forbidden:
            assert token not in contract

    # 6. contract_id deterministic
    def test_contract_id_deterministic(self):
        merge = _build_merge()
        c1 = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
        c2 = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
        assert c1["contract_id"] == c2["contract_id"]
        assert c1["contract_id"] is not None

    # 7. contract_id changes when accepted event count changes
    def test_contract_id_changes_with_count(self):
        merge = _build_merge()
        c1 = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
        c2 = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=5,
        )
        assert c1["same_accepted_event_count"] != c2["same_accepted_event_count"]
        assert c1["contract_id"] != c2["contract_id"]

    # 8. Input mutation guard
    def test_input_not_mutated(self):
        merge = _build_merge()
        original = copy.deepcopy(merge)
        create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=5,
        )
        assert merge == original

    # 9. Structural failures: non-dict, ok=False, wrong types, empty ids, same ids
    def test_structural_failures(self):
        # Non-dict
        c = create_shared_accepted_event_count_equality_contract("not a dict")
        assert c["ok"] is False
        assert "merge must be a dict" in c["errors"]

        # ok=False merge
        bad_merge = {"ok": False, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_accepted_event_count_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_type
        bad_merge = {"ok": True, "merge_type": "wrong",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_accepted_event_count_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_schema_version
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "9X.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_accepted_event_count_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_a
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_b": {}}
        c = create_shared_accepted_event_count_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_b
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {}}
        c = create_shared_accepted_event_count_equality_contract(bad_merge)
        assert c["ok"] is False

        # Empty agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": ""},
                     "agent_b": {"agent_id": ""}}
        c = create_shared_accepted_event_count_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id is missing or empty" in c["errors"]

        # Same agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": "same_id"},
                     "agent_b": {"agent_id": "same_id"}}
        c = create_shared_accepted_event_count_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id and agent_b_id must be distinct" in c["errors"]

    # 10. Type validation: accepted_event_count not an integer
    def test_type_validation_non_integer_accepted_event_count(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count="three",
            agent_b_accepted_event_count=3,
        )
        assert contract["ok"] is True
        assert contract["agent_a_accepted_event_count"] is None
        assert contract["agent_b_accepted_event_count"] == 3
        assert contract["same_accepted_event_count"] is False
        assert contract["shared_accepted_event_count"] is None

    # 11. Private markers redacted in exported JSON
    def test_private_markers_redacted(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
        # Inject a private marker into agent ids via the merge (will be
        # sanitized by sanitize_public_mapping)
        merge["agent_a"]["agent_id"] = "/home/user/secret"
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
        exported = export_shared_accepted_event_count_equality_contract(contract)
        assert "/home/user/secret" not in exported

    # 12. Graceful handling of missing/None accepted event counts
    def test_graceful_missing_accepted_event_counts(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=None,
            agent_b_accepted_event_count=3,
        )
        assert contract["ok"] is True
        assert contract["agent_a_accepted_event_count"] is None
        assert contract["agent_b_accepted_event_count"] == 3
        assert contract["same_accepted_event_count"] is False
        assert contract["shared_accepted_event_count"] is None

    # 13. Stable JSON export / round-trip
    def test_export_stable_json(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
        exported = export_shared_accepted_event_count_equality_contract(contract)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == contract["contract_id"]
        # Round-trip: re-export is identical
        exported2 = export_shared_accepted_event_count_equality_contract(parsed)
        assert exported == exported2

    # 14. contract_accepted_event_count_equality_file reads and builds
    def test_contract_accepted_event_count_equality_file(self):
        merge = _build_merge()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            result = contract_accepted_event_count_equality_file(
                path,
                agent_a_accepted_event_count=3,
                agent_b_accepted_event_count=3,
            )
        assert result["ok"] is True
        assert result["agent_a_accepted_event_count"] == 3
        assert result["agent_b_accepted_event_count"] == 3

    # 15. All three public functions exercised
    def test_all_public_functions_exercised(self):
        merge = _build_merge()
        c1 = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
        assert c1["ok"] is True

        exported = export_shared_accepted_event_count_equality_contract(c1)
        assert isinstance(exported, str)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == c1["contract_id"]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            c2 = contract_accepted_event_count_equality_file(
                path,
                agent_a_accepted_event_count=3,
                agent_b_accepted_event_count=3,
            )
        assert c2["ok"] is True
        assert c2["same_accepted_event_count"] is True

    # 16. Module has no forbidden imports
    def test_module_has_no_forbidden_imports(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_accepted_event_count_equality_contract.py"
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
                "forbidden token in 10BE module source: " + token
            )

    # 17. Module source does not call upstream creators
    def test_module_does_not_call_upstream_creators(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_accepted_event_count_equality_contract.py"
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
                "10BE module must not call upstream creator: " + creator
            )

    # 18. Happy path contains no forbidden tokens
    def test_happy_path_contains_no_forbidden_tokens(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
        exported = export_shared_accepted_event_count_equality_contract(contract)
        forbidden_tokens = [
            "same_accepted_events",
            "event_content",
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
        ]
        lowered = exported.lower()
        for token in forbidden_tokens:
            assert token not in lowered, (
                "forbidden token in exported contract: " + token
            )


class TestAcceptedEventCountBoundaries:
    """Additional boundary cases for 10BE."""

    # 19. Negative accepted_event_count treated as None
    def test_negative_accepted_event_count_treated_as_none(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=-1,
            agent_b_accepted_event_count=3,
        )
        assert contract["ok"] is True
        assert contract["agent_a_accepted_event_count"] is None
        assert contract["agent_b_accepted_event_count"] == 3
        assert contract["same_accepted_event_count"] is False
        assert contract["shared_accepted_event_count"] is None

    # 20. Zero accepted_event_count handled correctly
    def test_zero_accepted_event_count_handled(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=0,
            agent_b_accepted_event_count=0,
        )
        assert contract["ok"] is True
        assert contract["agent_a_accepted_event_count"] == 0
        assert contract["agent_b_accepted_event_count"] == 0
        assert contract["same_accepted_event_count"] is True
        assert contract["shared_accepted_event_count"] == 0

    # 21. contract_id preserves A/B agent orientation
    def test_contract_id_preserves_ab_orientation(self):
        merge = _build_merge()
        c1 = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=2,
        )
        # Build a merge with swapped agent ids
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
        c2 = create_shared_accepted_event_count_equality_contract(
            swap_merge,
            agent_a_accepted_event_count=2,
            agent_b_accepted_event_count=3,
        )
        # contract_ids must differ because agent_a_id/agent_b_id order differs
        assert c1["contract_id"] != c2["contract_id"]
        assert c2["agent_a_id"] == AGENT_B_ID
        assert c2["agent_b_id"] == AGENT_A_ID


class TestAcceptedEventCountScalarOnly:
    """Additional scalar-only boundary cases for 10BE."""

    # 10BE is scalar-only: no lists, no dedup, no set algebra.

    def test_no_list_fields_in_output(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
        for key, value in contract.items():
            if key in ("errors",):
                continue
            assert not isinstance(value, list), (
                "10BE is scalar-only; field " + key + " must not be a list"
            )

    def test_counts_not_present_beyond_count_fields(self):
        merge = _build_merge()
        contract = create_shared_accepted_event_count_equality_contract(
            merge,
            agent_a_accepted_event_count=3,
            agent_b_accepted_event_count=3,
        )
        forbidden_fields = [
            "agent_a_accepted_event_count_count",
            "agent_b_accepted_event_count_count",
            "shared_accepted_event_count_count",
        ]
        for field in forbidden_fields:
            assert field not in contract, (
                "10BE is scalar-only; count field " + field + " must not exist"
            )

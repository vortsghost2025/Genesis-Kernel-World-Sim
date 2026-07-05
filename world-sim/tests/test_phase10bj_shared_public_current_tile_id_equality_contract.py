"""Phase 10BJ - shared public current tile id equality contract proof.

These tests prove that a Phase 10AS two-agent public merge artifact can
be wrapped in a deterministic, sanitized shared-public-current-tile-id-
equality contract that formalizes whether two agents' public current
tile IDs are identical, without ever inferring same place at same time,
co-presence, meeting, interaction, proximity, awareness, route, or
relationship.

Current tile IDs are read from 10AS agent bundles. Missing, non-string,
or empty-after-sanitize current tile IDs are treated as ``None``.

10BJ may say:

    "Agent A's public current_tile_id is X."

    "Agent B's public current_tile_id is Y."

    "Both agents report the same public current_tile_id value."
    (public-surface equality only)

10BJ may not say:

    "Both agents are in the same place at the same time."

    "Both agents are co-present."

    "Both agents met or interacted."

    "Both agents are near or aware of each other."

    "Both agents have the same route, path, destination, or timing."

    "Both agents have a relationship, trust, cooperation, or conflict."

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

from backend.world.local_shared_public_current_tile_id_equality_contract import (  # noqa: E402
    contract_current_tile_id_equality_file,
    create_shared_current_tile_id_equality_contract,
    export_shared_current_tile_id_equality_contract,
)
from backend.world.local_two_agent_public_merge import (  # noqa: E402
    create_two_agent_public_merge,
)

# NOTE: We import the 10AS creator here in the TEST file ONLY, to
# fabricate valid 10AS merge inputs.  The 10BJ MODULE under test
# (local_shared_public_current_tile_id_equality_contract.py) does not
# import any of these - that boundary is asserted below by a
# source-scan test.  Importing it here is the standard pattern used by
# earlier 10A* and 10B* contract tests.


AGENT_A_ID = "agent_adam"
AGENT_B_ID = "agent_eve"
TILE_A = "tile_start"
TILE_B = "tile_east"
TILE_C = "tile_north"
TILE_SHARED = "tile_central"


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
# Fixtures: build real 10AS merges to feed 10BJ
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


class TestCreateSharedCurrentTileIdEqualityContract:
    """Tests 1-21 from the 10BJ spec test plan."""

    # 1. Happy path: both bundle current tile IDs equal
    def test_happy_path_equal_ids(self):
        merge = _build_merge(a_current=TILE_SHARED, b_current=TILE_SHARED)
        contract = create_shared_current_tile_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["contract_schema_version"] == "10BJ.1"
        assert contract["contract_type"] == "shared_public_current_tile_id_equality_contract"
        assert contract["contract_id"].startswith("10BJ-")
        assert contract["claim_scope"] == "shared_public_current_tile_id_equality_only"
        assert contract["errors"] == []
        assert contract["same_current_tile_id"] is True
        assert contract["shared_current_tile_id"] == TILE_SHARED

    # 2. Different bundle current tile IDs
    def test_different_current_tile_ids(self):
        merge = _build_merge(a_current=TILE_A, b_current=TILE_B)
        contract = create_shared_current_tile_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["same_current_tile_id"] is False
        assert contract["shared_current_tile_id"] is None
        assert contract["agent_a_current_tile_id"] == TILE_A
        assert contract["agent_b_current_tile_id"] == TILE_B

    # 3. One bundle current tile ID missing/None
    def test_one_bundle_missing_current_tile_id(self):
        merge = _build_merge()
        merge["agent_a"].pop("current_tile_id")
        contract = create_shared_current_tile_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_current_tile_id"] is None
        assert contract["agent_b_current_tile_id"] == TILE_B
        assert contract["same_current_tile_id"] is False
        assert contract["shared_current_tile_id"] is None

    # 4. Both bundle current tile IDs missing/None
    def test_both_bundles_missing_current_tile_id(self):
        merge = _build_merge()
        merge["agent_a"].pop("current_tile_id")
        merge["agent_b"]["current_tile_id"] = None
        contract = create_shared_current_tile_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_current_tile_id"] is None
        assert contract["agent_b_current_tile_id"] is None
        assert contract["same_current_tile_id"] is False
        assert contract["shared_current_tile_id"] is None

    # 5. Output has exactly required top-level fields; no forbidden fields
    def test_output_has_exact_fields(self):
        merge = _build_merge(a_current=TILE_SHARED, b_current=TILE_SHARED)
        contract = create_shared_current_tile_id_equality_contract(merge)
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
            "agent_a_current_tile_id",
            "agent_b_current_tile_id",
            "same_current_tile_id",
            "shared_current_tile_id",
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
            "same_place_at_same_time",
            "same_event",
            "same_time",
            "same_sequence",
            "same_interaction",
            "same_relationship",
            "proximity",
            "near",
            "route_path",
            "route_destination",
            "travel_timing",
            "eta",
            "same_state",
            "meeting",
            "interaction",
        ]
        for token in forbidden:
            assert token not in contract

    # 6. contract_id deterministic
    def test_contract_id_deterministic(self):
        merge = _build_merge(a_current=TILE_SHARED, b_current=TILE_SHARED)
        c1 = create_shared_current_tile_id_equality_contract(merge)
        c2 = create_shared_current_tile_id_equality_contract(merge)
        assert c1["contract_id"] == c2["contract_id"]
        assert c1["contract_id"] is not None

    # 7. contract_id changes when current tile ID changes
    def test_contract_id_changes_with_id(self):
        c1 = create_shared_current_tile_id_equality_contract(
            _build_merge(a_current=TILE_SHARED, b_current=TILE_SHARED)
        )
        c2 = create_shared_current_tile_id_equality_contract(
            _build_merge(a_current=TILE_SHARED, b_current=TILE_B)
        )
        assert c1["same_current_tile_id"] != c2["same_current_tile_id"]
        assert c1["contract_id"] != c2["contract_id"]

    # 8. Input mutation guard
    def test_input_not_mutated(self):
        merge = _build_merge(a_current=TILE_A, b_current=TILE_B)
        original = copy.deepcopy(merge)
        create_shared_current_tile_id_equality_contract(merge)
        assert merge == original

    # 9. Structural failures: non-dict, ok=False, wrong types, empty ids, same ids
    def test_structural_failures(self):
        # Non-dict
        c = create_shared_current_tile_id_equality_contract("not a dict")
        assert c["ok"] is False
        assert "merge must be a dict" in c["errors"]

        # ok=False merge
        bad_merge = {"ok": False, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_current_tile_id_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_type
        bad_merge = {"ok": True, "merge_type": "wrong",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_current_tile_id_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_schema_version
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "9X.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_current_tile_id_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_a
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_b": {}}
        c = create_shared_current_tile_id_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_b
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {}}
        c = create_shared_current_tile_id_equality_contract(bad_merge)
        assert c["ok"] is False

        # Empty agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": ""},
                     "agent_b": {"agent_id": ""}}
        c = create_shared_current_tile_id_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id is missing or empty" in c["errors"]

        # Same agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": "same_id"},
                     "agent_b": {"agent_id": "same_id"}}
        c = create_shared_current_tile_id_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id and agent_b_id must be distinct" in c["errors"]

    # 10. Type validation: current_tile_id not a string or empty after sanitize
    def test_type_validation_non_string_current_tile_id(self):
        merge = _build_merge()
        merge["agent_a"]["current_tile_id"] = 123
        contract = create_shared_current_tile_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_current_tile_id"] is None
        assert contract["agent_b_current_tile_id"] == TILE_B
        assert contract["same_current_tile_id"] is False
        assert contract["shared_current_tile_id"] is None

    # 11. Private markers redacted in exported JSON
    def test_private_markers_redacted(self):
        merge = _build_merge()
        merge["agent_a"]["current_tile_id"] = "/home/user/secret"
        merge["agent_b"]["current_tile_id"] = "/home/user/secret"
        contract = create_shared_current_tile_id_equality_contract(merge)
        # sanitize_public_mapping redacts private markers, and any
        # sanitized value containing a redaction marker is treated as
        # None so it cannot participate in equality comparisons.
        assert contract["agent_a_current_tile_id"] is None
        assert contract["agent_b_current_tile_id"] is None
        assert contract["same_current_tile_id"] is False
        assert contract["shared_current_tile_id"] is None
        exported = export_shared_current_tile_id_equality_contract(contract)
        assert "/home/user/secret" not in exported

    # 12. Graceful handling of missing/None current tile IDs
    def test_graceful_missing_current_tile_ids(self):
        merge = _build_merge()
        merge["agent_a"]["current_tile_id"] = None
        contract = create_shared_current_tile_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_current_tile_id"] is None
        assert contract["agent_b_current_tile_id"] == TILE_B
        assert contract["same_current_tile_id"] is False
        assert contract["shared_current_tile_id"] is None

    # 13. Stable JSON export / round-trip
    def test_export_stable_json(self):
        merge = _build_merge(a_current=TILE_SHARED, b_current=TILE_SHARED)
        contract = create_shared_current_tile_id_equality_contract(merge)
        exported = export_shared_current_tile_id_equality_contract(contract)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == contract["contract_id"]
        # Round-trip: re-export is identical
        exported2 = export_shared_current_tile_id_equality_contract(parsed)
        assert exported == exported2

    # 14. contract_current_tile_id_equality_file reads and builds
    def test_contract_current_tile_id_equality_file(self):
        merge = _build_merge(a_current=TILE_SHARED, b_current=TILE_SHARED)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            result = contract_current_tile_id_equality_file(path)
        assert result["ok"] is True
        assert result["agent_a_current_tile_id"] == TILE_SHARED
        assert result["agent_b_current_tile_id"] == TILE_SHARED

    # 15. All three public functions exercised
    def test_all_public_functions_exercised(self):
        merge = _build_merge(a_current=TILE_SHARED, b_current=TILE_SHARED)
        c1 = create_shared_current_tile_id_equality_contract(merge)
        assert c1["ok"] is True

        exported = export_shared_current_tile_id_equality_contract(c1)
        assert isinstance(exported, str)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == c1["contract_id"]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            c2 = contract_current_tile_id_equality_file(path)
        assert c2["ok"] is True
        assert c2["same_current_tile_id"] is True

    # 16. Module has no forbidden imports
    def test_module_has_no_forbidden_imports(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_current_tile_id_equality_contract.py"
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
                "forbidden token in 10BJ module source: " + token
            )

    # 17. Module source does not call upstream creators
    def test_module_does_not_call_upstream_creators(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_current_tile_id_equality_contract.py"
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
                "10BJ module must not call upstream creator: " + creator
            )

    # 18. Happy path contains no forbidden tokens
    def test_happy_path_contains_no_forbidden_tokens(self):
        merge = _build_merge(a_current=TILE_SHARED, b_current=TILE_SHARED)
        contract = create_shared_current_tile_id_equality_contract(merge)
        exported = export_shared_current_tile_id_equality_contract(contract)
        forbidden_tokens = [
            "same_place_at_same_time",
            "co_presence",
            "co-present",
            "meeting",
            "interaction",
            "proximity",
            "awareness",
            "communication",
            "relationship",
            "trust",
            "cooperation",
            "conflict",
            "route_path",
            "route_destination",
            "pathfinding",
            "travel_timing",
            "eta",
            "nearby",
            "aware",
            "shared_private",
            "private_knowledge",
            "tick_window",
            "active_at_same_time",
        ]
        lowered = exported.lower()
        for token in forbidden_tokens:
            assert token not in lowered, (
                "forbidden token in exported contract: " + token
            )


class TestCurrentTileIdBoundaries:
    """Additional boundary cases for 10BJ."""

    # 19. Boundary: private-marker-like current tile ID is sanitized/redacted and never leaks
    def test_private_marker_like_current_tile_id_never_leaks(self):
        merge = _build_merge()
        merge["agent_a"]["current_tile_id"] = "/home/user/secret"
        merge["agent_b"]["current_tile_id"] = "/home/user/secret"
        contract = create_shared_current_tile_id_equality_contract(merge)
        # sanitize_public_mapping redacts private markers, and any
        # sanitized value containing a redaction marker is treated as
        # None so it cannot participate in equality comparisons.
        assert contract["agent_a_current_tile_id"] is None
        assert contract["agent_b_current_tile_id"] is None
        assert contract["same_current_tile_id"] is False
        assert contract["shared_current_tile_id"] is None
        exported = export_shared_current_tile_id_equality_contract(contract)
        assert "/home/user/secret" not in exported

    # 20. Boundary: empty string current tile ID treated as None
    def test_empty_string_current_tile_id_treated_as_none(self):
        merge = _build_merge()
        merge["agent_a"]["current_tile_id"] = ""
        merge["agent_b"]["current_tile_id"] = ""
        contract = create_shared_current_tile_id_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_current_tile_id"] is None
        assert contract["agent_b_current_tile_id"] is None
        assert contract["same_current_tile_id"] is False
        assert contract["shared_current_tile_id"] is None

    # 21. contract_id preserves A/B agent orientation
    def test_contract_id_preserves_ab_orientation(self):
        merge = _build_merge(a_current=TILE_A, b_current=TILE_B)
        c1 = create_shared_current_tile_id_equality_contract(merge)
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
        c2 = create_shared_current_tile_id_equality_contract(swap_merge)
        # contract_ids must differ because agent_a_id/agent_b_id order differs
        assert c1["contract_id"] != c2["contract_id"]
        assert c2["agent_a_id"] == AGENT_B_ID
        assert c2["agent_b_id"] == AGENT_A_ID


class TestCurrentTileIdScalarOnly:
    """Additional scalar-only boundary cases for 10BJ."""

    # 10BJ is scalar-only: no lists, no dedup, no set algebra.

    def test_no_list_fields_in_output(self):
        merge = _build_merge(a_current=TILE_SHARED, b_current=TILE_SHARED)
        contract = create_shared_current_tile_id_equality_contract(merge)
        for key, value in contract.items():
            if key in ("errors",):
                continue
            assert not isinstance(value, list), (
                "10BJ is scalar-only; field " + key + " must not be a list"
            )

    def test_current_tile_ids_not_present_beyond_id_fields(self):
        merge = _build_merge(a_current=TILE_SHARED, b_current=TILE_SHARED)
        contract = create_shared_current_tile_id_equality_contract(merge)
        forbidden_fields = [
            "agent_a_current_tile_id_count",
            "agent_b_current_tile_id_count",
            "shared_current_tile_id_count",
        ]
        for field in forbidden_fields:
            assert field not in contract, (
                "10BJ is scalar-only; id field " + field + " must not exist"
            )

"""Phase 10BL - shared public known tile IDs set equality proof.

These tests prove that a Phase 10AS two-agent public merge artifact can
be wrapped in a deterministic, sanitized shared-public-known-tile-ids
set-equality contract that compares the two public bundle
``known_tile_ids`` lists mechanically.

10BL may say:

    "Both agents report the same public known_tile_ids set."
    (public-surface set equality only)

10BL may not say:

    "Both agents have the same map knowledge."

    "Both agents have the same exploration history."

    "Both agents observed the same event."

    "Both agents are in the same place."

    "Both agents are co-present, aware of each other, on the same route,
     or in any relationship."

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

from backend.world.local_shared_public_known_tile_ids_set_equality_contract import (  # noqa: E402
    contract_known_tile_ids_set_equality_file,
    create_shared_known_tile_ids_set_equality_contract,
    export_shared_known_tile_ids_set_equality_contract,
)
from backend.world.local_two_agent_public_merge import (  # noqa: E402
    create_two_agent_public_merge,
)

# NOTE: We import the 10AS creator here in the TEST file ONLY, to
# fabricate valid 10AS merge inputs.  The 10BL MODULE under test
# (local_shared_public_known_tile_ids_set_equality_contract.py) does
# not import any of these - that boundary is asserted below by source
# scan tests.


AGENT_A_ID = "agent_adam"
AGENT_B_ID = "agent_eve"
TILE_A = "tile_start"
TILE_B = "tile_east"
TILE_C = "tile_north"
TILE_SHARED = "tile_central"
TILE_OTHER = "tile_far"


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


def _module_source() -> str:
    module_path = (
        PROJECT_ROOT
        / "backend"
        / "world"
        / "local_shared_public_known_tile_ids_set_equality_contract.py"
    )
    return module_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures: build real 10AS merges to feed 10BL
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


def _build_merge() -> dict:
    """Build a real 10AS merge via the 10AS creator."""

    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED, TILE_C],
        visited=[TILE_A, TILE_SHARED],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B, TILE_SHARED],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED, TILE_C],
        visited=[TILE_A, TILE_SHARED],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B, TILE_SHARED],
    )
    merge = create_two_agent_public_merge(public_a, snap_a, public_b, snap_b)
    assert merge["ok"] is True, "fixture merge must be ok=True; got: " + repr(
        merge.get("errors")
    )
    return merge


def _build_merge_with_known(a_known, b_known) -> dict:
    merge = _build_merge()
    merge["agent_a"]["known_tile_ids"] = copy.deepcopy(a_known)
    merge["agent_b"]["known_tile_ids"] = copy.deepcopy(b_known)
    return merge


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateSharedKnownTileIdsSetEqualityContract:
    """Tests 1-22 from the 10BL spec test plan."""

    # 1. Happy path: equal non-empty known-tile sets
    def test_equal_non_empty_sets(self):
        merge = _build_merge_with_known(
            [TILE_A, TILE_SHARED],
            [TILE_A, TILE_SHARED],
        )
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["contract_schema_version"] == "10BL.1"
        assert contract["contract_type"] == (
            "shared_public_known_tile_ids_set_equality_contract"
        )
        assert contract["contract_id"].startswith("10BL-")
        assert contract["claim_scope"] == (
            "shared_public_known_tile_ids_set_equality_only"
        )
        assert contract["errors"] == []
        assert contract["agent_a_known_tile_ids"] == sorted([TILE_A, TILE_SHARED])
        assert contract["agent_b_known_tile_ids"] == sorted([TILE_A, TILE_SHARED])
        assert contract["same_known_tile_ids"] is True
        assert contract["shared_known_tile_ids"] == sorted([TILE_A, TILE_SHARED])
        assert contract["shared_known_tile_count"] == 2
        assert contract["agent_a_only_known_tile_ids"] == []
        assert contract["agent_b_only_known_tile_ids"] == []

    # 2. Different known-tile sets
    def test_different_sets(self):
        merge = _build_merge_with_known([TILE_A, TILE_C], [TILE_A, TILE_B])
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["same_known_tile_ids"] is False
        assert contract["shared_known_tile_ids"] == [TILE_A]
        assert contract["agent_a_only_known_tile_ids"] == [TILE_C]
        assert contract["agent_b_only_known_tile_ids"] == [TILE_B]

    # 3. Partial overlap
    def test_partial_overlap_recomputed(self):
        merge = _build_merge_with_known(
            [TILE_A, TILE_SHARED, TILE_C],
            [TILE_B, TILE_SHARED],
        )
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["same_known_tile_ids"] is False
        assert contract["shared_known_tile_ids"] == [TILE_SHARED]
        assert contract["shared_known_tile_count"] == 1
        assert contract["agent_a_only_known_tile_ids"] == sorted([TILE_A, TILE_C])
        assert contract["agent_a_only_known_tile_count"] == 2
        assert contract["agent_b_only_known_tile_ids"] == [TILE_B]
        assert contract["agent_b_only_known_tile_count"] == 1

    # 4. Disjoint sets
    def test_disjoint_sets(self):
        merge = _build_merge_with_known([TILE_A, TILE_C], [TILE_B, TILE_OTHER])
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["same_known_tile_ids"] is False
        assert contract["shared_known_tile_ids"] == []
        assert contract["agent_a_only_known_tile_ids"] == sorted([TILE_A, TILE_C])
        assert contract["agent_b_only_known_tile_ids"] == sorted([TILE_B, TILE_OTHER])

    # 5. One side missing known_tile_ids
    def test_one_side_missing_known_tile_ids(self):
        merge = _build_merge_with_known([TILE_A], [TILE_B])
        merge["agent_a"].pop("known_tile_ids")
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_known_tile_ids"] == []
        assert contract["agent_b_known_tile_ids"] == [TILE_B]
        assert contract["same_known_tile_ids"] is False

    # 6. One side known_tile_ids is None
    def test_one_side_none_known_tile_ids(self):
        merge = _build_merge_with_known(None, [TILE_B])
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_known_tile_ids"] == []
        assert contract["agent_b_known_tile_ids"] == [TILE_B]
        assert contract["same_known_tile_ids"] is False

    # 7. One side known_tile_ids is not a list
    def test_one_side_non_list_known_tile_ids(self):
        merge = _build_merge_with_known("not-a-list", [TILE_B])
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_known_tile_ids"] == []
        assert contract["agent_b_known_tile_ids"] == [TILE_B]
        assert contract["same_known_tile_ids"] is False

    # 8. Both sides empty -> same_known_tile_ids False
    def test_both_empty_sets_are_not_same_claim(self):
        merge = _build_merge_with_known([], [])
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_known_tile_ids"] == []
        assert contract["agent_b_known_tile_ids"] == []
        assert contract["same_known_tile_ids"] is False
        assert contract["shared_known_tile_ids"] == []

    # 9. Duplicate entries within each bundle are deduplicated
    def test_duplicate_entries_deduped(self):
        merge = _build_merge_with_known(
            [TILE_A, TILE_A, TILE_SHARED, TILE_SHARED],
            [TILE_SHARED, TILE_SHARED, TILE_B, TILE_B],
        )
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["agent_a_known_tile_ids"] == sorted([TILE_A, TILE_SHARED])
        assert contract["agent_b_known_tile_ids"] == sorted([TILE_B, TILE_SHARED])
        assert contract["shared_known_tile_ids"] == [TILE_SHARED]
        assert contract["agent_a_known_tile_count"] == 2
        assert contract["agent_b_known_tile_count"] == 2

    # 10. Order-insensitive equality with deterministic sorted output
    def test_order_insensitive_equality(self):
        merge = _build_merge_with_known(
            [TILE_SHARED, TILE_A, TILE_C],
            [TILE_C, TILE_SHARED, TILE_A],
        )
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["same_known_tile_ids"] is True
        expected = sorted([TILE_A, TILE_C, TILE_SHARED])
        assert contract["agent_a_known_tile_ids"] == expected
        assert contract["agent_b_known_tile_ids"] == expected
        assert contract["shared_known_tile_ids"] == expected

    # 11. Private-marker entries dropped and never exported
    def test_private_marker_entries_dropped(self):
        merge = _build_merge_with_known(
            ["C:\\Users\\Sean\\secret.txt", TILE_A],
            [TILE_A, "/home/user/secret"],
        )
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["agent_a_known_tile_ids"] == [TILE_A]
        assert contract["agent_b_known_tile_ids"] == [TILE_A]
        assert contract["same_known_tile_ids"] is True
        exported = export_shared_known_tile_ids_set_equality_contract(contract)
        assert "C:\\Users\\Sean\\secret.txt" not in exported
        assert "/home/user/secret" not in exported
        assert "[REDACTED" not in exported

    # 12. Root shared_known_tile_ids tampering is ignored as authority
    def test_root_shared_known_tile_ids_tampering_ignored(self):
        merge = _build_merge_with_known([TILE_A, TILE_SHARED], [TILE_B, TILE_SHARED])
        merge["shared_known_tile_ids"] = ["tampered_root_tile"]
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["shared_known_tile_ids"] == [TILE_SHARED]
        assert "tampered_root_tile" not in contract["shared_known_tile_ids"]

    # 13. Root only-list tampering is ignored as authority
    def test_root_only_known_tile_ids_tampering_ignored(self):
        merge = _build_merge_with_known([TILE_A, TILE_SHARED], [TILE_B, TILE_SHARED])
        merge["agent_a_only_known_tile_ids"] = ["tampered_a"]
        merge["agent_b_only_known_tile_ids"] = ["tampered_b"]
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["agent_a_only_known_tile_ids"] == [TILE_A]
        assert contract["agent_b_only_known_tile_ids"] == [TILE_B]
        assert "tampered_a" not in contract["agent_a_only_known_tile_ids"]
        assert "tampered_b" not in contract["agent_b_only_known_tile_ids"]

    # 14. Output has exactly required top-level fields; no forbidden fields
    def test_output_has_exact_fields(self):
        merge = _build_merge_with_known([TILE_A], [TILE_A])
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
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
            "agent_a_known_tile_ids",
            "agent_b_known_tile_ids",
            "agent_a_known_tile_count",
            "agent_b_known_tile_count",
            "same_known_tile_ids",
            "shared_known_tile_ids",
            "shared_known_tile_count",
            "agent_a_only_known_tile_ids",
            "agent_a_only_known_tile_count",
            "agent_b_only_known_tile_ids",
            "agent_b_only_known_tile_count",
            "claim_scope",
            "errors",
        }
        assert sorted(contract.keys()) == sorted(expected_fields)
        forbidden = [
            "same_map_knowledge",
            "same_exploration_history",
            "same_observation_event",
            "same_place",
            "co_presence",
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
            "timing_window",
            "plan",
            "topology",
            "adjacency",
            "pathfinding",
        ]
        for token in forbidden:
            assert token not in contract

    # 15. contract_id deterministic across repeated calls
    def test_contract_id_deterministic(self):
        merge = _build_merge_with_known([TILE_A, TILE_SHARED], [TILE_A, TILE_SHARED])
        c1 = create_shared_known_tile_ids_set_equality_contract(merge)
        c2 = create_shared_known_tile_ids_set_equality_contract(merge)
        assert c1["contract_id"] == c2["contract_id"]
        assert c1["contract_id"] is not None

    # 16. contract_id changes when a bundle known-tile set changes
    def test_contract_id_changes_when_bundle_set_changes(self):
        c1 = create_shared_known_tile_ids_set_equality_contract(
            _build_merge_with_known([TILE_A], [TILE_A])
        )
        c2 = create_shared_known_tile_ids_set_equality_contract(
            _build_merge_with_known([TILE_A], [TILE_B])
        )
        assert c1["same_known_tile_ids"] != c2["same_known_tile_ids"]
        assert c1["contract_id"] != c2["contract_id"]

    # 17. contract_id preserves A/B agent orientation
    def test_contract_id_preserves_ab_orientation(self):
        c1 = create_shared_known_tile_ids_set_equality_contract(
            _build_merge_with_known([TILE_A], [TILE_B])
        )
        c2 = create_shared_known_tile_ids_set_equality_contract(
            _build_merge_with_known([TILE_B], [TILE_A])
        )
        assert c1["contract_id"] != c2["contract_id"]
        assert c1["agent_a_known_tile_ids"] == [TILE_A]
        assert c2["agent_a_known_tile_ids"] == [TILE_B]

    # 18. Input mutation guard
    def test_input_not_mutated(self):
        merge = _build_merge_with_known([TILE_A, TILE_SHARED], [TILE_B, TILE_SHARED])
        original = copy.deepcopy(merge)
        create_shared_known_tile_ids_set_equality_contract(merge)
        assert merge == original

    # 19. Structural failures
    def test_structural_failures(self):
        c = create_shared_known_tile_ids_set_equality_contract("not a dict")
        assert c["ok"] is False
        assert "merge must be a dict" in c["errors"]

        bad_merge = {"ok": False, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_known_tile_ids_set_equality_contract(bad_merge)
        assert c["ok"] is False

        bad_merge = {"ok": True, "merge_type": "wrong",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_known_tile_ids_set_equality_contract(bad_merge)
        assert c["ok"] is False

        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "9X.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_known_tile_ids_set_equality_contract(bad_merge)
        assert c["ok"] is False

        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_b": {}}
        c = create_shared_known_tile_ids_set_equality_contract(bad_merge)
        assert c["ok"] is False

        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {}}
        c = create_shared_known_tile_ids_set_equality_contract(bad_merge)
        assert c["ok"] is False

        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": ""},
                     "agent_b": {"agent_id": ""}}
        c = create_shared_known_tile_ids_set_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id is missing or empty" in c["errors"]

        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": "same_id"},
                     "agent_b": {"agent_id": "same_id"}}
        c = create_shared_known_tile_ids_set_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id and agent_b_id must be distinct" in c["errors"]

    # 20. Stable JSON export / round-trip
    def test_export_stable_json(self):
        merge = _build_merge_with_known([TILE_A, TILE_SHARED], [TILE_A, TILE_SHARED])
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        exported = export_shared_known_tile_ids_set_equality_contract(contract)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == contract["contract_id"]
        exported2 = export_shared_known_tile_ids_set_equality_contract(parsed)
        assert exported == exported2

    # 21. File helper reads and builds from path
    def test_contract_known_tile_ids_set_equality_file(self):
        merge = _build_merge_with_known([TILE_A, TILE_SHARED], [TILE_A, TILE_SHARED])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            result = contract_known_tile_ids_set_equality_file(path)
        assert result["ok"] is True
        assert result["same_known_tile_ids"] is True
        assert result["agent_a_known_tile_ids"] == sorted([TILE_A, TILE_SHARED])

    # 22. All three public functions exercised
    def test_all_public_functions_exercised(self):
        merge = _build_merge_with_known([TILE_A], [TILE_A])
        c1 = create_shared_known_tile_ids_set_equality_contract(merge)
        assert c1["ok"] is True

        exported = export_shared_known_tile_ids_set_equality_contract(c1)
        assert isinstance(exported, str)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == c1["contract_id"]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            c2 = contract_known_tile_ids_set_equality_file(path)
        assert c2["ok"] is True
        assert c2["same_known_tile_ids"] is True


class TestKnownTileIdsSetEqualityBoundaries:
    """Source and boundary cases for 10BL."""

    # 23. Module has no forbidden imports
    def test_module_has_no_forbidden_imports(self):
        source = _module_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                assert not module_name.startswith("backend.world.local_"), (
                    "10BL module must not import local phase modules"
                )
                if module_name.startswith("backend.world."):
                    assert module_name == "backend.world.world_event_sanitizer"
                    assert [alias.name for alias in node.names] == [
                        "sanitize_public_mapping"
                    ]
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("backend."), (
                        "10BL module must not import backend modules directly"
                    )
        assert "world-sim/data" not in source

    # 24. Module source does not call upstream creators
    def test_module_does_not_call_upstream_creators(self):
        source = _module_source()
        prose = _strip_python_prose(source)
        creators = [
            "create_two_agent_public_merge",
            "create_known_map_snapshot",
            "project_public_state",
            "create_route_intent_contract",
        ]
        for creator in creators:
            assert creator not in prose, (
                "10BL module must not call upstream creator: " + creator
            )

    # 25. Happy path contains no forbidden inference tokens
    def test_happy_path_contains_no_forbidden_tokens(self):
        merge = _build_merge_with_known([TILE_A], [TILE_A])
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        exported = export_shared_known_tile_ids_set_equality_contract(contract)
        forbidden_tokens = [
            "same_map_knowledge",
            "same_exploration_history",
            "same_observation_event",
            "same_place",
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
            "destination_tile_id",
            "pathfinding",
            "timing_window",
            "same_route",
            "same_path",
            "same_destination",
            "same_timing",
            "same_plan",
            "exploration_history",
            "map_knowledge",
            "observation_event",
        ]
        lowered = exported.lower()
        for token in forbidden_tokens:
            assert token not in lowered, (
                "forbidden token in exported contract: " + token
            )

    # 26. Non-string and empty entries are dropped after sanitization
    def test_non_string_and_empty_entries_dropped(self):
        merge = _build_merge_with_known(
            [TILE_A, "", None, 123, TILE_A],
            [TILE_A, "", False, {"bad": "value"}],
        )
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["agent_a_known_tile_ids"] == [TILE_A]
        assert contract["agent_b_known_tile_ids"] == [TILE_A]
        assert contract["same_known_tile_ids"] is True

    # 27. Root set algebra can contradict bundle lists without affecting contract
    def test_root_set_algebra_contradiction_ignored(self):
        merge = _build_merge_with_known([TILE_A, TILE_SHARED], [TILE_B, TILE_SHARED])
        merge["shared_known_tile_ids"] = []
        merge["agent_a_only_known_tile_ids"] = [TILE_SHARED, "wrong_a"]
        merge["agent_b_only_known_tile_ids"] = [TILE_SHARED, "wrong_b"]
        contract = create_shared_known_tile_ids_set_equality_contract(merge)
        assert contract["shared_known_tile_ids"] == [TILE_SHARED]
        assert contract["agent_a_only_known_tile_ids"] == [TILE_A]
        assert contract["agent_b_only_known_tile_ids"] == [TILE_B]

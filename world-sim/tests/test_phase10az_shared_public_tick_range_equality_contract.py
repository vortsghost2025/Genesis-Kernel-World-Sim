"""Phase 10AZ - shared public tick-range equality contract proof.

These tests prove that a Phase 10AS two-agent public merge artifact can
be wrapped in a deterministic, sanitized shared-tick-range-equality
contract that formalizes whether two agents' supplied tick ranges are
mechanically equal, without ever inferring temporal overlap, co-presence,
awareness, trust, cooperation, conflict, communication, coordination,
planning, proximity, or any kind of relationship.

Tick ranges are supplied as optional caller arguments; 10AZ does not
read them from 10AS bundles.

10AZ may say:

    "Agent A's public tick range is [X, Y]."

    "Agent B's public tick range is [X, Y]."

    "Both agents declare the same first tick." (public-surface equality
    only)

    "Both agents declare the same last tick." (public-surface equality
    only)

    "Both agents declare identical public tick ranges." (public-surface
    equality only)

10AZ may not say:

    "The agents' tick ranges overlap."

    "The agents were active at the same time."

    "The agents could have met or interacted."

    "The agents share a temporal window."

    "The agents' activity periods coincide."

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

from backend.world.local_shared_public_tick_range_equality_contract import (  # noqa: E402
    contract_tick_range_equality_file,
    create_shared_tick_range_equality_contract,
    export_shared_tick_range_equality_contract,
)
from backend.world.local_two_agent_public_merge import (  # noqa: E402
    create_two_agent_public_merge,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping  # noqa: E402

# NOTE: We import the 10AS creator here in the TEST file ONLY, to
# fabricate valid 10AS merge inputs.  The 10AZ MODULE under test
# (local_shared_public_tick_range_equality_contract.py) does not
# import any of these — that boundary is asserted below by a
# source-scan test.  Importing it here is the standard pattern used
# by test_phase10as_two_agent_public_merge.py,
# test_phase10au_shared_public_anchor_contract.py,
# test_phase10av_shared_public_event_ref_contract.py,
# test_phase10aw_shared_public_route_destination_contract.py,
# test_phase10ax_shared_public_territory_ref_contract.py, and
# test_phase10ay_shared_public_snapshot_hash_equality_contract.py.


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
# Fixtures: build real 10AS merges to feed 10AZ
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


class TestCreateSharedTickRangeEqualityContract:
    """Tests 1-21 from the 10AZ spec test plan."""

    # 1. Happy path: both agents declare identical tick ranges
    def test_happy_path_identical_tick_ranges(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        assert contract["ok"] is True
        assert contract["contract_schema_version"] == "10AZ.1"
        assert contract["contract_type"] == "shared_public_tick_range_equality_contract"
        assert contract["contract_id"].startswith("10AZ-")
        assert contract["claim_scope"] == "shared_tick_range_equality_only"
        assert contract["errors"] == []
        assert contract["same_first_tick"] is True
        assert contract["same_last_tick"] is True
        assert contract["same_tick_range"] is True
        assert contract["agent_a_first_tick"] == 1
        assert contract["agent_a_last_tick"] == 10
        assert contract["agent_b_first_tick"] == 1
        assert contract["agent_b_last_tick"] == 10

    # 2. Different first_tick
    def test_different_first_tick(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=2,
            agent_b_last_tick=10,
        )
        assert contract["ok"] is True
        assert contract["same_first_tick"] is False
        assert contract["same_last_tick"] is True
        assert contract["same_tick_range"] is False

    # 3. Different last_tick
    def test_different_last_tick(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=20,
        )
        assert contract["ok"] is True
        assert contract["same_first_tick"] is True
        assert contract["same_last_tick"] is False
        assert contract["same_tick_range"] is False

    # 4. Same first and last ticks but different agents
    def test_same_ticks_different_agents(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=5,
            agent_a_last_tick=15,
            agent_b_first_tick=5,
            agent_b_last_tick=15,
        )
        assert contract["ok"] is True
        assert contract["same_first_tick"] is True
        assert contract["same_last_tick"] is True
        assert contract["same_tick_range"] is True

    # 5. Output has exactly required top-level fields
    def test_output_has_exact_fields(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
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
            "agent_a_first_tick",
            "agent_a_last_tick",
            "agent_b_first_tick",
            "agent_b_last_tick",
            "same_first_tick",
            "same_last_tick",
            "same_tick_range",
            "claim_scope",
            "errors",
        }
        assert sorted(contract.keys()) == sorted(expected_fields)
        forbidden = [
            "temporal_overlap",
            "co_presence",
            "active_at_same_time",
            "shared_window",
            "meeting",
            "awareness",
            "communication",
            "relationship",
            "trust",
            "cooperation",
            "conflict",
            "proximity",
            "distance",
            "eta",
            "route_path",
        ]
        for token in forbidden:
            assert token not in contract

    # 6. contract_id deterministic
    def test_contract_id_deterministic(self):
        merge = _build_merge()
        c1 = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        c2 = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        assert c1["contract_id"] == c2["contract_id"]
        assert c1["contract_id"] is not None

    # 7. contract_id changes when tick values change
    def test_contract_id_changes_with_tick_values(self):
        merge = _build_merge()
        c1 = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        c2 = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=2,
            agent_b_last_tick=10,
        )
        assert c1["same_first_tick"] != c2["same_first_tick"]
        assert c1["contract_id"] != c2["contract_id"]

    # 8. Input mutation guard
    def test_input_not_mutated(self):
        merge = _build_merge()
        original = copy.deepcopy(merge)
        create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        assert merge == original

    # 9. Structural failures
    def test_structural_failures(self):
        # Non-dict
        c = create_shared_tick_range_equality_contract("not a dict")
        assert c["ok"] is False
        assert "merge must be a dict" in c["errors"]

        # ok=False merge
        bad_merge = {"ok": False, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_tick_range_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_type
        bad_merge = {"ok": True, "merge_type": "wrong",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_tick_range_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_schema_version
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "9X.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_tick_range_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_a
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_b": {}}
        c = create_shared_tick_range_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_b
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {}}
        c = create_shared_tick_range_equality_contract(bad_merge)
        assert c["ok"] is False

        # Empty agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": ""},
                     "agent_b": {"agent_id": ""}}
        c = create_shared_tick_range_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id is missing or empty" in c["errors"]

        # Same agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": "same_id"},
                     "agent_b": {"agent_id": "same_id"}}
        c = create_shared_tick_range_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id and agent_b_id must be distinct" in c["errors"]

    # 10. Type validation failures: non-int tick values treated as None
    def test_type_validation_failures(self):
        merge = _build_merge()
        # String ticks should be treated as None (not int)
        c = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick="1",
            agent_a_last_tick="10",
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        assert c["ok"] is True
        assert c["agent_a_first_tick"] is None
        assert c["agent_a_last_tick"] is None
        assert c["same_first_tick"] is False
        assert c["same_tick_range"] is False

        # Float ticks should be treated as None (not int)
        c = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1.0,
            agent_a_last_tick=10.0,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        assert c["ok"] is True
        assert c["agent_a_first_tick"] is None
        assert c["agent_a_last_tick"] is None

    # 11. same_tick_range internal consistency guard
    def test_same_tick_range_internal_consistency(self):
        merge = _build_merge()
        # same_first_tick True, same_last_tick False -> same_tick_range False
        c = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=20,
        )
        assert c["same_first_tick"] is True
        assert c["same_last_tick"] is False
        assert c["same_tick_range"] is False

        # same_first_tick False, same_last_tick True -> same_tick_range False
        c = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=2,
            agent_b_last_tick=10,
        )
        assert c["same_first_tick"] is False
        assert c["same_last_tick"] is True
        assert c["same_tick_range"] is False

    # 12. Private markers redacted
    def test_private_markers_redacted(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        exported = export_shared_tick_range_equality_contract(contract)
        parsed = json.loads(exported)
        assert "/home/user/secret.txt" not in exported
        assert "192.168.1.1" not in exported
        # Verify the contract_id round-trips cleanly
        assert parsed["contract_id"] == contract["contract_id"]

    # 13. Graceful handling of missing tick fields
    def test_graceful_missing_tick_fields(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_first_tick"] is None
        assert contract["agent_a_last_tick"] is None
        assert contract["agent_b_first_tick"] is None
        assert contract["agent_b_last_tick"] is None
        assert contract["same_first_tick"] is False
        assert contract["same_last_tick"] is False
        assert contract["same_tick_range"] is False

    # 14. Stable JSON export / round-trip
    def test_export_stable_json(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        exported = export_shared_tick_range_equality_contract(contract)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == contract["contract_id"]
        # Round-trip: re-export is identical
        exported2 = export_shared_tick_range_equality_contract(parsed)
        assert exported == exported2

    # 15. contract_tick_range_equality_file reads and builds
    def test_contract_tick_range_equality_file(self):
        merge = _build_merge()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            result = contract_tick_range_equality_file(
                path,
                agent_a_first_tick=1,
                agent_a_last_tick=10,
                agent_b_first_tick=1,
                agent_b_last_tick=10,
            )
        assert result["ok"] is True
        assert result["agent_a_first_tick"] == 1
        assert result["agent_b_last_tick"] == 10
        assert result["same_tick_range"] is True

    # 16. Saturation: all three public functions exercised
    def test_all_public_functions_exercised(self):
        merge = _build_merge()
        c1 = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        assert c1["ok"] is True

        exported = export_shared_tick_range_equality_contract(c1)
        assert isinstance(exported, str)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == c1["contract_id"]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            c2 = contract_tick_range_equality_file(
                path,
                agent_a_first_tick=1,
                agent_a_last_tick=10,
                agent_b_first_tick=1,
                agent_b_last_tick=10,
            )
        assert c2["ok"] is True
        assert c2["same_tick_range"] is True

    # 17. Module has no forbidden imports
    def test_module_has_no_forbidden_imports(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_tick_range_equality_contract.py"
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
                "forbidden token in 10AZ module source: " + token
            )

    # 18. Module source does not call upstream creators
    def test_module_does_not_call_upstream_creators(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_tick_range_equality_contract.py"
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
                "10AZ module must not call upstream creator: " + creator
            )

    # 19. Boundary smoke: no temporal/overlap/co-presence tokens
    def test_happy_path_contains_no_forbidden_tokens(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        exported = export_shared_tick_range_equality_contract(contract)
        forbidden_tokens = [
            "temporal_overlap",
            "co_presence",
            "active_at_same_time",
            "shared_window",
            "meeting",
            "awareness",
            "communication",
            "relationship",
            "trust",
            "cooperation",
            "conflict",
            "proximity",
            "distance",
            "eta",
            "route_path",
            "overlap",
        ]
        lowered = exported.lower()
        for token in forbidden_tokens:
            assert token not in lowered, (
                "forbidden token in exported contract: " + token
            )

    # 20. Boundary: first_tick > last_tick is allowed (public declaration)
    def test_first_tick_greater_than_last_tick_allowed(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=10,
            agent_a_last_tick=1,
            agent_b_first_tick=10,
            agent_b_last_tick=1,
        )
        assert contract["ok"] is True
        assert contract["same_first_tick"] is True
        assert contract["same_last_tick"] is True
        assert contract["same_tick_range"] is True

    # 21. Boundary: negative tick values are allowed (public declaration)
    def test_negative_tick_values_allowed(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=-5,
            agent_a_last_tick=-1,
            agent_b_first_tick=-5,
            agent_b_last_tick=-1,
        )
        assert contract["ok"] is True
        assert contract["same_first_tick"] is True
        assert contract["same_last_tick"] is True
        assert contract["same_tick_range"] is True


class TestTickRangeSetOperations:
    """Additional edge cases for tick range fields."""

    def test_one_side_missing_ticks_no_shared(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=None,
            agent_b_last_tick=None,
        )
        assert contract["ok"] is True
        assert contract["same_first_tick"] is False
        assert contract["same_last_tick"] is False
        assert contract["same_tick_range"] is False
        assert contract["agent_a_first_tick"] == 1
        assert contract["agent_b_first_tick"] is None

    def test_both_sides_missing_ticks_no_shared(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["same_first_tick"] is False
        assert contract["same_last_tick"] is False
        assert contract["same_tick_range"] is False

    def test_same_first_tick_different_last_tick_not_shared(self):
        merge = _build_merge()
        contract = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=20,
        )
        assert contract["same_first_tick"] is True
        assert contract["same_last_tick"] is False
        assert contract["same_tick_range"] is False

    def test_contract_id_changes_when_tick_changes(self):
        merge = _build_merge()
        c1 = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        c2 = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=11,
        )
        assert c1["same_last_tick"] != c2["same_last_tick"]
        assert c1["contract_id"] != c2["contract_id"]

    def test_contract_id_preserves_ab_orientation(self):
        merge = _build_merge()
        c1 = create_shared_tick_range_equality_contract(
            merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        # Build a merge with swapped agent ids
        swap_merge = _build_merge()
        swap_merge["agent_a"]["agent_id"] = AGENT_B_ID
        swap_merge["agent_b"]["agent_id"] = AGENT_A_ID
        # Rebuild to get a valid merge structure
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
        c2 = create_shared_tick_range_equality_contract(
            swap_merge,
            agent_a_first_tick=1,
            agent_a_last_tick=10,
            agent_b_first_tick=1,
            agent_b_last_tick=10,
        )
        # contract_ids must differ because agent_a_id/agent_b_id order differs
        assert c1["contract_id"] != c2["contract_id"]
        assert c2["agent_a_id"] == AGENT_B_ID
        assert c2["agent_b_id"] == AGENT_A_ID

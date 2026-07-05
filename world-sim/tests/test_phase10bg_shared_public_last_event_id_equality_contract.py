"""Phase 10BG - shared public last event id equality contract proof.

These tests prove that a Phase 10AS two-agent public merge artifact can
be wrapped in a deterministic, sanitized shared-public-last-event-id-
equality contract that formalizes whether two agents' public last event
IDs are identical, without ever inferring same event, same time, same
sequence, same interaction, or same relationship.

Last event IDs are supplied as optional caller arguments; 10BG does
not read them from 10AS bundles.  Missing, non-string, or empty-after-
sanitize last event IDs are treated as ``None``.

10BG may say:

    "Agent A's public last_event_id is X."

    "Agent B's public last_event_id is Y."

    "Both agents report the same public last_event_id value."
    (public-surface equality only)

10BG may not say:

    "Both agents experienced the same event." (event-content inference)

    "Both agents were active at the same time." (temporal overlap inference)

    "The agents could have met or interacted." (meeting/interaction inference)

    "The agents have a temporal window in common." (window inference)

    "The agents' last event IDs imply a relationship." (relationship inference)

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

from backend.world.local_shared_public_last_event_id_equality_contract import (  # noqa: E402
    contract_last_event_id_equality_file,
    create_shared_last_event_id_equality_contract,
    export_shared_last_event_id_equality_contract,
)
from backend.world.local_two_agent_public_merge import (  # noqa: E402
    create_two_agent_public_merge,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping  # noqa: E402

# NOTE: We import the 10AS creator here in the TEST file ONLY, to
# fabricate valid 10AS merge inputs.  The 10BG MODULE under test
# (local_shared_public_last_event_id_equality_contract.py) does not
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
# test_phase10bc_shared_public_observation_count_equality_contract.py,
# test_phase10bd_shared_public_movement_count_equality_contract.py,
# test_phase10be_shared_public_accepted_event_count_equality_contract.py, and
# test_phase10bf_shared_public_ignored_event_count_equality_contract.py.


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
# Fixtures: build real 10AS merges to feed 10BG
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


class TestCreateSharedLastEventIdEqualityContract:
    """Tests 1-21 from the 10BG spec test plan."""

    # 1. Happy path: both caller-supplied last event IDs equal
    def test_happy_path_equal_ids(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-adam",
        )
        assert contract["ok"] is True
        assert contract["contract_schema_version"] == "10BG.1"
        assert contract["contract_type"] == "shared_public_last_event_id_equality_contract"
        assert contract["contract_id"].startswith("10BG-")
        assert contract["claim_scope"] == "shared_public_last_event_id_equality_only"
        assert contract["errors"] == []
        assert contract["same_last_event_id"] is True
        assert contract["shared_last_event_id"] == "ev-adam"

    # 2. Different caller-supplied last event IDs
    def test_different_last_event_ids(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-eve",
        )
        assert contract["ok"] is True
        assert contract["same_last_event_id"] is False
        assert contract["shared_last_event_id"] is None
        assert contract["agent_a_last_event_id"] == "ev-adam"
        assert contract["agent_b_last_event_id"] == "ev-eve"

    # 3. One caller-supplied last event ID missing/None
    def test_one_bundle_missing_last_event_id(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id=None,
            agent_b_last_event_id="ev-eve",
        )
        assert contract["ok"] is True
        assert contract["agent_a_last_event_id"] is None
        assert contract["agent_b_last_event_id"] == "ev-eve"
        assert contract["same_last_event_id"] is False
        assert contract["shared_last_event_id"] is None

    # 4. Both caller-supplied last event IDs missing/None
    def test_both_bundles_missing_last_event_id(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id=None,
            agent_b_last_event_id=None,
        )
        assert contract["ok"] is True
        assert contract["agent_a_last_event_id"] is None
        assert contract["agent_b_last_event_id"] is None
        assert contract["same_last_event_id"] is False
        assert contract["shared_last_event_id"] is None

    # 5. Output has exactly required top-level fields; no forbidden fields
    def test_output_has_exact_fields(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-adam",
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
            "agent_a_last_event_id",
            "agent_b_last_event_id",
            "same_last_event_id",
            "shared_last_event_id",
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
        ]
        for token in forbidden:
            assert token not in contract

    # 6. contract_id deterministic
    def test_contract_id_deterministic(self):
        merge = _build_merge()
        c1 = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-adam",
        )
        c2 = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-adam",
        )
        assert c1["contract_id"] == c2["contract_id"]
        assert c1["contract_id"] is not None

    # 7. contract_id changes when last event ID changes
    def test_contract_id_changes_with_id(self):
        merge = _build_merge()
        c1 = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-adam",
        )
        c2 = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-eve",
        )
        assert c1["same_last_event_id"] != c2["same_last_event_id"]
        assert c1["contract_id"] != c2["contract_id"]

    # 8. Input mutation guard
    def test_input_not_mutated(self):
        merge = _build_merge()
        original = copy.deepcopy(merge)
        create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-eve",
        )
        assert merge == original

    # 9. Structural failures: non-dict, ok=False, wrong types, empty ids, same ids
    def test_structural_failures(self):
        # Non-dict
        c = create_shared_last_event_id_equality_contract("not a dict")
        assert c["ok"] is False
        assert "merge must be a dict" in c["errors"]

        # ok=False merge
        bad_merge = {"ok": False, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_last_event_id_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_type
        bad_merge = {"ok": True, "merge_type": "wrong",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_last_event_id_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_schema_version
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "9X.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_last_event_id_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_a
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_b": {}}
        c = create_shared_last_event_id_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_b
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {}}
        c = create_shared_last_event_id_equality_contract(bad_merge)
        assert c["ok"] is False

        # Empty agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": ""},
                     "agent_b": {"agent_id": ""}}
        c = create_shared_last_event_id_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id is missing or empty" in c["errors"]

        # Same agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": "same_id"},
                     "agent_b": {"agent_id": "same_id"}}
        c = create_shared_last_event_id_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id and agent_b_id must be distinct" in c["errors"]

    # 10. Type validation: last_event_id not a string or empty after sanitize
    def test_type_validation_non_string_last_event_id(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id=123,
            agent_b_last_event_id="ev-eve",
        )
        assert contract["ok"] is True
        assert contract["agent_a_last_event_id"] is None
        assert contract["agent_b_last_event_id"] == "ev-eve"
        assert contract["same_last_event_id"] is False
        assert contract["shared_last_event_id"] is None

    # 11. Private markers redacted in exported JSON
    def test_private_markers_redacted(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="/home/user/secret",
            agent_b_last_event_id="/home/user/secret",
        )
        # sanitize_public_mapping redacts private markers, and any
        # sanitized value containing a redaction marker is treated as
        # None so it cannot participate in equality comparisons.
        assert contract["agent_a_last_event_id"] is None
        assert contract["agent_b_last_event_id"] is None
        assert contract["same_last_event_id"] is False
        assert contract["shared_last_event_id"] is None
        exported = export_shared_last_event_id_equality_contract(contract)
        assert "/home/user/secret" not in exported

    # 12. Graceful handling of missing/None last event IDs
    def test_graceful_missing_last_event_ids(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id=None,
            agent_b_last_event_id="ev-eve",
        )
        assert contract["ok"] is True
        assert contract["agent_a_last_event_id"] is None
        assert contract["agent_b_last_event_id"] == "ev-eve"
        assert contract["same_last_event_id"] is False
        assert contract["shared_last_event_id"] is None

    # 13. Stable JSON export / round-trip
    def test_export_stable_json(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-adam",
        )
        exported = export_shared_last_event_id_equality_contract(contract)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == contract["contract_id"]
        # Round-trip: re-export is identical
        exported2 = export_shared_last_event_id_equality_contract(parsed)
        assert exported == exported2

    # 14. contract_last_event_id_equality_file reads and builds
    def test_contract_last_event_id_equality_file(self):
        merge = _build_merge()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            result = contract_last_event_id_equality_file(
                path,
                agent_a_last_event_id="ev-adam",
                agent_b_last_event_id="ev-adam",
            )
        assert result["ok"] is True
        assert result["agent_a_last_event_id"] == "ev-adam"
        assert result["agent_b_last_event_id"] == "ev-adam"

    # 15. All three public functions exercised
    def test_all_public_functions_exercised(self):
        merge = _build_merge()
        c1 = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-adam",
        )
        assert c1["ok"] is True

        exported = export_shared_last_event_id_equality_contract(c1)
        assert isinstance(exported, str)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == c1["contract_id"]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            c2 = contract_last_event_id_equality_file(
                path,
                agent_a_last_event_id="ev-adam",
                agent_b_last_event_id="ev-adam",
            )
        assert c2["ok"] is True
        assert c2["same_last_event_id"] is True

    # 16. Module has no forbidden imports
    def test_module_has_no_forbidden_imports(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_last_event_id_equality_contract.py"
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
                "forbidden token in 10BG module source: " + token
            )

    # 17. Module source does not call upstream creators
    def test_module_does_not_call_upstream_creators(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_last_event_id_equality_contract.py"
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
                "10BG module must not call upstream creator: " + creator
            )

    # 18. Happy path contains no forbidden tokens
    def test_happy_path_contains_no_forbidden_tokens(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-adam",
        )
        exported = export_shared_last_event_id_equality_contract(contract)
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
        ]
        lowered = exported.lower()
        for token in forbidden_tokens:
            assert token not in lowered, (
                "forbidden token in exported contract: " + token
            )


class TestLastEventIdBoundaries:
    """Additional boundary cases for 10BG."""

    # 19. Boundary: private-marker-like last event ID is sanitized/redacted and never leaks
    def test_private_marker_like_last_event_id_never_leaks(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="/home/user/secret",
            agent_b_last_event_id="/home/user/secret",
        )
        # sanitize_public_mapping redacts private markers, and any
        # sanitized value containing a redaction marker is treated as
        # None so it cannot participate in equality comparisons.
        assert contract["agent_a_last_event_id"] is None
        assert contract["agent_b_last_event_id"] is None
        assert contract["same_last_event_id"] is False
        assert contract["shared_last_event_id"] is None
        exported = export_shared_last_event_id_equality_contract(contract)
        assert "/home/user/secret" not in exported

    # 20. Boundary: empty string last event ID treated as None
    def test_empty_string_last_event_id_treated_as_none(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="",
            agent_b_last_event_id="",
        )
        assert contract["ok"] is True
        assert contract["agent_a_last_event_id"] is None
        assert contract["agent_b_last_event_id"] is None
        assert contract["same_last_event_id"] is False
        assert contract["shared_last_event_id"] is None

    # 21. contract_id preserves A/B agent orientation
    def test_contract_id_preserves_ab_orientation(self):
        merge = _build_merge()
        c1 = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-1",
            agent_b_last_event_id="ev-2",
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
        c2 = create_shared_last_event_id_equality_contract(
            swap_merge,
            agent_a_last_event_id="ev-2",
            agent_b_last_event_id="ev-1",
        )
        # contract_ids must differ because agent_a_id/agent_b_id order differs
        assert c1["contract_id"] != c2["contract_id"]
        assert c2["agent_a_id"] == AGENT_B_ID
        assert c2["agent_b_id"] == AGENT_A_ID


class TestLastEventIdScalarOnly:
    """Additional scalar-only boundary cases for 10BG."""

    # 10BG is scalar-only: no lists, no dedup, no set algebra.

    def test_no_list_fields_in_output(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-adam",
        )
        for key, value in contract.items():
            if key in ("errors",):
                continue
            assert not isinstance(value, list), (
                "10BG is scalar-only; field " + key + " must not be a list"
            )

    def test_event_ids_not_present_beyond_id_fields(self):
        merge = _build_merge()
        contract = create_shared_last_event_id_equality_contract(
            merge,
            agent_a_last_event_id="ev-adam",
            agent_b_last_event_id="ev-adam",
        )
        forbidden_fields = [
            "agent_a_last_event_id_count",
            "agent_b_last_event_id_count",
            "shared_last_event_id_count",
        ]
        for field in forbidden_fields:
            assert field not in contract, (
                "10BG is scalar-only; id field " + field + " must not exist"
            )

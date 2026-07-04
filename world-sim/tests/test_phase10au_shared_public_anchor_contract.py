"""Phase 10AU - shared public anchor / reference sharing contract proof.

These tests prove that a Phase 10AS two-agent public merge artifact can
be wrapped in a deterministic, sanitized shared-public-anchor contract
that formalizes which public anchors / references two agents
demonstrably share, without ever inferring private knowledge,
co-presence, awareness, trust, cooperation, conflict, communication, or
any kind of relationship.

10AU may say:

    "These two agents share public anchor / reference IDs X / Y / Z."

    "Both agents cite the same public territory ref T." (a
    public-surface match; no claim of shared private knowledge)

    "Both agents' public surfaces reference the same event ID E."
    (a public-surface match; no claim of shared memory, communication,
    or awareness)

10AU may not say:

    "The agents share private state about these anchors."

    "The agents trust each other's anchor choices."

    "The agents are aware of each other because they cite the same
    anchor."

    "The agents can navigate to each other via shared anchors."

    "The agents' shared anchors imply they met, communicated,
    cooperate, conflict, or have a relationship."

These tests follow the established Genesis discipline: tempdir-only,
no daemon, no scheduler, no provider, no Docker, no network, no live
data, no ``world-sim/data`` access.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(TESTS_ROOT))

from backend.world.local_known_map_snapshot_export import (  # noqa: E402
    create_known_map_snapshot,
)
from backend.world.local_public_state_projector import project_public_state  # noqa: E402
from backend.world.local_route_intent_contract import (  # noqa: E402
    create_route_intent_contract,
)
from backend.world.local_shared_public_anchor_contract import (  # noqa: E402
    contract_shared_anchor_file,
    create_shared_public_anchor_contract,
    export_shared_public_anchor_contract,
)
from backend.world.local_two_agent_public_merge import (  # noqa: E402
    create_two_agent_public_merge,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping  # noqa: E402

# NOTE: We import the 10AS / 10AR / 10AQ / 10AP creators here in the
# TEST file ONLY, to fabricate valid 10AS merge inputs.  The 10AU
# MODULE under test (local_shared_public_anchor_contract.py) does
# not import any of these — that boundary is asserted below by a
# source-scan test.  Importing them here is the standard pattern used
# by test_phase10as_two_agent_public_merge.py and
# test_phase10at_shared_public_observation_contract.py.


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
# Fixtures: build real 10AS merges to feed 10AU
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
    snapshot_id_seed: str = "a",
) -> dict:
    known = sorted(set(observed) | set(visited))
    return {
        "ok": True,
        "snapshot_schema_version": "10AQ.1",
        "snapshot_type": "known_map_snapshot",
        "snapshot_id": "10AQ-" + snapshot_id_seed * 32,
        "source_phase": "10AP",
        "source_projection_hash": snapshot_id_seed * 64,
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
    route_a_dest: str | None = None,
    route_b_dest: str | None = None,
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
        snapshot_id_seed="a",
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=b_current,
        observed=b_obs,
        visited=b_vis,
        snapshot_id_seed="b",
    )

    route_intent_a = None
    route_intent_b = None
    if route_a_dest is not None:
        route_intent_a = create_route_intent_contract(snap_a, route_a_dest)
    if route_b_dest is not None:
        route_intent_b = create_route_intent_contract(snap_b, route_b_dest)

    merge = create_two_agent_public_merge(
        public_a,
        snap_a,
        public_b,
        snap_b,
        route_intent_a=route_intent_a,
        route_intent_b=route_intent_b,
    )
    assert merge["ok"] is True, "fixture merge must be ok=True; got: " + repr(
        merge.get("errors")
    )
    return merge


def _build_merge_with_anchors(
    *,
    a_current: str = TILE_A,
    a_observed: list[str] | None = None,
    a_visited: list[str] | None = None,
    a_anchor_ids: list[str] | None = None,
    b_current: str = TILE_B,
    b_observed: list[str] | None = None,
    b_visited: list[str] | None = None,
    b_anchor_ids: list[str] | None = None,
    route_a_dest: str | None = None,
    route_b_dest: str | None = None,
) -> dict:
    """Build a real 10AS merge and inject public_anchor_ids into bundles."""

    merge = _build_merge(
        a_current=a_current,
        a_observed=a_observed,
        a_visited=a_visited,
        b_current=b_current,
        b_observed=b_observed,
        b_visited=b_visited,
        route_a_dest=route_a_dest,
        route_b_dest=route_b_dest,
    )
    if a_anchor_ids is not None:
        merge["agent_a"]["public_anchor_ids"] = list(a_anchor_ids)
    if b_anchor_ids is not None:
        merge["agent_b"]["public_anchor_ids"] = list(b_anchor_ids)
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
    "shared_public_anchor_ids",
    "shared_public_anchor_count",
    "agent_a_only_anchor_ids",
    "agent_b_only_anchor_ids",
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
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateSharedPublicAnchorContract:
    """Tests 1-19 from the 10AU spec test plan."""

    # 1. Happy path: real 10AS merge with bundle public_anchor_ids
    def test_happy_path_bundle_anchors(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["anchor_a1", "anchor_shared", "anchor_a3"],
            b_anchor_ids=["anchor_b1", "anchor_shared", "anchor_b3"],
        )
        contract = create_shared_public_anchor_contract(merge)
        assert contract["ok"] is True
        assert contract["contract_schema_version"] == "10AU.1"
        assert contract["contract_type"] == "shared_public_anchor_contract"
        assert contract["contract_id"].startswith("10AU-")
        assert contract["claim_scope"] == "shared_public_anchors_only"
        assert contract["errors"] == []

    # 2. Caller-supplied anchor override
    def test_caller_supplied_anchor_override(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["bundle_a"],
            b_anchor_ids=["bundle_b"],
        )
        contract = create_shared_public_anchor_contract(
            merge,
            agent_a_anchor_ids=["caller_a", "shared_x"],
            agent_b_anchor_ids=["caller_b", "shared_x"],
        )
        assert contract["ok"] is True
        assert "shared_x" in contract["shared_public_anchor_ids"]
        assert "bundle_a" not in contract["shared_public_anchor_ids"]
        assert "caller_a" not in contract["shared_public_anchor_ids"]

    # 3. Output has exactly required top-level fields
    def test_output_has_exact_fields(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["a1"],
            b_anchor_ids=["b1"],
        )
        contract = create_shared_public_anchor_contract(merge)
        assert sorted(contract.keys()) == sorted(_REQUIRED_TOP_LEVEL_FIELDS)
        for forbidden in _FORBIDDEN_TOP_LEVEL_FIELDS:
            assert forbidden not in contract

    # 4. same_current_tile and shared_current_tile_id propagated
    def test_current_tile_propagation(self):
        merge = _build_merge(
            a_current=TILE_SHARED,
            b_current=TILE_SHARED,
        )
        merge["agent_a"]["public_anchor_ids"] = ["a1"]
        merge["agent_b"]["public_anchor_ids"] = ["b1"]
        contract = create_shared_public_anchor_contract(merge)
        assert contract["same_current_tile"] is True
        assert contract["shared_current_tile_id"] == TILE_SHARED

    # 5. shared_known_tile_ids and count lifted
    def test_shared_known_tiles_propagation(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["a1"],
            b_anchor_ids=["b1"],
        )
        contract = create_shared_public_anchor_contract(merge)
        assert contract["shared_known_tile_ids"] == merge["shared_known_tile_ids"]
        assert contract["shared_known_tile_count"] == len(
            merge["shared_known_tile_ids"]
        )

    # 6. contract_id deterministic
    def test_contract_id_deterministic(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["a1", "shared_anchor"],
            b_anchor_ids=["b1", "shared_anchor"],
        )
        c1 = create_shared_public_anchor_contract(merge)
        c2 = create_shared_public_anchor_contract(merge)
        assert c1["contract_id"] == c2["contract_id"]
        assert c1["contract_id"] is not None

    # 7. contract_id changes when material changes
    def test_contract_id_changes_with_material(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["a1", "shared_x"],
            b_anchor_ids=["b1", "shared_x"],
        )
        c1 = create_shared_public_anchor_contract(merge)
        merge2 = _build_merge_with_anchors(
            a_anchor_ids=["a1", "shared_x", "extra"],
            b_anchor_ids=["b1", "shared_x", "extra"],
        )
        c2 = create_shared_public_anchor_contract(merge2)
        assert c1["contract_id"] != c2["contract_id"]

    # 8. Input mutation guard
    def test_input_not_mutated(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["a1"],
            b_anchor_ids=["b1"],
        )
        original = copy.deepcopy(merge)
        create_shared_public_anchor_contract(merge)
        assert merge == original

    # 9. Non-dict / ok=False / wrong types / empty ids / same ids
    def test_structural_failures(self):
        # Non-dict
        c = create_shared_public_anchor_contract("not a dict")
        assert c["ok"] is False
        assert "merge must be a dict" in c["errors"]

        # ok=False merge
        bad_merge = {"ok": False, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_public_anchor_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_type
        bad_merge = {"ok": True, "merge_type": "wrong",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_public_anchor_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_schema_version
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "9X.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_public_anchor_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_a
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_b": {}}
        c = create_shared_public_anchor_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_b
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {}}
        c = create_shared_public_anchor_contract(bad_merge)
        assert c["ok"] is False

        # Empty agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": ""},
                     "agent_b": {"agent_id": ""}}
        c = create_shared_public_anchor_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id is missing or empty" in c["errors"]

        # Same agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": "same_id"},
                     "agent_b": {"agent_id": "same_id"}}
        c = create_shared_public_anchor_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id and agent_b_id must be distinct" in c["errors"]

    # 10. shared_known_tile_ids not a list / same_current_tile not bool
    def test_type_validation_failures(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["a1"],
            b_anchor_ids=["b1"],
        )
        merge["shared_known_tile_ids"] = "not a list"
        c = create_shared_public_anchor_contract(merge)
        assert c["ok"] is False

        merge = _build_merge_with_anchors(
            a_anchor_ids=["a1"],
            b_anchor_ids=["b1"],
        )
        merge["same_current_tile"] = "yes"
        c = create_shared_public_anchor_contract(merge)
        assert c["ok"] is False

    # 11. same_current_tile True but bundle current tiles differ
    def test_same_current_tile_internal_consistency_guard(self):
        merge = _build_merge(
            a_current=TILE_A,
            b_current=TILE_B,
        )
        merge["agent_a"]["public_anchor_ids"] = ["a1"]
        merge["agent_b"]["public_anchor_ids"] = ["b1"]
        merge["same_current_tile"] = True
        c = create_shared_public_anchor_contract(merge)
        assert c["ok"] is False
        assert "same_current_tile is True but agent current_tile_ids differ" in c[
            "errors"
        ]

    # 12. Private markers redacted
    def test_private_markers_redacted(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["/home/user/secret.txt", "anchor_shared"],
            b_anchor_ids=["192.168.1.1", "anchor_shared"],
        )
        contract = create_shared_public_anchor_contract(merge)
        exported = export_shared_public_anchor_contract(contract)
        assert "/home/user/secret.txt" not in exported
        assert "192.168.1.1" not in exported
        assert "anchor_shared" in exported

    # 13. Graceful handling of missing public_anchor_ids
    def test_graceful_missing_public_anchor_ids(self):
        merge = _build_merge()  # No public_anchor_ids injected
        # Do NOT inject public_anchor_ids — simulate older 10AS merge
        contract = create_shared_public_anchor_contract(merge)
        assert contract["ok"] is True
        assert contract["shared_public_anchor_ids"] == []
        assert contract["agent_a_only_anchor_ids"] == []
        assert contract["agent_b_only_anchor_ids"] == []
        assert contract["shared_public_anchor_count"] == 0

    # 14. export_shared_public_anchor_contract stable JSON
    def test_export_stable_json(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["anchor1"],
            b_anchor_ids=["anchor1", "anchor2"],
        )
        contract = create_shared_public_anchor_contract(merge)
        exported = export_shared_public_anchor_contract(contract)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == contract["contract_id"]
        # Round-trip: re-export is identical
        exported2 = export_shared_public_anchor_contract(parsed)
        assert exported == exported2

    # 15. contract_shared_anchor_file reads and builds
    def test_contract_shared_anchor_file(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["fa", "shared_anchor"],
            b_anchor_ids=["fb", "shared_anchor"],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            result = contract_shared_anchor_file(path)
        assert result["ok"] is True
        assert result["shared_public_anchor_ids"] == ["shared_anchor"]

    # 16. Saturation: all three public functions exercised
    def test_all_public_functions_exercised(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["a1"],
            b_anchor_ids=["b1"],
        )
        c1 = create_shared_public_anchor_contract(merge)
        assert c1["ok"] is True

        exported = export_shared_public_anchor_contract(c1)
        assert isinstance(exported, str)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == c1["contract_id"]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            c2 = contract_shared_anchor_file(path)
        assert c2["ok"] is True
        assert c2["shared_public_anchor_ids"] == []

    # 17. Boundary scan: no forbidden imports in the 10AU module
    def test_module_has_no_forbidden_imports(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_anchor_contract.py"
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
                "forbidden token in 10AU module source: " + token
            )

    # 18. Module source does not call upstream creators
    def test_module_does_not_call_upstream_creators(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_anchor_contract.py"
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
                "10AU module must not call upstream creator: " + creator
            )

    # 19. Boundary smoke: no relationship/trust/etc tokens in happy path
    def test_happy_path_contains_no_forbidden_tokens(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["anchor_shared"],
            b_anchor_ids=["anchor_shared"],
        )
        contract = create_shared_public_anchor_contract(merge)
        exported = export_shared_public_anchor_contract(contract)
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
        ]
        lowered = exported.lower()
        for token in forbidden_tokens:
            assert token not in lowered, (
                "forbidden token in exported contract: " + token
            )


class TestAnchorSetOperations:
    """Additional set-operation edge cases for anchor fields."""

    def test_empty_anchor_lists_both_sides(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=[],
            b_anchor_ids=[],
        )
        contract = create_shared_public_anchor_contract(merge)
        assert contract["shared_public_anchor_ids"] == []
        assert contract["agent_a_only_anchor_ids"] == []
        assert contract["agent_b_only_anchor_ids"] == []

    def test_no_overlap_between_anchor_sets(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["a1", "a2"],
            b_anchor_ids=["b1", "b2"],
        )
        contract = create_shared_public_anchor_contract(merge)
        assert contract["shared_public_anchor_ids"] == []
        assert set(contract["agent_a_only_anchor_ids"]) == {"a1", "a2"}
        assert set(contract["agent_b_only_anchor_ids"]) == {"b1", "b2"}

    def test_full_overlap_between_anchor_sets(self):
        anchors = ["x", "y", "z"]
        merge = _build_merge_with_anchors(
            a_anchor_ids=list(anchors),
            b_anchor_ids=list(anchors),
        )
        contract = create_shared_public_anchor_contract(merge)
        assert contract["shared_public_anchor_ids"] == sorted(anchors)
        assert contract["agent_a_only_anchor_ids"] == []
        assert contract["agent_b_only_anchor_ids"] == []

    def test_duplicates_in_anchor_lists_deduplicated(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["dup", "dup", "shared_a"],
            b_anchor_ids=["dup", "shared_a"],
        )
        contract = create_shared_public_anchor_contract(merge)
        assert contract["shared_public_anchor_ids"] == ["dup", "shared_a"]
        assert contract["agent_a_only_anchor_ids"] == []
        assert contract["agent_b_only_anchor_ids"] == []

    def test_malformed_anchor_entries_dropped(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["", None, "valid_a", 123],
            b_anchor_ids=["valid_b"],
        )
        contract = create_shared_public_anchor_contract(merge)
        assert contract["shared_public_anchor_ids"] == []
        assert contract["agent_a_only_anchor_ids"] == ["valid_a"]
        assert contract["agent_b_only_anchor_ids"] == ["valid_b"]

    def test_caller_overrides_with_empty_lists(self):
        merge = _build_merge_with_anchors(
            a_anchor_ids=["bundle_a"],
            b_anchor_ids=["bundle_b"],
        )
        contract = create_shared_public_anchor_contract(
            merge,
            agent_a_anchor_ids=[],
            agent_b_anchor_ids=[],
        )
        assert contract["shared_public_anchor_ids"] == []
        assert contract["agent_a_only_anchor_ids"] == []
        assert contract["agent_b_only_anchor_ids"] == []

    def test_contract_id_changes_when_agent_a_only_anchor_ids_change(self):
        merge1 = _build_merge_with_anchors(
            a_anchor_ids=["shared_anchor"],
            b_anchor_ids=["shared_anchor"],
        )
        c1 = create_shared_public_anchor_contract(merge1)

        merge2 = _build_merge_with_anchors(
            a_anchor_ids=["shared_anchor", "a_only"],
            b_anchor_ids=["shared_anchor"],
        )
        c2 = create_shared_public_anchor_contract(merge2)

        assert c1["shared_public_anchor_ids"] == c2["shared_public_anchor_ids"]
        assert c1["agent_b_only_anchor_ids"] == c2["agent_b_only_anchor_ids"]
        assert c1["agent_a_only_anchor_ids"] != c2["agent_a_only_anchor_ids"]
        assert c1["contract_id"] != c2["contract_id"]

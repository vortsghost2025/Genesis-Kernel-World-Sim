"""Phase 10AX - shared public territory ref contract proof.

These tests prove that a Phase 10AS two-agent public merge artifact can
be wrapped in a deterministic, sanitized shared-territory-ref contract
that formalizes which public territory references two agents
demonstrably share, without ever inferring private knowledge,
co-presence, awareness, trust, cooperation, conflict, communication,
temporal overlap, coordination, planning, proximity, or any kind of
relationship.

10AX may say:

    "Both agents publicly cite territory ref T."

    "Both agents' public surfaces reference the same territory ref T."
    (a public-surface match; no claim of shared private knowledge,
    coordination, or awareness)

    "Both agents declare the same public territory ref."
    (a public-surface match; no claim of proximity, co-presence,
    travel timing, or relationship)

10AX may not say:

    "The agents are in the same territory."

    "The agents are aware of each other's territory refs."

    "The agents are coordinating or planning jointly."

    "The agents are or were co-present, nearby, or in the same
    location."

    "The agents' shared territory ref implies they have a
    relationship."

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

from backend.world.local_shared_public_territory_ref_contract import (  # noqa: E402
    contract_territory_ref_file,
    create_shared_territory_ref_contract,
    export_shared_territory_ref_contract,
)
from backend.world.local_two_agent_public_merge import (  # noqa: E402
    create_two_agent_public_merge,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping  # noqa: E402

# NOTE: We import the 10AS creator here in the TEST file ONLY, to
# fabricate valid 10AS merge inputs.  The 10AX MODULE under test
# (local_shared_public_territory_ref_contract.py) does not import any
# of these — that boundary is asserted below by a source-scan test.
# Importing it here is the standard pattern used by
# test_phase10as_two_agent_public_merge.py,
# test_phase10au_shared_public_anchor_contract.py,
# test_phase10av_shared_public_event_ref_contract.py, and
# test_phase10aw_shared_public_route_destination_contract.py.


AGENT_A_ID = "agent_adam"
AGENT_B_ID = "agent_eve"
TILE_A = "tile_start"
TILE_B = "tile_east"
TILE_C = "tile_north"
TILE_SHARED = "tile_central"
TILE_OTHER = "tile_far"
TERR_A = "territory_a"
TERR_B = "territory_b"
TERR_SHARED = "territory_shared"


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
# Fixtures: build real 10AS merges to feed 10AX
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
    "agent_a_territory_ref",
    "agent_b_territory_ref",
    "same_territory_ref",
    "shared_territory_ref",
    "agent_a_only_territory_ref",
    "agent_b_only_territory_ref",
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


class TestCreateSharedTerritoryRefContract:
    """Tests 1-21 from the 10AX spec test plan."""

    # 1. Happy path: caller-supplied territory refs
    def test_happy_path_caller_supplied_territory_refs(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_SHARED,
            agent_b_territory_ref=TERR_SHARED,
        )
        assert contract["ok"] is True
        assert contract["contract_schema_version"] == "10AX.1"
        assert contract["contract_type"] == "shared_territory_ref_contract"
        assert contract["contract_id"].startswith("10AX-")
        assert contract["claim_scope"] == "shared_territory_refs_only"
        assert contract["errors"] == []
        assert contract["same_territory_ref"] is True
        assert contract["shared_territory_ref"] == TERR_SHARED

    # 2. Caller-supplied territory-ref override
    def test_caller_supplied_territory_ref_override(self):
        merge = _build_merge()
        # Inject bundle territory refs to prove they are overridden
        merge["agent_a"]["territory_ref"] = "bundle_a_terr"
        merge["agent_b"]["territory_ref"] = "bundle_b_terr"
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref="caller_a_terr",
            agent_b_territory_ref="caller_b_terr",
        )
        assert contract["ok"] is True
        assert contract["agent_a_territory_ref"] == "caller_a_terr"
        assert contract["agent_b_territory_ref"] == "caller_b_terr"
        assert "bundle_a_terr" not in contract["agent_a_territory_ref"]
        assert "bundle_b_terr" not in contract["agent_b_territory_ref"]

    # 3. Output has exactly required top-level fields
    def test_output_has_exact_fields(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_A,
            agent_b_territory_ref=TERR_B,
        )
        assert sorted(contract.keys()) == sorted(_REQUIRED_TOP_LEVEL_FIELDS)
        for forbidden in _FORBIDDEN_TOP_LEVEL_FIELDS:
            assert forbidden not in contract

    # 4. same_current_tile and shared_current_tile_id propagated
    def test_current_tile_propagation(self):
        merge = _build_merge(
            a_current=TILE_SHARED,
            b_current=TILE_SHARED,
        )
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_A,
            agent_b_territory_ref=TERR_B,
        )
        assert contract["same_current_tile"] is True
        assert contract["shared_current_tile_id"] == TILE_SHARED

    # 5. shared_known_tile_ids and count lifted
    def test_shared_known_tiles_propagation(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_A,
            agent_b_territory_ref=TERR_B,
        )
        assert contract["shared_known_tile_ids"] == merge["shared_known_tile_ids"]
        assert contract["shared_known_tile_count"] == len(
            merge["shared_known_tile_ids"]
        )

    # 6. same_territory_ref and shared_territory_ref when both same non-empty
    def test_same_territory_ref_populates_shared(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_SHARED,
            agent_b_territory_ref=TERR_SHARED,
        )
        assert contract["same_territory_ref"] is True
        assert contract["shared_territory_ref"] == TERR_SHARED

    # 7. agent_a_only / agent_b_only when only one has a territory ref
    def test_only_one_agent_has_territory_ref(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_A,
            agent_b_territory_ref=None,
        )
        assert contract["same_territory_ref"] is False
        assert contract["shared_territory_ref"] is None
        assert contract["agent_a_only_territory_ref"] == TERR_A
        assert contract["agent_b_only_territory_ref"] is None

        merge2 = _build_merge()
        contract2 = create_shared_territory_ref_contract(
            merge2,
            agent_a_territory_ref=None,
            agent_b_territory_ref=TERR_B,
        )
        assert contract2["agent_a_only_territory_ref"] is None
        assert contract2["agent_b_only_territory_ref"] == TERR_B

    # 8. contract_id deterministic
    def test_contract_id_deterministic(self):
        merge = _build_merge()
        c1 = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_SHARED,
            agent_b_territory_ref=TERR_SHARED,
        )
        c2 = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_SHARED,
            agent_b_territory_ref=TERR_SHARED,
        )
        assert c1["contract_id"] == c2["contract_id"]
        assert c1["contract_id"] is not None

    # 9. contract_id changes when territory ref changes
    def test_contract_id_changes_with_territory_ref(self):
        merge = _build_merge()
        c1 = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_SHARED,
            agent_b_territory_ref=TERR_SHARED,
        )
        merge2 = _build_merge()
        c2 = create_shared_territory_ref_contract(
            merge2,
            agent_a_territory_ref=TERR_A,
            agent_b_territory_ref=TERR_SHARED,
        )
        assert c1["contract_id"] != c2["contract_id"]

    # 10. Input mutation guard
    def test_input_not_mutated(self):
        merge = _build_merge()
        original = copy.deepcopy(merge)
        create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_A,
            agent_b_territory_ref=TERR_B,
        )
        assert merge == original

    # 11. Non-dict / ok=False / wrong types / empty ids / same ids
    def test_structural_failures(self):
        # Non-dict
        c = create_shared_territory_ref_contract("not a dict")
        assert c["ok"] is False
        assert "merge must be a dict" in c["errors"]

        # ok=False merge
        bad_merge = {"ok": False, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_territory_ref_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_type
        bad_merge = {"ok": True, "merge_type": "wrong",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_territory_ref_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_schema_version
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "9X.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_territory_ref_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_a
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_b": {}}
        c = create_shared_territory_ref_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_b
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {}}
        c = create_shared_territory_ref_contract(bad_merge)
        assert c["ok"] is False

        # Empty agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": ""},
                     "agent_b": {"agent_id": ""}}
        c = create_shared_territory_ref_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id is missing or empty" in c["errors"]

        # Same agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": "same_id"},
                     "agent_b": {"agent_id": "same_id"}}
        c = create_shared_territory_ref_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id and agent_b_id must be distinct" in c["errors"]

    # 12. shared_known_tile_ids not a list / same_current_tile not bool
    def test_type_validation_failures(self):
        merge = _build_merge()
        merge["shared_known_tile_ids"] = "not a list"
        c = create_shared_territory_ref_contract(merge)
        assert c["ok"] is False

        merge = _build_merge()
        merge["same_current_tile"] = "yes"
        c = create_shared_territory_ref_contract(merge)
        assert c["ok"] is False

    # 13. same_current_tile True but bundle current tiles differ
    def test_same_current_tile_internal_consistency_guard(self):
        merge = _build_merge(
            a_current=TILE_A,
            b_current=TILE_B,
        )
        merge["same_current_tile"] = True
        c = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_A,
            agent_b_territory_ref=TERR_B,
        )
        assert c["ok"] is False
        assert "same_current_tile is True but agent current_tile_ids differ" in c[
            "errors"
        ]

    # 14. Private markers redacted
    def test_private_markers_redacted(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref="/home/user/secret.txt",
            agent_b_territory_ref="192.168.1.1",
        )
        exported = export_shared_territory_ref_contract(contract)
        assert "/home/user/secret.txt" not in exported
        assert "192.168.1.1" not in exported

    # 15. Graceful handling of missing territory refs
    def test_graceful_missing_territory_refs(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_territory_ref"] is None
        assert contract["agent_b_territory_ref"] is None
        assert contract["same_territory_ref"] is False
        assert contract["shared_territory_ref"] is None
        assert contract["agent_a_only_territory_ref"] is None
        assert contract["agent_b_only_territory_ref"] is None

    # 16. export_shared_territory_ref_contract stable JSON
    def test_export_stable_json(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_SHARED,
            agent_b_territory_ref=TERR_SHARED,
        )
        exported = export_shared_territory_ref_contract(contract)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == contract["contract_id"]
        # Round-trip: re-export is identical
        exported2 = export_shared_territory_ref_contract(parsed)
        assert exported == exported2

    # 17. contract_territory_ref_file reads and builds
    def test_contract_territory_ref_file(self):
        merge = _build_merge()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            result = contract_territory_ref_file(path)
        assert result["ok"] is True
        assert result["agent_a_territory_ref"] is None
        assert result["agent_b_territory_ref"] is None

    # 18. Saturation: all three public functions exercised
    def test_all_public_functions_exercised(self):
        merge = _build_merge()
        c1 = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_A,
            agent_b_territory_ref=TERR_B,
        )
        assert c1["ok"] is True

        exported = export_shared_territory_ref_contract(c1)
        assert isinstance(exported, str)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == c1["contract_id"]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            c2 = contract_territory_ref_file(path)
        assert c2["ok"] is True
        assert c2["agent_a_territory_ref"] is None

    # 19. Boundary scan: no forbidden imports in the 10AX module
    def test_module_has_no_forbidden_imports(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_territory_ref_contract.py"
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
                "forbidden token in 10AX module source: " + token
            )

    # 20. Module source does not call upstream creators
    def test_module_does_not_call_upstream_creators(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_territory_ref_contract.py"
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
                "10AX module must not call upstream creator: " + creator
            )

    # 21. Boundary smoke: no relationship/trust/etc tokens in happy path
    def test_happy_path_contains_no_forbidden_tokens(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_SHARED,
            agent_b_territory_ref=TERR_SHARED,
        )
        exported = export_shared_territory_ref_contract(contract)
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


class TestTerritoryRefSetOperations:
    """Additional set-operation edge cases for territory ref fields."""

    def test_both_same_non_empty_populates_shared(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_SHARED,
            agent_b_territory_ref=TERR_SHARED,
        )
        assert contract["same_territory_ref"] is True
        assert contract["shared_territory_ref"] == TERR_SHARED

    def test_both_non_empty_different_no_shared(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_A,
            agent_b_territory_ref=TERR_B,
        )
        assert contract["same_territory_ref"] is False
        assert contract["shared_territory_ref"] is None

    def test_one_empty_no_shared(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref=TERR_SHARED,
            agent_b_territory_ref="",
        )
        assert contract["same_territory_ref"] is False
        assert contract["shared_territory_ref"] is None
        assert contract["agent_a_only_territory_ref"] == TERR_SHARED
        assert contract["agent_b_only_territory_ref"] is None

    def test_both_empty_no_shared(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref="",
            agent_b_territory_ref="",
        )
        assert contract["same_territory_ref"] is False
        assert contract["shared_territory_ref"] is None
        assert contract["agent_a_only_territory_ref"] is None
        assert contract["agent_b_only_territory_ref"] is None

    def test_caller_override_non_empty_treated_as_known(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref="caller_terr",
            agent_b_territory_ref="caller_terr",
        )
        assert contract["agent_a_territory_ref"] == "caller_terr"
        assert contract["agent_b_territory_ref"] == "caller_terr"
        assert contract["same_territory_ref"] is True
        assert contract["shared_territory_ref"] == "caller_terr"

    def test_caller_override_empty_string_not_treated_as_known(self):
        merge = _build_merge()
        contract = create_shared_territory_ref_contract(
            merge,
            agent_a_territory_ref="",
            agent_b_territory_ref="",
        )
        assert contract["agent_a_territory_ref"] is None
        assert contract["agent_b_territory_ref"] is None
        assert contract["same_territory_ref"] is False

    def test_contract_id_changes_when_territory_ref_changes(self):
        merge1 = _build_merge()
        c1 = create_shared_territory_ref_contract(
            merge1,
            agent_a_territory_ref=TERR_A,
            agent_b_territory_ref=TERR_A,
        )

        merge2 = _build_merge()
        c2 = create_shared_territory_ref_contract(
            merge2,
            agent_a_territory_ref=TERR_A,
            agent_b_territory_ref=TERR_B,
        )

        assert c1["shared_territory_ref"] != c2["shared_territory_ref"]
        assert c1["contract_id"] != c2["contract_id"]

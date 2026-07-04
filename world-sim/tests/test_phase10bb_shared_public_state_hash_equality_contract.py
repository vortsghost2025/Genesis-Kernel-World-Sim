"""Phase 10BB - shared public state hash equality contract proof.

These tests prove that a Phase 10AS two-agent public merge artifact can
be wrapped in a deterministic, sanitized shared-public-state-hash-equality
contract that formalizes whether two agents' public state hash strings are
identical, without ever inferring same state, temporal overlap, co-presence,
awareness, trust, cooperation, conflict, communication, coordination,
planning, proximity, or any kind of relationship.

Public state hashes are supplied as optional caller arguments; 10BB does
not read them from 10AS bundles.  Caller-supplied public state hashes are
sanitized through `sanitize_public_mapping` first; empty strings and
non-string items are then dropped; redacted sanitizer output participates
in comparison if non-empty.

10BB may say:

    "Agent A's public state hash is X."

    "Agent B's public state hash is Y."

    "Both agents declare the same public state hash string."
    (public-surface equality only)

10BB may not say:

    "The agents' public state contents are identical." (state inference)

    "The agents were active at the same time." (co-presence inference)

    "The agents could have met or interacted." (meeting/interaction inference)

    "The agents have a temporal window in common." (window inference)

    "The agents' public state hashes imply a relationship." (relationship inference)

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

from backend.world.local_shared_public_state_hash_equality_contract import (  # noqa: E402
    contract_public_state_hash_equality_file,
    create_shared_public_state_hash_equality_contract,
    export_shared_public_state_hash_equality_contract,
)
from backend.world.local_two_agent_public_merge import (  # noqa: E402
    create_two_agent_public_merge,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping  # noqa: E402

# NOTE: We import the 10AS creator here in the TEST file ONLY, to
# fabricate valid 10AS merge inputs.  The 10BB MODULE under test
# (local_shared_public_state_hash_equality_contract.py) does not
# import any of these — that boundary is asserted below by a
# source-scan test.  Importing it here is the standard pattern used
# by test_phase10as_two_agent_public_merge.py,
# test_phase10au_shared_public_anchor_contract.py,
# test_phase10av_shared_public_event_ref_contract.py,
# test_phase10aw_shared_public_route_destination_contract.py,
# test_phase10ax_shared_public_territory_ref_contract.py,
# test_phase10ay_shared_public_snapshot_hash_equality_contract.py,
# test_phase10az_shared_public_tick_range_equality_contract.py, and
# test_phase10ba_shared_public_tick_label_contract.py.


AGENT_A_ID = "agent_adam"
AGENT_B_ID = "agent_eve"
TILE_A = "tile_start"
TILE_B = "tile_east"
TILE_C = "tile_north"
TILE_SHARED = "tile_central"
TILE_OTHER = "tile_far"
STATE_HASH_A = "a" * 64
STATE_HASH_B = "b" * 64
STATE_HASH_SHARED = "s" * 64


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
# Fixtures: build real 10AS merges to feed 10BB
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


class TestCreateSharedPublicStateHashEqualityContract:
    """Tests 1-21 from the 10BB spec test plan."""

    # 1. Happy path: both hashes identical
    def test_happy_path_equal_hashes(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_SHARED,
            agent_b_public_state_hash=STATE_HASH_SHARED,
        )
        assert contract["ok"] is True
        assert contract["contract_schema_version"] == "10BB.1"
        assert contract["contract_type"] == "shared_public_state_hash_equality_contract"
        assert contract["contract_id"].startswith("10BB-")
        assert contract["claim_scope"] == "shared_public_state_hash_equality_only"
        assert contract["errors"] == []
        assert contract["same_public_state_hash"] is True
        assert contract["shared_public_state_hash"] == STATE_HASH_SHARED

    # 2. Different public state hashes
    def test_different_public_state_hashes(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_A,
            agent_b_public_state_hash=STATE_HASH_B,
        )
        assert contract["ok"] is True
        assert contract["same_public_state_hash"] is False
        assert contract["shared_public_state_hash"] is None
        assert contract["agent_a_public_state_hash"] == STATE_HASH_A
        assert contract["agent_b_public_state_hash"] == STATE_HASH_B

    # 3. Output has exactly required top-level fields
    def test_output_has_exact_fields(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_A,
            agent_b_public_state_hash=STATE_HASH_A,
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
            "agent_a_public_state_hash",
            "agent_b_public_state_hash",
            "same_public_state_hash",
            "shared_public_state_hash",
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

    # 4. Public state hashes propagated correctly
    def test_public_state_hashes_propagated(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_A,
            agent_b_public_state_hash=STATE_HASH_B,
        )
        assert contract["agent_a_public_state_hash"] == STATE_HASH_A
        assert contract["agent_b_public_state_hash"] == STATE_HASH_B

    # 5. contract_id deterministic
    def test_contract_id_deterministic(self):
        merge = _build_merge()
        c1 = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_SHARED,
            agent_b_public_state_hash=STATE_HASH_SHARED,
        )
        c2 = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_SHARED,
            agent_b_public_state_hash=STATE_HASH_SHARED,
        )
        assert c1["contract_id"] == c2["contract_id"]
        assert c1["contract_id"] is not None

    # 6. contract_id changes when hash changes
    def test_contract_id_changes_with_hash(self):
        merge = _build_merge()
        c1 = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_A,
            agent_b_public_state_hash=STATE_HASH_A,
        )
        c2 = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_A,
            agent_b_public_state_hash=STATE_HASH_B,
        )
        assert c1["same_public_state_hash"] != c2["same_public_state_hash"]
        assert c1["contract_id"] != c2["contract_id"]

    # 7. Input mutation guard
    def test_input_not_mutated(self):
        merge = _build_merge()
        original = copy.deepcopy(merge)
        create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_A,
            agent_b_public_state_hash=STATE_HASH_B,
        )
        assert merge == original

    # 8. Non-dict / ok=False / wrong types / empty ids / same ids
    def test_structural_failures(self):
        # Non-dict
        c = create_shared_public_state_hash_equality_contract("not a dict")
        assert c["ok"] is False
        assert "merge must be a dict" in c["errors"]

        # ok=False merge
        bad_merge = {"ok": False, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_public_state_hash_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_type
        bad_merge = {"ok": True, "merge_type": "wrong",
                     "merge_schema_version": "10AS.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_public_state_hash_equality_contract(bad_merge)
        assert c["ok"] is False

        # Wrong merge_schema_version
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "9X.1", "agent_a": {},
                     "agent_b": {}}
        c = create_shared_public_state_hash_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_a
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_b": {}}
        c = create_shared_public_state_hash_equality_contract(bad_merge)
        assert c["ok"] is False

        # Missing agent_b
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1", "agent_a": {}}
        c = create_shared_public_state_hash_equality_contract(bad_merge)
        assert c["ok"] is False

        # Empty agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": ""},
                     "agent_b": {"agent_id": ""}}
        c = create_shared_public_state_hash_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id is missing or empty" in c["errors"]

        # Same agent ids
        bad_merge = {"ok": True, "merge_type": "two_agent_public_merge",
                     "merge_schema_version": "10AS.1",
                     "agent_a": {"agent_id": "same_id"},
                     "agent_b": {"agent_id": "same_id"}}
        c = create_shared_public_state_hash_equality_contract(bad_merge)
        assert c["ok"] is False
        assert "agent_a_id and agent_b_id must be distinct" in c["errors"]

    # 9. Private markers redacted in exported JSON
    def test_private_markers_redacted(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash="/home/user/secret.txt",
            agent_b_public_state_hash="192.168.1.1",
        )
        exported = export_shared_public_state_hash_equality_contract(contract)
        assert "/home/user/secret.txt" not in exported
        assert "192.168.1.1" not in exported

    # 10. Graceful handling of missing/None public state hashes
    def test_graceful_missing_hashes(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(merge)
        assert contract["ok"] is True
        assert contract["agent_a_public_state_hash"] is None
        assert contract["agent_b_public_state_hash"] is None
        assert contract["same_public_state_hash"] is False
        assert contract["shared_public_state_hash"] is None

    # 11. Graceful handling of empty string hashes
    def test_graceful_empty_string_hashes(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash="",
            agent_b_public_state_hash="",
        )
        assert contract["ok"] is True
        assert contract["agent_a_public_state_hash"] is None
        assert contract["agent_b_public_state_hash"] is None
        assert contract["same_public_state_hash"] is False
        assert contract["shared_public_state_hash"] is None

    # 12. Non-string hashes treated as None
    def test_non_string_hashes_treated_as_none(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=42,
            agent_b_public_state_hash=None,
        )
        assert contract["ok"] is True
        assert contract["agent_a_public_state_hash"] is None
        assert contract["agent_b_public_state_hash"] is None
        assert contract["same_public_state_hash"] is False
        assert contract["shared_public_state_hash"] is None

    # 13. One empty hash, one valid
    def test_one_empty_one_valid_hash(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_A,
            agent_b_public_state_hash="",
        )
        assert contract["ok"] is True
        assert contract["same_public_state_hash"] is False
        assert contract["shared_public_state_hash"] is None

    # 14. Sanitization: path/IP markers redacted but kept in comparison
    def test_sanitization_redacts_path_and_ip_markers(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash="/home/user/secret.txt",
            agent_b_public_state_hash="/home/user/secret.txt",
        )
        assert contract["ok"] is True
        exported = export_shared_public_state_hash_equality_contract(contract)
        assert "/home/user/secret.txt" not in exported
        # Both sanitized to the same redacted form, so equality holds
        assert contract["same_public_state_hash"] is True
        assert contract["shared_public_state_hash"] is not None

    # 15. Sanitization: IP markers redacted but kept in comparison
    def test_sanitization_redacts_ip_markers(self):
        merge = _build_merge()
        # Both IPs redact to [REDACTED_RUNTIME]; equality should hold
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash="192.168.1.1",
            agent_b_public_state_hash="10.0.0.1",
        )
        assert contract["ok"] is True
        exported = export_shared_public_state_hash_equality_contract(contract)
        assert "192.168.1.1" not in exported
        assert "10.0.0.1" not in exported
        assert contract["same_public_state_hash"] is True
        assert contract["shared_public_state_hash"] is not None

    # 16. Sanitization: different inputs that sanitize to same form
    def test_different_inputs_sanitize_to_same(self):
        merge = _build_merge()
        # Windows paths with different suffixes both redact to [REDACTED_PATH]
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash="C:\\path\\a",
            agent_b_public_state_hash="C:\\path\\b",
        )
        assert contract["ok"] is True
        assert contract["same_public_state_hash"] is True
        assert contract["shared_public_state_hash"] is not None

    # 17. Stable JSON export / round-trip
    def test_export_stable_json(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_SHARED,
            agent_b_public_state_hash=STATE_HASH_SHARED,
        )
        exported = export_shared_public_state_hash_equality_contract(contract)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == contract["contract_id"]
        # Round-trip: re-export is identical
        exported2 = export_shared_public_state_hash_equality_contract(parsed)
        assert exported == exported2

    # 18. contract_public_state_hash_equality_file reads and builds
    def test_contract_public_state_hash_equality_file(self):
        merge = _build_merge()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            result = contract_public_state_hash_equality_file(
                path,
                agent_a_public_state_hash="ha",
                agent_b_public_state_hash="hb",
            )
        assert result["ok"] is True
        assert result["agent_a_public_state_hash"] == "ha"
        assert result["agent_b_public_state_hash"] == "hb"

    # 19. Saturation: all three public functions exercised
    def test_all_public_functions_exercised(self):
        merge = _build_merge()
        c1 = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_SHARED,
            agent_b_public_state_hash=STATE_HASH_SHARED,
        )
        assert c1["ok"] is True

        exported = export_shared_public_state_hash_equality_contract(c1)
        assert isinstance(exported, str)
        parsed = json.loads(exported)
        assert parsed["contract_id"] == c1["contract_id"]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "merge.json"
            path.write_text(json.dumps(merge), encoding="utf-8")
            c2 = contract_public_state_hash_equality_file(
                path,
                agent_a_public_state_hash=STATE_HASH_SHARED,
                agent_b_public_state_hash=STATE_HASH_SHARED,
            )
        assert c2["ok"] is True
        assert c2["same_public_state_hash"] is True

    # 20. Boundary scan: no forbidden imports in the 10BB module
    def test_module_has_no_forbidden_imports(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_state_hash_equality_contract.py"
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
                "forbidden token in 10BB module source: " + token
            )

    # 21. Module source does not call upstream creators
    def test_module_does_not_call_upstream_creators(self):
        module_path = (
            PROJECT_ROOT
            / "backend"
            / "world"
            / "local_shared_public_state_hash_equality_contract.py"
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
                "10BB module must not call upstream creator: " + creator
            )

    # 22. Boundary smoke: no relationship/trust/etc tokens in happy path
    def test_happy_path_contains_no_forbidden_tokens(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_SHARED,
            agent_b_public_state_hash=STATE_HASH_SHARED,
        )
        exported = export_shared_public_state_hash_equality_contract(contract)
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
            "same_state",
            "meeting",
            "interaction",
        ]
        lowered = exported.lower()
        for token in forbidden_tokens:
            assert token not in lowered, (
                "forbidden token in exported contract: " + token
            )


class TestPublicStateHashScalarOnly:
    """Additional scalar-only boundary cases for 10BB."""

    # 10BB is scalar-only: no lists, no dedup, no set algebra, no
    # agent_a_only/agent_b_only fields.

    def test_no_list_fields_in_output(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_A,
            agent_b_public_state_hash=STATE_HASH_B,
        )
        for key, value in contract.items():
            if key in ("errors",):
                continue
            assert not isinstance(value, list), (
                "10BB is scalar-only; field " + key + " must not be a list"
            )

    def test_no_dedup_or_set_algebra_fields(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_A,
            agent_b_public_state_hash=STATE_HASH_B,
        )
        forbidden_fields = [
            "agent_a_only_public_state_hash",
            "agent_b_only_public_state_hash",
            "agent_a_only_public_state_hash_count",
            "agent_b_only_public_state_hash_count",
            "shared_public_state_hash_count",
        ]
        for field in forbidden_fields:
            assert field not in contract, (
                "10BB is scalar-only; field " + field + " must not exist"
            )

    def test_contract_id_preserves_ab_orientation(self):
        merge = _build_merge()
        c1 = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_SHARED,
            agent_b_public_state_hash=STATE_HASH_SHARED,
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
        c2 = create_shared_public_state_hash_equality_contract(
            swap_merge,
            agent_a_public_state_hash=STATE_HASH_SHARED,
            agent_b_public_state_hash=STATE_HASH_SHARED,
        )
        # contract_ids must differ because agent_a_id/agent_b_id order differs
        assert c1["contract_id"] != c2["contract_id"]
        assert c2["agent_a_id"] == AGENT_B_ID
        assert c2["agent_b_id"] == AGENT_A_ID

    def test_empty_string_hash_becomes_none(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash="   ",
            agent_b_public_state_hash="",
        )
        assert contract["ok"] is True
        assert contract["agent_a_public_state_hash"] is None
        assert contract["agent_b_public_state_hash"] is None
        assert contract["same_public_state_hash"] is False

    def test_redacted_non_empty_participates_in_comparison(self):
        merge = _build_merge()
        # Both Windows paths redact to [REDACTED_PATH]; equality should hold
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash="C:\\path\\a",
            agent_b_public_state_hash="C:\\path\\b",
        )
        assert contract["ok"] is True
        assert contract["same_public_state_hash"] is True
        assert contract["shared_public_state_hash"] is not None
        exported = export_shared_public_state_hash_equality_contract(contract)
        assert "C:\\path\\a" not in exported
        assert "C:\\path\\b" not in exported

    def test_counts_not_present(self):
        merge = _build_merge()
        contract = create_shared_public_state_hash_equality_contract(
            merge,
            agent_a_public_state_hash=STATE_HASH_A,
            agent_b_public_state_hash=STATE_HASH_B,
        )
        forbidden_fields = [
            "agent_a_public_state_hash_count",
            "agent_b_public_state_hash_count",
            "shared_public_state_hash_count",
        ]
        for field in forbidden_fields:
            assert field not in contract, (
                "10BB is scalar-only; count field " + field + " must not exist"
            )

"""Phase 10AS - two-agent public merge proof.

These tests prove that two agents' already-public surfaces (10AP
public_state, 10AQ known_map_snapshot, optional 10AR route_intent)
can be combined into a deterministic, sanitized comparison artifact
without inferring meeting, trust, communication, relationship,
cooperation, conflict, awareness, movement, or adjacency.

10AS may say:

    "These two public surfaces overlap on tiles X/Y/Z."

10AS may not say:

    "The agents know each other, met, communicated, trust each other,
     cooperate, conflict, are aware of each other, or can travel
     between those tiles."
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(TESTS_ROOT))

from backend.world.local_known_map_snapshot_export import (  # noqa: E402
    create_known_map_snapshot,
    export_known_map_snapshot,
)
from backend.world.local_public_state_projector import project_public_state  # noqa: E402
from backend.world.local_route_intent_contract import (  # noqa: E402
    create_route_intent_contract,
    export_route_intent_contract,
)
from backend.world.local_two_agent_public_merge import (  # noqa: E402
    create_two_agent_public_merge,
    export_two_agent_public_merge,
    merge_public_surface_files,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping  # noqa: E402

from test_phase10am_bounded_heartbeat_sequence import (  # noqa: E402
    AGENT_ID,
    _empty_known_map,
    _start_position,
)

TENAM = importlib.import_module("test_phase10am_bounded_heartbeat_sequence")
_MAKE_SOURCE_MAP = getattr(TENAM, "_make_" + "true" + "_map")

AGENT_A_ID = "agent_adam"
AGENT_B_ID = "agent_eve"
TILE_A = "tile_start"
TILE_B = "tile_east"
TILE_C = "tile_north"
TILE_SHARED = "tile_central"


# ---------------------------------------------------------------------------
# Fixtures
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


def _route_intent_dict(
    snapshot: dict,
    *,
    destination_tile_id: str,
    reason: str | None = None,
) -> dict:
    intent = create_route_intent_contract(
        snapshot, destination_tile_id, reason=reason
    )
    return intent


def _route_intent_for_other_agent(
    *,
    agent_id: str,
    snapshot_id: str,
    current_tile_id: str,
    destination_tile_id: str,
    destination_known: bool = True,
) -> dict:
    # Constructed directly with mismatched fields for negative test cases.
    return {
        "ok": True,
        "intent_schema_version": "10AR.1",
        "intent_type": "route_intent_contract",
        "intent_id": "10AR-" + "f" * 32,
        "source_phase": "10AQ",
        "source_snapshot_id": snapshot_id,
        "source_snapshot_hash": "c" * 64,
        "agent_id": agent_id,
        "from_tile_id": current_tile_id,
        "destination_tile_id": destination_tile_id,
        "destination_known": destination_known,
        "claim_scope": "intent_only",
        "reason": None,
        "errors": [],
    }


_REQUIRED_TOP_LEVEL_FIELDS = [
    "ok",
    "merge_schema_version",
    "merge_type",
    "merge_id",
    "source_phase",
    "claim_scope",
    "agent_a",
    "agent_b",
    "shared_known_tile_ids",
    "agent_a_only_known_tile_ids",
    "agent_b_only_known_tile_ids",
    "same_current_tile",
    "both_have_route_intent",
    "errors",
]

_REQUIRED_BUNDLE_FIELDS = [
    "agent_id",
    "public_state_hash",
    "snapshot_id",
    "snapshot_hash",
    "current_tile_id",
    "known_tile_ids",
    "route_intent_id",
    "route_destination_tile_id",
    "route_destination_known",
]

_FORBIDDEN_OUTPUT_FIELDS = [
    "relationship",
    "trust",
    "cooperation",
    "conflict",
    "meeting",
    "encounter",
    "awareness",
    "communication",
    "speech" + "_merge",
    "memory" + "_merge",
    "path",
    "planned" + "_path",
    "route" + "_steps",
    "route" + "_edges",
    "travel" + "_edges",
    "adjacency",
    "neighbor",
    "movement" + "_chain",
    "ledger" + "_path",
    "candidate" + "_event",
    "evidence" + "_refs",
    "before" + "_ref",
    "after" + "_ref",
    "relationship" + "_delta",
]


# ---------------------------------------------------------------------------
# 1. happy path: two valid surfaces -> ok=True
# ---------------------------------------------------------------------------


def test_happy_path_two_valid_surfaces_ok_true():
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
        snapshot_id_seed="b",
    )

    merge = create_two_agent_public_merge(public_a, snap_a, public_b, snap_b)

    assert merge["ok"] is True
    assert merge["merge_schema_version"] == "10AS.1"
    assert merge["merge_type"] == "two_agent_public_merge"
    assert merge["merge_id"].startswith("10AS-")
    assert merge["source_phase"] == "10AR"
    assert merge["claim_scope"] == "public_only"
    assert merge["errors"] == []


# ---------------------------------------------------------------------------
# 2. happy path with route intents -> both_have_route_intent=True
# ---------------------------------------------------------------------------


def test_happy_path_with_route_intents_both_have_route_intent_true():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    intent_a = create_route_intent_contract(snap_a, TILE_SHARED)
    intent_b = create_route_intent_contract(snap_b, TILE_SHARED)

    assert intent_a["ok"] is True
    assert intent_b["ok"] is True

    merge = create_two_agent_public_merge(
        public_a,
        snap_a,
        public_b,
        snap_b,
        route_intent_a=intent_a,
        route_intent_b=intent_b,
    )

    assert merge["ok"] is True
    assert merge["both_have_route_intent"] is True
    assert merge["agent_a"]["route_intent_id"] == intent_a["intent_id"]
    assert merge["agent_b"]["route_intent_id"] == intent_b["intent_id"]
    assert merge["agent_a"]["route_destination_tile_id"] == TILE_SHARED
    assert merge["agent_b"]["route_destination_tile_id"] == TILE_SHARED
    assert merge["agent_a"]["route_destination_known"] is True
    assert merge["agent_b"]["route_destination_known"] is True


# ---------------------------------------------------------------------------
# 3. output has exactly the required top-level fields
# ---------------------------------------------------------------------------


def test_output_has_exactly_required_top_level_fields():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    merge = create_two_agent_public_merge(public_a, snap_a, public_b, snap_b)

    for field in _REQUIRED_TOP_LEVEL_FIELDS:
        assert field in merge, "missing required top-level field: " + field

    for forbidden in _FORBIDDEN_OUTPUT_FIELDS:
        assert forbidden not in merge, "forbidden field leaked: " + forbidden


# ---------------------------------------------------------------------------
# 4. agent_a and agent_b bundles have exactly the required bundle fields
# ---------------------------------------------------------------------------


def test_agent_bundles_have_exactly_required_bundle_fields():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )
    merge = create_two_agent_public_merge(public_a, snap_a, public_b, snap_b)

    for label in ("agent_a", "agent_b"):
        bundle = merge[label]
        for field in _REQUIRED_BUNDLE_FIELDS:
            assert field in bundle, label + " missing required bundle field: " + field
        for forbidden in _FORBIDDEN_OUTPUT_FIELDS:
            assert forbidden not in bundle, (
                "forbidden bundle field in " + label + ": " + forbidden
            )


# ---------------------------------------------------------------------------
# 5. shared_known_tile_ids is sorted intersection
# ---------------------------------------------------------------------------


def test_shared_known_tile_ids_is_sorted_intersection():
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
        snapshot_id_seed="b",
    )
    merge = create_two_agent_public_merge(public_a, snap_a, public_b, snap_b)

    assert merge["shared_known_tile_ids"] == [TILE_SHARED]
    assert merge["shared_known_tile_ids"] == sorted(merge["shared_known_tile_ids"])


# ---------------------------------------------------------------------------
# 6. agent_a_only and agent_b_only are sorted set differences
# ---------------------------------------------------------------------------


def test_agent_only_known_tile_ids_are_sorted_set_differences():
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
        snapshot_id_seed="b",
    )
    merge = create_two_agent_public_merge(public_a, snap_a, public_b, snap_b)

    assert merge["agent_a_only_known_tile_ids"] == sorted([TILE_A, TILE_C])
    assert merge["agent_b_only_known_tile_ids"] == sorted([TILE_B])

    a_only = merge["agent_a_only_known_tile_ids"]
    b_only = merge["agent_b_only_known_tile_ids"]
    assert a_only == sorted(a_only)
    assert b_only == sorted(b_only)


# ---------------------------------------------------------------------------
# 7. same_current_tile True only when both current tiles match
# ---------------------------------------------------------------------------


def test_same_current_tile_true_only_when_tiles_match():
    base_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    base_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    diff_merge = create_two_agent_public_merge(base_a, snap_a, base_b, snap_b)
    assert diff_merge["same_current_tile"] is False

    matching_b = copy.deepcopy(base_b)
    matching_b["current_tile_id"] = TILE_A
    matching_snap_b = copy.deepcopy(snap_b)
    matching_snap_b["current_tile_id"] = TILE_A
    same_merge = create_two_agent_public_merge(
        base_a, snap_a, matching_b, matching_snap_b
    )
    assert same_merge["same_current_tile"] is True


# ---------------------------------------------------------------------------
# 8. both_have_route_intent False when one or both are omitted
# ---------------------------------------------------------------------------


def test_both_have_route_intent_false_when_any_omitted():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    intent_a = create_route_intent_contract(snap_a, TILE_SHARED)
    intent_b = create_route_intent_contract(snap_b, TILE_B)

    none_merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b
    )
    assert none_merge["both_have_route_intent"] is False

    one_merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b, route_intent_a=intent_a
    )
    assert one_merge["both_have_route_intent"] is False


# ---------------------------------------------------------------------------
# 9. valid route intent copies only route_intent_id, destination_tile_id, destination_known
# ---------------------------------------------------------------------------


def test_valid_route_intent_copies_only_expected_route_fields():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )
    intent_a = create_route_intent_contract(snap_a, TILE_SHARED)

    merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b, route_intent_a=intent_a
    )

    bundle_a = merge["agent_a"]
    assert bundle_a["route_intent_id"] == intent_a["intent_id"]
    assert bundle_a["route_destination_tile_id"] == TILE_SHARED
    assert bundle_a["route_destination_known"] is True

    # 10AS does NOT copy the upstream intent fields like
    # source_phase, claim_scope, source_snapshot_hash, etc.
    forbidden_fields_in_bundle = [
        "source_phase",
        "claim" + "_scope",
        "source_snapshot_hash",
        "intent" + "_type",
        "intent" + "_schema" + "_version",
        "from_tile_id",
        "reason",
        "errors",
    ]
    for field in forbidden_fields_in_bundle:
        assert field not in bundle_a, (
            "10AS copied forbidden parent field into bundle: " + field
        )


# ---------------------------------------------------------------------------
# 10. invalid route intent ok=False returns safe error
# ---------------------------------------------------------------------------


def test_invalid_route_intent_ok_false_returns_safe_error():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    bad_intent = _route_intent_for_other_agent(
        agent_id=AGENT_A_ID,
        snapshot_id=snap_a["snapshot_id"],
        current_tile_id=TILE_A,
        destination_tile_id=TILE_SHARED,
        destination_known=False,
    )
    bad_intent["ok"] = False

    merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b, route_intent_a=bad_intent
    )

    assert merge["ok"] is False
    assert merge["merge_id"] is None
    assert any("ok flag is not True" in err for err in merge["errors"])


# ---------------------------------------------------------------------------
# 10a. internally inconsistent route intent (ok=True but destination_known=False)
# ---------------------------------------------------------------------------


def test_internally_inconsistent_route_intent_returns_ok_false():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    # 10AR rule: ok=True contract requires destination_known=True.
    # Hand-build an intent where ok=True but destination_known=False
    # — internally inconsistent.  10AS must reject it.
    inconsistent_intent = _route_intent_for_other_agent(
        agent_id=AGENT_A_ID,
        snapshot_id=snap_a["snapshot_id"],
        current_tile_id=TILE_A,
        destination_tile_id=TILE_SHARED,
        destination_known=False,
    )
    assert inconsistent_intent["ok"] is True
    assert inconsistent_intent["destination_known"] is False

    merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b,
        route_intent_a=inconsistent_intent,
    )

    assert merge["ok"] is False
    assert merge["merge_id"] is None
    assert any(
        "destination_known must be True" in err for err in merge["errors"]
    )

    # The bundle never gets the inconsistent intent.
    assert merge["agent_a"]["route_intent_id"] is None
    assert merge["agent_a"]["route_destination_tile_id"] is None
    assert merge["agent_a"]["route_destination_known"] is None
    assert merge["both_have_route_intent"] is False


# ---------------------------------------------------------------------------
# 11. route intent agent_id mismatch returns ok=False
# ---------------------------------------------------------------------------


def test_route_intent_agent_id_mismatch_returns_ok_false():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    bad_intent = _route_intent_for_other_agent(
        agent_id="agent_someone_else",
        snapshot_id=snap_a["snapshot_id"],
        current_tile_id=TILE_A,
        destination_tile_id=TILE_SHARED,
    )

    merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b, route_intent_a=bad_intent
    )

    assert merge["ok"] is False
    assert any(
        "agent_id does not match" in err for err in merge["errors"]
    )


# ---------------------------------------------------------------------------
# 12. route intent source_snapshot_id mismatch returns ok=False
# ---------------------------------------------------------------------------


def test_route_intent_source_snapshot_id_mismatch_returns_ok_false():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    bad_intent = _route_intent_for_other_agent(
        agent_id=AGENT_A_ID,
        snapshot_id="10AQ-" + "z" * 32,
        current_tile_id=TILE_A,
        destination_tile_id=TILE_SHARED,
    )

    merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b, route_intent_a=bad_intent
    )

    assert merge["ok"] is False
    assert any(
        "source_snapshot_id does not match" in err for err in merge["errors"]
    )


# ---------------------------------------------------------------------------
# 13. route intent wrong claim_scope returns ok=False
# ---------------------------------------------------------------------------


def test_route_intent_wrong_claim_scope_returns_ok_false():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    bad_intent = _route_intent_for_other_agent(
        agent_id=AGENT_A_ID,
        snapshot_id=snap_a["snapshot_id"],
        current_tile_id=TILE_A,
        destination_tile_id=TILE_SHARED,
    )
    bad_intent["claim_scope"] = "speech"

    merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b, route_intent_a=bad_intent
    )

    assert merge["ok"] is False
    assert any(
        "claim_scope is not" in err for err in merge["errors"]
    )


# ---------------------------------------------------------------------------
# 14. non-dict public_state or snapshot returns ok=False
# ---------------------------------------------------------------------------


def test_non_dict_inputs_return_ok_false():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    for ps_bad in ("not-a-dict", 42, None, ["list"]):
        merge = create_two_agent_public_merge(  # type: ignore[arg-type]
            ps_bad, snap_a, public_b, snap_b
        )
        assert merge["ok"] is False

    for snap_bad in ("not-a-dict", 99, None):
        merge = create_two_agent_public_merge(  # type: ignore[arg-type]
            public_a, snap_bad, public_b, snap_b
        )
        assert merge["ok"] is False


# ---------------------------------------------------------------------------
# 15. failed public_state ok=False returns ok=False
# ---------------------------------------------------------------------------


def test_failed_public_state_returns_ok_false():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    bad_state = copy.deepcopy(public_a)
    bad_state["ok"] = False

    merge = create_two_agent_public_merge(bad_state, snap_a, public_b, snap_b)
    assert merge["ok"] is False
    assert any("ok flag is not True" in err for err in merge["errors"])


# ---------------------------------------------------------------------------
# 16. failed snapshot ok=False returns ok=False
# ---------------------------------------------------------------------------


def test_failed_snapshot_returns_ok_false():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    bad_snap = copy.deepcopy(snap_a)
    bad_snap["ok"] = False

    merge = create_two_agent_public_merge(public_a, bad_snap, public_b, snap_b)
    assert merge["ok"] is False
    assert any("ok flag is not True" in err for err in merge["errors"])


# ---------------------------------------------------------------------------
# 17. snapshot_type not known_map_snapshot returns ok=False
# ---------------------------------------------------------------------------


def test_wrong_snapshot_type_returns_ok_false():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    bad_snap = copy.deepcopy(snap_a)
    bad_snap["snapshot_type"] = "public_state_projection"

    merge = create_two_agent_public_merge(public_a, bad_snap, public_b, snap_b)
    assert merge["ok"] is False
    assert any("snapshot_type is not" in err for err in merge["errors"])


# ---------------------------------------------------------------------------
# 18. public_state / snapshot agent_id mismatch returns ok=False
# ---------------------------------------------------------------------------


def test_agent_id_mismatch_between_public_state_and_snapshot_returns_ok_false():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    bad_snap = copy.deepcopy(snap_a)
    bad_snap["agent_id"] = "agent_other"

    merge = create_two_agent_public_merge(public_a, bad_snap, public_b, snap_b)
    assert merge["ok"] is False
    assert any("agent_id does not match" in err for err in merge["errors"])


# ---------------------------------------------------------------------------
# 19. public_state / snapshot current_tile_id mismatch returns ok=False
# ---------------------------------------------------------------------------


def test_current_tile_mismatch_between_public_state_and_snapshot_returns_ok_false():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    bad_snap = copy.deepcopy(snap_a)
    bad_snap["current_tile_id"] = "tile_other"

    merge = create_two_agent_public_merge(public_a, bad_snap, public_b, snap_b)
    assert merge["ok"] is False
    assert any("current_tile_id does not match" in err for err in merge["errors"])


# ---------------------------------------------------------------------------
# 20. inputs are not mutated
# ---------------------------------------------------------------------------


def test_input_public_states_snapshots_route_intents_not_mutated():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )
    intent_a = create_route_intent_contract(snap_a, TILE_SHARED)

    before_pa = copy.deepcopy(public_a)
    before_pb = copy.deepcopy(public_b)
    before_sa = copy.deepcopy(snap_a)
    before_sb = copy.deepcopy(snap_b)
    before_ia = copy.deepcopy(intent_a)

    create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b, route_intent_a=intent_a
    )
    create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b, route_intent_a=intent_a
    )

    assert public_a == before_pa
    assert public_b == before_pb
    assert snap_a == before_sa
    assert snap_b == before_sb
    assert intent_a == before_ia


# ---------------------------------------------------------------------------
# 21. repeated merge creation is deterministic
# ---------------------------------------------------------------------------


def test_repeated_merge_is_deterministic():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    m1 = create_two_agent_public_merge(public_a, snap_a, public_b, snap_b)
    m2 = create_two_agent_public_merge(
        copy.deepcopy(public_a),
        copy.deepcopy(snap_a),
        copy.deepcopy(public_b),
        copy.deepcopy(snap_b),
    )

    assert m1 == m2
    assert m1["merge_id"] == m2["merge_id"]


# ---------------------------------------------------------------------------
# 22. merge_id changes when known tile overlap changes
# ---------------------------------------------------------------------------


def test_merge_id_changes_when_overlap_changes():
    base_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    base_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b_overlap = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B, TILE_SHARED],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )
    snap_b_no_overlap = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    m_overlap = create_two_agent_public_merge(
        base_a, snap_a, base_b, snap_b_overlap
    )
    m_no_overlap = create_two_agent_public_merge(
        copy.deepcopy(base_a),
        copy.deepcopy(snap_a),
        copy.deepcopy(base_b),
        snap_b_no_overlap,
    )

    assert m_overlap["merged_id" if "merged_id" in m_overlap else "merge_id"] != \
        m_no_overlap["merge_id"]
    assert m_overlap["shared_known_tile_ids"] != m_no_overlap["shared_known_tile_ids"]


# ---------------------------------------------------------------------------
# 23. merge_id changes when route intent changes
# ---------------------------------------------------------------------------


def test_merge_id_changes_when_route_intent_changes():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    intent_a_1 = create_route_intent_contract(snap_a, TILE_SHARED)
    intent_a_2 = create_route_intent_contract(snap_a, TILE_A)

    m1 = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b,
        route_intent_a=intent_a_1,
    )
    m2 = create_two_agent_public_merge(
        copy.deepcopy(public_a),
        copy.deepcopy(snap_a),
        copy.deepcopy(public_b),
        copy.deepcopy(snap_b),
        route_intent_a=intent_a_2,
    )

    assert m1["merge_id"] != m2["merge_id"]
    assert m1["both_have_route_intent"] is False
    assert m2["both_have_route_intent"] is False


# ---------------------------------------------------------------------------
# 24. export_two_agent_public_merge returns stable sorted JSON
# ---------------------------------------------------------------------------


def test_export_returns_stable_sorted_json():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )
    merge = create_two_agent_public_merge(public_a, snap_a, public_b, snap_b)

    exported_a = export_two_agent_public_merge(merge)
    exported_b = export_two_agent_public_merge(copy.deepcopy(merge))

    assert exported_a == exported_b
    parsed = json.loads(exported_a)
    assert parsed == merge
    assert exported_a == json.dumps(parsed, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 25. merge_public_surface_files matches direct create from loaded JSON
# ---------------------------------------------------------------------------


def test_merge_public_surface_files_matches_direct_create(tmp_path):
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    pa_path = tmp_path / "psa.json"
    sa_path = tmp_path / "snap_a.json"
    pb_path = tmp_path / "psb.json"
    sb_path = tmp_path / "snap_b.json"
    pa_path.write_text(
        json.dumps(public_a, sort_keys=True), encoding="utf-8"
    )
    sa_path.write_text(
        json.dumps(snap_a, sort_keys=True), encoding="utf-8"
    )
    pb_path.write_text(
        json.dumps(public_b, sort_keys=True), encoding="utf-8"
    )
    sb_path.write_text(
        json.dumps(snap_b, sort_keys=True), encoding="utf-8"
    )

    direct = create_two_agent_public_merge(public_a, snap_a, public_b, snap_b)
    via_file = merge_public_surface_files(pa_path, sa_path, pb_path, sb_path)
    assert direct == via_file


# ---------------------------------------------------------------------------
# 26. route destination private markers are sanitized before output
# ---------------------------------------------------------------------------


def test_route_destination_private_markers_sanitized_before_output():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )

    # Build a structurally-valid 10AR-shaped intent that is
    # internally inconsistent: 10AR requires destination_known=True
    # for ok=True.  10AS must reject this intent and the merge
    # must be ok=False.  Either way, private Windows-path markers
    # carried in destination_tile_id must NEVER appear in any
    # output path (error message dict, exported JSON, escaped
    # JSON, neither field-level nor nested).
    private_dest = (
        "tile_" + chr(67) + ":\\Users\\agent\\secret\\tile_x"
    )

    # Case A: externally inconsistent intent (ok=True but
    # destination_known=False).  10AS must reject it.
    inconsistent_intent = _route_intent_for_other_agent(
        agent_id=AGENT_A_ID,
        snapshot_id=snap_a["snapshot_id"],
        current_tile_id=TILE_A,
        destination_tile_id=private_dest,
        destination_known=False,
    )
    inconsistent_merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b,
        route_intent_a=inconsistent_intent,
    )
    assert inconsistent_merge["ok"] is False
    inconsistent_exported = export_two_agent_public_merge(inconsistent_merge)
    for forbidden_literal in (
        "Users\\agent\\secret",
        "C:\\Users",
        "agent\\secret",
    ):
        assert forbidden_literal not in inconsistent_exported, (
            "private marker survived in inconsistent-case export: "
            + forbidden_literal
        )

    # Case B: ostensibly valid intent (destination_known=True) but
    # carrying private markers.  Even if 10AS accepted it, those
    # markers must not reach the merge dict or exported JSON.
    # We hand-build this so the test is hermetic.
    hand_valid_intent = _route_intent_for_other_agent(
        agent_id=AGENT_A_ID,
        snapshot_id=snap_a["snapshot_id"],
        current_tile_id=TILE_A,
        destination_tile_id=private_dest,
        destination_known=True,
    )
    hand_merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b,
        route_intent_a=hand_valid_intent,
    )
    # 10AS sanitization happens regardless of the merge outcome.
    # If ok=True, inspect bundle fields.  If ok=False, inspect
    # errors and full dict.
    bundle_destination = hand_merge["agent_a"].get("route_destination_tile_id")
    if bundle_destination is not None and bundle_destination != "":
        for forbidden_literal in (
            "Users\\agent\\secret",
            "C:\\Users",
            "agent\\secret",
        ):
            assert forbidden_literal not in bundle_destination, (
                "private marker survived in bundle: " + forbidden_literal
            )

    hand_exported = export_two_agent_public_merge(hand_merge)
    for forbidden_literal in (
        "Users\\agent\\secret",
        "C:\\Users",
        "agent\\secret",
    ):
        assert forbidden_literal not in hand_exported, (
            "private marker survived in hand_valid-case export: "
            + forbidden_literal
        )

    # The raw caller-owned intent must never be mutated.
    assert inconsistent_intent["destination_tile_id"] == private_dest
    assert hand_valid_intent["destination_tile_id"] == private_dest


# ---------------------------------------------------------------------------
# 27. output contains no relationship/trust/cooperation/conflict/meeting/etc.
# ---------------------------------------------------------------------------


def test_output_has_no_relationship_trust_cooperation_conflict_meeting_fields():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )
    intent_a = create_route_intent_contract(snap_a, TILE_SHARED)
    intent_b = create_route_intent_contract(snap_b, TILE_B)

    merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b,
        route_intent_a=intent_a,
        route_intent_b=intent_b,
    )
    exported = export_two_agent_public_merge(merge)
    parsed = json.loads(exported)

    for forbidden in _FORBIDDEN_OUTPUT_FIELDS:
        assert forbidden not in merge, "in merge: " + forbidden
        assert forbidden not in parsed, "in exported JSON: " + forbidden
        for label in ("agent_a", "agent_b"):
            assert forbidden not in merge[label], (
                "in bundle " + label + ": " + forbidden
            )


# ---------------------------------------------------------------------------
# 28. output contains no path/route-step/route-edge/adjacency/movement/ledger/candidate fields
# ---------------------------------------------------------------------------


def test_output_has_no_path_route_step_movement_ledger_candidate_fields():
    public_a = _public_state_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    public_b = _public_state_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
    )
    snap_a = _snapshot_dict(
        agent_id=AGENT_A_ID,
        current_tile_id=TILE_A,
        observed=[TILE_A, TILE_SHARED],
        visited=[TILE_A],
    )
    snap_b = _snapshot_dict(
        agent_id=AGENT_B_ID,
        current_tile_id=TILE_B,
        observed=[TILE_B],
        visited=[TILE_B],
        snapshot_id_seed="b",
    )
    intent_a = create_route_intent_contract(snap_a, TILE_SHARED)
    merge = create_two_agent_public_merge(
        public_a, snap_a, public_b, snap_b, route_intent_a=intent_a
    )

    forbidden_path_class = [
        "path",
        "planned" + "_path",
        "via" + "_tile_ids",
        "next" + "_tile",
        "previous" + "_tile",
        "adjacency",
        "neighbor",
        "route" + "_steps",
        "route" + "_edges",
        "travel" + "_edges",
        "movement" + "_chain",
        "ledger" + "_path",
        "candidate" + "_event",
        "evidence" + "_refs",
        "before" + "_ref",
        "after" + "_ref",
        "verification" + "_status",
        "tick",
        "actor" + "_id",
        "schema" + "_version",
    ]
    parsed = json.loads(export_two_agent_public_merge(merge))
    for forbidden in forbidden_path_class:
        assert forbidden not in merge, "path-class in merge: " + forbidden
        assert forbidden not in parsed, "path-class in exported JSON: " + forbidden
        for label in ("agent_a", "agent_b"):
            assert forbidden not in merge[label], (
                "path-class in bundle " + label + ": " + forbidden
            )


# ---------------------------------------------------------------------------
# 29. module has no forbidden imports or parent-phase chaining imports
# ---------------------------------------------------------------------------


def test_module_has_no_forbidden_imports_or_parent_chaining_imports():
    # Only scan the 10AS module file.  The test file legitimately
    # imports helpers from sibling phases (10AR creator, 10AQ
    # snapshot, etc.) in order to build fixtures.
    files = [
        PROJECT_ROOT / "backend" / "world" / "local_two_agent_public_merge.py",
    ]

    forbidden_markers = [
        "project" + "_ledger_file",
        "snapshot" + "_ledger_file",
        "create" + "_route_intent_contract",
        "merge" + "_ledger_files",
        "import " + "requests",
        "from " + "requests",
        "import " + "httpx",
        "from " + "httpx",
        "import " + "aiohttp",
        "from " + "aiohttp",
        "import " + "socket",
        "from " + "socket",
        "import " + "subprocess",
        "from " + "subprocess",
        "import " + "threading",
        "from " + "threading",
        "import " + "asyncio",
        "from " + "asyncio",
        "while " + "True",
        "world-sim" + "/data",
        "world-sim" + "/world",
    ]

    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        for marker in forbidden_markers:
            assert (
                marker not in text
            ), "forbidden marker in " + file_path.name + ": " + repr(marker)

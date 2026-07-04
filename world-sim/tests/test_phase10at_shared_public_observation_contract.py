"""Phase 10AT - shared public observation contract proof.

These tests prove that a Phase 10AS two-agent public merge artifact can
be wrapped in a deterministic, sanitized shared-public-observation
contract that formalizes which public observations two agents
demonstrably share, without ever inferring private knowledge,
co-presence, awareness, trust, cooperation, conflict, communication,
or any kind of relationship.

10AT may say:

    "These two agents share public observation of tiles X/Y/Z."

    "Their two published public surfaces report the same current
     public tile T (a public-surface match; no co-presence claim)."

    "Both agents have each published an intent_only route intent toward
     the same destination tile D."

10AT may not say:

    "The agents are / were co-present, met, became aware of each other,
     or know each other privately."

    "The agents trust, cooperate, conflict, communicate, exchange
     memory, share private state, perceive each other, or traveled
     together."

These tests follow the established Genesis discipline: tempdir-only,
no daemon, no scheduler, no provider, no Docker, no network, no live
data, no ``world-sim/data`` access.
"""

from __future__ import annotations

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
from backend.world.local_shared_public_observation_contract import (  # noqa: E402
    contract_shared_observation_file,
    create_shared_public_observation_contract,
    export_shared_public_observation_contract,
)
from backend.world.local_two_agent_public_merge import (  # noqa: E402
    create_two_agent_public_merge,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping  # noqa: E402

# NOTE: We import the 10AS / 10AR / 10AQ / 10AP creators here in the
# TEST file ONLY, to fabricate valid 10AS merge inputs.  The 10AT
# MODULE under test (local_shared_public_observation_contract.py) does
# not import any of these — that boundary is asserted below by a
# source-scan test.  Importing them here is the standard pattern used
# by test_phase10as_two_agent_public_merge.py.


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
# Fixtures: build real 10AS merges to feed 10AT
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
    """Build a real 10AS merge via the 10AS creator.

    This is the sanctioned way to produce a well-formed 10AS merge
    artifact for 10AT to consume.  Returns the dict returned by
    ``create_two_agent_public_merge`` (ok=True on the happy path).
    """

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
    "both_have_route_intent",
    "both_route_to_same_destination",
    "shared_route_destination_tile_id",
    "agent_a_route_destination_tile_id",
    "agent_b_route_destination_tile_id",
    "claim_scope",
    "errors",
]

# Fields that must never appear in a 10AT contract output — they would
# signal a forbidden inference (private knowledge or co-presence /
# awareness / relationship claim).
_FORBIDDEN_OUTPUT_FIELDS = [
    "co_presence",
    "copresence",
    "co_present",
    "met",
    "meeting",
    "encounter",
    "encountered",
    "awareness",
    "aware",
    "aware_of",
    "trust",
    "cooperation",
    "cooperate",
    "conflict",
    "communication",
    "communicate",
    "relationship",
    "private_state",
    "shared_private",
    "shared_private_state",
    "joint_plan",
    "joint_route",
    "joint_memory",
    "joint_ledger",
    "perceive",
    "perceived",
    "perception",
    "saw_each_other",
    "knows_each_other",
    "know_each_other",
    "memory_shared",
]


# ---------------------------------------------------------------------------
# 1. happy path: real 10AS merge -> ok=True contract
# ---------------------------------------------------------------------------


def test_happy_path_real_merge_produces_ok_true_contract():
    merge = _build_merge()
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is True
    assert contract["contract_schema_version"] == "10AT.1"
    assert contract["contract_type"] == "shared_public_observation_contract"
    assert contract["contract_id"].startswith("10AT-")
    assert contract["source_phase"] == "10AS"
    assert contract["claim_scope"] == "shared_public_only"
    assert contract["errors"] == []
    assert contract["source_merge_id"] == merge["merge_id"]
    assert contract["source_merge_schema_version"] == "10AS.1"


# ---------------------------------------------------------------------------
# 2. output has exactly the required top-level fields; no forbidden fields
# ---------------------------------------------------------------------------


def test_output_has_exactly_required_top_level_fields():
    merge = _build_merge()
    contract = create_shared_public_observation_contract(merge)

    for field in _REQUIRED_TOP_LEVEL_FIELDS:
        assert field in contract, "missing required top-level field: " + field

    for forbidden in _FORBIDDEN_OUTPUT_FIELDS:
        assert forbidden not in contract, "forbidden field leaked: " + forbidden


# ---------------------------------------------------------------------------
# 3. shared_known_tile_ids is sorted intersection lifted from 10AS merge
# ---------------------------------------------------------------------------


def test_shared_known_tile_ids_is_sorted_intersection_from_merge():
    merge = _build_merge()
    contract = create_shared_public_observation_contract(merge)

    # 10AS already computed the intersection of the two known_tile_ids
    # lists; 10AT must lift that exactly (sorted, unique, deduped).
    expected = sorted(set(merge["shared_known_tile_ids"]))
    assert contract["shared_known_tile_ids"] == expected
    assert contract["shared_known_tile_ids"] == sorted(
        contract["shared_known_tile_ids"]
    )
    assert contract["shared_known_tile_count"] == len(expected)


def test_shared_known_tile_ids_drops_non_string_and_empty_entries():
    merge = _build_merge()
    # Inject a non-string and an empty string into the merge's
    # shared_known_tile_ids; 10AT must drop them and dedupe.
    merge_modified = copy.deepcopy(merge)
    merge_modified["shared_known_tile_ids"] = [
        TILE_SHARED,
        TILE_SHARED,
        "",
        42,
        None,
        TILE_A,
    ]
    contract = create_shared_public_observation_contract(merge_modified)
    assert contract["ok"] is True
    assert contract["shared_known_tile_ids"] == sorted([TILE_SHARED, TILE_A])
    assert contract["shared_known_tile_count"] == 2


# ---------------------------------------------------------------------------
# 4. same_current_tile True only when both public current tiles match
#    shared_current_tile_id carries the matching tile or None.
#    No co-presence claim is inferable.
# ---------------------------------------------------------------------------


def test_same_current_tile_false_distinct_tiles():
    merge = _build_merge(a_current=TILE_A, b_current=TILE_B)
    contract = create_shared_public_observation_contract(merge)

    assert contract["same_current_tile"] is False
    assert contract["shared_current_tile_id"] is None
    # The contract must not promote a public-surface match into a
    # co-presence / awareness / meeting claim.  None of these fields
    # may exist in the output.
    for forbidden in ("co_presence", "met", "awareness", "encounter"):
        assert forbidden not in contract


def test_same_current_tile_true_same_tile():
    merge = _build_merge(a_current=TILE_A, b_current=TILE_A)
    contract = create_shared_public_observation_contract(merge)

    assert contract["same_current_tile"] is True
    assert contract["shared_current_tile_id"] == TILE_A
    # Even with same_current_tile True, the contract must remain
    # free of any private co-presence / awareness / relationship claim.
    for forbidden in ("co_presence", "met", "awareness", "encounter"):
        assert forbidden not in contract


# ---------------------------------------------------------------------------
# 5. both_have_route_intent mirrors the 10AS merge flag
# ---------------------------------------------------------------------------


def test_both_have_route_intent_false_when_none_provided():
    merge = _build_merge()
    contract = create_shared_public_observation_contract(merge)

    assert contract["both_have_route_intent"] is False
    assert contract["both_route_to_same_destination"] is False
    assert contract["shared_route_destination_tile_id"] is None


def test_both_have_route_intent_true_when_both_provided():
    merge = _build_merge(route_a_dest=TILE_SHARED, route_b_dest=TILE_SHARED)
    contract = create_shared_public_observation_contract(merge)

    assert contract["both_have_route_intent"] is True


# ---------------------------------------------------------------------------
# 6. both_route_to_same_destination logic
# ---------------------------------------------------------------------------


def test_both_route_to_same_destination_true_when_destinations_equal():
    merge = _build_merge(route_a_dest=TILE_SHARED, route_b_dest=TILE_SHARED)
    contract = create_shared_public_observation_contract(merge)

    assert contract["both_route_to_same_destination"] is True
    assert contract["shared_route_destination_tile_id"] == TILE_SHARED
    assert contract["agent_a_route_destination_tile_id"] == TILE_SHARED
    assert contract["agent_b_route_destination_tile_id"] == TILE_SHARED


def test_both_route_to_same_destination_false_when_destinations_differ():
    merge = _build_merge(route_a_dest=TILE_SHARED, route_b_dest=TILE_B)
    contract = create_shared_public_observation_contract(merge)

    assert contract["both_route_to_same_destination"] is False
    assert contract["shared_route_destination_tile_id"] is None
    assert contract["agent_a_route_destination_tile_id"] == TILE_SHARED
    assert contract["agent_b_route_destination_tile_id"] == TILE_B


def test_both_route_to_same_destination_false_when_only_one_intent():
    merge = _build_merge(route_a_dest=TILE_SHARED, route_b_dest=None)
    contract = create_shared_public_observation_contract(merge)

    assert contract["both_have_route_intent"] is False
    assert contract["both_route_to_same_destination"] is False
    assert contract["shared_route_destination_tile_id"] is None
    assert contract["agent_a_route_destination_tile_id"] == TILE_SHARED
    assert contract["agent_b_route_destination_tile_id"] is None


def test_both_route_to_same_destination_false_when_dest_empty_strings():
    # An empty-string destination must not trigger a false match even
    # if both bundles report an empty-string route_destination_tile_id.
    merge = _build_merge()
    merge_modified = copy.deepcopy(merge)
    merge_modified["both_have_route_intent"] = True
    merge_modified["agent_a"]["route_intent_id"] = "10AR-aaaa"
    merge_modified["agent_b"]["route_intent_id"] = "10AR-bbbb"
    merge_modified["agent_a"]["route_destination_tile_id"] = ""
    merge_modified["agent_b"]["route_destination_tile_id"] = ""
    contract = create_shared_public_observation_contract(merge_modified)

    assert contract["ok"] is True
    assert contract["both_have_route_intent"] is True
    assert contract["both_route_to_same_destination"] is False
    assert contract["shared_route_destination_tile_id"] is None
    assert contract["agent_a_route_destination_tile_id"] is None
    assert contract["agent_b_route_destination_tile_id"] is None


# ---------------------------------------------------------------------------
# 7. per-agent route destination fields come from sanitized bundles only
# ---------------------------------------------------------------------------


def test_route_destination_fields_read_from_sanitized_bundles():
    merge = _build_merge(route_a_dest=TILE_SHARED, route_b_dest=TILE_B)
    contract = create_shared_public_observation_contract(merge)

    # The contract copies the sanitized bundle route_destination_tile_id
    # fields, never the raw route intent objects (which are not even
    # present in a 10AS merge artifact — only bundle fields are).
    assert contract["agent_a_route_destination_tile_id"] == TILE_SHARED
    assert contract["agent_b_route_destination_tile_id"] == TILE_B
    # The contract must not contain any raw route intent fields.
    for forbidden in (
        "route_intent_a",
        "route_intent_b",
        "intent_schema_version",
        "intent_type",
        "source_snapshot_id",
        "source_snapshot_hash",
        "from_tile_id",
        "reason",
    ):
        assert forbidden not in contract


# ---------------------------------------------------------------------------
# 8. contract_id is deterministic across repeated calls
# ---------------------------------------------------------------------------


def test_contract_id_is_deterministic_across_repeated_calls():
    merge1 = _build_merge()
    merge2 = _build_merge()
    contract1 = create_shared_public_observation_contract(merge1)
    contract2 = create_shared_public_observation_contract(merge2)

    assert contract1["contract_id"] == contract2["contract_id"]
    # And the contract id must be a 10AT- prefix plus 32 hex chars.
    assert re.match(r"^10AT-[0-9a-f]{32}$", contract1["contract_id"])


# ---------------------------------------------------------------------------
# 9. contract_id changes when any contract-material field changes
# ---------------------------------------------------------------------------


def test_contract_id_changes_when_shared_known_tile_ids_change():
    merge_x = _build_merge(a_observed=[TILE_A, TILE_SHARED], b_observed=[TILE_B, TILE_SHARED])
    merge_y = _build_merge(
        a_observed=[TILE_A, TILE_SHARED, TILE_C],
        b_observed=[TILE_B, TILE_SHARED],
    )
    contract_x = create_shared_public_observation_contract(merge_x)
    contract_y = create_shared_public_observation_contract(merge_y)

    assert contract_x["contract_id"] != contract_y["contract_id"]


def test_contract_id_changes_when_same_current_tile_changes():
    merge_diff = _build_merge(a_current=TILE_A, b_current=TILE_B)
    merge_same = _build_merge(a_current=TILE_A, b_current=TILE_A)
    contract_diff = create_shared_public_observation_contract(merge_diff)
    contract_same = create_shared_public_observation_contract(merge_same)

    assert contract_diff["contract_id"] != contract_same["contract_id"]


def test_contract_id_changes_when_shared_route_destination_changes():
    merge_same = _build_merge(route_a_dest=TILE_SHARED, route_b_dest=TILE_SHARED)
    merge_diff = _build_merge(route_a_dest=TILE_SHARED, route_b_dest=TILE_B)
    contract_same = create_shared_public_observation_contract(merge_same)
    contract_diff = create_shared_public_observation_contract(merge_diff)

    assert contract_same["contract_id"] != contract_diff["contract_id"]


# ---------------------------------------------------------------------------
# 10. input mutation guard: caller's merge dict is unchanged after call
# ---------------------------------------------------------------------------


def test_caller_merge_dict_is_unchanged_after_call():
    merge = _build_merge()
    merge_snapshot = copy.deepcopy(merge)
    _ = create_shared_public_observation_contract(merge)

    assert merge == merge_snapshot


def test_caller_merge_dict_unchanged_even_when_sanitizer_redacts():
    # Plant a private marker in the merge bundle's agent id field.  The
    # sanitizer must redact it in the OUTPUT, but the caller's input
    # must remain byte-for-byte unchanged.
    merge = _build_merge()
    original = copy.deepcopy(merge)
    merge["agent_a"]["agent_id"] = "C:\\Users\\leak\\agent_adam"
    merge_with_leak = copy.deepcopy(merge)

    _ = create_shared_public_observation_contract(merge)

    assert merge == merge_with_leak
    # And the original-shaped input (without the leak) should still
    # match its own snapshot when run independently.
    contract = create_shared_public_observation_contract(original)
    assert contract["ok"] is True


# ---------------------------------------------------------------------------
# 11. non-dict merge -> ok=False with safe error
# ---------------------------------------------------------------------------


def test_non_dict_merge_returns_ok_false():
    for bad in ("not-a-dict", 42, None, ["a", "list"], 3.14, True):
        contract = create_shared_public_observation_contract(bad)  # type: ignore[arg-type]
        assert contract["ok"] is False
        assert contract["contract_id"] is None
        assert any("merge must be a dict" in e for e in contract["errors"])


# ---------------------------------------------------------------------------
# 12. merge ok=False -> ok=False with safe error
# ---------------------------------------------------------------------------


def test_merge_ok_false_returns_ok_false():
    merge = _build_merge()
    merge["ok"] = False
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is False
    assert contract["contract_id"] is None
    assert any("merge ok flag is not True" in e for e in contract["errors"])


# ---------------------------------------------------------------------------
# 13. wrong merge_type -> ok=False
# ---------------------------------------------------------------------------


def test_wrong_merge_type_returns_ok_false():
    merge = _build_merge()
    merge["merge_type"] = "something_else"
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is False
    assert any("merge_type is not" in e for e in contract["errors"])


# ---------------------------------------------------------------------------
# 14. wrong merge_schema_version -> ok=False
# ---------------------------------------------------------------------------


def test_wrong_merge_schema_version_returns_ok_false():
    merge = _build_merge()
    merge["merge_schema_version"] = "10AS.99"
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is False
    assert any("merge_schema_version is not" in e for e in contract["errors"])


# ---------------------------------------------------------------------------
# 15. missing / non-dict agent_a or agent_b -> ok=False
# ---------------------------------------------------------------------------


def test_missing_agent_a_returns_ok_false():
    merge = _build_merge()
    del merge["agent_a"]
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is False
    assert any("agent_a must be a dict" in e for e in contract["errors"])


def test_non_dict_agent_b_returns_ok_false():
    merge = _build_merge()
    merge["agent_b"] = "not-a-dict"
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is False
    assert any("agent_b must be a dict" in e for e in contract["errors"])


# ---------------------------------------------------------------------------
# 16. empty agent_a_id or agent_b_id -> ok=False
# ---------------------------------------------------------------------------


def test_empty_agent_a_id_returns_ok_false():
    merge = _build_merge()
    merge["agent_a"]["agent_id"] = ""
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is False
    assert any("agent_a_id is missing or empty" in e for e in contract["errors"])


def test_empty_agent_b_id_returns_ok_false():
    merge = _build_merge()
    merge["agent_b"]["agent_id"] = ""
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is False
    assert any("agent_b_id is missing or empty" in e for e in contract["errors"])


# ---------------------------------------------------------------------------
# 17. same agent_a_id and agent_b_id -> ok=False (distinct-agent rule)
# ---------------------------------------------------------------------------


def test_same_agent_a_and_agent_b_id_returns_ok_false():
    merge = _build_merge()
    merge["agent_b"]["agent_id"] = merge["agent_a"]["agent_id"]
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is False
    assert contract["contract_id"] is None
    assert any(
        "agent_a_id and agent_b_id must be distinct" in e
        for e in contract["errors"]
    )


# ---------------------------------------------------------------------------
# 18. shared_known_tile_ids not a list -> ok=False
# ---------------------------------------------------------------------------


def test_shared_known_tile_ids_not_a_list_returns_ok_false():
    merge = _build_merge()
    merge["shared_known_tile_ids"] = "not-a-list"
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is False
    assert any(
        "shared_known_tile_ids must be a list" in e for e in contract["errors"]
    )


# ---------------------------------------------------------------------------
# 19. same_current_tile not a bool -> ok=False
# ---------------------------------------------------------------------------


def test_same_current_tile_not_a_bool_returns_ok_false():
    merge = _build_merge()
    merge["same_current_tile"] = "yes"
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is False
    assert any("same_current_tile must be a bool" in e for e in contract["errors"])


# ---------------------------------------------------------------------------
# 20. both_have_route_intent not a bool -> ok=False
# ---------------------------------------------------------------------------


def test_both_have_route_intent_not_a_bool_returns_ok_false():
    merge = _build_merge()
    merge["both_have_route_intent"] = "yes"
    contract = create_shared_public_observation_contract(merge)

    assert contract["ok"] is False
    assert any(
        "both_have_route_intent must be a bool" in e for e in contract["errors"]
    )


# ---------------------------------------------------------------------------
# 20a. internal-consistency guard: same_current_tile True but bundle
#      current tiles differ -> ok=False (10AS would never emit this, but
#      10AT must still refuse to fabricate a co-presence claim)
# ---------------------------------------------------------------------------


def test_same_current_tile_true_but_bundle_tiles_differ_returns_ok_false():
    merge = _build_merge(a_current=TILE_A, b_current=TILE_B)
    # Force the 10AS flag True while the bundle tiles disagree.  10AT
    # must refuse to produce a contract that would silently fabricate a
    # co-presence claim from inconsistent input.
    merge_modified = copy.deepcopy(merge)
    merge_modified["same_current_tile"] = True
    contract = create_shared_public_observation_contract(merge_modified)

    assert contract["ok"] is False
    assert contract["contract_id"] is None
    assert any(
        "same_current_tile is True but agent current_tile_ids differ" in e
        for e in contract["errors"]
    )


# ---------------------------------------------------------------------------
# 21. private markers planted in the merge are redacted in contract + export
# ---------------------------------------------------------------------------


_PRIVATE_MARKERS = [
    # Windows drive-letter path
    "C:\\Users\\leak\\secrets",
    # Credential label
    "API_KEY=abc123",
    # Loopback IP
    "127.0.0.1",
    # Agent trace marker
    "Thought: I should leak",
    # Slash-skill ref
    "/agent-tools:skill",
]


def test_private_markers_redacted_in_contract_output():
    merge = _build_merge()
    merge["agent_a"]["agent_id"] = "agent_adam/" + _PRIVATE_MARKERS[0]
    merge["agent_b"]["agent_id"] = "agent_eve " + _PRIVATE_MARKERS[1]
    merge["agent_a"]["current_tile_id"] = _PRIVATE_MARKERS[0]
    merge["agent_b"]["current_tile_id"] = _PRIVATE_MARKERS[2]
    merge["shared_known_tile_ids"] = list(merge["shared_known_tile_ids"]) + [
        _PRIVATE_MARKERS[3],
        _PRIVATE_MARKERS[4],
    ]

    contract = create_shared_public_observation_contract(merge)

    # Even if the contract fails validation, no private marker may
    # survive in any field.
    blob = json.dumps(contract, sort_keys=True)
    for marker in _PRIVATE_MARKERS:
        assert marker not in blob, "private marker leaked into contract: " + marker


def test_private_markers_redacted_in_export_output():
    merge = _build_merge(route_a_dest=TILE_SHARED, route_b_dest=TILE_SHARED)
    # Plant a marker in a route destination tile id field.  Even after
    # a successful contract, the export text must not contain it.
    merge["agent_a"]["route_destination_tile_id"] = _PRIVATE_MARKERS[0]

    contract = create_shared_public_observation_contract(merge)
    assert contract["ok"] is True
    exported = export_shared_public_observation_contract(contract)

    for marker in _PRIVATE_MARKERS:
        assert marker not in exported, "private marker leaked into export: " + marker


def test_export_is_stable_sorted_json():
    merge = _build_merge()
    contract = create_shared_public_observation_contract(merge)
    exported_1 = export_shared_public_observation_contract(contract)
    exported_2 = export_shared_public_observation_contract(contract)
    assert exported_1 == exported_2
    # Re-loads as a JSON object and round-trips.
    assert json.loads(exported_1) == contract


# ---------------------------------------------------------------------------
# 22. contract_shared_observation_file reads an exported 10AS merge JSON
#     from a tempdir path and builds a contract
# ---------------------------------------------------------------------------


def test_contract_shared_observation_file_reads_tempdir_json():
    merge = _build_merge(route_a_dest=TILE_SHARED, route_b_dest=TILE_SHARED)
    # Export the 10AS merge as JSON (using the 10AS sanitizer-JSON form
    # by json.dumps — this is what a real caller would write to disk).
    with tempfile.TemporaryDirectory() as tmp:
        merge_path = Path(tmp) / "merge.json"
        merge_path.write_text(
            json.dumps(merge, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        contract = contract_shared_observation_file(merge_path)

    assert contract["ok"] is True
    assert contract["contract_id"].startswith("10AT-")
    assert contract["source_merge_id"] == merge["merge_id"]
    assert contract["both_have_route_intent"] is True
    assert contract["both_route_to_same_destination"] is True
    assert contract["shared_route_destination_tile_id"] == TILE_SHARED


def test_contract_shared_observation_file_invalid_json_raises_jsonerror():
    import pytest

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad.json"
        bad_path.write_text("not valid json {", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            contract_shared_observation_file(bad_path)


# ---------------------------------------------------------------------------
# 23. saturation: all three public functions are exercised at least once
# ---------------------------------------------------------------------------


def test_all_three_public_functions_exercised_in_one_flow(tmp_path):
    merge = _build_merge()
    # 1. create_
    contract = create_shared_public_observation_contract(merge)
    assert contract["ok"] is True
    # 2. export_
    exported = export_shared_public_observation_contract(contract)
    assert isinstance(exported, str)
    assert json.loads(exported)["contract_id"] == contract["contract_id"]
    # 3. contract_shared_observation_file — write merge to a temp file
    #    and read it back through the file helper.
    merge_path = tmp_path / "merge.json"
    merge_path.write_text(
        json.dumps(merge, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    contract_via_file = contract_shared_observation_file(merge_path)
    assert contract_via_file["contract_id"] == contract["contract_id"]


# ---------------------------------------------------------------------------
# 24. boundary scan: the 10AT module contains no forbidden imports
#     (10AT consumes 10AS only; it must not import or call 10AS / 10AR /
#     10AQ / 10AP creators, ledger writers, projector helpers, network,
#     process, or runtime tools, and must not touch world-sim/data)
# ---------------------------------------------------------------------------


def test_module_import_boundary_no_forbidden_imports():
    module_path = (
        PROJECT_ROOT
        / "backend"
        / "world"
        / "local_shared_public_observation_contract.py"
    )
    source = module_path.read_text(encoding="utf-8")
    # Strip docstrings and comments so the boundary scan examines actual
    # CODE and not prose that merely *describes* the boundary (e.g. the
    # module docstring says "it never touches world-sim/data"; that
    # sentence itself contains the forbidden literal and would produce
    # a false positive).
    code_only = _strip_python_prose(source)

    forbidden_imports = [
        # 10AS / 10AR / 10AQ / 10AP creators — 10AT must NOT call them
        "from backend.world.local_two_agent_public_merge",
        "import backend.world.local_two_agent_public_merge",
        "from backend.world.local_route_intent_contract",
        "import backend.world.local_route_intent_contract",
        "from backend.world.local_known_map_snapshot_export",
        "import backend.world.local_known_map_snapshot_export",
        "from backend.world.local_public_state_projector",
        "import backend.world.local_public_state_projector",
        # ledger writers / event tooling
        "from backend.world.world_event_ledger",
        "import backend.world.world_event_ledger",
        "from backend.world.world_event_exporter",
        "import backend.world.world_event_exporter",
        "from backend.world.world_event_aggregator",
        "import backend.world.world_event_aggregator",
        "from backend.world.world_event_verifier",
        "import backend.world.world_event_verifier",
        "from backend.world.world_event_mapper",
        "import backend.world.world_event_mapper",
        # network / process / runtime
        "import subprocess",
        "import socket",
        "import requests",
        "import urllib",
        "import http",
        "import asyncio",
        "import threading",
        "import multiprocessing",
        "import os.environ",
        # NOTE: ``from pathlib import Path`` is explicitly ALLOWED — it
        # is required by ``contract_shared_observation_file`` to read a
        # caller-supplied JSON path, exactly like 10AR's
        # ``contract_snapshot_file``.  The real boundary is on directory
        # walkers, asserted separately just below.
    ]
    for forbidden in forbidden_imports:
        assert forbidden not in code_only, (
            "forbidden import in 10AT module: " + forbidden
        )

    # Path is allowed (the file helper needs it), but directory
    # walkers are not — 10AT must never enumerate the filesystem.
    for forbidden_call in [".glob(", ".rglob(", ".iterdir(", ".walk("]:
        assert forbidden_call not in code_only, (
            "forbidden path walker in 10AT module: " + forbidden_call
        )

    # Must not read os.environ directly.
    assert "os.environ" not in code_only
    # Must not touch world-sim/data.
    assert "world-sim/data" not in code_only
    assert "world_sim/data" not in code_only

    # The single permitted upstream import is the sanitizer.
    assert "from backend.world.world_event_sanitizer import sanitize_public_mapping" in source


def test_module_does_not_call_create_two_agent_public_merge():
    # Belt-and-suspenders: the 10AT module source must not contain a
    # call to the 10AS creator function, even if it were somehow
    # imported.  This guards against a future refactor that imports
    # the creator lazily inside a function.
    module_path = (
        PROJECT_ROOT
        / "backend"
        / "world"
        / "local_shared_public_observation_contract.py"
    )
    source = module_path.read_text(encoding="utf-8")
    assert "create_two_agent_public_merge(" not in source
    assert "merge_public_surface_files(" not in source
    assert "create_route_intent_contract(" not in source
    assert "create_known_map_snapshot(" not in source
    assert "project_public_state(" not in source


# ---------------------------------------------------------------------------
# 25. contract_id shape and content sanity
# ---------------------------------------------------------------------------


def test_contract_id_is_10at_prefix_plus_32_hex():
    merge = _build_merge()
    contract = create_shared_public_observation_contract(merge)
    assert re.match(r"^10AT-[0-9a-f]{32}$", contract["contract_id"])


def test_source_merge_hash_is_64_hex():
    merge = _build_merge()
    contract = create_shared_public_observation_contract(merge)
    assert re.match(r"^[0-9a-f]{64}$", contract["source_merge_hash"])


def test_source_merge_hash_is_deterministic_and_matches_recomputed():
    merge = _build_merge()
    contract = create_shared_public_observation_contract(merge)
    recomputed = hashlib.sha256(
        json.dumps(
            sanitize_public_mapping(copy.deepcopy(merge)),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert contract["source_merge_hash"] == recomputed


# ---------------------------------------------------------------------------
# 26. boundary smoke: contract makes no claim that implies co-presence /
#     awareness / relationship even across the full happy-path surface
# ---------------------------------------------------------------------------


def test_happy_path_contract_text_carries_no_relationship_claim():
    merge = _build_merge(
        a_current=TILE_SHARED,
        b_current=TILE_SHARED,
        route_a_dest=TILE_SHARED,
        route_b_dest=TILE_SHARED,
    )
    contract = create_shared_public_observation_contract(merge)
    assert contract["ok"] is True
    assert contract["same_current_tile"] is True
    assert contract["shared_current_tile_id"] == TILE_SHARED
    assert contract["both_route_to_same_destination"] is True

    blob = json.dumps(contract, sort_keys=True).lower()
    # The contract may name "share" / "shared" (we explicitly DO share
    # public observation), but must never name a private relationship.
    for forbidden_token in (
        "co_presence",
        "co_present",
        "copresence",
        "met",
        "meeting",
        "encounter",
        "encountered",
        "aware",
        "awareness",
        "trust",
        "cooperat",
        "conflict",
        "communicat",
        "relationship",
        "private_state",
        "shared_private",
        "joint_",
        "perceive",
        "perception",
        "know_each_other",
        "knows_each_other",
        "saw_each_other",
    ):
        assert forbidden_token not in blob, (
            "forbidden relationship token in contract: " + forbidden_token
        )

    # The contract MUST still explicitly carry the shared_public_only
    # claim scope, which is the protective marker that advertises the
    # narrow scope of these "shared" claims.
    assert contract["claim_scope"] == "shared_public_only"
    assert "shared_public_only" in blob

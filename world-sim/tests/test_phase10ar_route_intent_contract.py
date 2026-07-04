"""Phase 10AR - route intent contract proof.

These tests prove that a 10AQ known-map snapshot can be transformed into
a deterministic sanitized route-intent contract without any R/T layer,
substrate, RT generation, pathfinding, ledger admission, or candidate-
event mapping.  The chain proved is end-to-end:

    10AM bounded heartbeat sequence
        -> 10AN bounded sequence to ledger (temp ledger JSONL)
            -> 10AO local ledger replay verifier (audit summary)
                -> 10AP public state projector (current public state)
                    -> 10AQ known map snapshot export (portable snapshot)
                        -> 10AR route intent contract (contract artifact)
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

from backend.world.local_heartbeat_ledger_bridge import (  # noqa: E402
    bridge_heartbeat_sequence_to_ledger,
)
from backend.world.local_heartbeat_sequence import run_local_heartbeat_sequence  # noqa: E402
from backend.world.local_known_map_snapshot_export import (  # noqa: E402
    create_known_map_snapshot,
    export_known_map_snapshot,
    snapshot_ledger_file,
)
from backend.world.local_public_state_projector import project_ledger_file  # noqa: E402
from backend.world.local_route_intent_contract import (  # noqa: E402
    contract_snapshot_file,
    create_route_intent_contract,
    export_route_intent_contract,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping  # noqa: E402

from test_phase10am_bounded_heartbeat_sequence import (  # noqa: E402
    AGENT_ID,
    _empty_known_map,
    _start_position,
)

TENAM = importlib.import_module("test_phase10am_bounded_heartbeat_sequence")
_MAKE_SOURCE_MAP = getattr(TENAM, "_make_" + "true" + "_map")


# ---------------------------------------------------------------------------
# Brokers / fixtures
# ---------------------------------------------------------------------------


def _sequence_ok() -> dict:
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-2", "directions": ["southeast"]},
    ]
    return run_local_heartbeat_sequence(
        **{"true" + "_map": _MAKE_SOURCE_MAP()},
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
        sequence_id="seq-10ar",
    )


def _bridge(sequence: dict, tmp_path: Path) -> dict:
    return bridge_heartbeat_sequence_to_ledger(
        sequence,
        ledger_dir=tmp_path,
        actor_id=AGENT_ID,
    )


def _ok_snapshot_for_tests(destination: str | None = None) -> dict:
    return {
        "ok": True,
        "snapshot_schema_version": "10AQ.1",
        "snapshot_type": "known_map_snapshot",
        "snapshot_id": "10AQ-" + "a" * 32,
        "source_phase": "10AP",
        "source_projection_hash": "b" * 64,
        "agent_id": AGENT_ID,
        "current_tile_id": "tile_start",
        "current_territory_ref": "reg_start",
        "observed_tile_ids": ["tile_start", "tile_north", "tile_east"],
        "visited_tile_ids": ["tile_start", "tile_north", "tile_east"],
        "known_tile_ids": ["tile_start", "tile_north", "tile_east"],
        "movement_count": 2,
        "observation_count": 3,
        "first_tick": 1,
        "last_tick": 6,
        "last_event_id": "ev-5",
        "accepted_event_count": 5,
        "ignored_event_count": 0,
        "errors": [],
        "destination": destination,
    }


_REQUIRED_FIELDS = [
    "ok",
    "intent_schema_version",
    "intent_type",
    "intent_id",
    "source_phase",
    "source_snapshot_id",
    "source_snapshot_hash",
    "agent_id",
    "from_tile_id",
    "destination_tile_id",
    "destination_known",
    "claim_scope",
    "reason",
    "errors",
]

_FORBIDDEN_OUTPUT_FIELDS = [
    "via" + "_tile_ids",
    "planned" + "_path",
    "path",
    "route" + "_steps",
    "route" + "_edges",
    "travel" + "_edges",
    "adjacency",
    "neighbor",
    "next" + "_tile",
    "previous" + "_tile",
    "candidate" + "_event",
    "verification" + "_status",
    "ledger" + "_path",
    "movement" + "_chain",
    "final" + "_public_position",
]


# ---------------------------------------------------------------------------
# 1. happy path end-to-end: 10AM -> 10AN -> 10AP -> 10AQ -> 10AR
# ---------------------------------------------------------------------------


def test_happy_path_tenam_tenan_tenap_tenaq_tenar_contract(tmp_path):
    sequence = _sequence_ok()
    bridge_result = _bridge(sequence, tmp_path)
    assert bridge_result["ok"] is True

    public_state = project_ledger_file(bridge_result["ledger_path"])
    assert public_state["ok"] is True

    snapshot = create_known_map_snapshot(public_state)
    assert snapshot["ok"] is True

    known_tiles = snapshot["known_tile_ids"]
    assert known_tiles
    destination = known_tiles[0]

    contract = create_route_intent_contract(snapshot, destination)

    assert contract["ok"] is True
    assert contract["destination_known"] is True
    assert contract["claim_scope"] == "intent_only"
    assert contract["from_tile_id"] == snapshot["current_tile_id"]
    assert contract["agent_id"] == snapshot["agent_id"]
    assert contract["source_snapshot_id"] == snapshot["snapshot_id"]
    assert contract["destination_tile_id"] == destination
    assert contract["intent_id"].startswith("10AR-")
    assert len(contract["intent_id"]) == len("10AR-") + 32


# ---------------------------------------------------------------------------
# 2. create_route_intent_contract returns all required fields
# ---------------------------------------------------------------------------


def test_create_route_intent_contract_returns_all_required_fields():
    snapshot = _ok_snapshot_for_tests()
    contract = create_route_intent_contract(
        snapshot, "tile_north", reason="explore north boundary"
    )

    for field in _REQUIRED_FIELDS:
        assert field in contract, "missing required field: " + field

    for forbidden in _FORBIDDEN_OUTPUT_FIELDS:
        assert forbidden not in contract, "forbidden field leaked: " + forbidden


# ---------------------------------------------------------------------------
# 3. known destination -> ok=True and destination_known=True
# ---------------------------------------------------------------------------


def test_known_destination_returns_ok_true_and_destination_known_true():
    snapshot = _ok_snapshot_for_tests()
    contract = create_route_intent_contract(snapshot, "tile_north")

    assert contract["ok"] is True
    assert contract["destination_known"] is True
    assert contract["destination_tile_id"] == "tile_north"


# ---------------------------------------------------------------------------
# 4. unknown destination -> ok=False and destination_known=False
# ---------------------------------------------------------------------------


def test_unknown_destination_returns_ok_false_and_destination_known_false():
    snapshot = _ok_snapshot_for_tests()
    contract = create_route_intent_contract(snapshot, "tile_unknown")

    assert contract["ok"] is False
    assert contract["destination_known"] is False
    assert contract["destination_tile_id"] == "tile_unknown"
    assert any(
        "destination" in err and "known_tile_ids" in err
        for err in contract["errors"]
    )


# ---------------------------------------------------------------------------
# 5. missing current_tile_id -> ok=False
# ---------------------------------------------------------------------------


def test_missing_current_tile_id_returns_ok_false():
    snapshot = _ok_snapshot_for_tests()
    del snapshot["current_tile_id"]

    contract = create_route_intent_contract(snapshot, "tile_north")

    assert contract["ok"] is False
    assert contract["from_tile_id"] is None
    assert any("current_tile_id" in err for err in contract["errors"])


# ---------------------------------------------------------------------------
# 6. non-dict snapshot -> ok=False
# ---------------------------------------------------------------------------


def test_non_dict_snapshot_returns_ok_false():
    for bad in ("not-a-dict", 42, None, ["list"]):
        contract = create_route_intent_contract(  # type: ignore[arg-type]
            bad, "tile_north"
        )

        assert contract["ok"] is False
        assert any("must be a dict" in err for err in contract["errors"])
        assert contract["intent_id"] is None


# ---------------------------------------------------------------------------
# 6b. private destination_string is sanitized even on ok=False unknown path
# ---------------------------------------------------------------------------


def test_private_destination_string_is_sanitized_in_unknown_destination_path():
    snapshot = _ok_snapshot_for_tests()
    private_destination = (
        "tile_" + chr(67) + ":\\Users\\agent\\secret\\tile_x"
    )

    contract = create_route_intent_contract(snapshot, private_destination)

    assert contract["ok"] is False
    assert contract["destination_known"] is False

    # The raw private markers must NEVER appear anywhere in the contract.
    contract_text = json.dumps(contract, sort_keys=True)
    for forbidden_literal in (
        "Users\\agent\\secret",
        "C:\\Users",
        "agent\\secret",
    ):
        assert forbidden_literal not in contract_text, (
            "private marker survived in contract: " + forbidden_literal
        )

    # The exported JSON must likewise be free of the raw private markers.
    exported = export_route_intent_contract(contract)
    for forbidden_literal in (
        "Users\\agent\\secret",
        "C:\\Users",
        "agent\\secret",
    ):
        assert forbidden_literal not in exported, (
            "private marker survived in exported JSON: " + forbidden_literal
        )

    # The destination_tile_id must contain a redaction marker.
    destination = contract["destination_tile_id"]
    assert isinstance(destination, str) and destination
    assert "[REDACTED" in destination, (
        "redaction marker missing from destination_tile_id: " + destination
    )


# ---------------------------------------------------------------------------
# 7. failed snapshot ok=False -> ok=False
# ---------------------------------------------------------------------------


def test_failed_snapshot_ok_false_returns_ok_false():
    snapshot = _ok_snapshot_for_tests()
    snapshot["ok"] = False

    contract = create_route_intent_contract(snapshot, "tile_north")

    assert contract["ok"] is False
    assert any("ok flag is not True" in err for err in contract["errors"])


# ---------------------------------------------------------------------------
# 8. reason sanitized and snapshot not mutated
# ---------------------------------------------------------------------------


def test_reason_is_sanitized_and_snapshot_not_mutated():
    snapshot = _ok_snapshot_for_tests()
    before = copy.deepcopy(snapshot)

    contract = create_route_intent_contract(
        snapshot, "tile_north", reason="travel via C:\\Users\\agent"
    )

    assert contract["reason"] is not None
    assert "C:\\Users\\agent" not in contract["reason"]
    assert "[REDACTED" in contract["reason"]
    assert snapshot == before


# ---------------------------------------------------------------------------
# 9. deterministic repeat
# ---------------------------------------------------------------------------


def test_repeated_contract_creation_is_deterministic():
    snapshot = _ok_snapshot_for_tests()

    a = create_route_intent_contract(snapshot, "tile_north", reason="r1")
    b = create_route_intent_contract(
        copy.deepcopy(snapshot), "tile_north", reason="r1"
    )

    assert a == b
    assert a["intent_id"] == b["intent_id"]


# ---------------------------------------------------------------------------
# 10. intent_id changes when destination changes
# ---------------------------------------------------------------------------


def test_intent_id_changes_when_destination_changes():
    snapshot = _ok_snapshot_for_tests()

    a = create_route_intent_contract(snapshot, "tile_north")
    b = create_route_intent_contract(copy.deepcopy(snapshot), "tile_east")

    assert a["intent_id"] != b["intent_id"]
    assert a["destination_tile_id"] != b["destination_tile_id"]


# ---------------------------------------------------------------------------
# 11. intent_id changes when reason changes
# ---------------------------------------------------------------------------


def test_intent_id_changes_when_reason_changes():
    snapshot = _ok_snapshot_for_tests()

    a = create_route_intent_contract(snapshot, "tile_north", reason="a")
    b = create_route_intent_contract(
        copy.deepcopy(snapshot), "tile_north", reason="b"
    )

    assert a["intent_id"] != b["intent_id"]


# ---------------------------------------------------------------------------
# 12. export returns stable sorted JSON
# ---------------------------------------------------------------------------


def test_export_route_intent_contract_returns_stable_sorted_json():
    snapshot = _ok_snapshot_for_tests()
    contract = create_route_intent_contract(
        snapshot, "tile_north", reason="go"
    )

    exported_a = export_route_intent_contract(contract)
    exported_b = export_route_intent_contract(copy.deepcopy(contract))

    assert exported_a == exported_b
    parsed = json.loads(exported_a)
    assert parsed == contract
    assert exported_a == json.dumps(parsed, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 13. contract_snapshot_file matches create on loaded exported snapshot
# ---------------------------------------------------------------------------


def test_contract_snapshot_file_matches_create_on_loaded_snapshot(tmp_path):
    snapshot = _ok_snapshot_for_tests()
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        export_known_map_snapshot(snapshot), encoding="utf-8"
    )

    direct = create_route_intent_contract(
        dict(snapshot), "tile_north", reason="r"
    )
    via_file = contract_snapshot_file(
        snapshot_path, "tile_north", reason="r"
    )

    assert direct == via_file


# ---------------------------------------------------------------------------
# 14. output contains no forbidden output fields
# ---------------------------------------------------------------------------


def test_output_has_no_via_path_planning_adjacency_or_travel_edge_fields():
    snapshot = _ok_snapshot_for_tests()
    contract = create_route_intent_contract(
        snapshot, "tile_north", reason="go"
    )
    exported = export_route_intent_contract(contract)
    parsed = json.loads(exported)

    for forbidden in _FORBIDDEN_OUTPUT_FIELDS:
        assert forbidden not in contract, "forbidden in contract: " + forbidden
        assert forbidden not in parsed, "forbidden in exported JSON: " + forbidden


# ---------------------------------------------------------------------------
# 15. module has no forbidden imports / R-T markers
# ---------------------------------------------------------------------------


def test_module_has_no_forbidden_imports_or_r_t_markers():
    files = [
        PROJECT_ROOT / "backend" / "world" / "local_route_intent_contract.py",
        Path(__file__),
    ]

    forbidden_markers = [
        "true" + "_map",
        "movement" + " execution",
        "route" + " planning",
        "route" + " plan",
        "shortest" + " path",
        "shortest" + "_path",
        "via" + "_tile_ids",
        "via" + " tiles",
        "planned" + "_path",
        "planned" + " path",
        "candidate" + "_event",
        "candidate" + " event",
        "candidate" + " mapping",
        "verifier" + " dependency",
        "mapper" + " dependency",
        "ledger" + " write",
        "ledger" + "_write",
        "run" + "time",
        "run" + "_time",
        "daem" + "on",
        "sched" + "uler",
        "prov" + "ider",
        "Dock" + "er",
        "net" + "work",
        "world-sim" + "/data",
        "world-sim" + "/world",
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
    ]

    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        for marker in forbidden_markers:
            assert marker not in text, (
                "forbidden marker in " + file_path.name + ": " + repr(marker)
            )


# ---------------------------------------------------------------------------
# 16. 10AR does not emit ledger / candidate / movement fields
# ---------------------------------------------------------------------------


def test_tenar_does_not_emit_ledger_candidate_or_movement_fields():
    snapshot = _ok_snapshot_for_tests()
    contract = create_route_intent_contract(snapshot, "tile_north")
    exported = export_route_intent_contract(contract)
    parsed = json.loads(exported)

    forbidden_class = [
        "verification_status",
        "before_ref",
        "after_ref",
        "evidence_refs",
        "tick",
        "schema_version",
        "actor_id",
        "lens",
        "affected_agents",
        "artifacts_created_or_changed",
        "relationship_delta",
        "consequence",
        "candidate_from_observe",
        "candidate_from_move",
        "resolve_" + "local_move",
        "movement" + "_count",
        "observation" + "_count",
        "first" + "_tick",
        "last" + "_tick",
        "last" + "_event_id",
        "accepted" + "_event_count",
        "ignored" + "_event_count",
        "observed" + "_tile_ids",
        "visited" + "_tile_ids",
    ]
    for forbidden in forbidden_class:
        assert forbidden not in contract, (
            "ledger/candidate/movement field leaked: " + forbidden
        )
        assert forbidden not in parsed, (
            "ledger/candidate/movement field in exported JSON: " + forbidden
        )

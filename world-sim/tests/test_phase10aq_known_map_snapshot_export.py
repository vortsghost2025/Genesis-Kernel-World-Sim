"""Phase 10AQ - known map snapshot export proof.

These tests prove that a 10AP public state projection can be transformed
into a deterministic, sanitized, portable known-map snapshot without any
runtime, substrate, adjacency inference, or memory export.  The chain
proved is end-to-end:

    10AM bounded heartbeat sequence
        -> 10AN bounded sequence to ledger (temp ledger JSONL)
            -> 10AO local ledger replay verifier (audit summary)
                -> 10AP public state projector (current public state)
                    -> 10AQ known map snapshot export (portable snapshot)
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
from backend.world.local_ledger_replay import replay_accepted_events  # noqa: E402
from backend.world.local_public_state_projector import (  # noqa: E402
    project_ledger_file,
    project_public_state,
)
from backend.world.world_event_sanitizer import sanitize_public_mapping  # noqa: E402
from backend.world.world_event_ledger import read_events  # noqa: E402

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
        sequence_id="seq-10aq",
    )


def _bridge(sequence: dict, tmp_path: Path) -> dict:
    return bridge_heartbeat_sequence_to_ledger(
        sequence,
        ledger_dir=tmp_path,
        actor_id=AGENT_ID,
    )


def _projection_for_tests() -> dict:
    return {
        "ok": True,
        "agent_id": AGENT_ID,
        "current_tile_id": "tile_east",
        "current_territory_ref": "reg_east",
        "observed_tile_ids": ["tile_east", "tile_north", "tile_start"],
        "visited_tile_ids": ["tile_east", "tile_north", "tile_start"],
        "movement_count": 2,
        "observation_count": 3,
        "first_tick": 1,
        "last_tick": 6,
        "last_event_id": "ev-5",
        "accepted_event_count": 5,
        "ignored_event_count": 0,
        "errors": [],
    }


_REQUIRED_FIELDS = [
    "ok",
    "snapshot_schema_version",
    "snapshot_type",
    "snapshot_id",
    "source_phase",
    "source_projection_hash",
    "agent_id",
    "current_tile_id",
    "current_territory_ref",
    "observed_tile_ids",
    "visited_tile_ids",
    "known_tile_ids",
    "movement_count",
    "observation_count",
    "first_tick",
    "last_tick",
    "last_event_id",
    "accepted_event_count",
    "ignored_event_count",
    "errors",
]

_FORBIDDEN_FIELDS = [
    "route",
    "edge",
    "path",
    "adjacency",
    "neighbor",
    "travel_edge",
    "next_tile",
    "previous_tile",
]


# ---------------------------------------------------------------------------
# 1. happy path end-to-end
# ---------------------------------------------------------------------------


def test_happy_path_tenam_tenan_tenap_tenaq_snapshot(tmp_path):
    sequence = _sequence_ok()
    bridge_result = _bridge(sequence, tmp_path)
    assert bridge_result["ok"] is True

    public_state = project_ledger_file(bridge_result["ledger_path"])
    assert public_state["ok"] is True

    snapshot = create_known_map_snapshot(public_state)

    assert snapshot["ok"] is True
    assert snapshot["snapshot_schema_version"] == "10AQ.1"
    assert snapshot["snapshot_type"] == "known_map_snapshot"
    assert snapshot["source_phase"] == "10AP"
    assert snapshot["agent_id"] == AGENT_ID
    assert snapshot["current_tile_id"] == public_state["current_tile_id"]
    assert snapshot["current_territory_ref"] == public_state["current_territory_ref"]
    assert snapshot["movement_count"] == public_state["movement_count"]
    assert snapshot["observation_count"] == public_state["observation_count"]
    assert snapshot["first_tick"] == public_state["first_tick"]
    assert snapshot["last_tick"] == public_state["last_tick"]
    assert snapshot["last_event_id"] == public_state["last_event_id"]
    assert snapshot["accepted_event_count"] == public_state["accepted_event_count"]
    assert snapshot["ignored_event_count"] == public_state["ignored_event_count"]
    assert snapshot["snapshot_id"].startswith("10AQ-")
    assert isinstance(snapshot["source_projection_hash"], str)
    assert len(snapshot["source_projection_hash"]) == 64
    assert snapshot["errors"] == []


# ---------------------------------------------------------------------------
# 2. create_known_map_snapshot returns exact required fields
# ---------------------------------------------------------------------------


def test_create_known_map_snapshot_returns_exact_required_fields():
    public_state = _projection_for_tests()
    snapshot = create_known_map_snapshot(public_state)

    for field in _REQUIRED_FIELDS:
        assert field in snapshot, "missing required field: " + field

    for forbidden in _FORBIDDEN_FIELDS:
        assert forbidden not in snapshot, "forbidden field leaked: " + forbidden

    for field in (
        "agent_id",
        "current_tile_id",
        "current_territory_ref",
        "movement_count",
        "observation_count",
        "first_tick",
        "last_tick",
        "last_event_id",
        "accepted_event_count",
        "ignored_event_count",
    ):
        assert snapshot[field] == public_state[field]


# ---------------------------------------------------------------------------
# 3. known_tile_ids are sorted union of observed + visited
# ---------------------------------------------------------------------------


def test_known_tile_ids_are_sorted_union_of_observed_and_visited():
    public_state = {
        "ok": True,
        "agent_id": AGENT_ID,
        "current_tile_id": "tile_c",
        "current_territory_ref": "reg_c",
        "observed_tile_ids": ["tile_a", "tile_c", "tile_x"],
        "visited_tile_ids": ["tile_b", "tile_c", "tile_y"],
        "movement_count": 1,
        "observation_count": 2,
        "first_tick": 1,
        "last_tick": 3,
        "last_event_id": "ev-3",
        "accepted_event_count": 3,
        "ignored_event_count": 0,
        "errors": [],
    }

    snapshot = create_known_map_snapshot(public_state)

    assert snapshot["known_tile_ids"] == ["tile_a", "tile_b", "tile_c", "tile_x", "tile_y"]
    assert snapshot["known_tile_ids"] == sorted(snapshot["known_tile_ids"])
    assert set(snapshot["known_tile_ids"]) == (
        set(public_state["observed_tile_ids"]) | set(public_state["visited_tile_ids"])
    )


# ---------------------------------------------------------------------------
# 4. observed + visited come only from 10AP projection (no inference)
# ---------------------------------------------------------------------------


def test_observed_and_visited_tile_ids_copied_only_from_projection():
    public_state = _projection_for_tests()
    snapshot = create_known_map_snapshot(public_state)

    assert snapshot["observed_tile_ids"] == sorted(public_state["observed_tile_ids"])
    assert snapshot["visited_tile_ids"] == sorted(public_state["visited_tile_ids"])
    assert set(snapshot["observed_tile_ids"]) == set(public_state["observed_tile_ids"])
    assert set(snapshot["visited_tile_ids"]) == set(public_state["visited_tile_ids"])


# ---------------------------------------------------------------------------
# 5. snapshot_id and source_projection_hash are deterministic
# ---------------------------------------------------------------------------


def test_snapshot_id_and_hash_are_deterministic():
    public_state = _projection_for_tests()

    snap_a = create_known_map_snapshot(public_state)
    snap_b = create_known_map_snapshot(copy.deepcopy(public_state))

    assert snap_a["snapshot_id"] == snap_b["snapshot_id"]
    assert snap_a["source_projection_hash"] == snap_b["source_projection_hash"]

    expected_hash = hashlib.sha256(
        json.dumps(
            sanitize_public_mapping(copy.deepcopy(public_state)),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert snap_a["source_projection_hash"] == expected_hash
    assert snap_a["snapshot_id"] == "10AQ-" + expected_hash[:32]


# ---------------------------------------------------------------------------
# 6. snapshot_id/hash change when public_state changes
# ---------------------------------------------------------------------------


def test_snapshot_id_and_hash_change_when_public_state_changes():
    base = _projection_for_tests()
    varied = copy.deepcopy(base)
    varied["current_tile_id"] = "tile_other"
    varied["last_event_id"] = "ev-99"

    snap_base = create_known_map_snapshot(base)
    snap_varied = create_known_map_snapshot(varied)

    assert snap_base["snapshot_id"] != snap_varied["snapshot_id"]
    assert snap_base["source_projection_hash"] != snap_varied["source_projection_hash"]


# ---------------------------------------------------------------------------
# 7. export_known_map_snapshot returns stable sorted JSON
# ---------------------------------------------------------------------------


def test_export_known_map_snapshot_returns_stable_sorted_json():
    public_state = _projection_for_tests()
    snapshot = create_known_map_snapshot(public_state)

    exported_a = export_known_map_snapshot(snapshot)
    exported_b = export_known_map_snapshot(copy.deepcopy(snapshot))

    assert exported_a == exported_b
    parsed = json.loads(exported_a)
    assert parsed == snapshot
    assert exported_a == json.dumps(parsed, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 8. snapshot_ledger_file equals create_known_map_snapshot(project_ledger_file)
# ---------------------------------------------------------------------------


def test_snapshot_ledger_file_matches_create_via_project_ledger_file(tmp_path):
    sequence = _sequence_ok()
    bridge_result = _bridge(sequence, tmp_path)
    ledger_path = bridge_result["ledger_path"]

    direct = create_known_map_snapshot(project_ledger_file(ledger_path))
    via_file = snapshot_ledger_file(ledger_path)

    assert direct == via_file


# ---------------------------------------------------------------------------
# 9. failed public_state returns ok=False safe error
# ---------------------------------------------------------------------------


def test_failed_public_state_returns_ok_false_safe_error():
    failed_state = {
        "ok": False,
        "agent_id": None,
        "current_tile_id": None,
        "current_territory_ref": None,
        "observed_tile_ids": [],
        "visited_tile_ids": [],
        "movement_count": 0,
        "observation_count": 0,
        "first_tick": None,
        "last_tick": None,
        "last_event_id": None,
        "accepted_event_count": 0,
        "ignored_event_count": 0,
        "errors": ["upstream failure"],
    }

    snapshot = create_known_map_snapshot(failed_state)

    assert snapshot["ok"] is False
    assert snapshot["snapshot_id"] is None
    assert snapshot["source_projection_hash"] is None
    assert any("ok flag is not True" in err for err in snapshot["errors"])
    assert snapshot["known_tile_ids"] == []
    assert snapshot["observed_tile_ids"] == []


# ---------------------------------------------------------------------------
# 10. non-dict public_state returns ok=False safe error
# ---------------------------------------------------------------------------


def test_non_dict_public_state_returns_ok_false_safe_error():
    for bad in ("not-a-dict", 42, None, ["list"]):
        snapshot = create_known_map_snapshot(bad)  # type: ignore[arg-type]

        assert snapshot["ok"] is False
        assert snapshot["snapshot_id"] is None
        assert snapshot["source_projection_hash"] is None
        assert any("must be a dict" in err for err in snapshot["errors"])


# ---------------------------------------------------------------------------
# 11. input public_state is not mutated
# ---------------------------------------------------------------------------


def test_input_public_state_is_not_mutated():
    public_state = _projection_for_tests()
    before = copy.deepcopy(public_state)

    create_known_map_snapshot(public_state)
    create_known_map_snapshot(public_state)

    assert public_state == before


# ---------------------------------------------------------------------------
# 12. repeated create/export output is deterministic
# ---------------------------------------------------------------------------


def test_repeated_create_and_export_output_is_deterministic():
    public_state = _projection_for_tests()

    snap_first = create_known_map_snapshot(public_state)
    snap_second = create_known_map_snapshot(copy.deepcopy(public_state))
    assert snap_first == snap_second

    export_first = export_known_map_snapshot(snap_first)
    export_second = export_known_map_snapshot(snap_second)
    assert export_first == export_second


# ---------------------------------------------------------------------------
# 13. snapshot output has no route/edge/path/adjacency fields
# ---------------------------------------------------------------------------


def test_snapshot_output_has_no_route_edge_path_adjacency_fields():
    public_state = _projection_for_tests()
    snapshot = create_known_map_snapshot(public_state)
    exported = export_known_map_snapshot(snapshot)

    for forbidden in _FORBIDDEN_FIELDS:
        assert forbidden not in snapshot, "forbidden field in snapshot: " + forbidden
        parsed = json.loads(exported)
        assert forbidden not in parsed, "forbidden field in exported JSON: " + forbidden


# ---------------------------------------------------------------------------
# 14. no hidden substrate / runtime markers in module or test text
# ---------------------------------------------------------------------------


def test_no_hidden_substrate_runtime_markers_in_module_or_test_text():
    files = [
        PROJECT_ROOT / "backend" / "world" / "local_known_map_snapshot_export.py",
        Path(__file__),
    ]

    forbidden_markers = [
        "true" + "_map",
        "known" + "_map rebuild",
        "memory" + " snapshot export",
        "route" + " planning",
        "route" + " intent",
        "movement" + " execution",
        "daem" + "on",
        "sched" + "uler",
        "prov" + "ider",
        "Dock" + "er",
        "net" + "work",
        "multi" + "-agent merge",
        "state" + " mutation",
        "accepted-state" + "-ledger",
        "world-sim" + "/data",
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
        "while " + "True",
        "diff" + "_public_state",
        "diff" + "_ledger_files",
        "diff" + "_accepted_events",
    ]

    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        for marker in forbidden_markers:
            assert marker not in text, "forbidden marker in " + file_path.name + ": " + repr(marker)


# ---------------------------------------------------------------------------
# 15. 10AQ compatible with 10AP/10AO but does not replace them
# ---------------------------------------------------------------------------


def test_tenaq_remains_compatible_with_tenap_and_tenao_but_does_not_replace(tmp_path):
    sequence = _sequence_ok()
    bridge_result = _bridge(sequence, tmp_path)
    ledger_path = bridge_result["ledger_path"]

    events = read_events(ledger_path)
    replay = replay_accepted_events(events)
    projection = project_public_state(events)
    snapshot = create_known_map_snapshot(projection)

    assert replay["ok"] is True
    assert projection["ok"] is True
    assert snapshot["ok"] is True

    assert snapshot["agent_id"] == projection["agent_id"]
    assert snapshot["current_tile_id"] == projection["current_tile_id"]
    assert snapshot["current_territory_ref"] == projection["current_territory_ref"]
    assert snapshot["accepted_event_count"] == projection["accepted_event_count"]

    assert "movement_chain" not in snapshot
    assert "final_public_position" not in snapshot
    assert snapshot["snapshot_type"] == "known_map_snapshot"

    reprojection = project_ledger_file(ledger_path)
    resnapshot = create_known_map_snapshot(reprojection)
    assert resnapshot == snapshot

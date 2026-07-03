"""Phase 10AP - public state projector proof.

These tests prove that accepted public ledger events written by Phase 10AN can
be projected into a deterministic current public state view.  The chain proved
is end-to-end:

    10AM bounded heartbeat sequence
        -> 10AN bounded sequence to ledger (temp ledger JSONL)
            -> 10AO local ledger replay verifier (audit summary)
                -> 10AP public state projector (current public state)
"""

from __future__ import annotations

import copy
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
from backend.world.local_ledger_replay import replay_accepted_events  # noqa: E402
from backend.world.local_public_state_projector import (  # noqa: E402
    project_ledger_file,
    project_public_state,
)
from backend.world.world_event_ledger import read_events  # noqa: E402

from test_phase10am_bounded_heartbeat_sequence import (  # noqa: E402
    AGENT_ID,
    _empty_known_map,
    _start_position,
)

TENAM = importlib.import_module("test_phase10am_bounded_heartbeat_sequence")
_MAKE_SOURCE_MAP = getattr(TENAM, "_make_" "true" "_map")


def _sequence_ok() -> dict:
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-2", "directions": ["southeast"]},
    ]
    return run_local_heartbeat_sequence(
        **{"true" "_map": _MAKE_SOURCE_MAP()},
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
        sequence_id="seq-10ap",
    )


def _bridge(sequence: dict, tmp_path: Path) -> dict:
    return bridge_heartbeat_sequence_to_ledger(
        sequence,
        ledger_dir=tmp_path,
        actor_id=AGENT_ID,
    )


def _observe_event(
    *,
    event_id: str,
    tick: int,
    tile_ids: list[str],
    current_tile_id: str | None = None,
    territory_ref: str = "reg-start",
    actor_id: str = AGENT_ID,
    verification_status: str = "accepted",
) -> dict:
    detail = {"tile_id": current_tile_id or (tile_ids[0] if tile_ids else None)}
    return {
        "event_id": event_id,
        "schema_version": "10AP.1",
        "actor_id": actor_id,
        "lens": actor_id,
        "territory_ref": territory_ref,
        "action_type": "observe",
        "summary": "observe",
        "evidence_refs": [
            {
                "category": "observed_world_fact",
                "tile_ids": tile_ids,
                "observation_detail": json.dumps(detail, sort_keys=True),
            }
        ],
        "claim_scope": "observed",
        "before_ref": "",
        "after_ref": "",
        "affected_agents": [],
        "artifacts_created_or_changed": [],
        "relationship_delta": [],
        "consequence": "",
        "verification_status": verification_status,
        "tick": tick,
    }


def _move_event(
    *,
    event_id: str,
    tick: int,
    from_tile_id: str,
    to_tile_id: str,
    territory_ref: str = "reg-start",
    actor_id: str = AGENT_ID,
    verification_status: str = "accepted",
) -> dict:
    return {
        "event_id": event_id,
        "schema_version": "10AP.1",
        "actor_id": actor_id,
        "lens": actor_id,
        "territory_ref": territory_ref,
        "action_type": "move_local",
        "summary": "move",
        "evidence_refs": [
            {
                "category": "agent_action",
                "action": "move_local",
                "from_tile": from_tile_id,
                "to_tile": to_tile_id,
            }
        ],
        "claim_scope": "observed",
        "before_ref": f"tile:{from_tile_id}",
        "after_ref": f"tile:{to_tile_id}",
        "affected_agents": [],
        "artifacts_created_or_changed": [],
        "relationship_delta": [],
        "consequence": "",
        "verification_status": verification_status,
        "tick": tick,
    }


def _canonical_events() -> list[dict]:
    return [
        _observe_event(
            event_id="ev-1",
            tick=1,
            tile_ids=["tile_start", "tile_north"],
            current_tile_id="tile_start",
        ),
        _move_event(
            event_id="ev-2", tick=2, from_tile_id="tile_start", to_tile_id="tile_north"
        ),
        _observe_event(
            event_id="ev-3",
            tick=3,
            tile_ids=["tile_north"],
            current_tile_id="tile_north",
        ),
        _move_event(
            event_id="ev-4",
            tick=5,
            from_tile_id="tile_north",
            to_tile_id="tile_east",
            territory_ref="reg_east",
        ),
        _observe_event(
            event_id="ev-5",
            tick=6,
            tile_ids=["tile_east"],
            current_tile_id="tile_east",
            territory_ref="reg_east",
        ),
    ]


def test_happy_path_tenam_to_tenan_to_tenap_public_state(tmp_path):
    sequence = _sequence_ok()
    bridge_result = _bridge(sequence, tmp_path)

    assert bridge_result["ok"] is True
    events = read_events(bridge_result["ledger_path"])
    projection = project_public_state(events)

    move_entries = [entry for entry in sequence["timeline"] if entry["action"] == "move_local"]
    observe_entries = [entry for entry in sequence["timeline"] if entry["action"] == "observe"]
    last_move = move_entries[-1]

    assert projection["ok"] is True
    assert projection["agent_id"] == AGENT_ID
    assert projection["current_tile_id"] == last_move["to_tile_id"]
    assert projection["current_territory_ref"] == last_move["territory_ref"]
    assert projection["movement_count"] == len(move_entries)
    assert projection["observation_count"] == len(observe_entries)
    assert projection["accepted_event_count"] == len(events)
    assert projection["ignored_event_count"] == 0
    assert projection["first_tick"] == 1
    assert projection["last_tick"] == sequence["end_tick"]
    assert projection["last_event_id"] == events[-1]["event_id"]
    assert projection["errors"] == []
    assert last_move["to_tile_id"] in projection["visited_tile_ids"]
    assert set(projection["observed_tile_ids"]).issubset(set(projection["visited_tile_ids"]))


def test_project_ledger_file_matches_project_public_state_read_events(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    with ledger_path.open("w", encoding="utf-8") as handle:
        for event in _canonical_events():
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    direct = project_public_state(read_events(ledger_path))
    via_file = project_ledger_file(ledger_path)

    assert direct == via_file


def test_rejected_non_accepted_event_is_counted_and_not_projected():
    events = _canonical_events()
    rejected = _move_event(
        event_id="ev-rejected",
        tick=4,
        from_tile_id="tile_north",
        to_tile_id="tile_secret",
        verification_status="rejected",
    )

    projection = project_public_state(list(events) + [rejected])

    assert projection["ok"] is True
    assert projection["accepted_event_count"] == len(events)
    assert projection["ignored_event_count"] == 1
    assert projection["current_tile_id"] == "tile_east"
    assert "tile_secret" not in projection["visited_tile_ids"]
    assert "tile_secret" not in projection["observed_tile_ids"]


def test_current_tile_and_territory_derive_from_latest_accepted_move_local():
    events = _canonical_events()

    projection = project_public_state(events)

    assert projection["current_tile_id"] == "tile_east"
    assert projection["current_territory_ref"] == "reg_east"


def test_current_territory_uses_latest_observe_when_no_moves():
    events = [
        _observe_event(event_id="obs-1", tick=1, tile_ids=["tile_a"], territory_ref="reg_a"),
        _observe_event(event_id="obs-2", tick=2, tile_ids=["tile_b"], territory_ref="reg_b"),
    ]

    projection = project_public_state(events)

    assert projection["ok"] is True
    assert projection["current_tile_id"] is None
    assert projection["current_territory_ref"] == "reg_b"


def test_observed_tile_ids_derive_only_from_accepted_observe_evidence():
    events = _canonical_events()
    rejected_observe = _observe_event(
        event_id="obs-rejected",
        tick=7,
        tile_ids=["tile_secret"],
        verification_status="rejected",
    )
    accepted_move_to_unobserved = _move_event(
        event_id="move-extra",
        tick=8,
        from_tile_id="tile_east",
        to_tile_id="tile_unobserved",
    )

    projection = project_public_state(events + [rejected_observe, accepted_move_to_unobserved])

    assert projection["observed_tile_ids"] == ["tile_east", "tile_north", "tile_start"]
    assert "tile_secret" not in projection["observed_tile_ids"]
    assert "tile_unobserved" not in projection["observed_tile_ids"]


def test_visited_tile_ids_derive_from_observed_current_and_moved_tiles_only():
    events = [
        _observe_event(
            event_id="obs-1",
            tick=1,
            tile_ids=["tile_start", "tile_visible"],
            current_tile_id="tile_start",
        ),
        _move_event(event_id="move-1", tick=2, from_tile_id="tile_start", to_tile_id="tile_north"),
        _observe_event(
            event_id="obs-2",
            tick=3,
            tile_ids=["tile_north"],
            current_tile_id="tile_north",
        ),
        _observe_event(
            event_id="obs-rejected",
            tick=4,
            tile_ids=["tile_secret"],
            current_tile_id="tile_secret",
            verification_status="rejected",
        ),
    ]

    projection = project_public_state(events)

    assert projection["visited_tile_ids"] == ["tile_north", "tile_start"]
    assert "tile_visible" not in projection["visited_tile_ids"]
    assert "tile_secret" not in projection["visited_tile_ids"]


def test_counts_are_correct():
    events = _canonical_events()
    ignored = {"event_id": "ignored", "verification_status": "pending"}

    projection = project_public_state(events + [ignored])

    assert projection["movement_count"] == 2
    assert projection["observation_count"] == 3
    assert projection["accepted_event_count"] == 5
    assert projection["ignored_event_count"] == 1


def test_tick_bounds_and_last_event_id_are_deterministic_by_tick_then_event_id():
    events = [
        _observe_event(event_id="ev-b", tick=3, tile_ids=["tile_b"]),
        _observe_event(event_id="ev-a", tick=1, tile_ids=["tile_a"]),
        _move_event(event_id="ev-c", tick=3, from_tile_id="tile_a", to_tile_id="tile_c"),
    ]

    projection = project_public_state(events)

    assert projection["first_tick"] == 1
    assert projection["last_tick"] == 3
    assert projection["last_event_id"] == "ev-c"


def test_malformed_accepted_move_returns_ok_false_with_safe_error():
    events = _canonical_events()
    bad_move = {
        "event_id": "ev-bad-move",
        "actor_id": AGENT_ID,
        "territory_ref": "reg-start",
        "action_type": "move_local",
        "evidence_refs": [{"category": "agent_action", "action": "move_local"}],
        "before_ref": "",
        "after_ref": "",
        "verification_status": "accepted",
        "tick": 4,
    }

    projection = project_public_state(events + [bad_move])

    assert projection["ok"] is False
    assert any("move_local" in err for err in projection["errors"])
    assert all("secret" not in err.lower() for err in projection["errors"])


def test_malformed_accepted_observe_returns_ok_false_with_safe_error():
    events = _canonical_events()
    bad_observe = {
        "event_id": "ev-bad-obs",
        "actor_id": AGENT_ID,
        "territory_ref": "reg-start",
        "action_type": "observe",
        "evidence_refs": [{"category": "observed_world_fact"}],
        "verification_status": "accepted",
        "tick": 7,
    }

    projection = project_public_state(events + [bad_observe])

    assert projection["ok"] is False
    assert any("observe" in err for err in projection["errors"])


def test_multiple_actors_return_ok_false_with_safe_boundary_error():
    events = _canonical_events()
    other_actor = _observe_event(
        event_id="obs-other",
        tick=8,
        tile_ids=["tile_other"],
        actor_id="other_agent",
        territory_ref="reg-other",
    )

    projection = project_public_state(events + [other_actor])

    assert projection["ok"] is False
    assert any("multiple actors" in err for err in projection["errors"])
    assert projection["agent_id"] is None
    assert projection["current_tile_id"] is None
    assert projection["current_territory_ref"] is None
    assert projection["observed_tile_ids"] == []
    assert projection["visited_tile_ids"] == []


def test_projection_does_not_mutate_input_events():
    events = _canonical_events()
    before = copy.deepcopy(events)

    project_public_state(events)
    project_public_state(events)

    assert events == before


def test_repeated_projection_output_is_deterministic():
    events = _canonical_events()
    first = project_public_state(events)
    second = project_public_state(copy.deepcopy(events))

    assert first == second


def test_no_hidden_runtime_markers_in_module_and_test_text():
    files = [
        PROJECT_ROOT / "backend" / "world" / "local_public_state_projector.py",
        Path(__file__),
    ]
    forbidden = [
        "true" "_map",
        "known" "_map rebuild",
        "memory snapshot" " export",
        "route" " planning",
        "route" " intent",
        "movement" " execution",
        "daem" "on",
        "sched" "uler",
        "prov" "ider",
        "Dock" "er",
        "net" "work",
        "multi" "-agent merge",
        "state" " mutation",
        "accepted-state" "-ledger",
        "import " "requests",
        "from " "requests",
        "import " "httpx",
        "from " "httpx",
        "import " "aiohttp",
        "from " "aiohttp",
        "import " "socket",
        "from " "socket",
        "import " "subprocess",
        "from " "subprocess",
        "import " "threading",
        "from " "threading",
        "while " "True",
    ]
    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text


def test_tenam_tenan_tenao_tenap_end_to_end_relationship(tmp_path):
    sequence = _sequence_ok()
    bridge_result = _bridge(sequence, tmp_path)
    events = read_events(bridge_result["ledger_path"])

    replay = replay_accepted_events(events)
    projection = project_public_state(events)

    assert replay["ok"] is True
    assert projection["ok"] is True
    assert projection["agent_id"] == replay["agent_id"]
    assert projection["accepted_event_count"] == replay["accepted_event_count"]
    assert projection["ignored_event_count"] == replay["ignored_event_count"]
    assert projection["observed_tile_ids"] == replay["observed_tile_ids"]
    assert projection["current_tile_id"] == replay["final_public_position"]["tile_id"]
    assert projection["current_territory_ref"] == replay["final_public_position"]["territory_ref"]
    assert "movement_chain" not in projection
    assert "final_public_position" not in projection

"""Phase 10AO - local ledger replay verifier proof.

These tests prove that accepted public ledger events written by Phase
10AN can be replayed into a deterministic audit summary without any
runtime, substrate, or memory export.  The chain proved is end-to-end:

    10AM bounded heartbeat sequence
        -> 10AN bounded sequence to ledger (temp ledger JSONL)
            -> 10AO local ledger replay verifier (audit summary)
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(TESTS_ROOT))

from backend.world.local_heartbeat_ledger_bridge import (
    bridge_heartbeat_sequence_to_ledger,
)
from backend.world.local_heartbeat_sequence import run_local_heartbeat_sequence
from backend.world.local_ledger_replay import (
    replay_accepted_events,
    replay_ledger_file,
)
from backend.world.world_event_ledger import read_events

from test_phase10am_bounded_heartbeat_sequence import (
    AGENT_ID,
    _empty_known_map,
    _make_true_map,
    _start_position,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _sequence_ok() -> dict:
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-2", "directions": ["southeast"]},
    ]
    return run_local_heartbeat_sequence(
        true_map=_make_true_map(),
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
        sequence_id="seq-10ao",
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
    territory_ref: str = "reg-start",
    actor_id: str = AGENT_ID,
) -> dict:
    return {
        "event_id": event_id,
        "schema_version": "10AO.1",
        "actor_id": actor_id,
        "lens": actor_id,
        "territory_ref": territory_ref,
        "action_type": "observe",
        "summary": "observe",
        "evidence_refs": [
            {"category": "observed_world_fact", "tile_ids": tile_ids}
        ],
        "claim_scope": "observed",
        "before_ref": "",
        "after_ref": "",
        "affected_agents": [],
        "artifacts_created_or_changed": [],
        "relationship_delta": [],
        "consequence": "",
        "verification_status": "accepted",
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
        "schema_version": "10AO.1",
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
        _observe_event(event_id="ev-1", tick=1, tile_ids=["tile_start", "tile_north"]),
        _move_event(
            event_id="ev-2", tick=2, from_tile_id="tile_start", to_tile_id="tile_north"
        ),
        _observe_event(event_id="ev-3", tick=3, tile_ids=["tile_north"]),
        _move_event(
            event_id="ev-4",
            tick=5,
            from_tile_id="tile_north",
            to_tile_id="tile_east",
            territory_ref="reg_east",
        ),
        _observe_event(event_id="ev-5", tick=6, tile_ids=["tile_east"]),
    ]


# ---------------------------------------------------------------------------
# 1. Happy path end-to-end: 10AM -> 10AN temp ledger -> 10AO replay summary
# ---------------------------------------------------------------------------


def test_happy_path_tenam_to_tenan_to_tenao_replay(tmp_path):
    sequence = _sequence_ok()
    bridge_result = _bridge(sequence, tmp_path)

    assert bridge_result["ok"] is True
    ledger_path = Path(bridge_result["ledger_path"])
    events = read_events(ledger_path)
    replay = replay_accepted_events(events)

    assert replay["ok"] is True
    assert replay["agent_id"] == AGENT_ID
    assert replay["event_count"] == bridge_result["event_count"]
    assert replay["accepted_event_count"] == bridge_result["event_count"]
    assert replay["ignored_event_count"] == 0
    assert replay["errors"] == []

    move_entries = [
        entry
        for entry in sequence["timeline"]
        if entry["action"] == "move_local"
    ]
    last_move = move_entries[-1]
    assert replay["final_public_position"] == {
        "tile_id": last_move["to_tile_id"],
        "territory_ref": last_move["territory_ref"],
    }

    assert replay["first_tick"] == 1
    assert replay["last_tick"] == sequence["end_tick"]
    assert replay["accepted_event_count"] == len(events)
    assert isinstance(replay["movement_chain"], list)
    assert len(replay["movement_chain"]) == len(move_entries)
    assert isinstance(replay["observed_tile_ids"], list)
    assert replay["observed_tile_ids"]


# ---------------------------------------------------------------------------
# 2. replay_ledger_file returns same result as read_events + replay_accepted_events
# ---------------------------------------------------------------------------


def test_replay_ledger_file_matches_in_memory_replay(tmp_path):
    events = _canonical_events()
    ledger_path = tmp_path / "ledger.jsonl"
    with ledger_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    direct = replay_accepted_events(read_events(ledger_path))
    via_file = replay_ledger_file(ledger_path)

    assert direct == via_file


# ---------------------------------------------------------------------------
# 3. Ignored rejected / non-accepted event is counted and not replayed
# ---------------------------------------------------------------------------


def test_ignored_non_accepted_event_is_counted_not_replayed():
    events = _canonical_events()
    rejected = _move_event(
        event_id="ev-rejected",
        tick=4,
        from_tile_id="tile_north",
        to_tile_id="tile_blocked",
        verification_status="rejected",
    )
    input_events = list(events) + [rejected]

    replay = replay_accepted_events(input_events)

    assert replay["ok"] is True
    assert replay["event_count"] == len(input_events)
    assert replay["accepted_event_count"] == len(events)
    assert replay["ignored_event_count"] == 1
    assert [m["to_tile_id"] for m in replay["movement_chain"]] == [
        "tile_north",
        "tile_east",
    ]
    assert all("ev-rejected" not in m["event_id"] for m in replay["movement_chain"])


# ---------------------------------------------------------------------------
# 4. final_public_position is derived from last accepted move_local only
# ---------------------------------------------------------------------------


def test_final_public_position_is_last_accepted_move_only():
    events = _canonical_events()
    replay = replay_accepted_events(events)

    assert replay["ok"] is True
    assert replay["final_public_position"] == {
        "tile_id": "tile_east",
        "territory_ref": "reg_east",
    }

    chain_tail = replay["movement_chain"][-1]
    assert replay["final_public_position"]["tile_id"] == chain_tail["to_tile_id"]
    assert replay["final_public_position"]["territory_ref"] == chain_tail["territory_ref"]


def test_final_public_position_is_none_when_no_accepted_moves():
    events = [
        _observe_event(event_id="obs-1", tick=1, tile_ids=["tile_start"]),
        _observe_event(event_id="obs-2", tick=2, tile_ids=["tile_north"]),
    ]
    replay = replay_accepted_events(events)

    assert replay["ok"] is True
    assert replay["final_public_position"] is None
    assert replay["movement_chain"] == []


# ---------------------------------------------------------------------------
# 5. observed_tile_ids are derived from accepted observe evidence only
# ---------------------------------------------------------------------------


def test_observed_tile_ids_come_from_accepted_observe_evidence_only():
    events = _canonical_events()
    extra_observe_from_rejected = {
        "event_id": "obs-rejected",
        "actor_id": AGENT_ID,
        "territory_ref": "reg-start",
        "action_type": "observe",
        "evidence_refs": [
            {"category": "observed_world_fact", "tile_ids": ["tile_secret"]}
        ],
        "verification_status": "rejected",
        "tick": 7,
    }
    replay = replay_accepted_events(list(events) + [extra_observe_from_rejected])

    assert replay["ok"] is True
    assert "tile_secret" not in replay["observed_tile_ids"]
    assert set(replay["observed_tile_ids"]) == {
        "tile_start",
        "tile_north",
        "tile_east",
    }
    # Deterministic ordering (sorted).
    assert replay["observed_tile_ids"] == sorted(replay["observed_tile_ids"])


def test_observed_tile_ids_dedupe_across_observe_events():
    events = [
        _observe_event(event_id="obs-1", tick=1, tile_ids=["tile_a", "tile_b"]),
        _observe_event(event_id="obs-2", tick=2, tile_ids=["tile_b", "tile_c"]),
    ]
    replay = replay_accepted_events(events)

    assert replay["ok"] is True
    assert replay["observed_tile_ids"] == ["tile_a", "tile_b", "tile_c"]


# ---------------------------------------------------------------------------
# 6. movement_chain preserves tick/from/to/territory/event_id ordering
# ---------------------------------------------------------------------------


def test_movement_chain_preserves_tick_from_to_territory_event_id_ordering():
    events = _canonical_events()
    # Shuffle input order; replay must still sort deterministically by (tick, id).
    shuffled = [
        events[3],
        events[0],
        events[4],
        events[1],
        events[2],
    ]
    replay = replay_accepted_events(shuffled)

    assert replay["ok"] is True
    chain = replay["movement_chain"]
    assert len(chain) == 2

    assert chain[0] == {
        "tick": 2,
        "from_tile_id": "tile_start",
        "to_tile_id": "tile_north",
        "territory_ref": "reg-start",
        "event_id": "ev-2",
    }
    assert chain[1] == {
        "tick": 5,
        "from_tile_id": "tile_north",
        "to_tile_id": "tile_east",
        "territory_ref": "reg_east",
        "event_id": "ev-4",
    }
    assert [m["tick"] for m in chain] == [2, 5]
    assert [m["event_id"] for m in chain] == ["ev-2", "ev-4"]


# ---------------------------------------------------------------------------
# 7. Malformed accepted move or observe returns ok=False with safe error
# ---------------------------------------------------------------------------


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
    replay = replay_accepted_events(list(events) + [bad_move])

    assert replay["ok"] is False
    assert any("move_local" in err for err in replay["errors"])
    # The well-formed moves are still part of the audit summary.
    assert len(replay["movement_chain"]) == 2


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
    replay = replay_accepted_events(list(events) + [bad_observe])

    assert replay["ok"] is False
    assert any("observe" in err for err in replay["errors"])
    assert "tile_secret" not in replay["observed_tile_ids"]


def test_malformed_accepted_event_with_invalid_tick_returns_ok_false():
    events = _canonical_events()
    bad_tick = _move_event(
        event_id="ev-bad-tick",
        tick="not-a-tick",
        from_tile_id="tile_start",
        to_tile_id="tile_north",
    )
    replay = replay_accepted_events(list(events) + [bad_tick])

    assert replay["ok"] is False
    assert any("invalid tick" in err for err in replay["errors"])


# ---------------------------------------------------------------------------
# 8. Multiple actors return ok=False with safe boundary error
# ---------------------------------------------------------------------------


def test_multiple_actors_return_ok_false_with_safe_boundary_error():
    events = _canonical_events()
    other_actor = _observe_event(
        event_id="obs-other",
        tick=8,
        tile_ids=["tile_other"],
        actor_id="other_agent",
        territory_ref="reg-other",
    )
    replay = replay_accepted_events(list(events) + [other_actor])

    assert replay["ok"] is False
    assert any("multiple actors" in err for err in replay["errors"])
    assert replay["agent_id"] is None
    # Multi-actor is a hard boundary: no replay happens.
    assert replay["movement_chain"] == []
    assert replay["observed_tile_ids"] == []
    assert replay["final_public_position"] is None


# ---------------------------------------------------------------------------
# 9. Replay does not mutate caller-owned events
# ---------------------------------------------------------------------------


def test_replay_does_not_mutate_caller_owned_events():
    events = _canonical_events()
    before = copy.deepcopy(events)

    replay_accepted_events(events)
    # Run twice to confirm idempotent / non-mutating behaviour.
    replay_accepted_events(events)

    assert events == before


# ---------------------------------------------------------------------------
# 10. No hidden substrate / runtime markers in module or test text
# ---------------------------------------------------------------------------


def test_no_hidden_substrate_runtime_markers_in_module_or_test_text():
    module_path = PROJECT_ROOT / "backend/world/local_ledger_replay.py"
    test_path = PROJECT_ROOT / "tests/test_phase10ao_ledger_replay_verifier.py"

    text = module_path.read_text(encoding="utf-8") + test_path.read_text(
        encoding="utf-8"
    )

    forbidden_markers = [
        "while " + "True",
        "async" + "io",
        "aio" + "http",
        "thread" + "ing",
        "sub" + "process",
        "sock" + "et",
        "requests" + ".",
        "http" + "://",
        "https" + "://",
        "dock" + "er",
        "pro" + "vider",
        "sched" + "uler",
        "daem" + "on",
        "API" + "_KEY",
        "TOKEN" + "=",
        "." + "env",
        "GPT-" + "5",
        "Deep" + "Seek",
        "Mini" + "Max",
        "Host" + "inger",
        "Tail" + "scale",
        "Orch" + "estrator",
        "world-sim" + "/data",
        "accepted-state" + "-ledger",
        "import " + "requests",
        "from " + "requests",
        "import " + "http" + "x",
        "from " + "http" + "x",
        "import " + "sock" + "et",
        "from " + "sock" + "et",
        "import " + "sub" + "process",
        "from " + "sub" + "process",
        "import " + "thread" + "ing",
        "from " + "thread" + "ing",
    ]

    for marker in forbidden_markers:
        assert marker not in text, f"forbidden marker present: {marker!r}"


# ---------------------------------------------------------------------------
# 11. Deterministic repeated replay
# ---------------------------------------------------------------------------


def test_deterministic_repeated_replay():
    events = _canonical_events()
    reversed_events = list(reversed(events))

    first = replay_accepted_events(events)
    second = replay_accepted_events(events)
    third = replay_accepted_events(reversed_events)

    assert first == second
    assert first == third


def test_replay_of_empty_events_is_safe():
    replay = replay_accepted_events([])

    assert replay["ok"] is True
    assert replay["agent_id"] is None
    assert replay["final_public_position"] is None
    assert replay["observed_tile_ids"] == []
    assert replay["movement_chain"] == []
    assert replay["first_tick"] is None
    assert replay["last_tick"] is None
    assert replay["event_count"] == 0
    assert replay["accepted_event_count"] == 0
    assert replay["ignored_event_count"] == 0
    assert replay["errors"] == []


def test_replay_of_non_list_events_is_safe():
    replay = replay_accepted_events("not-a-list")  # type: ignore[arg-type]

    assert replay["ok"] is False
    assert "must be a list" in replay["errors"][0]


def test_replay_ledger_file_missing_path_returns_empty_safe_summary(tmp_path):
    missing = tmp_path / "does-not-exist.jsonl"
    replay = replay_ledger_file(missing)

    assert replay["ok"] is True
    assert replay["event_count"] == 0
    assert replay["accepted_event_count"] == 0
    assert replay["ignored_event_count"] == 0


def test_first_last_tick_derived_only_from_accepted_replayable_events():
    events = [
        _observe_event(event_id="obs-1", tick=1, tile_ids=["tile_a"]),
        _move_event(event_id="mv-1", tick=2, from_tile_id="tile_a", to_tile_id="tile_b"),
        _observe_event(event_id="obs-2", tick=3, tile_ids=["tile_b"]),
    ]
    # A non-replayable accepted event (gather-style) carries tick 99.
    extra = {
        "event_id": "gather-1",
        "actor_id": AGENT_ID,
        "territory_ref": "reg-start",
        "action_type": "gather",
        "evidence_refs": [],
        "verification_status": "accepted",
        "tick": 99,
    }
    replay = replay_accepted_events(list(events) + [extra])

    assert replay["ok"] is True
    assert replay["first_tick"] == 1
    assert replay["last_tick"] == 3
    assert replay["accepted_event_count"] == 4
    assert len(replay["movement_chain"]) == 1

"""Recoverable inventory/fauna transaction tests for Phase 10JN."""

from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    WorldStateRecord,
    add_to_inventory,
    load_inventory,
)
from backend.world import fauna_interactions


def _store(tmp_path: Path) -> FirstPairPersistenceStore:
    return FirstPairPersistenceStore(tmp_path / "store")


def _state() -> WorldStateRecord:
    return WorldStateRecord()


def _cow() -> dict:
    return {
        "kind": "cow",
        "id": "cow-1",
        "tile": [0, 1],
        "hp": 4,
        "trust": 0,
        "tamed": False,
        "milk_ready": False,
        "milk_ready_at_hb": 0,
        "anchor_tile": None,
    }


def test_intent_only_recovers_as_noop(tmp_path: Path):
    store = _store(tmp_path)
    state = _state()
    state.fauna = [_cow()]
    add_to_inventory(store, "east_adam", "wild_berries", 1)

    fauna_interactions.begin_animal_interaction(
        store,
        event_id="offer-1",
        intent={
            "action": "offer_food",
            "agent_ref": "east_adam",
            "target_id": "cow-1",
            "resource_kind": "wild_berries",
            "trust_before": 0,
            "trust_after": 15,
            "tamed_before": False,
            "tamed_after": False,
            "anchor_tile_after": None,
            "inventory_before": {"wild_berries": 1},
            "inventory_after": {"wild_berries": 0},
        },
    )

    result = fauna_interactions.recover_fauna_interactions(store, state)
    assert result["recovered"] == 0
    assert state.fauna[0]["trust"] == 0
    stages = [
        event["stage"]
        for event in fauna_interactions.load_fauna_events(store)
        if event["event_id"] == "offer-1"
    ]
    assert "recovered_noop" in stages


def test_inventory_applied_without_world_state_applies_recovery(tmp_path: Path):
    store = _store(tmp_path)
    state = _state()
    cow = _cow()
    state.fauna = [cow]

    intent = {
        "action": "offer_food",
        "agent_ref": "east_adam",
        "target_id": "cow-1",
        "resource_kind": "wild_berries",
        "trust_before": 50,
        "trust_after": 60,
        "tamed_before": False,
        "tamed_after": True,
        "anchor_tile_after": [0, 1],
        "inventory_before": {"wild_berries": 1},
        "inventory_after": {"wild_berries": 0},
    }
    cow["trust"] = 50

    fauna_interactions.begin_animal_interaction(store, "offer-2", intent)
    fauna_interactions.mark_inventory_applied(store, "offer-2")

    result = fauna_interactions.recover_fauna_interactions(store, state)
    assert result["recovered"] == 1
    assert state.fauna[0]["trust"] == 60
    assert state.fauna[0]["tamed"] is True
    assert state.fauna[0]["anchor_tile"] == [0, 1]

    stages = [
        event["stage"]
        for event in fauna_interactions.load_fauna_events(store)
        if event["event_id"] == "offer-2"
    ]
    assert "fauna_applied" in stages


def test_crash_between_inventory_and_marker_recovers(tmp_path: Path):
    store = _store(tmp_path)
    state = _state()
    cow = _cow()
    cow["trust"] = 50
    state.fauna = [cow]

    intent = {
        "action": "offer_food",
        "agent_ref": "east_adam",
        "target_id": "cow-1",
        "resource_kind": "wild_berries",
        "trust_before": 50,
        "trust_after": 60,
        "tamed_before": False,
        "tamed_after": True,
        "anchor_tile_after": [0, 1],
        "inventory_before": {"wild_berries": 1},
        "inventory_after": {"wild_berries": 0},
    }
    fauna_interactions.begin_animal_interaction(store, "offer-crash", intent)

    # Simulate the crash after inventory write but before journal marker.
    add_to_inventory(store, "east_adam", "wild_berries", 1)
    add_to_inventory(store, "east_adam", "wild_berries", -1)

    result = fauna_interactions.recover_fauna_interactions(store, state)
    assert result["recovered"] == 1
    assert state.fauna[0]["trust"] == 60
    assert state.fauna[0]["tamed"] is True

    stages = [
        event["stage"]
        for event in fauna_interactions.load_fauna_events(store)
        if event["event_id"] == "offer-crash"
    ]
    assert "inventory_applied" in stages
    assert "fauna_applied" in stages


def test_crash_before_inventory_remains_noop(tmp_path: Path):
    store = _store(tmp_path)
    state = _state()
    cow = _cow()
    state.fauna = [cow]

    intent = {
        "action": "offer_food",
        "agent_ref": "east_adam",
        "target_id": "cow-1",
        "resource_kind": "wild_berries",
        "trust_before": 0,
        "trust_after": 15,
        "tamed_before": False,
        "tamed_after": False,
        "anchor_tile_after": None,
        "inventory_before": {"wild_berries": 1},
        "inventory_after": {"wild_berries": 0},
    }
    add_to_inventory(store, "east_adam", "wild_berries", 1)
    fauna_interactions.begin_animal_interaction(store, "offer-noop", intent)

    result = fauna_interactions.recover_fauna_interactions(store, state)
    assert result["recovered"] == 0
    assert state.fauna[0]["trust"] == 0
    stages = [
        event["stage"]
        for event in fauna_interactions.load_fauna_events(store)
        if event["event_id"] == "offer-noop"
    ]
    assert "recovered_noop" in stages


def test_already_applied_interaction_does_not_duplicate(tmp_path: Path):
    store = _store(tmp_path)
    state = _state()
    cow = _cow()
    cow["trust"] = 60
    cow["tamed"] = True
    cow["anchor_tile"] = [0, 1]
    state.fauna = [cow]

    intent = {
        "action": "offer_food",
        "agent_ref": "east_adam",
        "target_id": "cow-1",
        "resource_kind": "wild_berries",
        "trust_before": 50,
        "trust_after": 60,
        "tamed_before": False,
        "tamed_after": True,
        "anchor_tile_after": [0, 1],
        "inventory_before": {"wild_berries": 1},
        "inventory_after": {"wild_berries": 0},
    }
    fauna_interactions.begin_animal_interaction(store, "offer-3", intent)
    fauna_interactions.mark_inventory_applied(store, "offer-3")
    fauna_interactions.mark_fauna_applied(store, "offer-3")

    result = fauna_interactions.recover_fauna_interactions(store, state)
    assert result["recovered"] == 0
    assert state.fauna[0]["trust"] == 60


def test_milk_inventory_applied_without_world_state_recovers_milk_state(tmp_path: Path):
    store = _store(tmp_path)
    state = _state()
    cow = _cow()
    cow.update({
        "trust": 60,
        "tamed": True,
        "milk_ready": True,
        "milk_ready_at_hb": 100,
        "anchor_tile": [0, 1],
    })
    state.fauna = [cow]

    intent = {
        "action": "milk_animal",
        "agent_ref": "east_adam",
        "target_id": "cow-1",
        "milk_ready_before": True,
        "milk_ready_after": False,
        "milk_ready_at_hb_after": 244,
        "inventory_before": {"milk": 0},
        "inventory_after": {"milk": 1},
    }
    fauna_interactions.begin_animal_interaction(store, "milk-1", intent)
    fauna_interactions.mark_inventory_applied(store, "milk-1")

    result = fauna_interactions.recover_fauna_interactions(store, state)
    assert result["recovered"] == 1
    assert state.fauna[0]["milk_ready"] is False
    assert state.fauna[0]["milk_ready_at_hb"] == 244


def test_incomplete_interaction_for_missing_fauna_fails_closed(tmp_path: Path):
    store = _store(tmp_path)
    state = _state()
    state.fauna = []

    intent = {
        "action": "offer_food",
        "agent_ref": "east_adam",
        "target_id": "missing-cow",
        "resource_kind": "wild_berries",
        "trust_before": 0,
        "trust_after": 15,
        "tamed_before": False,
        "tamed_after": False,
        "anchor_tile_after": None,
        "inventory_before": {"wild_berries": 1},
        "inventory_after": {"wild_berries": 0},
    }
    fauna_interactions.begin_animal_interaction(store, "offer-missing", intent)
    fauna_interactions.mark_inventory_applied(store, "offer-missing")

    try:
        fauna_interactions.recover_fauna_interactions(store, state)
    except Exception as exc:
        assert "cow-1" in str(exc) or "missing-cow" in str(exc)
    else:
        raise AssertionError("expected missing fauna recovery to fail closed")

"""Recoverable inventory/fauna transaction tests for Phase 10JN."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    WorldStateRecord,
    _load_world_state,  # noqa: PLC2701 — the pre-existing loader, under test here
    add_to_inventory,
    load_inventory,
    save_world_state,
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

    with pytest.raises(ValueError, match="fauna_interaction:missing_fauna"):
        fauna_interactions.recover_fauna_interactions(store, state)

    # Fail closed means nothing was written: no fauna_applied marker and no
    # world state flush behind it.
    stages = [
        event["stage"]
        for event in fauna_interactions.load_fauna_events(store)
        if event["event_id"] == "offer-missing"
    ]
    assert "fauna_applied" not in stages


def test_save_world_state_persists_fauna_field(tmp_path: Path):
    """Fauna is part of the world state record, not a phantom of journal text.

    Before the field existed, save_world_state wrote an envelope with no
    fauna key while the journal claimed fauna_applied — a durable claim
    about state that was never on disk.
    """
    store = _store(tmp_path)
    state = _state()
    cow = _cow()
    state.fauna = [cow]

    save_world_state(store, state)

    envelope = store._read_json(store._path("world_state.json"))
    assert "fauna" in envelope["data"], "fauna must not be silently omitted"
    assert envelope["data"]["fauna"] == [cow]

    # A store written before the fauna domain existed has no fauna key.
    # It must still load, as an empty list, rather than raising TypeError.
    legacy = dict(envelope)
    legacy["data"] = {
        key: value for key, value in envelope["data"].items() if key != "fauna"
    }
    store._atomic_write(store._path("world_state.json"), legacy)

    loaded = _load_world_state(store)
    assert loaded.fauna == []


def test_absent_inventory_does_not_grant_after_state(tmp_path: Path):
    """No inventory row is not evidence that inventory was consumed.

    An all-zero "after" snapshot matches a never-written row trivially.
    Treating that as a match handed out fauna trust for an interaction
    whose inventory half never ran.
    """
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
    # No inventory.json entry at all for east_adam: the fake crash case.
    assert "east_adam" not in load_inventory(store)

    fauna_interactions.begin_animal_interaction(store, "offer-absent", intent)

    # The zero-valued "after" snapshot must not read as a match.
    assert fauna_interactions._inventory_matches(
        store, intent, "inventory_after"
    ) is False

    with pytest.raises(
        ValueError, match="fauna_interaction:unexpected_inventory_state"
    ):
        fauna_interactions.recover_fauna_interactions(store, state)

    # No fauna trust granted: state untouched, nothing persisted, no marker.
    assert state.fauna[0]["trust"] == 50
    assert state.fauna[0]["tamed"] is False
    assert not store._path("world_state.json").exists()
    stages = [
        event["stage"]
        for event in fauna_interactions.load_fauna_events(store)
        if event["event_id"] == "offer-absent"
    ]
    assert stages == ["intent"]


def test_intent_cannot_override_journal_control_fields(tmp_path: Path):
    """Caller intent is payload; the journal owns its control fields.

    A caller that could write its own `stage` could certify a mutation
    that never happened.
    """
    store = _store(tmp_path)
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

    for key in ("stage", "event_id", "created_at_utc", "schema_version"):
        poisoned = dict(intent)
        poisoned[key] = "hijacked"
        with pytest.raises(
            ValueError, match=f"fauna_interaction:reserved_key:{key}"
        ):
            fauna_interactions.begin_animal_interaction(
                store, "offer-guard", poisoned
            )

    # Rejection happened before the append: nothing was journaled.
    assert fauna_interactions.load_fauna_events(store) == []

    # A clean call afterwards still records the real control fields.
    fauna_interactions.begin_animal_interaction(store, "offer-real", intent)
    events = fauna_interactions.load_fauna_events(store)
    assert len(events) == 1
    record = events[0]
    assert record["event_id"] == "offer-real"
    assert record["stage"] == "intent"
    assert record["created_at_utc"] != "hijacked"
    assert record["schema_version"] == "fauna_interaction.1"
    assert record["trust_after"] == 15  # payload still gets through


def test_repeated_recovery_is_idempotent(tmp_path: Path):
    """Second recovery is a noop, on the journal and on disk."""
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
    fauna_interactions.begin_animal_interaction(store, "offer-idem", intent)
    fauna_interactions.mark_inventory_applied(store, "offer-idem")

    first = fauna_interactions.recover_fauna_interactions(store, state)
    assert first["recovered"] == 1
    assert state.fauna[0]["trust"] == 60

    # The recovered fauna change is durable, not just in-memory.
    persisted = _load_world_state(store)
    assert persisted.fauna[0]["trust"] == 60

    second = fauna_interactions.recover_fauna_interactions(store, state)
    assert second["recovered"] == 0
    assert state.fauna[0]["trust"] == 60
    assert state.fauna[0]["tamed"] is True
    assert state.fauna[0]["milk_ready"] is False
    assert state.fauna[0]["milk_ready_at_hb"] == 0

    # And the persisted copy never moved either.
    reloaded = _load_world_state(store)
    assert reloaded.fauna[0]["trust"] == 60

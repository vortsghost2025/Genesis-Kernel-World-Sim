"""Phase 10JN runtime tests: fauna state and observation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import fauna
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    WorldStateRecord,
    load_world_state,
)


def test_world_state_record_supports_fauna_default():
    state = WorldStateRecord()
    assert state.fauna == []


def test_world_state_json_without_fauna_loads_default(tmp_path: Path):
    store = FirstPairPersistenceStore(tmp_path / "store")
    # Write an old-shaped payload without the fauna field.
    store._atomic_write(store._path("world_state.json"), {
        "type": "world_state_record",
        "schema_version": "world_state.1",
        "data": {
            "tick": 0,
            "public_objects": {},
            "tile_occupancy": {},
            "public_messages": [],
            "vitals": {},
            "wildlife": [],
        },
    })
    loaded = load_world_state(store)
    assert loaded.fauna == []


def _runtime(tmp_path: Path):
    from backend.world.first_pair_runtime import FirstPairRuntime
    store = FirstPairPersistenceStore(tmp_path / "store")
    runtime = FirstPairRuntime(heartbeat_limit=1, store=store)
    runtime._load_or_initialize()
    return runtime


def test_fauna_visible_includes_ids_and_state(tmp_path: Path):
    runtime = _runtime(tmp_path)
    agent = "east_adam"
    runtime._world_state.tile_occupancy[agent] = "cont_a_gen_0_0"
    runtime._world_state.fauna = [
        {"kind": "cow", "id": "cow-1", "tile": [0, 1],
         "hp": 4, "trust": 60, "tamed": True, "milk_ready": True},
        {"kind": "snake", "id": "snake-1", "tile": [1, 0], "hp": 2},
    ]
    observed = runtime._fauna_visible(agent)
    assert [item["kind"] for item in observed["nearby"]] == ["cow", "snake"]
    cow = observed["nearby"][0]
    assert cow["id"] == "cow-1"
    assert cow["distance"] == 1
    assert cow["tamed"] is True
    assert cow["milk_ready"] is True
    snake = observed["nearby"][1]
    assert snake["id"] == "snake-1"


def test_fauna_tick_advances_snake_bite(tmp_path: Path, monkeypatch):
    from backend.world.first_pair_runtime import FirstPairRuntime
    from backend.world import survival

    runtime = _runtime(tmp_path)
    agent = "east_adam"
    runtime._world_state.tile_occupancy[agent] = "cont_a_gen_0_0"
    runtime._world_state.vitals[agent] = {
        "hunger": 0.0, "warmth": 100.0, "vitality": 100.0,
        "wetness": 0.0, "downed": False,
    }
    runtime._world_state.fauna = [
        {"kind": "snake", "id": "snake-1", "tile": [1, 0], "hp": 2},
    ]

    monkeypatch.setattr(survival, "weather_at", lambda pid, hb: ("clear", 5000))
    monkeypatch.setattr(survival, "is_night", lambda hb: False)
    monkeypatch.setattr(survival, "effective_temperature", lambda hb, w: 62.0)
    monkeypatch.setattr(
        fauna,
        "snake_bite_events",
        lambda **kwargs: [("east_adam", "snake-1", fauna.SNAKE_BITE_DAMAGE)],
    )

    runtime.fauna_tick(heartbeat_number=100)
    assert runtime._world_state.vitals[agent]["vitality"] == 95.0


def test_fauna_tick_skips_snake_bites_when_inactive(tmp_path: Path, monkeypatch):
    from backend.world import survival

    runtime = _runtime(tmp_path)
    agent = "east_adam"
    runtime._world_state.tile_occupancy[agent] = "cont_a_gen_0_0"
    runtime._world_state.vitals[agent] = {
        "hunger": 0.0, "warmth": 100.0, "vitality": 100.0,
        "wetness": 0.0, "downed": False,
    }
    runtime._world_state.fauna = [
        {"kind": "snake", "id": "snake-1", "tile": [1, 0], "hp": 2},
    ]

    monkeypatch.setattr(survival, "weather_at", lambda pid, hb: ("rain", 5000))
    monkeypatch.setattr(survival, "is_night", lambda hb: False)
    monkeypatch.setattr(survival, "effective_temperature", lambda hb, w: 62.0)
    monkeypatch.setattr(
        fauna,
        "snake_bite_events",
        lambda **kwargs: pytest.fail("snake bites must be gated by snake_active"),
    )

    runtime.fauna_tick(heartbeat_number=100)
    assert runtime._world_state.vitals[agent]["vitality"] == 100.0


def _action_runtime(tmp_path: Path):
    runtime = _runtime(tmp_path)
    agent = "east_adam"
    runtime._world_state.tile_occupancy[agent] = "cont_a_gen_0_0"
    runtime._world_state.fauna = [{
        "kind": "cow",
        "id": "cow-1",
        "tile": [0, 1],
        "hp": 4,
        "trust": 0,
        "tamed": False,
        "milk_ready": False,
        "milk_ready_at_hb": 0,
        "anchor_tile": None,
    }]
    return runtime


def test_offer_food_tames_cow_after_trusted_offerings(tmp_path: Path):
    from backend.world.first_pair_persistence import add_to_inventory
    runtime = _action_runtime(tmp_path)

    for kind, trust in (
        ("wild_berries", 15),
        ("edible_roots", 18),
        ("wild_apples", 20),
        ("fiber_plants", 7),
    ):
        add_to_inventory(runtime._store, "east_adam", kind, 1)
        outcome = runtime._execute_action("east_adam", {
            "action_type": "offer_food",
            "target_id": "cow-1",
            "resource_kind": kind,
            "reason": "offer food",
        }, 100)
        assert outcome["status"] == "success"
        assert outcome["target_id"] == "cow-1"

    assert runtime._world_state.fauna[0]["tamed"] is True
    assert runtime._world_state.fauna[0]["trust"] == 60
    assert runtime._world_state.fauna[0]["anchor_tile"] is not None


def test_offer_food_rejects_non_diet_before_mutation(tmp_path: Path):
    from backend.world.first_pair_persistence import add_to_inventory, load_inventory
    runtime = _action_runtime(tmp_path)
    add_to_inventory(runtime._store, "east_adam", "stone", 1)

    outcome = runtime._execute_action("east_adam", {
        "action_type": "offer_food",
        "target_id": "cow-1",
        "resource_kind": "stone",
        "reason": "offer food",
    }, 100)

    assert outcome["status"] == "rejected"
    assert "Animals do not eat stone" in outcome["reason"]
    assert load_inventory(runtime._store)["east_adam"]["stone"] == 1
    assert runtime._world_state.fauna[0]["trust"] == 0


def test_offer_food_rejects_unhashable_resource_without_crash(tmp_path: Path):
    from backend.world.first_pair_persistence import load_inventory
    runtime = _action_runtime(tmp_path)

    outcome = runtime._execute_action("east_adam", {
        "action_type": "offer_food",
        "target_id": "cow-1",
        "resource_kind": {"bad": "dict"},
        "reason": "offer food",
    }, 100)

    assert outcome["status"] == "rejected"
    assert "resource kind" in outcome["reason"].lower()
    assert runtime._world_state.fauna[0]["trust"] == 0
    assert not load_inventory(runtime._store).get("east_adam")


def test_milk_animal_only_for_ready_tamed_cow(tmp_path: Path):
    from backend.world.first_pair_persistence import add_to_inventory, load_inventory
    runtime = _action_runtime(tmp_path)
    runtime._world_state.fauna[0].update({
        "trust": 60,
        "tamed": True,
        "milk_ready": False,
        "milk_ready_at_hb": 100,
        "anchor_tile": [0, 1],
    })

    rejected = runtime._execute_action("east_adam", {
        "action_type": "milk_animal",
        "target_id": "cow-1",
        "reason": "milk",
    }, 120)
    assert rejected["status"] == "rejected"
    assert "not ready" in rejected["reason"].lower()

    runtime._world_state.fauna[0]["milk_ready"] = True
    add_to_inventory(runtime._store, "east_adam", "wild_berries", 10)
    success = runtime._execute_action("east_adam", {
        "action_type": "milk_animal",
        "target_id": "cow-1",
        "reason": "milk",
    }, 121)
    assert success["status"] == "success"
    assert load_inventory(runtime._store)["east_adam"]["milk"] == 1
    assert runtime._world_state.fauna[0]["milk_ready"] is False
    assert runtime._world_state.fauna[0]["milk_ready_at_hb"] == 121


def test_attack_snake_succeeds_and_drops_meat(tmp_path: Path):
    from backend.world.first_pair_persistence import add_to_inventory, load_inventory
    runtime = _runtime(tmp_path)
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    runtime._world_state.fauna = [{
        "kind": "snake", "id": "snake-1", "tile": [1, 0], "hp": 2,
    }]
    runtime._world_state.wildlife = []
    # A snake's 2 HP needs a knapped knife (2.2 dmg) to fall in one strike;
    # bare hands deal 1 damage and wound it instead.
    add_to_inventory(runtime._store, "east_adam", "flint_knife", 1)

    outcome = runtime._execute_action("east_adam", {
        "action_type": "attack",
        "target_id": "snake-1",
        "reason": "kill snake",
    }, 100)

    assert outcome["status"] == "success"
    assert outcome["target_kind"] == "snake"
    assert outcome["killed"] is True
    assert outcome["meat"] == 1
    assert load_inventory(runtime._store)["east_adam"]["meat"] == 1
    assert runtime._world_state.fauna == []


def test_attack_cow_is_rejected(tmp_path: Path):
    runtime = _runtime(tmp_path)
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    runtime._world_state.fauna = [{
        "kind": "cow", "id": "cow-1", "tile": [1, 0], "hp": 4,
        "trust": 0, "tamed": False, "milk_ready": False,
    }]
    runtime._world_state.wildlife = []

    outcome = runtime._execute_action("east_adam", {
        "action_type": "attack",
        "target_id": "cow-1",
        "reason": "kill cow",
    }, 100)

    assert outcome["status"] == "rejected"
    assert "not hostile" in outcome["reason"].lower()


def test_attack_snake_without_tool_requires_two_strikes(tmp_path: Path):
    from backend.world.first_pair_persistence import load_inventory
    runtime = _runtime(tmp_path)
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    runtime._world_state.fauna = [{
        "kind": "snake", "id": "snake-1", "tile": [1, 0], "hp": 2,
    }]
    runtime._world_state.wildlife = []

    first = runtime._execute_action("east_adam", {
        "action_type": "attack",
        "target_id": "snake-1",
        "reason": "strike snake",
    }, 100)

    assert first["status"] == "success"
    assert first["target_kind"] == "snake"
    assert first["damage"] == 1.0
    assert first["killed"] is False
    assert first["meat"] == 0
    assert runtime._world_state.fauna[0]["id"] == "snake-1"
    assert runtime._world_state.fauna[0]["hp"] == 1.0
    assert load_inventory(runtime._store).get("east_adam", {}) == {}

    second = runtime._execute_action("east_adam", {
        "action_type": "attack",
        "target_id": "snake-1",
        "reason": "strike snake again",
    }, 101)

    assert second["status"] == "success"
    assert second["target_kind"] == "snake"
    assert second["damage"] == 1.0
    assert second["killed"] is True
    assert second["meat"] == 1
    assert load_inventory(runtime._store)["east_adam"]["meat"] == 1
    assert runtime._world_state.fauna == []


def test_wildlife_attack_preserves_detail_and_driven_off(tmp_path: Path):
    from backend.world import wildlife
    from backend.world.first_pair_persistence import add_to_inventory
    runtime = _runtime(tmp_path)
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    runtime._world_state.wildlife = [{
        "kind": "deer", "id": "deer-1", "tile": [1, 0], "hp": 2,
    }]
    runtime._world_state.fauna = []
    add_to_inventory(runtime._store, "east_adam", "flint_knife", 1)

    deer_outcome = runtime._execute_action("east_adam", {
        "action_type": "attack",
        "target_id": "deer-1",
        "reason": "hunt deer",
    }, 100)

    assert deer_outcome["status"] == "success"
    assert deer_outcome["killed"] is True
    assert deer_outcome["driven_off"] is False
    assert "Struck deer" in deer_outcome["detail"]

    runtime._world_state.wildlife = [{
        "kind": "wolf", "id": "wolf-1", "tile": [1, 0], "hp": wildlife.WOLF_FLEE_HP,
    }]
    wolf_outcome = runtime._execute_action("east_adam", {
        "action_type": "attack",
        "target_id": "wolf-1",
        "reason": "strike wolf",
    }, 101)

    assert wolf_outcome["status"] == "success"
    assert wolf_outcome["killed"] is True
    assert wolf_outcome["driven_off"] is True
    assert "wolf fled" in wolf_outcome["detail"]


def test_fauna_visible_skips_malformed_tiles(tmp_path: Path):
    runtime = _runtime(tmp_path)
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    runtime._world_state.fauna = [
        {"kind": "snake", "id": "snake-valid", "tile": [1, 0], "hp": 2},
        {"kind": "snake", "id": "snake-short", "tile": [5], "hp": 2},
        {"kind": "snake", "id": "snake-string", "tile": "nowhere", "hp": 2},
        {"kind": "snake", "id": "snake-none", "tile": [None, 1], "hp": 2},
    ]

    observed = runtime._fauna_visible("east_adam")
    assert [animal["id"] for animal in observed["nearby"]] == ["snake-valid"]

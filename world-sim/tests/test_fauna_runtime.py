"""Phase 10JN runtime tests: fauna state and observation."""

from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

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

    runtime.fauna_tick(heartbeat_number=100)
    assert runtime._world_state.vitals[agent]["vitality"] == 95.0

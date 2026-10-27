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

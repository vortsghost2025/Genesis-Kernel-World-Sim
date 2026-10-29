"""Phase 10JX tests: Compound Settlement Architecture & Modular Addons."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival, wildlife
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    WorldStateRecord,
    load_world_state,
    add_to_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime


def test_world_state_record_supports_compounds_default():
    state = WorldStateRecord()
    assert hasattr(state, "compounds")
    assert state.compounds == {}


def test_world_state_json_without_compounds_loads_default(tmp_path: Path):
    store = FirstPairPersistenceStore(tmp_path / "store")
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
            "fauna": [],
        },
    })
    loaded = load_world_state(store)
    assert loaded.compounds == {}


def _setup_runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    runtime = FirstPairRuntime(heartbeat_limit=10, store=store, pair_id="east")
    runtime._load_or_initialize()
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    runtime._world_state.tile_occupancy["east_eve"] = "cont_a_gen_0_1"
    return runtime


def test_compound_addon_build_validation(tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    agent = "east_adam"
    cur_pos = runtime._world_state.tile_occupancy[agent]
    cur_xy = runtime._tile_xy(cur_pos)
    adj_pos = f"cont_a_gen_{cur_xy[0] + 1}_{cur_xy[1]}"
    far_pos = f"cont_a_gen_{cur_xy[0] + 5}_{cur_xy[1] + 5}"

    # Give agent timber and wood
    add_to_inventory(runtime._store, agent, "timber", 10)
    add_to_inventory(runtime._store, agent, "wood", 10)
    add_to_inventory(runtime._store, agent, "fiber_plants", 10)

    # 1. Attempt addon to nonexistent structure
    res_fake = runtime._execute_build(agent, {
        "action_type": "build",
        "object_id": "addon-room-1",
        "object_type": "shelter",
        "tile_id": adj_pos,
        "addon_to": "nonexistent-hall-999",
        "materials": {"timber": 2, "wood": 2},
        "description": "Attached room to ghost hall",
    }, heartbeat_number=1)
    assert res_fake["status"] == "rejected"
    assert "nonexistent" in res_fake["reason"].lower() or "missing" in res_fake["reason"].lower() or "invalid" in res_fake["reason"].lower()

    # 2. Build root structure on current tile
    res_root = runtime._execute_build(agent, {
        "action_type": "build",
        "object_id": "hearth-hall-001",
        "object_type": "hearth",
        "tile_id": cur_pos,
        "materials": {"timber": 4, "wood": 2},
        "description": "Central hearth hall",
    }, heartbeat_number=2)
    assert res_root["status"] == "success"

    # 3. Attempt addon to non-adjacent tile
    res_far = runtime._execute_build(agent, {
        "action_type": "build",
        "object_id": "addon-room-far",
        "object_type": "shelter",
        "tile_id": far_pos,
        "addon_to": "hearth-hall-001",
        "materials": {"timber": 2, "wood": 2},
        "description": "Distant unattached room",
    }, heartbeat_number=3)
    assert res_far["status"] == "rejected"
    assert "adjacent" in res_far["reason"].lower()

    # 4. Build valid adjacent addon
    res_adj = runtime._execute_build(agent, {
        "action_type": "build",
        "object_id": "pantry-002",
        "object_type": "storage_cellar",
        "tile_id": adj_pos,
        "addon_to": "hearth-hall-001",
        "materials": {"timber": 2, "wood": 2},
        "description": "Attached pantry cellar",
    }, heartbeat_number=4)
    assert res_adj["status"] == "success"


def test_compound_adjacency_network(tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    agent = "east_adam"
    cur_pos = runtime._world_state.tile_occupancy[agent]
    cur_xy = runtime._tile_xy(cur_pos)
    north_pos = f"cont_a_gen_{cur_xy[0]}_{cur_xy[1] + 1}"
    east_pos = f"cont_a_gen_{cur_xy[0] + 1}_{cur_xy[1]}"

    add_to_inventory(runtime._store, agent, "timber", 20)
    add_to_inventory(runtime._store, agent, "wood", 20)
    add_to_inventory(runtime._store, agent, "fiber_plants", 20)

    # Build central hall
    r1 = runtime._execute_build(agent, {
        "action_type": "build",
        "object_id": "hall-1",
        "object_type": "hearth",
        "tile_id": cur_pos,
        "materials": {"timber": 4, "wood": 4},
        "description": "Main living hearth",
    }, heartbeat_number=1)
    assert r1["status"] == "success"

    # Add north room (stable)
    r2 = runtime._execute_build(agent, {
        "action_type": "build",
        "object_id": "stable-1",
        "object_type": "shelter_stable",
        "tile_id": north_pos,
        "addon_to": "hall-1",
        "materials": {"timber": 4, "wood": 4},
        "description": "Attached animal stable",
    }, heartbeat_number=2)
    assert r2["status"] == "success"

    # Add east room (cellar)
    r3 = runtime._execute_build(agent, {
        "action_type": "build",
        "object_id": "cellar-1",
        "object_type": "storage_cellar",
        "tile_id": east_pos,
        "addon_to": "hall-1",
        "materials": {"timber": 4, "wood": 4},
        "description": "Attached food storage cellar",
    }, heartbeat_number=3)
    assert r3["status"] == "success"

    # Verify compound tracking
    compounds = runtime._world_state.compounds
    assert len(compounds) >= 1
    # Find compound containing hall-1
    comp = None
    for c in compounds.values():
        if "hall-1" in c.get("rooms", {}):
            comp = c
            break
    assert comp is not None
    assert "stable-1" in comp["rooms"]
    assert "cellar-1" in comp["rooms"]
    assert comp["thermal_mass"] >= 3


def test_shared_compound_hearth(tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    agent_adam = "east_adam"
    pos_adam = runtime._world_state.tile_occupancy[agent_adam]
    xy_adam = runtime._tile_xy(pos_adam)
    pos_b = f"cont_a_gen_{xy_adam[0] + 1}_{xy_adam[1]}"

    add_to_inventory(runtime._store, agent_adam, "timber", 20)
    add_to_inventory(runtime._store, agent_adam, "wood", 20)

    # Build active hearth in room A
    runtime._execute_build(agent_adam, {
        "action_type": "build",
        "object_id": "hearth-hall-1",
        "object_type": "hearth",
        "tile_id": pos_adam,
        "materials": {"timber": 4, "wood": 4},
        "description": "Blazing hearth hall",
    }, heartbeat_number=1)

    # Build attached room B
    runtime._execute_build(agent_adam, {
        "action_type": "build",
        "object_id": "room-b",
        "object_type": "shelter",
        "tile_id": pos_b,
        "addon_to": "hearth-hall-1",
        "materials": {"timber": 4, "wood": 4},
        "description": "Sleeping quarters attached to hearth hall",
    }, heartbeat_number=2)

    # Verify that tile B receives by_fire from the connected compound hearth
    assert runtime._nearby_fire(pos_b, heartbeat_number=3) is True


def test_compound_roof_fire_protection(tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    agent = "east_adam"
    pos = runtime._world_state.tile_occupancy[agent]

    add_to_inventory(runtime._store, agent, "timber", 10)
    add_to_inventory(runtime._store, agent, "wood", 10)

    # Build shelter hall first, then addon hearth inside
    runtime._execute_build(agent, {
        "action_type": "build",
        "object_id": "shelter-hall-1",
        "object_type": "shelter",
        "tile_id": pos,
        "materials": {"timber": 4, "wood": 4},
        "description": "Sheltered hall",
    }, heartbeat_number=1)
    runtime._execute_build(agent, {
        "action_type": "build",
        "object_id": "roofed-hearth-1",
        "object_type": "hearth",
        "tile_id": pos,
        "addon_to": "shelter-hall-1",
        "materials": {"timber": 2, "wood": 2},
        "description": "Roofed indoor hearth",
    }, heartbeat_number=2)

    # Rain condition (find a rain heartbeat or verify fire_is_snuffed logic)
    # Inside compound room, fire tile is sheltered
    assert runtime._in_shelter(pos) is True
    assert survival.fire_is_snuffed("rain", fire_tile_sheltered=True) is False
    assert survival.fire_is_snuffed("storm", fire_tile_sheltered=True) is False


def test_compound_thermal_decay_scaling():
    # Table from Phase 10JV Spec §3.2:
    # Open terrain: factor 1.0, floor ambient
    # Isolated shack (1 room): factor 0.45, floor 45.0
    # Dual-room home (2 rooms): factor 0.30, floor 52.0
    # Homestead compound (>= 3 rooms): factor 0.18, floor 62.0

    warmth_initial = 80.0
    ambient = 10.0  # freezing winter night

    # 1. Open terrain
    w_open = survival.warmth_next(warmth_initial, ambient, by_fire=False, in_shelter=False)
    # 2. Isolated shack (1 room)
    w_1room = survival.warmth_next(warmth_initial, ambient, by_fire=False, in_shelter=True,
                                   comfort_floor=45.0, shelter_decay_factor=0.45)
    # 3. Dual-room home (2 rooms)
    w_2room = survival.warmth_next(warmth_initial, ambient, by_fire=False, in_shelter=True,
                                   comfort_floor=52.0, shelter_decay_factor=0.30)
    # 4. Homestead compound (3 rooms)
    w_3room = survival.warmth_next(warmth_initial, ambient, by_fire=False, in_shelter=True,
                                   comfort_floor=62.0, shelter_decay_factor=0.18)

    # More connected rooms preserve warmth significantly better
    assert w_3room > w_2room > w_1room > w_open
    # Verify vitality regen inside homestead compound
    v_open = survival.vitality_next(80.0, hunger=20.0, warmth=70.0, downed=False, in_shelter=False)
    v_comp = survival.vitality_next(80.0, hunger=20.0, warmth=70.0, downed=False, in_shelter=True, regen_rate=1.50)
    assert v_comp - 80.0 == pytest.approx(1.50)


def test_stable_wolf_exclusion(tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    agent = "east_adam"
    cur_pos = runtime._world_state.tile_occupancy[agent]
    cur_xy = runtime._tile_xy(cur_pos)
    stable_pos = f"cont_a_gen_{cur_xy[0] + 1}_{cur_xy[1]}"
    stable_xy = runtime._tile_xy(stable_pos)

    add_to_inventory(runtime._store, agent, "timber", 10)
    add_to_inventory(runtime._store, agent, "wood", 10)

    # Build stable
    runtime._execute_build(agent, {
        "action_type": "build",
        "object_id": "stable-hall",
        "object_type": "shelter_stable",
        "tile_id": cur_pos,
        "materials": {"timber": 4, "wood": 4},
        "description": "Attached animal stable",
    }, heartbeat_number=1)

    assert runtime._in_shelter(cur_pos) is True
    # Stable tile is sheltered, so move_wolf refuses to enter it
    import random
    wolf = {"id": "wolf-1", "kind": "wolf", "tile": [cur_xy[0] + 2, cur_xy[1]], "hp": 3}
    moved = wildlife.move_wolf(wolf, agent_xys=[cur_xy], agent_positions={},
                               fire_xys=[], sheltered_tiles={cur_xy}, rng=random.Random(42))
    assert tuple(moved["tile"]) != cur_xy

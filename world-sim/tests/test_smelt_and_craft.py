"""Crafting and smelting: the furnace works, the surface works.

West Eve built a furnace and a furnace. West Adam refuted the tower claim
because the tower made his tile visible but didn't give him anything new
to DO. The interaction mechanic (deposit/extract) is a one-way write —
materials go in and come back out, but nothing transforms.

This is the transformation: a furnace converts ore to metal, a crafting
surface combines materials into tools. The agents discover the recipes
by testing, not by instruction. Every operation is a world mechanic.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m  # noqa: E402
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore, add_to_inventory, load_inventory,
)


def _rt(tmp_path):
    store = FirstPairPersistenceStore(root=tmp_path)
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt._load_or_initialize()
    return rt


def _seed_object(rt, obj_id="furnace-1", obj_type="furnace",
                 tile="public-start-adam", contents=None):
    rt._world_state.public_objects[obj_id] = {
        "object_id": obj_id, "object_type": obj_type,
        "tile_id": tile,
        "creator_agent_id": "genesis-agent-test-adam-" + "0" * 48,
        "public_description": "test furnace",
        "materials": {}, "contents": contents or {},
        "created_heartbeat": 1,
    }
    rt._world_state.tile_occupancy["east_adam"] = tile


class TestSmelt:
    def test_smelt_iron_ore_produces_iron(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt, contents={"iron_ore": 6})
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "furnace-1",
            "operation": "smelt",
            "materials": {"iron_ore": 6},
        }, 100)
        assert out["status"] == "success"
        obj = rt._world_state.public_objects["furnace-1"]
        assert obj["contents"].get("iron") == 2
        assert obj["contents"].get("iron_ore") == 0

    def test_smelt_requires_correct_ratio(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt, contents={"iron_ore": 2})
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "furnace-1",
            "operation": "smelt",
            "materials": {"iron_ore": 2},
        }, 100)
        assert out["status"] == "rejected"

    def test_smelt_only_works_on_furnace(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt, obj_id="road-1", obj_type="road",
                     contents={"iron_ore": 6})
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "road-1",
            "operation": "smelt",
            "materials": {"iron_ore": 6},
        }, 100)
        assert out["status"] == "rejected"

    def test_smelt_produces_iron_in_contents(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt, contents={"iron_ore": 3})
        rt._execute_use_object("east_adam", {
            "target_object_id": "furnace-1",
            "operation": "smelt",
            "materials": {"iron_ore": 3},
        }, 100)
        obj = rt._world_state.public_objects["furnace-1"]
        assert obj["contents"]["iron"] == 1

    def test_extract_after_smelt_gives_iron(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt, contents={"iron_ore": 3})
        rt._execute_use_object("east_adam", {
            "target_object_id": "furnace-1",
            "operation": "smelt",
            "materials": {"iron_ore": 3},
        }, 100)
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "furnace-1",
            "operation": "extract",
            "materials": {"iron": 1},
        }, 100)
        assert out["status"] == "success"
        inv = load_inventory(rt._store)
        assert inv.get("east_adam", {}).get("iron") == 1


class TestCraft:
    def test_craft_stone_axe_from_stone_and_wood(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt, obj_id="surface-1", obj_type="crafting_surface")
        _seed_inventory(rt, "east_adam", {"stone": 5, "wood": 3})
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "surface-1",
            "operation": "craft",
            "materials": {"stone": 2, "wood": 1},
        }, 100)
        assert out["status"] == "success"
        inv = load_inventory(rt._store)
        assert inv.get("east_adam", {}).get("stone_axe") == 1
        assert inv.get("east_adam", {}).get("stone") == 3
        assert inv.get("east_adam", {}).get("wood") == 2

    def test_craft_fiber_rope(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt, obj_id="surface-1", obj_type="crafting_surface")
        _seed_inventory(rt, "east_adam", {"fiber_plants": 5})
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "surface-1",
            "operation": "craft",
            "materials": {"fiber_plants": 3},
        }, 100)
        assert out["status"] == "success"
        inv = load_inventory(rt._store)
        assert inv.get("east_adam", {}).get("fiber_rope") == 1

    def test_craft_only_works_on_crafting_surface(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt, obj_id="storage-1", obj_type="storage")
        _seed_inventory(rt, "east_adam", {"stone": 5, "wood": 3})
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "storage-1",
            "operation": "craft",
            "materials": {"stone": 2, "wood": 1},
        }, 100)
        assert out["status"] == "rejected"

    def test_craft_requires_exact_materials(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt, obj_id="surface-1", obj_type="crafting_surface")
        _seed_inventory(rt, "east_adam", {"stone": 5, "wood": 3})
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "surface-1",
            "operation": "craft",
            "materials": {"stone": 5, "wood": 5},
        }, 100)
        assert out["status"] == "rejected"


def _seed_inventory(rt, agent_ref, holdings):
    from backend.world.first_pair_persistence import add_to_inventory
    for kind, amount in holdings.items():
        add_to_inventory(rt._store, agent_ref, kind, amount)

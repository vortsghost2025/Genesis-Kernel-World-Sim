"""Runtime wildlife wiring: the wild breathes in the loop.

The engine is pure (test_wildlife.py). These pin the seams: entities
persist in world_state, the tick ages them, wolves bite unsheltered
adjacent agents, shelters and fire protect, observation carries the
wild, and the attack action hunts with tools.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival
from backend.world import wildlife as wl


class _FakeWorldState:
    def __init__(self):
        self.tile_occupancy = {
            "east_adam": "cont_a_gen_0_0",
            "east_eve": "cont_a_gen_5_5",
        }
        self.public_objects = {}
        self.public_messages = []
        self.vitals = {}
        self.wildlife = []


def _runtime_stub(pair_id="east"):
    from backend.world.first_pair_runtime import FirstPairRuntime
    rt = object.__new__(FirstPairRuntime)
    rt._world_state = _FakeWorldState()
    rt._adam_ref = "east_adam"
    rt._eve_ref = "east_eve"
    rt._pair_id = pair_id
    rt._store = None
    return rt


class TestTick:
    def test_tick_survives_and_persists_empty(self):
        rt = _runtime_stub()
        rt.wildlife_tick(4000)
        assert isinstance(rt._world_state.wildlife, list)

    def test_wolf_bites_adjacent_unsheltered_agent(self):
        rt = _runtime_stub()
        rt._world_state.wildlife = [
            {"kind": "wolf", "id": "w1", "tile": (0, 1), "hp": 1}]
        rt._vitals_for("east_adam")["vitality"] = 100.0
        rt.wildlife_tick(4000)
        v = rt._world_state.vitals["east_adam"]
        assert v["vitality"] < 100.0, "an adjacent wolf bites"
        dropped = 100.0 - v["vitality"]
        assert dropped <= wl.WOLF_BITE_DAMAGE * 1.01

    def test_shelter_is_absolute_safety(self):
        rt = _runtime_stub()
        rt._world_state.public_objects = {
            "s1": {"tile_id": "cont_a_gen_0_0", "object_type": "shelter"}}
        rt._world_state.wildlife = [
            {"kind": "wolf", "id": "w1", "tile": (0, 1), "hp": 1}]
        rt._vitals_for("east_adam")["vitality"] = 100.0
        rt.wildlife_tick(4000)
        assert rt._world_state.vitals["east_adam"]["vitality"] == 100.0, (
            "a sheltered body is untouchable")

    def test_fire_radius_is_absolute_safety(self):
        rt = _runtime_stub()
        rt._world_state.public_objects = {
            "f1": {"tile_id": "cont_a_gen_0_1", "object_type": "campfire"}}
        rt._world_state.wildlife = [
            {"kind": "wolf", "id": "w1", "tile": (1, 0), "hp": 1}]
        rt._vitals_for("east_adam")["vitality"] = 100.0
        rt.wildlife_tick(4000)
        assert rt._world_state.vitals["east_adam"]["vitality"] == 100.0, (
            "firelight protects")


class TestAttackAction:
    def _rt_with_deer(self, tmp_path):
        from backend.world.first_pair_persistence import (
            FirstPairPersistenceStore)
        rt = _runtime_stub()
        rt._world_state.wildlife = [
            {"kind": "deer", "id": "d1", "tile": (0, 1), "hp": 2}]
        rt._store = FirstPairPersistenceStore(tmp_path / "s")
        return rt

    def test_adjacent_deer_is_strikable(self, tmp_path):
        from backend.world.first_pair_persistence import (
            add_to_inventory, load_inventory)
        rt = self._rt_with_deer(tmp_path)
        add_to_inventory(rt._store, "east_adam", "iron_tool", 1)
        out = rt._execute_attack("east_adam", {
            "action_type": "attack", "target_id": "d1"})
        assert out["status"] == "success"
        assert out["killed"] is True, "iron kills a deer outright"
        assert load_inventory(rt._store)["east_adam"].get("meat") == 4
        assert rt._world_state.wildlife == [], "the kill is removed"

    def test_distant_animal_rejects(self, tmp_path):
        rt = self._rt_with_deer(tmp_path)
        rt._world_state.wildlife[0]["tile"] = (9, 9)
        out = rt._execute_attack("east_adam", {
            "action_type": "attack", "target_id": "d1"})
        assert out["status"] == "rejected"
        assert "reach" in out["reason"]


class TestObservation:
    def test_wildlife_visible_in_observation_shape(self):
        rt = _runtime_stub()
        rt._world_state.wildlife = [
            {"kind": "deer", "id": "d1", "tile": (2, 0), "hp": 2}]
        seen = rt._wildlife_visible("east_adam", 4000)
        assert seen["nearby"] and seen["nearby"][0]["kind"] == "deer"
        assert seen["howling"] is False

    def test_howling_carries_in_the_dark(self):
        rt = _runtime_stub()
        rt._world_state.wildlife = [
            {"kind": "wolf", "id": "w1", "tile": (9, 0), "hp": 1}]
        night_hb = 1008
        seen = rt._wildlife_visible("east_adam", night_hb)
        assert seen["howling"] is True, "howls carry before wolves arrive"

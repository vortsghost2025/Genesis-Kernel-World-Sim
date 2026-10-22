"""Survival wiring through the runtime — the body must reach the agents.

The physics module owns the arithmetic (test_survival_physics.py).
These pin the seams: the heartbeat hook ages bodies, the observation
carries the body and the hour, the eat action spends belongings, and
a collapsed body cannot act. The causal chain Sean named — hunger →
eat, cold → fire, neglect → collapse → rescue — is tested end to end
at the runtime seam, not in isolation.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    add_to_inventory,
)


class _FakeWorldState:
    """Minimal world-state stand-in: the seams the runtime touches."""

    def __init__(self):
        self.tile_occupancy = {
            "east_adam": "cont_a_gen_0_0",
            "east_eve": "cont_a_gen_0_0",
        }
        self.public_objects = {}
        self.public_messages = []
        self.vitals = {}


class _FakeIdentity:
    """Just enough identity for the message path."""

    birth_candidate = {
        "adam_identity": {"canonical_name": "Adam"},
        "eve_identity": {"canonical_name": "Eve"},
    }
    adam_agent_id = "a" * 64
    eve_agent_id = "b" * 64


def _runtime_stub():
    """A bare object carrying the survival methods, bound to a fake
    world state. This tests the runtime's own survival code, not the
    runtime's constructor."""
    from backend.world.first_pair_runtime import FirstPairRuntime
    rt = object.__new__(FirstPairRuntime)
    rt._world_state = _FakeWorldState()
    rt._adam_ref = "east_adam"
    rt._eve_ref = "east_eve"
    rt._pair_id = "east"
    rt._identity_record = _FakeIdentity()
    return rt


class TestHeartbeatHook:
    def test_hook_ages_both_bodies(self):
        rt = _runtime_stub()
        rt.apply_survival_to_all(100)
        for ref in ("east_adam", "east_eve"):
            v = rt._world_state.vitals[ref]
            assert v["hunger"] > survival.initial_vitals()["hunger"], (
                "hunger must rise each heartbeat"
            )
            assert "downed" in v

    def test_hook_persists_into_world_state(self):
        rt = _runtime_stub()
        rt.apply_survival_to_all(100)
        assert set(rt._world_state.vitals) == {"east_adam", "east_eve"}

    def test_fire_warms_and_hunger_still_rises(self):
        rt = _runtime_stub()
        rt._world_state.public_objects = {
            "o1": {"tile_id": "cont_a_gen_1_0", "object_type": "campfire"},
        }
        start = survival.initial_vitals()["warmth"]
        for hb in (200, 201, 202):
            rt.apply_survival_to_all(hb)
        v = rt._world_state.vitals["east_adam"]
        assert v["warmth"] == 100.0, "fire climbs fast and pins at full"
        assert v["hunger"] > 18.0, "fire feeds warmth, not hunger"
        assert v["warmth"] > start


class TestFireAndShelterDetection:
    def test_fire_within_radius_detected(self):
        rt = _runtime_stub()
        rt._world_state.public_objects = {
            "o1": {"tile_id": "cont_a_gen_3_0", "object_type": "campfire"},
        }
        assert rt._nearby_fire("cont_a_gen_0_0") is True
        assert rt._nearby_fire("cont_a_gen_9_9") is False

    def test_shelter_adjacent_detected(self):
        rt = _runtime_stub()
        rt._world_state.public_objects = {
            "o1": {"tile_id": "cont_a_gen_1_0", "object_type": "wooden_wall"},
        }
        assert rt._in_shelter("cont_a_gen_0_0") is True
        assert rt._in_shelter("cont_a_gen_5_5") is False

    def test_cave_and_overhang_shelter_detected(self):
        rt = _runtime_stub()
        rt._world_state.public_objects = {
            "o1": {"tile_id": "cont_a_gen_1_0", "object_type": "rock_cave_shelter"},
        }
        assert rt._in_shelter("cont_a_gen_0_0") is True
        assert rt._in_shelter("cont_a_gen_1_0") is True

    def test_nonfire_heat_sources_do_not_count(self):
        rt = _runtime_stub()
        rt._world_state.public_objects = {
            "o1": {"tile_id": "cont_a_gen_0_0", "object_type": "storage"},
        }
        assert rt._nearby_fire("cont_a_gen_0_0") is False


class TestEat:
    def _rt_with_food(self, tmp_path):
        from backend.world.first_pair_persistence import (
            FirstPairPersistenceStore, add_to_inventory)
        rt = _runtime_stub()
        rt._store = FirstPairPersistenceStore(tmp_path / "store")
        add_to_inventory(rt._store, "east_adam", "wild_berries", 5)
        return rt

    def test_eat_consumes_and_satisfies(self, tmp_path):
        from backend.world.first_pair_persistence import load_inventory
        rt = self._rt_with_food(tmp_path)
        rt._vitals_for("east_adam")["hunger"] = 80.0
        out = rt._eat_satisfaction("east_adam", "wild_berries")
        assert out["status"] == "success"
        assert out["hunger_now"] < 80.0
        assert load_inventory(rt._store)["east_adam"]["wild_berries"] == 4

    def test_eat_with_empty_hands_rejects(self, tmp_path):
        rt = self._rt_with_food(tmp_path)
        out = rt._eat_satisfaction("east_eve", "wild_berries")
        assert out["status"] == "rejected"
        assert "no wild_berries" in out["reason"]

    def test_downed_agent_cannot_act_but_can_cry_out(self, tmp_path):
        rt = self._rt_with_food(tmp_path)
        rt._vitals_for("east_adam")["downed"] = True
        blocked = rt._execute_action("east_adam", {
            "action_type": "gather", "resource_kind": "stone"}, 100)
        assert blocked["status"] == "rejected"
        assert "collapsed" in blocked["reason"]
        cry = rt._execute_action("east_adam", {
            "action_type": "leave_public_message",
            "recipient": "all", "message": "help"}, 100)
        assert cry.get("status") != "rejected"

    def test_eat_via_execute_action_dispatch(self, tmp_path):
        from backend.world.first_pair_persistence import load_inventory
        rt = self._rt_with_food(tmp_path)
        rt._vitals_for("east_adam")["hunger"] = 60.0
        out = rt._execute_action("east_adam", {
            "action_type": "eat", "resource_kind": "wild_berries"}, 100)
        assert out["status"] == "success"
        assert load_inventory(rt._store)["east_adam"]["wild_berries"] == 4


class TestDownedFeeding:
    """The changelog promised: food brought to a downed agent feeds
    them. These pin both rescue paths — own pocket, and the partner's
    deposit on the tile. Blocking eat while holding food would be the
    retired model's impossible board reborn."""

    def test_downed_agent_can_eat_own_food(self, tmp_path):
        rt = _runtime_stub()
        rt._store = FirstPairPersistenceStore(tmp_path / "s1")
        add_to_inventory(rt._store, "east_adam", "wild_berries", 3)
        rt._vitals_for("east_adam")["downed"] = True
        rt._vitals_for("east_adam")["hunger"] = 95.0
        out = rt._execute_action("east_adam", {
            "action_type": "eat", "resource_kind": "wild_berries"}, 100)
        assert out["status"] == "success", (
            "a collapsed body must still reach its own pocket"
        )

    def test_downed_agent_auto_eats_from_tile_object(self, tmp_path):
        rt = _runtime_stub()
        rt._store = FirstPairPersistenceStore(tmp_path / "s2")
        rt._world_state.public_objects = {
            "cache1": {"tile_id": "cont_a_gen_0_0",
                       "object_type": "storage",
                       "materials": {"wild_berries": 4}},
        }
        v = rt._vitals_for("east_adam")
        v["downed"] = True
        v["hunger"] = 90.0
        rt.apply_survival_to_all(300)
        v2 = rt._world_state.vitals["east_adam"]
        # 90 rises 1.4 then drops by the berry's 18 satisfaction
        assert v2["hunger"] < 90.0
        assert rt._world_state.public_objects["cache1"]["materials"]["wild_berries"] == 3

    def test_downed_with_no_food_stays_hungry(self, tmp_path):
        rt = _runtime_stub()
        rt._world_state.public_objects = {}
        v = rt._vitals_for("east_adam")
        v["downed"] = True
        v["vitality"] = 5.0
        v["hunger"] = 90.0
        rt.apply_survival_to_all(300)
        # no food: hunger only rises; passive recovery stays below standing
        assert rt._world_state.vitals["east_adam"]["hunger"] > 90.0
        assert rt._world_state.vitals["east_adam"]["downed"] is True

    def test_standing_agent_does_not_auto_eat(self, tmp_path):
        rt = _runtime_stub()
        rt._store = FirstPairPersistenceStore(tmp_path / "s3")
        rt._world_state.public_objects = {
            "cache1": {"tile_id": "cont_a_gen_0_0",
                       "object_type": "storage",
                       "materials": {"wild_berries": 4}},
        }
        v = rt._vitals_for("east_adam")
        v["downed"] = False
        v["hunger"] = 90.0
        rt.apply_survival_to_all(300)
        # standing bodies choose to eat; objects are not raided silently
        assert rt._world_state.public_objects["cache1"]["materials"]["wild_berries"] == 4


class TestObservationExposure:
    def test_vitals_and_environment_shapes(self):
        rt = _runtime_stub()
        v = dict(rt._vitals_for("east_adam"))
        v["state"] = survival.vitals_state_label(v)
        assert v["state"] in ("well", "hungry", "cold", "starving",
                              "freezing", "failing", "collapsed")
        env = {
            "time_of_day": "night" if survival.is_night(1000) else "day",
            "season": survival.season(1000),
            "temperature": round(survival.ambient_temperature(1000), 1),
        }
        assert env["time_of_day"] in ("day", "night")
        assert env["season"] in ("spring", "summer", "autumn", "winter")
        assert isinstance(env["temperature"], float)


class TestMigration:
    def test_old_store_gets_healthy_defaults(self):
        """An existing agent (3847 heartbeats old) wakes with a fed,
        warm body — no retroactive famine."""
        rt = _runtime_stub()
        v = rt._vitals_for("east_adam")
        assert v["hunger"] < 30.0 and v["warmth"] > 70.0
        assert v["vitality"] == 100.0 and v["downed"] is False

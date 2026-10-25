"""Tests for Insects, Bees, and Honeycomb Gathering (Epistemic Layer)."""
import pytest
from backend.world import insects
from backend.world.first_pair_runtime import FirstPairRuntime
from backend.world import wildlife


def test_bee_colony_states():
    # Warm clear day -> active
    assert insects.bee_colony_state("clear", 65.0, is_night=False, near_smoke=False) == "active"
    # Smoke present -> calmed (regardless of weather or time)
    assert insects.bee_colony_state("clear", 65.0, is_night=False, near_smoke=True) == "calmed"
    # Night -> dormant
    assert insects.bee_colony_state("clear", 65.0, is_night=True, near_smoke=False) == "dormant"
    # Rain -> dormant
    assert insects.bee_colony_state("rain", 55.0, is_night=False, near_smoke=False) == "dormant"
    # Storm -> dormant
    assert insects.bee_colony_state("storm", 55.0, is_night=False, near_smoke=False) == "dormant"
    # Cold temperature (< 45.0) -> dormant
    assert insects.bee_colony_state("clear", 40.0, is_night=False, near_smoke=False) == "dormant"


def test_resolve_bee_gather_calmed_and_dormant():
    dmg, msg = insects.resolve_bee_gather("calmed", current_vitality=100.0)
    assert dmg == 0.0
    assert "safely under the cover of campfire smoke" in msg

    dmg, msg = insects.resolve_bee_gather("dormant", current_vitality=100.0)
    assert dmg == 0.0
    assert "dormant" in msg


def test_resolve_bee_gather_active_stings_no_artificial_floor():
    dmg, msg = insects.resolve_bee_gather("active", current_vitality=100.0)
    assert dmg == 2.0
    assert "-2.0 vitality" in msg

    # At low vitality, stings still inflict standard 2.0 damage (standard collapse rules apply)
    dmg_low, _ = insects.resolve_bee_gather("active", current_vitality=1.5)
    assert dmg_low == 2.0


def test_ambient_insect_atmosphere_canonical_biomes():
    # Crickets on warm clear night
    desc = insects.ambient_insect_atmosphere("summer", "clear", is_night=True, biome="temperate_hills")
    assert desc is not None
    assert "Crickets" in desc

    # Midges in wetland / swamp / lake
    desc = insects.ambient_insect_atmosphere("summer", "rain", is_night=False, biome="wetland")
    assert desc is not None
    assert "midges" in desc

    desc_lake = insects.ambient_insect_atmosphere("summer", "clear", is_night=False, biome="deep_lake")
    assert desc_lake is not None
    assert "midges" in desc_lake

    # Pollinators in canonical forest biomes (temperate_forest, coastal_forest, dense_woodland, dark_thicket)
    for b in ("temperate_forest", "coastal_forest", "dense_woodland", "dark_thicket"):
        desc = insects.ambient_insect_atmosphere("spring", "clear", is_night=False, biome=b)
        assert desc is not None, f"Failed for biome {b}"
        assert "pollinators" in desc


class _FakeWorldState:
    def __init__(self):
        self.tile_occupancy = {"east_eve": "cont_a_gen_0_0", "east_adam": "cont_a_gen_10_10"}
        self.public_objects = {}
        self.public_messages = []
        self.vitals = {"east_eve": {"vitality": 50.0, "hunger": 20.0, "warmth": 100.0, "downed": False}}
        self.wildlife = []


def _make_runtime_stub(monkeypatch, tmp_path):
    rt = object.__new__(FirstPairRuntime)
    rt._world_state = _FakeWorldState()
    rt._adam_ref = "east_adam"
    rt._eve_ref = "east_eve"
    rt._pair_id = "east"
    rt._store = tmp_path
    rt._current_tile_resources = {
        "cont_a_gen_0_0": [{"kind": "honeycomb", "amount": 3}],
    }
    monkeypatch.setattr("backend.world.first_pair_runtime.add_to_inventory", lambda s, ref, k, amt: None)
    return rt


def test_runtime_gather_honeycomb_collapse_on_zero_vitality(monkeypatch, tmp_path):
    rt = _make_runtime_stub(monkeypatch, tmp_path)
    # Eve at 1.5 HP gathering active honeycomb without smoke
    rt._world_state.vitals["east_eve"]["vitality"] = 1.5
    monkeypatch.setattr("backend.world.survival.weather_forecast", lambda pid, hb: {"current": "clear", "next": "clear", "changes_at_heartbeat": 5000})
    monkeypatch.setattr("backend.world.survival.effective_temperature", lambda hb, w: 70.0)
    monkeypatch.setattr("backend.world.survival.is_night", lambda hb: False)
    monkeypatch.setattr(rt, "_nearby_smoke", lambda tile, hb: False)

    outcome = rt._execute_gather("east_eve", {"action_type": "gather", "resource_kind": "honeycomb"}, heartbeat_number=4500)
    assert outcome["status"] == "success"
    assert outcome["sting_damage"] == 2.0
    # 1.5 - 2.0 = 0.0 vitality -> downed state triggered
    assert rt._world_state.vitals["east_eve"]["vitality"] == 0.0
    assert rt._world_state.vitals["east_eve"]["downed"] is True


def test_runtime_gather_honeycomb_calmed_by_smoke(monkeypatch, tmp_path):
    rt = _make_runtime_stub(monkeypatch, tmp_path)
    monkeypatch.setattr("backend.world.survival.weather_forecast", lambda pid, hb: {"current": "clear", "next": "clear", "changes_at_heartbeat": 5000})
    monkeypatch.setattr("backend.world.survival.effective_temperature", lambda hb, w: 70.0)
    monkeypatch.setattr("backend.world.survival.is_night", lambda hb: False)
    monkeypatch.setattr(rt, "_nearby_smoke", lambda tile, hb: True)

    outcome = rt._execute_gather("east_eve", {"action_type": "gather", "resource_kind": "honeycomb"}, heartbeat_number=4500)
    assert outcome["status"] == "success"
    assert outcome["bee_colony_state"] == "calmed"
    assert outcome["sting_damage"] == 0.0
    assert "safely under the cover of campfire smoke" in outcome["detail"]
    assert rt._world_state.vitals["east_eve"]["vitality"] == 50.0


def test_wildlife_tick_rain_snuffed_fire_does_not_deter_wolves(monkeypatch, tmp_path):
    """Rain snuffs unsheltered fires; snuffed fires must not deter wolves or create safety zones."""
    rt = _make_runtime_stub(monkeypatch, tmp_path)
    rt._world_state.tile_occupancy = {"east_adam": "cont_a_gen_0_0"}
    rt._world_state.vitals = {"east_adam": {"vitality": 100.0, "downed": False}}

    # Place an unsheltered campfire at [0, 1]
    rt._world_state.public_objects = {
        "fire_1": {"object_type": "campfire", "tile_id": "cont_a_gen_0_1", "materials": {"wood": 2}}
    }
    # Place a wolf adjacent to adam at [1, 0]
    rt._world_state.wildlife = [{
        "kind": "wolf",
        "id": "wolf-1",
        "tile": [1, 0],
        "hp": 2,
    }]

    # CASE A: Clear weather -> fire burns, deters wolf bite (wolf is within FIRE_SAFETY_RADIUS of fire)
    monkeypatch.setattr("backend.world.survival.weather_at", lambda pid, hb: ("clear", 5000))
    monkeypatch.setattr("backend.world.survival.is_night", lambda hb: True)
    rt.wildlife_tick(heartbeat_number=4500)
    assert rt._world_state.vitals["east_adam"]["vitality"] == 100.0, "Burning fire in clear weather should protect"

    # CASE B: Rain -> unsheltered fire is snuffed -> wolf strikes!
    monkeypatch.setattr("backend.world.survival.weather_at", lambda pid, hb: ("rain", 5000))
    # Reset wolf to adjacent tile [1, 0]
    rt._world_state.wildlife = [{
        "kind": "wolf",
        "id": "wolf-1",
        "tile": [1, 0],
        "hp": 2,
    }]
    rt.wildlife_tick(heartbeat_number=4501)
    # Adam takes wolf bite damage (100 - 8 = 92)
    assert rt._world_state.vitals["east_adam"]["vitality"] == 92.0, "Snuffed fire in rain must NOT protect against wolves"

    # CASE C: Rain + sheltered fire -> fire stays lit and protects!
    # Place a roof/shelter on the fire tile
    rt._world_state.public_objects["roof_1"] = {
        "object_type": "roof",
        "tile_id": "cont_a_gen_0_1"
    }
    rt._world_state.wildlife = [{
        "kind": "wolf",
        "id": "wolf-1",
        "tile": [1, 0],
        "hp": 2,
    }]
    rt.wildlife_tick(heartbeat_number=4502)
    assert rt._world_state.vitals["east_adam"]["vitality"] == 92.0, "Roofed fire in rain stays lit and protects"


def test_unearned_fire_without_materials_rejected_and_nonfunctional(monkeypatch, tmp_path):
    """An agent cannot declare an unearned campfire without materials.
    Unearned zero-material objects fail _is_functional_fire and provide no warmth,
    no smoke (bee gathering stings), and no wolf deterrence.
    """
    rt = _make_runtime_stub(monkeypatch, tmp_path)
    rt._habitat = {"starting_tile_ids": {"east_adam": "cont_a_gen_0_0", "east_eve": "cont_a_gen_0_0"}}
    rt._agent_view = lambda ref: {"agent_id": f"id_{ref}"}

    # 1. create_public_object rejects functional construction types
    for bad_type in ("campfire", "fire", "hearth", "forge", "furnace", "shelter", "cabin", "hut", "lean-to"):
        outcome = rt._execute_create_public_object("east_adam", {
            "action_type": "create_public_object",
            "object_id": f"unearned-{bad_type}",
            "object_type": bad_type,
            "description": "magic object without materials",
            "tile_id": "cont_a_gen_0_0",
        }, heartbeat_number=100)
        assert outcome["status"] == "rejected", f"Expected {bad_type} to be rejected"
        assert "cannot be created without construction materials" in outcome["reason"]

    # 2. Existing public object with materials={} fails _is_functional_fire
    fake_fire = {
        "object_id": "cheat_fire",
        "object_type": "campfire",
        "tile_id": "cont_a_gen_0_0",
        "materials": {},
    }
    assert FirstPairRuntime._is_functional_fire(fake_fire) is False
    assert FirstPairRuntime._is_functional_fire({"object_id": "no_mats", "object_type": "campfire"}) is False

    # Legitimate constructed fire with materials passes
    real_fire = {
        "object_id": "real_fire",
        "object_type": "campfire",
        "tile_id": "cont_a_gen_0_0",
        "materials": {"wood": 2},
    }
    assert FirstPairRuntime._is_functional_fire(real_fire) is True

    # 3. An unearned fire in world_state does NOT warm, smoke, or protect from bees
    rt._world_state.public_objects = {"cheat_fire": fake_fire}
    assert rt._nearby_fire("cont_a_gen_0_0") is False
    assert rt._nearby_smoke("cont_a_gen_0_0") is False

    # Gathering honeycomb next to an unearned zero-material fire still stings Eve!
    monkeypatch.setattr("backend.world.survival.weather_forecast", lambda pid, hb: {"current": "clear", "next": "clear", "changes_at_heartbeat": 5000})
    monkeypatch.setattr("backend.world.survival.effective_temperature", lambda hb, w: 70.0)
    monkeypatch.setattr("backend.world.survival.is_night", lambda hb: False)
    rt._world_state.vitals["east_eve"]["vitality"] = 50.0
    gather_outcome = rt._execute_gather("east_eve", {"action_type": "gather", "resource_kind": "honeycomb"}, heartbeat_number=4500)
    assert gather_outcome["sting_damage"] == 2.0
    assert rt._world_state.vitals["east_eve"]["vitality"] == 48.0

    # 4. An unearned fire in world_state does NOT deter wolves
    rt._world_state.tile_occupancy = {"east_adam": "cont_a_gen_0_0"}
    rt._world_state.vitals["east_adam"] = {"vitality": 100.0, "downed": False}
    rt._world_state.wildlife = [{
        "kind": "wolf",
        "id": "wolf-unearned",
        "tile": [1, 0],
        "hp": 2,
    }]
    monkeypatch.setattr("backend.world.survival.weather_at", lambda pid, hb: ("clear", 5000))
    monkeypatch.setattr("backend.world.survival.is_night", lambda hb: True)
    rt.wildlife_tick(heartbeat_number=4510)
    # Wolf bites Adam because cheat fire provides no deterrence
    assert rt._world_state.vitals["east_adam"]["vitality"] == 92.0


def test_continent_isolation_prevents_cross_continent_fire_and_shelter_effects(monkeypatch, tmp_path):
    """Objects on Continent B must never affect agents or wildlife on Continent A (and vice-versa),
    even when coordinate offsets happen to match.
    """
    rt = _make_runtime_stub(monkeypatch, tmp_path)
    # Runtime is on Continent A (East pair)
    assert rt._pair_continent == "cont_a"
    assert FirstPairRuntime._tile_continent("cont_a_gen_0_0") == "cont_a"
    assert FirstPairRuntime._tile_continent("cont_b_gen_0_0") == "cont_b"

    # Both tiles resolve to coordinate (0, 0)
    assert FirstPairRuntime._tile_xy("cont_a_gen_0_0") == (0, 0)
    assert FirstPairRuntime._tile_xy("cont_b_gen_0_0") == (0, 0)

    # Place a fully-constructed legitimate campfire and shelter on Continent B at (0, 0)
    rt._world_state.public_objects = {
        "west_fire": {
            "object_id": "west_fire",
            "object_type": "campfire",
            "tile_id": "cont_b_gen_0_0",
            "materials": {"wood": 5},
        },
        "west_shelter": {
            "object_id": "west_shelter",
            "object_type": "shelter",
            "tile_id": "cont_b_gen_0_0",
            "materials": {"wood": 5},
        },
    }

    # Continent A agent standing at (0, 0) should NOT detect Continent B fire or shelter
    assert rt._nearby_fire("cont_a_gen_0_0") is False
    assert rt._nearby_smoke("cont_a_gen_0_0") is False
    assert rt._in_shelter("cont_a_gen_0_0") is False

    # Continent B lookup DOES detect them
    assert rt._nearby_fire("cont_b_gen_0_0") is True
    assert rt._nearby_smoke("cont_b_gen_0_0") is True
    assert rt._in_shelter("cont_b_gen_0_0") is True

    # Continent B campfire does NOT deter Continent A wolves in East wildlife_tick
    rt._world_state.tile_occupancy = {"east_adam": "cont_a_gen_0_0"}
    rt._world_state.vitals = {"east_adam": {"vitality": 100.0, "downed": False}}
    rt._world_state.wildlife = [{
        "kind": "wolf",
        "id": "wolf-cont-a",
        "tile": [1, 0],
        "hp": 2,
    }]
    monkeypatch.setattr("backend.world.survival.weather_at", lambda pid, hb: ("clear", 5000))
    monkeypatch.setattr("backend.world.survival.is_night", lambda hb: True)

    rt.wildlife_tick(heartbeat_number=4520)
    # Wolf bites Adam because Continent B fire cannot project warmth/light across the ocean!
    assert rt._world_state.vitals["east_adam"]["vitality"] == 92.0

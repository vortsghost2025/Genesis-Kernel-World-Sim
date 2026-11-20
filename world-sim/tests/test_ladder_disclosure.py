"""Phase 10RS — the ladder disclosure must state the numbers that decide it.

Measured 2026-11-15 against the live world: east has 68 roofed structures and
west 158, and NOT ONE above rung 1. The ladder's disclosure was the reason it
could not bite:

  * its closing sentence described the PRE-10QU mechanic -- "a connected home's
    comfort comes from its tier weight, which is the roofed footprint plus the
    bonus for the best rung". 10QU moved comfort onto the best RUNG alone, so
    the prompt had become a lie about the world it describes;
  * the number that actually decides whether to climb -- the comfort floor each
    rung holds -- appeared nowhere;
  * `shelter`, the type they build most, is a LEGACY ALIAS for rung 1, so it is
    the bottom of the ladder, not a way up it, and nothing said so while the
    action menu lists `shelter` first.

These tests require the disclosure to state the truth AND to be derived from the
runtime's own tables, so it cannot drift again.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m  # noqa: E402
from backend.world.first_pair_cognition_interface import AgentContext  # noqa: E402
from backend.world.first_pair_runtime import (  # noqa: E402
    _LEGACY_TYPE_RUNG,
    _STRUCTURE_RUNGS,
    _home_network_tier,
    _home_thermal_index,
)

TEXT = m._structure_ladder_description()


def _disclosed_floors(text: str) -> dict[str, float]:
    """{rung name: warmth figure} as the disclosure prints them."""
    out = {}
    for name in _STRUCTURE_RUNGS:
        match = re.search(
            rf"`{name}` \(rung \d+, [^;]*; warmth holds near ([\d.]+) inside", text)
        if match:
            out[name] = float(match.group(1))
    return out


# --- the numbers are the physics --------------------------------------------

def test_every_rung_discloses_the_floor_the_physics_uses():
    """Disclosure equals physics, rung by rung, from one source of truth."""
    disclosed = _disclosed_floors(TEXT)
    assert set(disclosed) == set(_STRUCTURE_RUNGS), disclosed
    for name, rung in _STRUCTURE_RUNGS.items():
        expected = _home_network_tier(_home_thermal_index(rung["rung"]))[0]
        assert disclosed[name] == expected, (name, disclosed[name], expected)


def test_the_floors_rise_with_the_rung_so_climbing_is_worth_something():
    floors = [_disclosed_floors(TEXT)[name] for name in _STRUCTURE_RUNGS]
    assert floors == sorted(floors) and len(set(floors)) == len(floors), floors
    assert floors[0] == 45.0 and floors[-1] == 88.0, floors


# --- and the sentence that had become a lie ---------------------------------

def test_it_no_longer_claims_the_footprint_drives_comfort():
    """10QU moved comfort onto the best rung; the old sentence said otherwise."""
    assert "comfort comes from its tier weight" not in TEXT
    assert "plus the bonus for the best rung" not in TEXT


def test_it_states_that_warmth_comes_from_the_best_rung_not_the_size():
    assert "warmth comes from the BEST rung" in TEXT
    assert "not from its size" in TEXT
    assert "nothing about how many roofed tiles a home covers changes that" in TEXT


def test_it_still_says_the_footprint_governs_capacity():
    """Size was not nerfed, only moved: it buys storage, not warmth."""
    assert "governs CAPACITY" in TEXT
    assert "cellar food" in TEXT and "water store" in TEXT


# --- and the specific thing they keep building ------------------------------

def test_it_says_the_generic_shelter_is_rung_1():
    """`shelter` is a legacy alias for rung 1 -- the bottom, not a way up."""
    rung = _LEGACY_TYPE_RUNG.get("shelter")
    assert rung == 1, rung
    assert f"The generic `shelter` type counts as rung {rung}" in TEXT
    assert "where the ladder starts, not a way up it" in TEXT


def test_every_rung_is_still_disclosed_with_its_cost_and_effects():
    """The 10QC property is preserved: the TABLE is rendered, not a list."""
    for name, record in _STRUCTURE_RUNGS.items():
        assert f"`{name}` (rung {record['rung']}," in TEXT, name
        for kind in record["floor"]:
            assert f"{kind} x{record['floor'][kind]}" in TEXT, (name, kind)
        assert record["effects"] in TEXT, name


def _ctx() -> AgentContext:
    return AgentContext(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position="cont_a_gen_0_0",
        observation={"self_body": {"downed": False, "vitality": 100.0,
                                   "thirst": 10.0, "hunger": 10.0,
                                   "warmth": 100.0, "wetness": 0.0}},
        memory=[], goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
    )


def test_it_reaches_the_prompt():
    """The description is resolved at call time inside build_system_prompt (to
    dodge a circular import), so the test asks the PROMPT, not the module."""
    prompt = m.build_system_prompt(_ctx())
    assert "Structure ladder, each rung a buildable roofed type" in prompt
    assert "warmth holds near 62 inside" in prompt
    assert "warmth comes from the BEST rung" in prompt
    assert "The generic `shelter` type counts as rung 1" in prompt


def test_settlement_line_computes_comfort_floor_from_best_rung_not_tier_weight():
    """Live bug caught 2026-11-15: `settlement_lines` passed `tier_weight`
    (footprint + rung_bonus = 70 in West!) into `_home_network_tier()`, printing
    `comfort floor is 82` on line 1 for a rung-1 shanty town while line 4 printed
    `warmth holds near 45 inside`. Comfort floor on line 1 must use
    `_home_thermal_index(best_rung)` so rung 1 prints `comfort floor is 45`
    regardless of footprint."""
    import dataclasses

    ctx = dataclasses.replace(
        _ctx(),
        home_network_footprint=69,
        home_rung={"best_rung": 1, "rung": 1, "type": "shelter"},
    )
    prompt = m.build_system_prompt(ctx)
    assert "comfort floor is 45" in prompt, prompt
    assert "comfort floor is 82" not in prompt, prompt


def test_homestead_timber_pool_and_project_continuation_let_partner_build_cabin(tmp_path):
    """Live bug caught 2026-11-15 (West HB 13923): `west_eve` held `wood: 206,
    timber: 0` while `west_adam` held `timber: 221, stone: 42`, and her `cabin`
    build was rejected because she had 0 personal timber and declared 0 timber.

    Phase 10RU reworked the answer to that. The homestead pool is KEPT -- a
    builder can draw structural materials from containers at the site and from a
    partner standing beside them -- but the world no longer fills the missing
    timber into the agent's declaration for it. A short declaration is refused
    with the pool named, so the agent re-declares from it itself; a declaration
    that names the floor succeeds by drawing on the pool. The project
    continuation half is unchanged and still asserted: repeating the build with
    an existing object_id advances the unfinished project on the current tile
    instead of spawning duplicate `-hb` foundations."""
    from backend.world.first_pair_persistence import FirstPairPersistenceStore, add_to_inventory
    from backend.world.first_pair_runtime import FirstPairRuntime

    store = FirstPairPersistenceStore(tmp_path / "homestead_store")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt._load_or_initialize()
    tile = "cont_a_gen_0_0"
    rt._world_state.tile_occupancy["east_eve"] = tile
    rt._world_state.tile_occupancy["east_adam"] = tile

    # Existing object with same id on another tile (triggers the -hb suffix path)
    rt._world_state.public_objects["my_cabin_01"] = {
        "object_id": "my_cabin_01",
        "object_type": "shelter",
        "tile_id": "cont_a_gen_5_5",
        "creator_agent_id": rt._agent_view("east_eve")["agent_id"],
    }

    # Eve has wood only; Adam has the timber & stone hoard
    add_to_inventory(store, "east_eve", "wood", 50)
    add_to_inventory(store, "east_adam", "timber", 30)
    add_to_inventory(store, "east_adam", "stone", 20)

    stages_seen = []

    # Phase 10RU: the world does not invent the missing timber. Eve declares
    # wood only, holds no timber, and the pool (Adam, beside her) has 30 --
    # so the refusal must SAY that rather than silently adding it.
    short = rt._execute_build(
        "east_eve",
        {
            "action_type": "build",
            "object_id": "my_cabin_01",
            "object_type": "cabin",
            "tile_id": tile,
            "materials": {"wood": 10},
            "description": "A proper timber cabin for our homestead.",
        },
        heartbeat_number=99,
    )
    assert short["status"] == "rejected", short
    assert "you declared 0" in short["reason"], short["reason"]
    assert "homestead pool holds" in short["reason"], short["reason"]

    for hb in range(100, 105):
        res = rt._execute_build(
            "east_eve",
            {
                "action_type": "build",
                "object_id": "my_cabin_01",
                "object_type": "cabin",
                "tile_id": tile,
                "materials": {"timber": 3, "stone": 4, "wood": 10},
                "description": "A proper timber cabin for our homestead.",
            },
            heartbeat_number=hb,
        )
        assert res["status"] == "success", res
        stages_seen.append(res.get("stage", "foundation"))

    assert stages_seen == ["foundation", "frame", "walls", "roofed", "finished"]
    # Only ONE project was created on `tile`, not 5 duplicate `-hb` foundations
    on_tile = [
        oid for oid, obj in rt._world_state.public_objects.items()
        if isinstance(obj, dict) and obj.get("tile_id") == tile
    ]
    assert len(on_tile) == 1, on_tile
    built = rt._world_state.public_objects[on_tile[0]]
    assert built["structure_rung"] == 3
    assert built["construction_stage"] == "finished"


def test_use_object_drink_and_empty_extract_inventory_reminder(tmp_path):
    """Live bugs caught 2026-11-15:
    1) `use_object` with `operation='drink'` was refused as unknown operation;
    2) `use_object` with `operation='extract'` on an empty cache did not remind
       the agent when they already carried that resource in their own pack."""
    from backend.world.first_pair_persistence import FirstPairPersistenceStore, add_to_inventory
    from backend.world.first_pair_runtime import FirstPairRuntime

    store = FirstPairPersistenceStore(tmp_path / "east_store")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt._load_or_initialize()
    tile = "cont_a_gen_0_0"
    rt._world_state.tile_occupancy["east_adam"] = tile

    rt._world_state.public_objects["water_pot"] = {
        "object_id": "water_pot",
        "object_type": "storage",
        "tile_id": tile,
        "creator_agent_id": rt._agent_view("east_adam")["agent_id"],
        "contents": {"fresh_water": 2},
    }
    rt._ensure_life_state("east_adam", 1)
    rt._vitals_for("east_adam")["thirst"] = 50.0

    # 1) use_object(operation="drink") routes to _execute_drink and succeeds
    drink_res = rt._execute_use_object(
        "east_adam",
        {"object_id": "water_pot", "operation": "drink"},
        heartbeat_number=10,
    )
    assert drink_res["status"] == "success", drink_res

    # 2) Empty container extract reminds agent of what they already carry
    rt._world_state.public_objects["water_pot"]["contents"] = {}
    add_to_inventory(store, "east_adam", "fresh_water", 1291)
    ext_res = rt._execute_use_object(
        "east_adam",
        {"object_id": "water_pot", "operation": "extract", "materials": {"fresh_water": 2}},
        heartbeat_number=11,
    )
    assert ext_res["status"] == "rejected"
    assert "You already carry 1291 fresh_water in your belongings." in ext_res["reason"]

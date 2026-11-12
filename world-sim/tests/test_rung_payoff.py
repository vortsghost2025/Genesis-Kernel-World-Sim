"""Phase 10QC - the rung ladder actually pays to climb.

Specification: docs/phase_10qc_rung_payoff_spec.md

Operator, 2026-11-11: "they're actually at level 4 which is progress, but
they're not building real houses then they only have shelters which is fine
but it doesn't make sense for level 4 to be the end here."

The measured cause is that `rung_weight` is written into the object envelope
and read by nothing, so a house and the three lean-tos it replaces were worth
exactly the same roofed units, the tier table stopped at footprint 8, and the
five-rung vocabulary appeared in exactly one string in the whole prompt - the
rejection message for an unknown type. These tests pin the fixed contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

import pytest

from backend.world import first_pair_cognition_model as m
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    load_inventory,
)
from backend.world.first_pair_runtime import (
    _CONSTRUCTION_STAGES,
    _HOME_NETWORK_TIERS,
    _STRUCTURE_RUNGS,
    FirstPairRuntime,
    _structure_rung_of,
    _BANNED_DIRECTIVE_PHRASES,
)

# The 10PJ rows, verbatim. 10QC appends rows and must not edit these: an
# existing settlement's comfort floor is a promise the world already made.
_TIERS_10PJ = (
    (1, 45.0, 0.45, 1.00, 0.40, 0.10),
    (2, 52.0, 0.30, 1.25, 0.55, 0.12),
    (3, 62.0, 0.18, 1.50, 0.70, 0.15),
    (5, 68.0, 0.14, 1.75, 0.90, 0.18),
    (8, 75.0, 0.10, 2.00, 1.10, 0.22),
)


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(
        heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store")
    )
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    rt._world_state.tile_occupancy["east_eve"] = "cont_a_gen_1_0"
    rt._world_state.tick = 100
    return rt


def _give(rt, **amounts):
    held = load_inventory(rt._store).get("east_adam", {})
    for kind, amount in amounts.items():
        need = amount - int(held.get(kind, 0) or 0)
        if need > 0:
            add_to_inventory(rt._store, "east_adam", kind, need)


def _move(rt, tile):
    """Stand the agent on a tile. Placement is enforced, so a settlement
    spread over several tiles requires the agent to actually be there."""
    rt._world_state.tile_occupancy["east_adam"] = tile


def _build(rt, object_id, object_type, tile, **materials):
    return rt._execute_action("east_adam", {
        "action_type": "build",
        "object_id": object_id,
        "object_type": object_type,
        "tile_id": tile,
        "description": f"a {object_type}",
        "materials": materials,
    }, 100)


def _advance(rt, object_id, object_type, tile, **materials):
    return rt._execute_action("east_adam", {
        "action_type": "build",
        "object_id": object_id,
        "object_type": object_type,
        "tile_id": tile,
        "description": f"a {object_type}",
        "materials": materials,
    }, 101)


def _finish(rt, object_id, object_type, tile):
    """Advance a staged project through every remaining stage."""
    for _ in range(len(_CONSTRUCTION_STAGES)):
        res = _advance(rt, object_id, object_type, tile)
        assert res.get("status") == "success", res
        if res.get("stage") == "finished":
            return res
    raise AssertionError("project never finished")


# ---------------------------------------------------------------------------
# the tier weight: a home is what it is, not how many tiles it covers
# ---------------------------------------------------------------------------

def test_rung_weight_is_actually_consumed_by_the_tier_lookup(tmp_path):
    """The 10PU section-5 promise, which 10PW never shipped.

    A finished rung-5 longhouse standing alone must reach a tier weight at
    least as high as the footprint units of four separate lean-tos would give.
    Before this phase `rung_weight` was written into the envelope and read by
    nothing, so the longhouse was worth exactly the same as the shacks.
    """
    rt = _runtime(tmp_path)
    _give(rt, timber=20, wood=20, stone=20, clay=20)
    res = _build(rt, "lh-1", "longhouse", "cont_a_gen_0_0",
                 timber=8, stone=10, wood=6)
    assert res["status"] == "success", res
    envelope = rt._world_state.public_objects["lh-1"]
    assert envelope["rung_weight"] == _STRUCTURE_RUNGS["longhouse"]["weight"]

    _finish(rt, "lh-1", "longhouse", "cont_a_gen_0_0")
    assert rt._home_network_footprint("cont_a_gen_0_0") >= 4

    weight = rt._home_tier_weight("cont_a_gen_0_0")
    # four lean-tos on four tiles would give footprint 4. One longhouse must
    # not be merely equal to them - it must outrank them.
    assert weight > 4, weight


def test_one_house_outranks_the_shacks_it_replaces(tmp_path):
    """The headline incentive: one proper home beats seven lean-tos.

    A house costs timber 4 / stone 6 / clay 4 - fourteen units against the
    single timber a lean-to costs. If the physics still priced it the same as
    a handful of shacks, the rational build stays a shack.
    """
    rt = _runtime(tmp_path)
    _give(rt, timber=40, stone=40, clay=40, wood=40)

    for i in range(7):
        tile = f"cont_a_gen_{i}_0"
        _move(rt, tile)
        assert _build(rt, f"lean-{i}", "lean-to", tile, timber=1)["status"] == "success"
        _finish(rt, f"lean-{i}", "lean-to", tile)

    shack_weight = rt._home_tier_weight("cont_a_gen_0_0")
    shack_params = rt._shelter_params_for("cont_a_gen_0_0")

    # Now the same settlement, but as one proper house plus the space it saves.
    rt2 = _runtime(tmp_path)
    _give(rt2, timber=4, stone=6, clay=4)
    assert _build(rt2, "house-1", "house", "cont_a_gen_0_0",
                  timber=4, stone=6, clay=4)["status"] == "success"
    _finish(rt2, "house-1", "house", "cont_a_gen_0_0")

    house_weight = rt2._home_tier_weight("cont_a_gen_0_0")
    house_params = rt2._shelter_params_for("cont_a_gen_0_0")
    assert house_weight > shack_weight, (house_weight, shack_weight)
    assert house_params["comfort_floor"] > shack_params["comfort_floor"]
    assert house_params["regen_rate"] > shack_params["regen_rate"]


def test_footprint_saturates_but_a_rung_upgrade_still_pays(tmp_path):
    """Past the saturation point another shack adds nothing; a better
    structure still adds its full bonus. This is the mechanic the operator
    has asked for since 10PH ("stop the 15 single houses beside each other").
    """
    from backend.world.first_pair_runtime import _FOOTPRINT_SATURATION
    rt = _runtime(tmp_path)
    _give(rt, timber=60, wood=60, stone=60, clay=60)
    for i in range(14):
        tile = f"cont_a_gen_{i}_0"
        _move(rt, tile)
        assert _build(rt, f"lean-{i}", "lean-to", tile, timber=1)["status"] == "success"
        _finish(rt, f"lean-{i}", "lean-to", tile)

    saturated = rt._home_tier_weight("cont_a_gen_0_0")
    assert rt._home_network_footprint("cont_a_gen_0_0") >= 14
    # 14 shacks: the tile count is capped at the saturation point and rung 1
    # adds no bonus, so the weight is exactly the cap.
    assert saturated == _FOOTPRINT_SATURATION, (saturated, _FOOTPRINT_SATURATION)

    # A rung upgrade on the same over-built settlement is still worth climbing.
    _give(rt, timber=8, stone=10, wood=6)
    _move(rt, "cont_a_gen_13_0")
    assert _build(rt, "lh", "longhouse", "cont_a_gen_13_0",
                  timber=8, stone=10, wood=6)["status"] == "success"
    _finish(rt, "lh", "longhouse", "cont_a_gen_13_0")
    # The longhouse sits at the far end of the 14-shack line, which is itself
    # connected, so the whole network now contains a rung-5 structure.
    assert rt._home_tier_weight("cont_a_gen_0_0") > saturated


def test_tier_table_rows_are_strictly_ordered_and_10pj_is_untouched():
    """The old cap was a wall. New rows must each beat the row below them on
    every axis, and the five rows the world already promised must not move."""
    assert _HOME_NETWORK_TIERS[:len(_TIERS_10PJ)] == _TIERS_10PJ
    assert len(_HOME_NETWORK_TIERS) > len(_TIERS_10PJ), (
        "the tier table must gain rows: 10QC's whole point is that the ladder "
        "does not end at footprint 8")

    for lower, higher in zip(_HOME_NETWORK_TIERS, _HOME_NETWORK_TIERS[1:]):
        assert higher[0] > lower[0]
        assert higher[1] > lower[1], f"floor must rise at {higher[0]}"
        assert higher[2] < lower[2], f"cold decay must fall at {higher[0]}"
        assert higher[3] > lower[3], f"rest regen must rise at {higher[0]}"
        assert higher[4] > lower[4], f"downed regen must rise at {higher[0]}"
        assert higher[5] > lower[5], f"warmth approach must rise at {higher[0]}"


def test_west_live_settlement_clears_the_old_cap(tmp_path):
    """The measured live lane: 46 roofed structures, best rung a cabin.

    Before 10QC that settlement sat at footprint 46 against a table that ended
    at 8, i.e. at the final answer with nothing left to earn. It must now sit
    above the old cap and still have room above it.
    """
    rt = _runtime(tmp_path)
    _give(rt, timber=200, wood=200, stone=200, clay=200)
    for i in range(46):
        tile = f"cont_a_gen_{i % 7}_{i // 7}"
        _move(rt, tile)
        assert _build(rt, f"s-{i}", "cabin", tile,
                      timber=3, stone=4)["status"] == "success"
        _finish(rt, f"s-{i}", "cabin", tile)

    footprint = rt._home_network_footprint("cont_a_gen_0_0")
    assert footprint >= 8, footprint
    weight = rt._home_tier_weight("cont_a_gen_0_0")
    assert weight > 8, (weight, footprint)
    params = rt._shelter_params_for("cont_a_gen_0_0")
    assert params["comfort_floor"] > _TIERS_10PJ[-1][1]
    assert weight < _HOME_NETWORK_TIERS[-1][0], (
        "a settlement of cabins must still have somewhere to climb")


# ---------------------------------------------------------------------------
# the rung effects the table always promised
# ---------------------------------------------------------------------------

def test_house_grants_a_hearth_slot(tmp_path):
    """Rung 4's promised effect, which did not exist.

    Cooking required a fire/campfire/hearth/cooker/oven object. A proper
    house has a hearth built in, so a roofed house cooks and a roofed cabin
    does not - that is the first thing in the game a rung-4 home does that no
    smaller structure does.
    """
    rt = _runtime(tmp_path)
    _give(rt, timber=4, stone=6, clay=4)
    assert _build(rt, "house-1", "house", "cont_a_gen_0_0",
                  timber=4, stone=6, clay=4)["status"] == "success"
    _finish(rt, "house-1", "house", "cont_a_gen_0_0")
    add_to_inventory(rt._store, "east_adam", "wild_berries", 3)

    cooked = rt._execute_action("east_adam", {
        "action_type": "use_object", "target_object_id": "house-1",
        "operation": "cook", "materials": {"wild_berries": 3},
    }, 200)
    assert cooked["status"] == "success", cooked
    assert load_inventory(rt._store)["east_adam"].get("cooked_meal") == 1

    # A rung-3 cabin on the same tile still needs its own fire.
    rt2 = _runtime(tmp_path)
    _give(rt2, timber=3, stone=4)
    assert _build(rt2, "cabin-1", "cabin", "cont_a_gen_0_0",
                  timber=3, stone=4)["status"] == "success"
    _finish(rt2, "cabin-1", "cabin", "cont_a_gen_0_0")
    add_to_inventory(rt2._store, "east_adam", "wild_berries", 3)
    refused = rt2._execute_action("east_adam", {
        "action_type": "use_object", "target_object_id": "cabin-1",
        "operation": "cook", "materials": {"wild_berries": 3},
    }, 200)
    assert refused["status"] == "rejected", refused
    assert "hearth" in refused["reason"].lower()


def test_longhouse_doubles_the_cellar_food_budget(tmp_path):
    """Rung 5's promised effect, which did not exist.

    `_cellar_food_capacity` was 20 x footprint with no rung term. The 10PU
    table said a longhouse is a campaign build with the cellar budget doubled.
    """
    rt = _runtime(tmp_path)
    _give(rt, timber=3, stone=4, wood=2)
    assert _build(rt, "cabin-1", "cabin", "cont_a_gen_0_0",
                  timber=3, stone=4)["status"] == "success"
    _finish(rt, "cabin-1", "cabin", "cont_a_gen_0_0")
    # The cellar must sit in the same connected network as the cabin.
    _move(rt, "cont_a_gen_1_0")
    assert _build(rt, "cellar-1", "storage_cellar", "cont_a_gen_1_0",
                  wood=2)["status"] == "success"
    before = rt._cellar_food_capacity("cellar-1")

    _give(rt, timber=8, stone=10, wood=6)
    _move(rt, "cont_a_gen_2_0")
    assert _build(rt, "lh", "longhouse", "cont_a_gen_2_0",
                  timber=8, stone=10, wood=6)["status"] == "success"
    _finish(rt, "lh", "longhouse", "cont_a_gen_2_0")
    after = rt._cellar_food_capacity("cellar-1")
    # The longhouse doubles the budget. The tier weight also rises because
    # the network's best rung is now 5, so assert the doubling against the
    # weight the runtime itself computes rather than a hand-derived total.
    tier_weight = rt._home_tier_weight("cont_a_gen_1_0")
    assert after == 2 * 20 * max(1, tier_weight), (after, tier_weight)

    # A network with no longhouse in it is not doubled, on the same weight.
    rt2 = _runtime(tmp_path)
    _give(rt2, timber=3, stone=4, wood=2)
    _move(rt2, "cont_a_gen_0_0")
    assert _build(rt2, "cabin-x", "cabin", "cont_a_gen_0_0",
                  timber=3, stone=4)["status"] == "success"
    _finish(rt2, "cabin-x", "cabin", "cont_a_gen_0_0")
    _move(rt2, "cont_a_gen_1_0")
    assert _build(rt2, "cellar-x", "storage_cellar", "cont_a_gen_1_0",
                  wood=2)["status"] == "success"
    plain = rt2._cellar_food_capacity("cellar-x")
    assert plain == 20 * max(1, rt2._home_tier_weight("cont_a_gen_1_0"))


def test_half_built_house_grants_nothing(tmp_path):
    """A foundation is not a home. The hearth slot and the cellar doubling
    only apply to a structure that actually shelters."""
    rt = _runtime(tmp_path)
    _give(rt, timber=4, stone=6, clay=4)
    assert _build(rt, "house-1", "house", "cont_a_gen_0_0",
                  timber=4, stone=6, clay=4)["status"] == "success"
    add_to_inventory(rt._store, "east_adam", "wild_berries", 3)
    res = rt._execute_action("east_adam", {
        "action_type": "use_object", "target_object_id": "house-1",
        "operation": "cook", "materials": {"wild_berries": 3},
    }, 200)
    assert res["status"] == "rejected", res


# ---------------------------------------------------------------------------
# the ladder becomes visible
# ---------------------------------------------------------------------------

def _ctx(**kw):
    base = dict(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position="cont_a_gen_0_0", observation={},
        memory=[], goals=[], unanswered_questions=[],
        world_public_objects={}, habitat_allowed_tiles=[],
        habitat_movement_allowed=False, previous_action=None,
        timestamp_utc="t", inventory={"timber": 38, "clay": 84, "stone": 643},
    )
    base.update(kw)
    return AgentContext(**base)


def test_the_five_rungs_are_disclosed_as_buildable_facts():
    """The vocabulary was invisible: `house` and `longhouse` appeared in one
    string in the whole prompt - the rejection for an unknown type. An agent
    cannot build what it has never been told exists, and in 12,700 heartbeats
    across two lanes neither ever tried.
    """
    ctx = _ctx()
    prompt = m.build_system_prompt(ctx)
    for name in ("lean-to", "hut", "cabin", "house", "longhouse"):
        assert f"`{name}`" in prompt, name
    # the floors, so a holder of materials can see what a house costs
    for fragment in ("timber x4", "stone x6", "clay x4"):
        assert fragment in prompt, fragment
    # the tier curve, including the rows that did not exist before
    for threshold in (12, 18, 26, 36):
        assert f"{threshold} footprint:" in prompt, threshold

    # No directive phrasing in the two lines this phase added. (The pre-existing
    # "with the build action" copy legitimately contains "build a" as a
    # substring of "build action", so the check is scoped to the new lines.)
    ladder = m._structure_ladder_description()
    home_tier = [
        line for line in prompt.splitlines()
        if "tier weight" in line or "Structure ladder" in line
    ]
    for banned in _BANNED_DIRECTIVE_PHRASES:
        for line in [ladder, *home_tier]:
            assert banned not in line.lower(), (banned, line[:120])


def test_home_tier_line_names_footprint_and_tier_weight():
    """Both numbers, so the ladder is legible rather than a mystery."""
    prompt = m.build_system_prompt(_ctx(home_network_footprint=46, home_rung={
        "object_id": "x", "object_type": "cabin", "rung": 3, "weight": 2,
        "footprint": 46, "comfort_floor": 80.0, "cold_decay": 0.09,
        "rest_regen": 2.2, "downed_regen": 1.25, "cellar_budget": 320,
    }))
    assert "connected roofed home footprint is 46" in prompt
    assert "tier weight" in prompt
    assert "saturates at" in prompt
    assert "cellar food budget is 320 units" in prompt


def test_rung_effects_column_no_longer_advertises_a_freebie():
    """Rung 2's 'predators refuse the tile' was true of every roofed kind via
    `_in_shelter`, so it was never a rung effect. Advertising it claimed a
    reward that a lean-to already gives."""
    for name, record in _STRUCTURE_RUNGS.items():
        assert record["effects"], name
    assert "predators refuse" not in _STRUCTURE_RUNGS["hut"]["effects"]
    assert "hearth" in _STRUCTURE_RUNGS["house"]["effects"]
    assert "doubled" in _STRUCTURE_RUNGS["longhouse"]["effects"]

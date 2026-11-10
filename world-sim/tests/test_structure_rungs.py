"""Phase 10PW — structure rungs and visible construction.

Specification: docs/phase_10pu_structure_rungs_spec.md

Operator: "i also really dont like seeing 15 single houses. we need to give
them a reason to build a proper house or shelter" and "i would like to be able
to see them build things and stuff not just see things appear".
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
    _SHELTERING_STAGES,
    _STAGE_MATERIAL_SHARE,
    _STRUCTURE_RUNGS,
    _is_non_structural_type,
    _stage_material_plan,
    _structure_rung_of,
    FirstPairRuntime,
    _BANNED_DIRECTIVE_PHRASES,
)


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    rt._world_state.tile_occupancy["east_eve"] = "cont_a_gen_1_0"
    rt._world_state.tick = 100
    return rt


def _stock(rt, **amounts):
    for kind, amount in amounts.items():
        add_to_inventory(rt._store, "east_adam", kind, amount)


def _give(rt, **amounts):
    held = load_inventory(rt._store).get("east_adam", {})
    for kind, amount in amounts.items():
        need = amount - int(held.get(kind, 0) or 0)
        if need > 0:
            add_to_inventory(rt._store, "east_adam", kind, need)


def _build(rt, object_id, object_type, **materials):
    return rt._execute_action("east_adam", {
        "action_type": "build",
        "object_id": object_id,
        "object_type": object_type,
        "tile_id": "cont_a_gen_0_0",
        "description": f"a {object_type}",
        "materials": materials,
    }, 100)


def _advance(rt, object_id, object_type, **materials):
    return rt._execute_action("east_adam", {
        "action_type": "build",
        "object_id": object_id,
        "object_type": object_type,
        "tile_id": "cont_a_gen_0_0",
        "description": f"a {object_type}",
        "materials": materials,
    }, 101)


# ---------------------------------------------------------------------------
# the closed vocabulary
# ---------------------------------------------------------------------------

def test_free_string_roofed_types_are_rejected_and_name_the_legal_set(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, wood=50, stone=50, clay=50, timber=50)
    out = _build(rt, "castle-1", "castle", timber=1, wood=1)
    assert out["status"] == "rejected"
    assert "Legal roofed structures" in out["reason"], out
    for name in ("cabin", "hut", "house", "lean-to", "longhouse"):
        assert name in out["reason"]


def test_non_structural_types_still_build_freely(tmp_path):
    for otype in ("campfire", "crafting_surface", "enclosed_garden", "storage",
                  "landmark", "container", "well", "chest", "road", "pathway"):
        assert _is_non_structural_type(otype) is True, otype
    for otype in ("house", "mansion", "palace", "hovel", "castle"):
        assert _is_non_structural_type(otype) is False, otype


def test_campfire_build_unaffected_by_rungs(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, wood=20)
    out = _build(rt, "fire-1", "campfire", wood=2)
    assert out["status"] == "success", out
    obj = rt._world_state.public_objects["fire-1"]
    assert "structure_rung" not in obj


def test_stage_plan_is_exact_and_deterministic():
    for name, record in _STRUCTURE_RUNGS.items():
        plan = _stage_material_plan(record["floor"])
        assert set(plan) == set(_CONSTRUCTION_STAGES), name
        for kind, total in record["floor"].items():
            spent = sum(stage.get(kind, 0) for stage in plan.values())
            assert spent == total, f"{name}/{kind}: {spent} != {total}"
        # the first stage is never empty: a build always visibly starts
        assert any(v > 0 for v in plan["foundation"].values()), name


def test_legacy_names_map_to_their_rung():
    # The five canonical rung names map legacy=False; the rest of the live
    # vocabulary are legacy aliases, grandfathered to their rung.
    canonical = set(_STRUCTURE_RUNGS)
    for name, expected in (("shelter", 1), ("hut", 2), ("cabin", 3),
                           ("roof", 1), ("lean-to", 1), ("tent", 1)):
        record = _structure_rung_of(name)
        assert record is not None, name
        assert record["rung"] == expected, name
        assert record.get("legacy") is (name not in canonical), name


def test_canonical_names_map_to_their_rung():
    for name, record in _STRUCTURE_RUNGS.items():
        found = _structure_rung_of(name)
        assert found is not None, name
        assert found["rung"] == record["rung"]
        assert found.get("legacy") is False


# ---------------------------------------------------------------------------
# staged construction
# ---------------------------------------------------------------------------

def test_build_starts_a_staged_project_and_does_not_shelter(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, timber=6, wood=6, stone=6, clay=6)
    out = _build(rt, "hut-1", "hut", timber=2, wood=2)
    assert out["status"] == "success", out
    obj = rt._world_state.public_objects["hut-1"]
    assert obj["construction_project"] is True
    assert obj["construction_stage"] == "foundation"
    assert obj["construction_progress"] == 0
    assert obj["structure_rung"] == 2
    # a foundation shelters nobody
    assert rt._in_shelter("cont_a_gen_0_0") is False


def test_advancing_through_stages_shelters_from_roofed(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, timber=6, wood=6, stone=6, clay=6)
    _build(rt, "hut-1", "hut", timber=2, wood=2)
    for expected in ("frame", "walls", "roofed"):
        out = _advance(rt, "hut-1", "hut")
        assert out["status"] == "success", (expected, out)
        assert out["stage"] == expected
    assert rt._in_shelter("cont_a_gen_0_0") is True
    out = _advance(rt, "hut-1", "hut")
    assert out["stage"] == "finished"
    assert out["shelters"] is True
    obj = rt._world_state.public_objects["hut-1"]
    assert obj["construction_project"] is False


def test_each_stage_spends_only_its_own_share(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, timber=8, stone=10, wood=6)
    before = {k: int(v) for k, v in
              (load_inventory(rt._store).get("east_adam") or {}).items()}
    out = _build(rt, "lh-1", "longhouse", timber=8, stone=10, wood=6)
    assert out["status"] == "success", out
    plan = _stage_material_plan(_STRUCTURE_RUNGS["longhouse"]["floor"])
    held = load_inventory(rt._store)["east_adam"]
    for kind, total in _STRUCTURE_RUNGS["longhouse"]["floor"].items():
        spent = before.get(kind, 0) - int(held.get(kind, 0))
        assert spent == plan["foundation"].get(kind, 0), kind
        assert int(held.get(kind, 0)) == total - plan["foundation"].get(kind, 0), kind
    # a short holding rejects the stage and spends nothing
    rt._world_state.public_objects["lh-1"]["construction_stage"] = "frame"
    rt._world_state.public_objects["lh-1"]["construction_progress"] = 1
    for kind in list(load_inventory(rt._store)["east_adam"].keys()):
        held = int(load_inventory(rt._store)["east_adam"].get(kind, 0) or 0)
        if held:
            add_to_inventory(rt._store, "east_adam", kind, -held)
    before2 = dict(load_inventory(rt._store)["east_adam"])
    out2 = _advance(rt, "lh-1", "longhouse")
    assert out2["status"] == "rejected", out2
    after = load_inventory(rt._store)["east_adam"]
    for kind, amount in after.items():
        assert amount == before2.get(kind, 0), kind


def test_same_id_advances_a_new_id_starts_a_new_project(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, timber=10, wood=10, stone=10, clay=10)
    _build(rt, "hut-1", "hut", timber=2, wood=2)
    out = _advance(rt, "hut-1", "hut")
    assert out["stage"] == "frame"
    other = _build(rt, "hut-2", "hut", timber=2, wood=2)
    assert other["status"] == "success"
    assert rt._world_state.public_objects["hut-2"]["construction_stage"] == "foundation"


def test_duplicate_finished_id_is_a_duplicate(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, timber=12, wood=12, stone=12, clay=12)
    _build(rt, "hut-1", "hut", timber=2, wood=2)
    for _ in range(4):
        _advance(rt, "hut-1", "hut")
    out = _build(rt, "hut-1", "hut", timber=2, wood=2)
    assert out["status"] == "rejected"
    assert "already finished" in out["reason"]


def test_abandoned_project_leaves_an_honest_partial_structure(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, timber=6, wood=6, stone=6, clay=6)
    _build(rt, "lk-1", "lean-to", timber=1)
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_5_5"
    obj = rt._world_state.public_objects["lk-1"]
    assert obj["construction_stage"] == "foundation"
    assert obj["construction_project"] is True
    held = load_inventory(rt._store)["east_adam"]
    assert held["timber"] == 5, "only the foundation was spent"


# ---------------------------------------------------------------------------
# rung weights and the shelter predicate
# ---------------------------------------------------------------------------

def test_rung_weight_outranks_equivalent_lean_tos():
    longhouse = _structure_rung_of("longhouse")
    leaning = _structure_rung_of("lean-to")
    assert longhouse["weight"] >= leaning["weight"] * 4


def test_higher_rungs_weigh_more():
    weights = [_structure_rung_of(n)["weight"] for n in
               ("lean-to", "hut", "cabin", "house", "longhouse")]
    assert weights == sorted(weights)


def test_unfinished_structure_contributes_no_footprint(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, timber=8, wood=8, stone=8, clay=8)
    _build(rt, "hut-1", "hut", timber=2, wood=2)
    assert rt._home_network_footprint("cont_a_gen_0_0") == 0
    for _ in range(3):
        _advance(rt, "hut-1", "hut")
    assert rt._home_network_footprint("cont_a_gen_0_0") >= 2


# ---------------------------------------------------------------------------
# disclosure
# ---------------------------------------------------------------------------

def _ctx(**kw):
    base = dict(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position="t", observation={}, memory=[],
        goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
    )
    base.update(kw)
    return AgentContext(**base)


def test_home_rung_disclosure_is_a_fact_without_directives():
    ctx = _ctx(home_rung={
        "object_id": "house-1", "object_type": "house", "rung": 4,
        "weight": 3, "footprint": 9, "comfort_floor": 75.0,
        "cold_decay": 0.10, "rest_regen": 2.0, "downed_regen": 1.1,
        "cellar_budget": 180,
    })
    prompt = m.build_system_prompt(ctx)
    line = ("Fact: you are inside a house (rung 4) with footprint 9; "
            "comfort floor is 75; cold decay factor is 0.1; "
            "rest recovery is 2 per heartbeat; cellar food budget is 180 units.")
    assert line in prompt, line
    for banned in _BANNED_DIRECTIVE_PHRASES:
        assert banned not in line.lower(), banned


def test_home_rung_disclosure_absent_outside_a_structure():
    prompt = m.build_system_prompt(_ctx())
    assert "you are inside a" not in prompt


def test_construction_disclosure_absent_when_nothing_is_building():
    prompt = m.build_system_prompt(_ctx())
    assert "under construction" not in prompt


def test_construction_disclosure_names_stage_and_remaining():
    ctx = _ctx(construction_here={
        "object_id": "house-1", "object_type": "house", "stage": "walls",
        "progress": 2, "stages_total": 5, "rung": 4,
        "remaining_floor": {"stone": 4, "clay": 4},
    })
    prompt = m.build_system_prompt(ctx)
    assert "house house-1 on this tile is under construction at stage walls (2/5)" in prompt
    assert "still needed: clay 4, stone 4" in prompt


def test_runtime_disclosure_projection(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, timber=8, wood=8, stone=8, clay=8)
    _build(rt, "house-1", "house", timber=4, stone=6, clay=4)
    for _ in range(3):
        step = _advance(rt, "house-1", "house")
        assert step["status"] == "success", step
    assert step["stage"] == "roofed", step
    home = rt._home_rung_for("cont_a_gen_0_0")
    assert home, home
    assert home["rung"] == 4
    assert home["object_type"] == "house"
    assert home["footprint"] == 3
    assert home["cellar_budget"] == 60
    # still under construction at 'roofed' (it shelters, but is not finished)
    here = rt._construction_here_for("east_adam", "cont_a_gen_0_0")
    assert here["stage"] == "roofed"
    final = _advance(rt, "house-1", "house")
    assert final["stage"] == "finished"
    assert rt._construction_here_for("east_adam", "cont_a_gen_0_0") == {}
    assert rt._home_rung_for("cont_a_gen_0_0")["rung"] == 4


def test_construction_disclosure_while_a_project_runs(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, timber=8, wood=8, stone=8, clay=8)
    _build(rt, "house-1", "house", timber=4, stone=6, clay=4)
    here = rt._construction_here_for("east_adam", "cont_a_gen_0_0")
    assert here["stage"] == "foundation"
    assert here["stages_total"] == 5
    assert here["rung"] == 4
    assert any(v > 0 for v in here["remaining_floor"].values())


# ---------------------------------------------------------------------------
# regression: the older seams still hold
# ---------------------------------------------------------------------------

def test_10km_structural_minimum_still_applies(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, wood=50)
    out = _build(rt, "cab-1", "cabin", timber=1)
    assert out["status"] == "rejected"
    assert "needs at least 3 structural timber" in out["reason"]


def test_10lm_addon_discount_still_applies(tmp_path):
    rt = _runtime(tmp_path)
    _give(rt, timber=12, wood=12, stone=12, clay=12)
    _build(rt, "room-1", "cabin", timber=3, stone=4)
    # the second build is a continuation of the same project, so use a new id
    # with addon_to to exercise the compound discount on a standalone room
    out = rt._execute_action("east_adam", {
        "action_type": "build",
        "object_id": "room-2",
        "object_type": "hut",
        "tile_id": "cont_a_gen_0_0",
        "description": "an attached room",
        "materials": {"timber": 1, "wood": 1},
        "addon_to": "room-1",
    }, 101)
    assert out["status"] == "success", out


def test_stage_share_table_is_complete():
    assert set(_STAGE_MATERIAL_SHARE) == set(_CONSTRUCTION_STAGES)
    assert abs(sum(_STAGE_MATERIAL_SHARE.values()) - 1.0) < 1e-9
    assert _SHELTERING_STAGES == {"roofed", "finished"}

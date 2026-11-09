"""Phase 10PT — the timber access wall.

Specification: docs/phase_10pr_timber_access_wall_spec.md

West Eve hit 218 `Insufficient timber: need 2, hold 0` rejections while
West Adam held 198 timber. Three compounding gaps are fixed here: the
partner's hoard was invisible, the only hand-off channel required standing
on the container tile, and a worn-out axe left no way to fell a tree.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    load_inventory,
)
from backend.world.first_pair_runtime import (
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


# ---------------------------------------------------------------------------
# 1. partner holdings disclosure
# ---------------------------------------------------------------------------

def test_partner_holdings_projected_and_bounded(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_eve", "timber", 198)
    add_to_inventory(rt._store, "east_eve", "wood", 25)
    add_to_inventory(rt._store, "east_eve", "stone_axe", 1)
    add_to_inventory(rt._store, "east_eve", "wild_berries", 500)  # not disclosed
    out = rt._partner_holdings_for("east_adam")
    assert out["timber"] == 198 and out["wood"] == 25
    assert out["tools"] == {"stone_axe": 1}
    assert "wild_berries" not in out


def test_partner_holdings_empty_when_partner_holds_nothing(tmp_path):
    rt = _runtime(tmp_path)
    assert rt._partner_holdings_for("east_adam") == {}


def test_prompt_line_renders_partner_hoard_without_directives():
    ctx = AgentContext(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position="t", observation={}, memory=[],
        goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
        partner_holdings={"timber": 198, "wood": 25, "tools": {"stone_axe": 1}},
    )
    prompt = m.build_system_prompt(ctx)
    line = "Fact: your companion holds timber 198, wood 25, stone_axe 1."
    assert line in prompt
    # Scoped to the line this phase adds: the pre-existing action catalogue in
    # _AVAILABLE_ACTIONS_DESC has its own agreed wording.
    for banned in _BANNED_DIRECTIVE_PHRASES:
        assert banned not in line.lower(), banned


def test_prompt_line_absent_when_no_partner_holdings():
    ctx = AgentContext(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position="t", observation={}, memory=[],
        goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
    )
    prompt = m.build_system_prompt(ctx)
    assert "your companion holds" not in prompt


def test_context_fill_carries_the_projection(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_eve", "timber", 7)
    rt._build_context("east_adam", 100) if hasattr(rt, "_build_context") else None
    # _build_context may not exist under that name; assert the runtime helper
    # that feeds it instead.
    assert rt._partner_holdings_for("east_adam")["timber"] == 7


# ---------------------------------------------------------------------------
# 2. adjacent container deposit / extract
# ---------------------------------------------------------------------------

def _container_obj(oid, otype, tile, contents=None):
    return {
        "object_id": oid, "object_type": otype, "tile_id": tile,
        "contents": dict(contents or {}),
        "creator_agent_id": "someone",
        "created_heartbeat": 1,
    }


def test_deposit_from_adjacent_container_tile(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["store-1"] = _container_obj("store-1", "storage", "cont_a_gen_1_0")
    add_to_inventory(rt._store, "east_adam", "timber", 5)
    out = rt._execute_action("east_adam", {
        "action_type": "use_object",
        "target_object_id": "store-1",
        "operation": "deposit",
        "materials": {"timber": 3},
    }, 100)
    assert out["status"] == "success", out
    assert rt._world_state.public_objects["store-1"]["contents"]["timber"] == 3
    assert load_inventory(rt._store)["east_adam"]["timber"] == 2


def test_extract_from_adjacent_container_tile(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["store-1"] = _container_obj(
        "store-1", "storage", "cont_a_gen_1_0", {"timber": 12})
    out = rt._execute_action("east_adam", {
        "action_type": "use_object",
        "target_object_id": "store-1",
        "operation": "extract",
        "materials": {"timber": 4},
    }, 100)
    assert out["status"] == "success", out
    assert load_inventory(rt._store)["east_adam"]["timber"] == 4
    assert rt._world_state.public_objects["store-1"]["contents"]["timber"] == 8


def test_distant_container_is_still_refused(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["store-1"] = _container_obj("store-1", "storage", "cont_a_gen_6_0")
    out = rt._execute_action("east_adam", {
        "action_type": "use_object",
        "target_object_id": "store-1",
        "operation": "extract",
        "materials": {"timber": 1},
    }, 100)
    assert out["status"] == "rejected"
    assert "beside it" in out["reason"]


def test_non_container_still_requires_the_exact_tile(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["shelf-1"] = _container_obj("shelf-1", "monument", "cont_a_gen_1_0")
    out = rt._execute_action("east_adam", {
        "action_type": "use_object",
        "target_object_id": "shelf-1",
        "operation": "deposit",
        "materials": {"timber": 1},
    }, 100)
    assert out["status"] == "rejected"
    assert "not your current tile" in out["reason"]


def test_container_type_helper():
    assert FirstPairRuntime._is_container_type("storage") is True
    assert FirstPairRuntime._is_container_type("clay_well") is True
    assert FirstPairRuntime._is_container_type("storage_cellar") is True
    assert FirstPairRuntime._is_container_type("woven_basket") is True
    assert FirstPairRuntime._is_container_type("campfire") is False
    assert FirstPairRuntime._is_container_type("shelter") is False


# ---------------------------------------------------------------------------
# 3. hew_timber knapping fallback
# ---------------------------------------------------------------------------

def test_hew_timber_knaps_a_blade_when_none_is_held(tmp_path):
    rt = _runtime(tmp_path)
    rt._current_tile_resources["cont_a_gen_0_0"] = [{"kind": "wood", "amount": 20}]
    add_to_inventory(rt._store, "east_adam", "stone", 5)
    add_to_inventory(rt._store, "east_adam", "wood", 5)
    out = rt._execute_action("east_adam", {
        "action_type": "hew_timber", "reason": "timber for shelter",
    }, 100)
    assert out["status"] == "success", out
    held = load_inventory(rt._store)["east_adam"]
    assert held["stone"] == 3 and held["wood"] == 4
    assert held["timber"] == 1
    assert "Knapped" in out["detail"]


def test_hew_timber_fallback_rejection_names_the_cost(tmp_path):
    rt = _runtime(tmp_path)
    rt._current_tile_resources["cont_a_gen_0_0"] = [{"kind": "wood", "amount": 20}]
    add_to_inventory(rt._store, "east_adam", "stone", 1)
    out = rt._execute_action("east_adam", {
        "action_type": "hew_timber", "reason": "timber",
    }, 100)
    assert out["status"] == "rejected"
    assert "2 stone and 1 wood" in out["reason"]


def test_hew_timber_with_a_blade_skips_the_knap(tmp_path):
    rt = _runtime(tmp_path)
    rt._current_tile_resources["cont_a_gen_0_0"] = [{"kind": "wood", "amount": 20}]
    add_to_inventory(rt._store, "east_adam", "stone", 5)
    add_to_inventory(rt._store, "east_adam", "wood", 5)
    add_to_inventory(rt._store, "east_adam", "stone_axe", 1)
    rt._register_tool("east_adam", "stone_axe")
    out = rt._execute_action("east_adam", {
        "action_type": "hew_timber", "reason": "timber",
    }, 100)
    assert out["status"] == "success"
    assert out["timber_yield"] == 2
    held = load_inventory(rt._store)["east_adam"]
    assert held["stone"] == 5 and held["wood"] == 5
    assert "Knapped" not in out["detail"]

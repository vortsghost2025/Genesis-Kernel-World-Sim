"""Phase 10KM tests: Load-Bearing Construction Chain.

Verifies the four defects isolated in the Phase 10KU diagnostic are fixed:
1. Craft recipes are discoverable (advertised from the runtime's own table).
2. A crafting surface can be built from commonly held materials.
3. Structural builds require hewn timber (hew_timber is load-bearing).
4. Attaching a room costs less than a freestanding hut.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_model import _craft_recipe_advertisement
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    WorldStateRecord,
    add_to_inventory,
    save_world_state,
)
from backend.world.first_pair_runtime import (
    FirstPairRuntime,
    _BANNED_DIRECTIVE_PHRASES,
)


def _setup_runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    runtime = FirstPairRuntime(heartbeat_limit=10, store=store, pair_id="east")
    runtime._load_or_initialize()
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    runtime._world_state.tile_occupancy["east_eve"] = "cont_a_gen_0_1"
    return runtime


def _grant_on(runtime: FirstPairRuntime, agent: str, **items) -> None:
    for kind, amount in items.items():
        add_to_inventory(runtime._store, agent, kind, amount)


# --- 1. Recipe discoverability -------------------------------------------------

def test_recipe_advertisement_covers_every_recipe():
    """Every entry in _CRAFT_RECIPES must appear in the advertised string.

    This is the drift guard: a recipe added to the runtime table cannot
    silently become undiscoverable again.
    """
    ad = _craft_recipe_advertisement()
    for materials, output in FirstPairRuntime._CRAFT_RECIPES.items():
        formula = dict(materials)
        assert output in ad, f"{output} missing from recipe advertisement"
        for kind, amount in formula.items():
            assert kind in ad and str(amount) in ad, (
                f"recipe {output}: material {kind}={amount} not disclosed"
            )


def test_recipe_advertisement_discloses_no_strategy():
    """The advertisement states formulas, never what to make."""
    ad = _craft_recipe_advertisement()
    lowered = ad.lower()
    for phrase in _BANNED_DIRECTIVE_PHRASES:
        assert phrase.lower() not in lowered, (
            f"recipe advertisement contains directive phrase {phrase!r}"
        )


# --- 2. Crafting surface availability ------------------------------------------

def test_crafting_surface_buildable_from_common_materials(tmp_path: Path):
    """An agent holding only stone/clay/wood can build a crafting surface."""
    runtime = _setup_runtime(tmp_path)
    agent = "east_adam"
    pos = runtime._world_state.tile_occupancy[agent]
    _grant_on(runtime, agent, stone=3, clay=3, wood=2)

    result = runtime._execute_build(
        agent,
        {
            "object_id": "surface-001",
            "object_type": "crafting_surface",
            "description": "A flat stone bench for working flint.",
            "tile_id": pos,
            "materials": {"stone": 3, "wood": 2},
        },
        heartbeat_number=1,
    )
    assert result.get("status") == "success", result


def test_craft_flint_knife_on_new_surface(tmp_path: Path):
    """With a surface on the agent's tile, flint_knife crafts on it."""
    runtime = _setup_runtime(tmp_path)
    agent = "east_adam"
    pos = runtime._world_state.tile_occupancy[agent]
    _grant_on(runtime, agent, stone=3, clay=3, wood=2)

    built = runtime._execute_build(
        agent,
        {
            "object_id": "surface-002",
            "object_type": "crafting_surface",
            "description": "A clay-daubed workbench.",
            "tile_id": pos,
            "materials": {"stone": 3, "wood": 2},
        },
        heartbeat_number=1,
    )
    assert built.get("status") == "success", built

    _grant_on(runtime, agent, flint=2, wood=1)
    result = runtime._execute_use_object(
        agent,
        {
            "target_object_id": "surface-002",
            "operation": "craft",
            "materials": {"flint": 2, "wood": 1},
        },
        heartbeat_number=2,
    )
    assert result.get("status") == "success", result
    assert result.get("crafted") == "flint_knife"
    assert runtime._get_agent_inventory(agent).get("flint_knife", 0) >= 1


# --- 3. Load-bearing timber ----------------------------------------------------

def test_shelter_requires_timber(tmp_path: Path):
    """A structural build without timber is rejected with guidance."""
    runtime = _setup_runtime(tmp_path)
    agent = "east_adam"
    pos = runtime._world_state.tile_occupancy[agent]
    _grant_on(runtime, agent, stone=10, wood=4)

    result = runtime._execute_build(
        agent,
        {
            "object_id": "hut-001",
            "object_type": "shelter",
            "description": "A shelter of stacked stone.",
            "tile_id": pos,
            "materials": {"stone": 6, "wood": 2},
        },
        heartbeat_number=3,
    )
    assert result.get("status") == "rejected", result
    reason = str(result.get("reason", ""))
    assert "timber" in reason.lower(), reason
    assert "hew_timber" in reason, reason


def test_shelter_succeeds_with_timber(tmp_path: Path):
    """A structural build with sufficient timber succeeds and deducts it."""
    runtime = _setup_runtime(tmp_path)
    agent = "east_adam"
    pos = runtime._world_state.tile_occupancy[agent]
    _grant_on(runtime, agent, stone=6, wood=2, timber=5)
    before = runtime._get_agent_inventory(agent).get("timber", 0)

    result = runtime._execute_build(
        agent,
        {
            "object_id": "hut-002",
            "object_type": "shelter",
            "description": "A timber-framed shelter.",
            "tile_id": pos,
            "materials": {"timber": 2, "stone": 6, "wood": 2},
        },
        heartbeat_number=3,
    )
    assert result.get("status") == "success", result
    after = runtime._get_agent_inventory(agent).get("timber", 0)
    assert after == before - 2, (before, after)


def test_campfire_still_cheap(tmp_path: Path):
    """Non-structural builds keep their existing material rules."""
    runtime = _setup_runtime(tmp_path)
    agent = "east_adam"
    pos = runtime._world_state.tile_occupancy[agent]
    _grant_on(runtime, agent, wood=4)

    result = runtime._execute_build(
        agent,
        {
            "object_id": "fire-001",
            "object_type": "campfire",
            "description": "A small campfire.",
            "tile_id": pos,
            "materials": {"wood": 4},
        },
        heartbeat_number=4,
    )
    assert result.get("status") == "success", result


def test_existing_shelters_grandfathered(tmp_path: Path):
    """Objects recorded without timber must survive a reload untouched."""
    runtime = _setup_runtime(tmp_path)
    tile = runtime._world_state.tile_occupancy["east_adam"]

    # A shelter built before the timber rule existed.
    runtime._world_state.public_objects["legacy-hut"] = {
        "object_id": "legacy-hut",
        "creator_agent_id": "agent-1",
        "tile_id": tile,
        "object_type": "shelter",
        "public_description": "Built long before timber mattered.",
        "created_heartbeat": 1,
        "materials": {"stone": 4},
    }
    save_world_state(runtime._store, runtime._world_state)

    # A fresh runtime on the same store must accept it, not purge it.
    reopened = FirstPairRuntime(
        heartbeat_limit=10, store=runtime._store, pair_id="east"
    )
    reopened._load_or_initialize()

    legacy = reopened._world_state.public_objects.get("legacy-hut")
    assert legacy is not None, "pre-existing shelter was dropped on load"
    assert legacy.get("object_type") == "shelter"
    # and the runtime still treats it as shelter for warmth purposes
    assert reopened._in_shelter(tile) is True


# --- 4. Compound economy -------------------------------------------------------

def test_addon_costs_less_than_freestanding(tmp_path: Path):
    """A 2-room compound must cost strictly less timber than two huts.

    Measured from real inventory deltas, and from the discount actually
    applying: a freestanding hut declaring 1 timber is rejected, while an
    attached room declaring the same 1 timber succeeds.
    """
    agent = "east_adam"

    # --- freestanding: two huts, each at the full floor ---
    runtime = _setup_runtime(tmp_path)
    pos = runtime._world_state.tile_occupancy[agent]
    xy = runtime._tile_xy(pos)
    adj = f"cont_a_gen_{xy[0] + 1}_{xy[1]}"
    _grant_on(runtime, agent, stone=40, wood=20, timber=20)
    start_timber = runtime._get_agent_inventory(agent).get("timber", 0)

    first = runtime._execute_build(
        agent,
        {
            "object_id": "hut-a",
            "object_type": "shelter",
            "description": "First freestanding hut.",
            "tile_id": pos,
            "materials": {"timber": 2, "stone": 6, "wood": 2},
        },
        heartbeat_number=5,
    )
    assert first.get("status") == "success", first

    # Whether an attached room would be cheaper is tested separately; here we
    # establish the freestanding floor is 2.
    short = runtime._execute_build(
        agent,
        {
            "object_id": "hut-short",
            "object_type": "shelter",
            "description": "A hut that skimps on timber.",
            "tile_id": adj,
            "materials": {"timber": 1, "stone": 6, "wood": 2},
        },
        heartbeat_number=6,
    )
    assert short.get("status") == "rejected", short

    runtime._world_state.tile_occupancy[agent] = adj
    second = runtime._execute_build(
        agent,
        {
            "object_id": "hut-b",
            "object_type": "shelter",
            "description": "Second freestanding hut.",
            "tile_id": adj,
            "materials": {"timber": 2, "stone": 6, "wood": 2},
        },
        heartbeat_number=7,
    )
    assert second.get("status") == "success", second
    assert len(runtime._world_state.compounds) == 0, (
        "two freestanding huts must not form a compound"
    )
    freestanding_spent = (
        start_timber - runtime._get_agent_inventory(agent).get("timber", 0)
    )

    # --- compound: root at the full floor, attached room discounted ---
    runtime2 = _setup_runtime(tmp_path / "compound")
    runtime2._world_state.tile_occupancy[agent] = pos
    _grant_on(runtime2, agent, stone=40, wood=20, timber=20)
    start_timber2 = runtime2._get_agent_inventory(agent).get("timber", 0)

    root = runtime2._execute_build(
        agent,
        {
            "object_id": "hut-root",
            "object_type": "shelter",
            "description": "Root hut.",
            "tile_id": pos,
            "materials": {"timber": 2, "stone": 6, "wood": 2},
        },
        heartbeat_number=8,
    )
    assert root.get("status") == "success", root

    addon = runtime2._execute_build(
        agent,
        {
            "object_id": "hut-addon",
            "object_type": "shelter",
            "description": "Attached second room.",
            "tile_id": adj,
            "materials": {"timber": 1, "stone": 6, "wood": 2},
            "addon_to": "hut-root",
        },
        heartbeat_number=9,
    )
    assert addon.get("status") == "success", addon
    assert len(runtime2._world_state.compounds) == 1

    compound_spent = (
        start_timber2 - runtime2._get_agent_inventory(agent).get("timber", 0)
    )

    assert compound_spent < freestanding_spent, (
        f"compound spent {compound_spent} timber but freestanding spent "
        f"{freestanding_spent}; attaching a room must be cheaper"
    )

"""Test suite for Phase 10LH: Action Schema Parity & Build Unblocking.

Specification: docs/phase_10lf_action_schema_parity_and_build_unblocking_spec.md §4
Required test coverage:
1. test_prompt_validator_runtime_action_set_parity
2. test_hew_timber_passes_validate_action_exact_and_model_output
3. test_build_with_addon_to_passes_validate_action_exact
4. test_plant_and_harvest_crop_pass_validate_action_exact
5. test_end_to_end_cognition_to_runtime_hew_timber_and_shelter_build
6. test_build_same_tile_duplicate_id_still_rejected
7. test_build_off_tile_duplicate_id_disambiguated_and_succeeds
8. test_build_chronicle_records_craft_and_hew_timber
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

from backend.world.first_pair_cognition_model import (
    _ACTION_SCHEMAS,
    _AVAILABLE_ACTIONS_DESC,
    _VALID_ACTIONS,
    validate_action_exact,
    validate_model_output,
)
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    load_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime
from scripts.export_viewer_snapshot import build_chronicle

ADAM_ID = "genesis_10ct_first_pair_east_adam"


def _fresh_runtime(tmp_path: Path) -> tuple[FirstPairPersistenceStore, FirstPairRuntime]:
    store = FirstPairPersistenceStore(tmp_path / ".runtime" / "first-pair")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt.run()
    return store, rt


def _valid_envelope(proposed_action: dict) -> dict:
    return {
        "observation_summary": "Standing in the northern forest holding a stone axe.",
        "self_model_update": None,
        "goal_updates": [],
        "proposed_action": proposed_action,
        "memory_candidates": [],
        "questions_for_humans": [],
        "uncertainty": "Whether two timber logs suffice for the shelter frame.",
        "decision_summary": "Execute the proposed action.",
        "confidence": 0.9,
    }


# ---------------------------------------------------------------------------
# 1. Prompt <-> Validator <-> Runtime Action Set Parity
# ---------------------------------------------------------------------------
def test_prompt_validator_runtime_action_set_parity():
    """Every action advertised in _AVAILABLE_ACTIONS_DESC and dispatched in
    FirstPairRuntime._execute_action must be present in _VALID_ACTIONS and
    _ACTION_SCHEMAS so prompt-to-validator drift can never recur."""
    advertised = set(re.findall(r"^- ([a-z_]+):", _AVAILABLE_ACTIONS_DESC, re.M))
    runtime_src = inspect.getsource(FirstPairRuntime._execute_action)
    dispatched = set(re.findall(r'action_type == "([a-z_]+)"', runtime_src))

    assert advertised == set(_VALID_ACTIONS), (
        f"Drift between _AVAILABLE_ACTIONS_DESC and _VALID_ACTIONS: "
        f"missing={advertised - set(_VALID_ACTIONS)}, extra={set(_VALID_ACTIONS) - advertised}"
    )
    assert set(_VALID_ACTIONS) == set(_ACTION_SCHEMAS.keys()), (
        f"Drift between _VALID_ACTIONS and _ACTION_SCHEMAS: "
        f"missing={set(_VALID_ACTIONS) - set(_ACTION_SCHEMAS.keys())}"
    )
    assert dispatched | {"no_action"} == set(_VALID_ACTIONS), (
        f"Drift between FirstPairRuntime._execute_action and _VALID_ACTIONS: "
        f"missing_in_validator={dispatched - set(_VALID_ACTIONS)}"
    )


# ---------------------------------------------------------------------------
# 2. hew_timber validation through validate_action_exact and validate_model_output
# ---------------------------------------------------------------------------
def test_hew_timber_passes_validate_action_exact_and_model_output():
    """Verify hew_timber with reason (and optional tool) passes both action
    and full model-output validation."""
    act_minimal = {
        "action_type": "hew_timber",
        "reason": "Fell a pine tree into structural timber for our shelter.",
    }
    assert validate_action_exact(act_minimal, ADAM_ID) == []

    act_with_tool = {
        "action_type": "hew_timber",
        "reason": "Fell a pine tree with stone_axe.",
        "tool": "stone_axe",
    }
    assert validate_action_exact(act_with_tool, ADAM_ID) == []

    validated = validate_model_output(_valid_envelope(act_with_tool), ADAM_ID)
    assert validated.is_valid, f"Expected valid ModelOutput, got errors: {validated.validation_errors}"
    assert validated.proposed_action is not None
    assert validated.proposed_action["action_type"] == "hew_timber"


# ---------------------------------------------------------------------------
# 3. build with addon_to validation
# ---------------------------------------------------------------------------
def test_build_with_addon_to_passes_validate_action_exact():
    """Verify build accepts optional addon_to and rejects unsafe addon_to IDs."""
    act = {
        "action_type": "build",
        "object_id": "hut-room-2",
        "object_type": "hut",
        "description": "Attached sleeping room",
        "tile_id": "cont_a_north_000",
        "materials": {"timber": 1, "stone": 2},
        "addon_to": "shelter-001",
    }
    assert validate_action_exact(act, ADAM_ID) == []

    bad_addon = dict(act, addon_to="../bad id!")
    errs = validate_action_exact(bad_addon, ADAM_ID)
    assert "action:unsafe_addon_to" in errs


# ---------------------------------------------------------------------------
# 4. plant_crop and harvest_crop validation
# ---------------------------------------------------------------------------
def test_plant_and_harvest_crop_pass_validate_action_exact():
    """Verify plant_crop and harvest_crop validate cleanly and enforce target_id."""
    plant_ok = {
        "action_type": "plant_crop",
        "target_id": "garden-001",
        "resource_kind": "wild_berries",
        "reason": "Sow berries in enclosed garden.",
    }
    assert validate_action_exact(plant_ok, ADAM_ID) == []

    harvest_ok = {
        "action_type": "harvest_crop",
        "target_id": "garden-001",
        "reason": "Harvest mature berry crop.",
    }
    assert validate_action_exact(harvest_ok, ADAM_ID) == []

    plant_missing_target = {
        "action_type": "plant_crop",
        "resource_kind": "wild_berries",
        "reason": "Sow berries.",
    }
    assert "action:empty_target_id" in validate_action_exact(plant_missing_target, ADAM_ID)

    harvest_missing_target = {
        "action_type": "harvest_crop",
        "reason": "Harvest.",
    }
    assert "action:empty_target_id" in validate_action_exact(harvest_missing_target, ADAM_ID)


# ---------------------------------------------------------------------------
# 5. End-to-end cognition -> runtime round-trip: hew_timber -> build shelter
# ---------------------------------------------------------------------------
def test_end_to_end_cognition_to_runtime_hew_timber_and_shelter_build(tmp_path):
    """Full round-trip replicating East Adam's HB 6355-6362 sequence:
    holding stone_axe -> validate_model_output(hew_timber) -> runtime executes
    hew_timber (2 timber) -> validate_model_output(build shelter) -> runtime
    executes build shelter (success)."""
    store, rt = _fresh_runtime(tmp_path)
    tile = "cont_a_north_000"
    rt._world_state.tile_occupancy["east_adam"] = tile
    rt._current_tile_resources[tile] = [{"kind": "wood", "amount": 5}]
    add_to_inventory(store, "east_adam", "stone_axe", 1)
    add_to_inventory(store, "east_adam", "stone", 5)
    add_to_inventory(store, "east_adam", "clay", 5)

    # Step 1: Model proposes hew_timber
    hew_out = validate_model_output(
        _valid_envelope({
            "action_type": "hew_timber",
            "reason": "Fell tree for shelter framing.",
            "tool": "stone_axe",
        }),
        ADAM_ID,
    )
    assert hew_out.is_valid
    hew_res = rt._execute_action("east_adam", hew_out.proposed_action, heartbeat_number=10)
    assert hew_res["status"] == "success"
    assert hew_res["timber_yield"] == 2
    assert load_inventory(store)["east_adam"]["timber"] == 2

    # Step 2: Model proposes build shelter with the 2 hewn timber
    build_out = validate_model_output(
        _valid_envelope({
            "action_type": "build",
            "object_id": "shelter-north-001",
            "object_type": "shelter",
            "description": "Timber-framed shelter against the rain",
            "tile_id": tile,
            "materials": {"timber": 2, "stone": 5, "clay": 5},
        }),
        ADAM_ID,
    )
    assert build_out.is_valid
    build_res = rt._execute_action("east_adam", build_out.proposed_action, heartbeat_number=11)
    assert build_res["status"] == "success", f"Expected shelter build to succeed, got: {build_res}"
    assert "shelter-north-001" in rt._world_state.public_objects


# ---------------------------------------------------------------------------
# 6. Same-tile duplicate object_id still rejected
# ---------------------------------------------------------------------------
def test_build_same_tile_duplicate_id_still_rejected(tmp_path):
    """When an object with the same object_id already exists on the SAME tile
    (visible in the agent's observation), duplicate object_id is rejected."""
    store, rt = _fresh_runtime(tmp_path)
    tile = "cont_a_north_000"
    rt._world_state.tile_occupancy["east_adam"] = tile
    add_to_inventory(store, "east_adam", "stone", 10)

    act = {
        "action_type": "build",
        "object_id": "campfire-001",
        "object_type": "campfire",
        "description": "Warm fire",
        "tile_id": tile,
        "materials": {"stone": 2},
    }
    first = rt._execute_action("east_adam", act, heartbeat_number=5)
    assert first["status"] == "success"

    second = rt._execute_action("east_adam", act, heartbeat_number=6)
    assert second["status"] == "rejected"
    assert "Duplicate object_id" in second["reason"]


# ---------------------------------------------------------------------------
# 7. Off-tile duplicate object_id disambiguated and succeeds
# ---------------------------------------------------------------------------
def test_build_off_tile_duplicate_id_disambiguated_and_succeeds(tmp_path):
    """When an agent proposes 'campfire-001' on a new tile and 'campfire-001'
    was built earlier on a different tile (invisible in current tile observation),
    _execute_build disambiguates the ID and succeeds instead of rejecting."""
    store, rt = _fresh_runtime(tmp_path)
    add_to_inventory(store, "east_adam", "stone", 10)

    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    first = rt._execute_action(
        "east_adam",
        {
            "action_type": "build",
            "object_id": "campfire-001",
            "object_type": "campfire",
            "description": "Origin campfire",
            "tile_id": "cont_a_gen_0_0",
            "materials": {"stone": 2},
        },
        heartbeat_number=5,
    )
    assert first["status"] == "success"

    # Move to a distant tile where campfire-001 is not visible
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_north_000"
    second = rt._execute_action(
        "east_adam",
        {
            "action_type": "build",
            "object_id": "campfire-001",
            "object_type": "campfire",
            "description": "North forest campfire",
            "tile_id": "cont_a_north_000",
            "materials": {"stone": 2},
        },
        heartbeat_number=42,
    )
    assert second["status"] == "success", f"Expected off-tile collision to disambiguate, got: {second}"
    created_id = second["object_id"]
    assert created_id != "campfire-001"
    assert created_id.startswith("campfire-001-")
    assert "campfire-001" in rt._world_state.public_objects
    assert created_id in rt._world_state.public_objects


# ---------------------------------------------------------------------------
# 8. Chronicle records craft (use_object) and hew_timber
# ---------------------------------------------------------------------------
def test_build_chronicle_records_craft_and_hew_timber():
    """Verify build_chronicle emits events when an agent crafts a tool via
    use_object or fells timber via hew_timber."""
    heartbeats = [
        {
            "heartbeat_number": 6355,
            "action_taken": {
                ADAM_ID: {
                    "action_type": "use_object",
                    "operation": "craft",
                    "target_object_id": "crafting_surface-001",
                    "materials": {"stone": 2, "wood": 1},
                }
            },
            "action_outcomes": {
                ADAM_ID: {
                    "status": "success",
                    "operation": "craft",
                    "crafted": "stone_axe",
                }
            },
        },
        {
            "heartbeat_number": 6360,
            "action_taken": {
                ADAM_ID: {
                    "action_type": "hew_timber",
                    "reason": "Fell tree for shelter.",
                }
            },
            "action_outcomes": {
                ADAM_ID: {
                    "status": "success",
                    "action_type": "hew_timber",
                    "timber_yield": 2,
                }
            },
        },
    ]
    chron = build_chronicle(heartbeats, {ADAM_ID: "east_adam"})
    kinds = [c["kind"] for c in chron]
    texts = [c["text"] for c in chron]
    assert "craft" in kinds, f"Expected 'craft' in chronicle kinds, got: {chron}"
    assert "hew_timber" in kinds, f"Expected 'hew_timber' in chronicle kinds, got: {chron}"
    assert any("stone_axe" in t for t in texts)
    assert any("timber" in t for t in texts)

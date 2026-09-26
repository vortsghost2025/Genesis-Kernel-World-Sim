"""Build layer — persistent belongings and agent-defined construction.

TDD suite for docs/build_layer_spec.md. Covers: inventory persistence
(load/add, fail-closed validation), gather persisting through the store,
build action validation + execution (cost enforcement, no debt, no partial
builds), ownership, context injection, and exporter payload.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import (
    _ACTION_SCHEMAS,
    _AVAILABLE_ACTIONS_DESC,
    _VALID_ACTIONS,
    build_system_prompt,
    validate_action_exact,
)
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    PublicObjectRecord,
    add_to_inventory,
    load_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime


ADAM_ID = "genesis-agent-4327298502de9566131e81212dd3b383666b6f18bc887d8508ab3a059e73f34e"


def _fresh_store(tmp_path: Path) -> FirstPairPersistenceStore:
    return FirstPairPersistenceStore(tmp_path / ".runtime" / "first-pair")


def _build_action(**overrides) -> dict:
    base = {
        "action_type": "build",
        "object_id": "wall-001",
        "object_type": "wall",
        "description": "A low dry-stone wall marking my corner of the world.",
        "tile_id": "tile-alpha",
        "materials": {"stone": 3},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Inventory persistence
# ---------------------------------------------------------------------------


class TestInventoryPersistence:
    def test_empty_store_loads_empty(self, tmp_path):
        store = _fresh_store(tmp_path)
        assert load_inventory(store) == {}

    def test_add_and_load(self, tmp_path):
        store = _fresh_store(tmp_path)
        inv = add_to_inventory(store, "east_adam", "stone", 2)
        assert inv == {"east_adam": {"stone": 2}}
        assert load_inventory(store) == {"east_adam": {"stone": 2}}

    def test_add_accumulates(self, tmp_path):
        store = _fresh_store(tmp_path)
        add_to_inventory(store, "east_adam", "stone", 2)
        inv = add_to_inventory(store, "east_adam", "stone", 3)
        assert inv["east_adam"]["stone"] == 5

    def test_spend_deducts(self, tmp_path):
        store = _fresh_store(tmp_path)
        add_to_inventory(store, "east_adam", "stone", 5)
        inv = add_to_inventory(store, "east_adam", "stone", -3)
        assert inv["east_adam"]["stone"] == 2

    def test_spend_to_zero_keeps_key(self, tmp_path):
        store = _fresh_store(tmp_path)
        add_to_inventory(store, "east_adam", "stone", 1)
        inv = add_to_inventory(store, "east_adam", "stone", -1)
        assert inv["east_adam"]["stone"] == 0

    def test_overdraft_rejected_nothing_written(self, tmp_path):
        store = _fresh_store(tmp_path)
        add_to_inventory(store, "east_adam", "stone", 2)
        with pytest.raises(ValueError):
            add_to_inventory(store, "east_adam", "stone", -3)
        assert load_inventory(store) == {"east_adam": {"stone": 2}}

    def test_empty_kind_rejected(self, tmp_path):
        store = _fresh_store(tmp_path)
        with pytest.raises(ValueError):
            add_to_inventory(store, "east_adam", "   ", 1)

    def test_non_integer_delta_rejected(self, tmp_path):
        store = _fresh_store(tmp_path)
        with pytest.raises(ValueError):
            add_to_inventory(store, "east_adam", "stone", 1.5)

    def test_bool_delta_rejected(self, tmp_path):
        store = _fresh_store(tmp_path)
        with pytest.raises(ValueError):
            add_to_inventory(store, "east_adam", "stone", True)

    def test_agents_independent(self, tmp_path):
        store = _fresh_store(tmp_path)
        add_to_inventory(store, "east_adam", "stone", 4)
        add_to_inventory(store, "east_eve", "stone", 1)
        inv = load_inventory(store)
        assert inv["east_adam"]["stone"] == 4
        assert inv["east_eve"]["stone"] == 1


# ---------------------------------------------------------------------------
# Build action validation
# ---------------------------------------------------------------------------


class TestBuildActionValidation:
    def test_in_vocabulary(self):
        assert "build" in _VALID_ACTIONS
        assert _ACTION_SCHEMAS["build"] == frozenset(
            {"action_type", "object_id", "object_type", "description",
             "tile_id", "materials"}
        )
        assert "build" in _AVAILABLE_ACTIONS_DESC

    def test_valid_accepted(self):
        assert validate_action_exact(_build_action(), ADAM_ID) == []

    def test_empty_materials_rejected(self):
        errors = validate_action_exact(_build_action(materials={}), ADAM_ID)
        assert "action:empty_materials" in errors

    def test_missing_materials_rejected(self):
        action = _build_action()
        del action["materials"]
        errors = validate_action_exact(action, ADAM_ID)
        assert "action:empty_materials" in errors

    def test_non_dict_materials_rejected(self):
        errors = validate_action_exact(
            _build_action(materials=["stone"]), ADAM_ID)
        assert "action:materials_not_a_dict" in errors

    def test_zero_amount_rejected(self):
        errors = validate_action_exact(
            _build_action(materials={"stone": 0}), ADAM_ID)
        assert "action:bad_material_amount_stone" in errors

    def test_negative_amount_rejected(self):
        errors = validate_action_exact(
            _build_action(materials={"stone": -2}), ADAM_ID)
        assert "action:bad_material_amount_stone" in errors

    def test_bool_amount_rejected(self):
        errors = validate_action_exact(
            _build_action(materials={"stone": True}), ADAM_ID)
        assert "action:bad_material_amount_stone" in errors

    def test_empty_kind_rejected(self):
        errors = validate_action_exact(
            _build_action(materials={"  ": 2}), ADAM_ID)
        assert "action:bad_material_kind" in errors

    def test_too_many_entries_rejected(self):
        mats = {f"mat{i}": 1 for i in range(9)}
        errors = validate_action_exact(_build_action(materials=mats), ADAM_ID)
        assert "action:too_many_materials" in errors

    def test_excessive_total_rejected(self):
        errors = validate_action_exact(
            _build_action(materials={"stone": 65}), ADAM_ID)
        assert "action:materials_total_too_large" in errors

    def test_unknown_field_rejected(self):
        errors = validate_action_exact(
            _build_action(surprise=True), ADAM_ID)
        assert any("unknown_field" in e for e in errors)


# ---------------------------------------------------------------------------
# Runtime end-to-end
# ---------------------------------------------------------------------------


class TestBuildRuntime:
    def _runtime(self, store) -> FirstPairRuntime:
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        return rt

    def test_gather_persists_inventory(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        # seed a gatherable resource on adam's tile via the tile map
        rt._current_tile_resources = {"tile-alpha": [{"kind": "stone", "amount": 5}]}
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        outcome = rt._execute_action(
            "east_adam",
            {"action_type": "gather", "resource_kind": "stone", "reason": "test"},
            heartbeat_number=2,
        )
        assert outcome.get("status") == "success"
        assert load_inventory(store)["east_adam"]["stone"] == 1

    def test_build_spends_and_creates(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        add_to_inventory(store, "east_adam", "stone", 5)
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        # tile-alpha must be allowed: fresh store habitat allows start tiles;
        # place explicitly to be robust
        rt._habitat.setdefault("allowed_tile_ids", []).append("tile-alpha")
        action = _build_action()
        outcome = rt._execute_action("east_adam", action, heartbeat_number=2)
        assert outcome.get("status") == "success"
        assert outcome.get("materials_spent") == {"stone": 3}
        assert load_inventory(store)["east_adam"]["stone"] == 2
        obj = rt._world_state.public_objects.get("wall-001")
        assert obj is not None
        assert obj.get("materials") == {"stone": 3}
        assert obj.get("creator_agent_id") == rt._agent_view("east_adam")["agent_id"]

    def test_build_insufficient_rejected_no_partial(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        add_to_inventory(store, "east_adam", "stone", 2)
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        rt._habitat.setdefault("allowed_tile_ids", []).append("tile-alpha")
        outcome = rt._execute_action(
            "east_adam", _build_action(materials={"stone": 3}),
            heartbeat_number=2)
        assert outcome.get("status") == "rejected"
        # nothing spent, nothing created
        assert load_inventory(store)["east_adam"]["stone"] == 2
        assert "wall-001" not in rt._world_state.public_objects

    def test_build_wrong_tile_rejected(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        add_to_inventory(store, "east_adam", "stone", 9)
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        outcome = rt._execute_action(
            "east_adam", _build_action(tile_id="tile-elsewhere"),
            heartbeat_number=2)
        assert outcome.get("status") == "rejected"
        assert load_inventory(store)["east_adam"]["stone"] == 9

    def test_build_duplicate_id_rejected(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        add_to_inventory(store, "east_adam", "stone", 9)
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        rt._habitat.setdefault("allowed_tile_ids", []).append("tile-alpha")
        first = rt._execute_action("east_adam", _build_action(), heartbeat_number=2)
        assert first.get("status") == "success"
        second = rt._execute_action("east_adam", _build_action(), heartbeat_number=3)
        assert second.get("status") == "rejected"
        # second build spent nothing
        assert load_inventory(store)["east_adam"]["stone"] == 6

    def test_build_counts_as_mutation(self, tmp_path):
        """Build joins the world-mutation action list (provenance)."""
        import backend.world.first_pair_runtime as rt_mod
        import inspect
        src = inspect.getsource(rt_mod.FirstPairRuntime.run)
        assert '"build"' in src or "'build'" in src

    def test_context_shows_holdings(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = self._runtime(store)
        add_to_inventory(store, "east_adam", "stone", 4)
        ctx = rt._build_context("east_adam", 2)
        assert ctx.inventory == {"east_adam": {"stone": 4}} or ctx.inventory == {"stone": 4}
        prompt = build_system_prompt(ctx)
        assert "YOUR BELONGINGS" in prompt
        assert "stone" in prompt

    def test_public_object_record_materials_default(self):
        rec = PublicObjectRecord(
            object_id="o", creator_agent_id="a", tile_id="t",
            object_type="wall", public_description="d", created_heartbeat=1,
        )
        assert rec.to_envelope().get("materials", {}) == {}

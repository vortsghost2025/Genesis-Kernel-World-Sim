"""Objects hold things: the interaction Eve asked for.

`docs/object_interaction_spec.md`. West Eve at HB1864: "What I need
that the world does not provide is an interaction mechanism. What I
cannot do is put materials into an object and get something back out."

This is the mechanic she named. A new action type, `use_object`, lets
an agent deposit into, extract from, and inspect any public object on
their tile. Objects get a `contents` dict. Deposits and extracts are
bounded by inventory and contents respectively, and every operation
changes both the object's record and the agent's inventory honestly.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m  # noqa: E402
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
)


def _rt(tmp_path):
    store = FirstPairPersistenceStore(root=tmp_path)
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt._load_or_initialize()
    return rt


def _seed_inventory(rt, agent_ref, holdings):
    from backend.world.first_pair_persistence import add_to_inventory
    for kind, amount in holdings.items():
        add_to_inventory(rt._store, agent_ref, kind, amount)


def _seed_object(rt, obj_id="obj-1", obj_type="storage", tile="public-start-adam"):
    rt._world_state.public_objects[obj_id] = {
        "object_id": obj_id,
        "object_type": obj_type,
        "tile_id": tile,
        "creator_agent_id": "genesis-agent-test-adam-" + "0" * 48,
        "public_description": "test object",
        "materials": {},
        "contents": {},
        "created_heartbeat": 1,
    }


class TestContractAcceptsUseObject:
    def test_use_object_validates(self):
        v = m.validate_model_output({
            "observation_summary": "s", "self_model_update": None,
            "goal_updates": [], "memory_candidates": [],
            "questions_for_humans": [], "uncertainty": "u",
            "decision_summary": "d", "confidence": 0.5,
            "proposed_action": {
                "action_type": "use_object",
                "target_object_id": "obj-1",
                "operation": "deposit",
                "materials": {"stone": 2},
            },
        }, "genesis-agent-test-adam-" + "0" * 48)
        assert v.is_valid, v.validation_errors

    def test_inspect_operation_validates(self):
        v = m.validate_model_output({
            "observation_summary": "s", "self_model_update": None,
            "goal_updates": [], "memory_candidates": [],
            "questions_for_humans": [], "uncertainty": "u",
            "decision_summary": "d", "confidence": 0.5,
            "proposed_action": {
                "action_type": "use_object",
                "target_object_id": "obj-1",
                "operation": "inspect",
            },
        }, "genesis-agent-test-adam-" + "0" * 48)
        assert v.is_valid, v.validation_errors


class TestDeposit:
    def test_deposit_moves_inventory_to_contents(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt)
        rt._world_state.tile_occupancy["east_adam"] = "public-start-adam"
        _seed_inventory(rt, "east_adam", {"stone": 5})
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "obj-1",
            "operation": "deposit",
            "materials": {"stone": 2},
        }, 100)
        assert out["status"] == "success"
        obj = rt._world_state.public_objects["obj-1"]
        assert obj["contents"].get("stone") == 2
        inv = rt._get_agent_inventory("east_adam")
        assert inv.get("stone") == 3

    def test_cannot_deposit_what_you_do_not_hold(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt)
        rt._world_state.tile_occupancy["east_adam"] = "public-start-adam"
        _seed_inventory(rt, "east_adam", {"stone": 1})
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "obj-1",
            "operation": "deposit",
            "materials": {"stone": 5},
        }, 100)
        assert out["status"] == "rejected"
        assert "not enough" in out.get("reason", "").lower() or \
            "do not hold" in out.get("reason", "").lower()

    def test_deposit_on_wrong_tile_rejected(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt, tile="somewhere-else")
        rt._world_state.tile_occupancy["east_adam"] = "public-start-adam"
        _seed_inventory(rt, "east_adam", {"stone": 5})
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "obj-1",
            "operation": "deposit",
            "materials": {"stone": 1},
        }, 100)
        assert out["status"] == "rejected"


class TestExtract:
    def test_extract_moves_contents_to_inventory(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt)
        rt._world_state.public_objects["obj-1"]["contents"] = {"stone": 3}
        rt._world_state.tile_occupancy["east_adam"] = "public-start-adam"
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "obj-1",
            "operation": "extract",
            "materials": {"stone": 2},
        }, 100)
        assert out["status"] == "success"
        obj = rt._world_state.public_objects["obj-1"]
        assert obj["contents"].get("stone") == 1
        inv = rt._get_agent_inventory("east_adam")
        assert inv.get("stone") == 2

    def test_cannot_extract_what_is_not_there(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt)
        rt._world_state.public_objects["obj-1"]["contents"] = {"stone": 1}
        rt._world_state.tile_occupancy["east_adam"] = "public-start-adam"
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "obj-1",
            "operation": "extract",
            "materials": {"stone": 5},
        }, 100)
        assert out["status"] == "rejected"


class TestInspect:
    def test_inspect_shows_contents(self, tmp_path):
        rt = _rt(tmp_path)
        _seed_object(rt)
        rt._world_state.public_objects["obj-1"]["contents"] = {"stone": 2}
        rt._world_state.tile_occupancy["east_adam"] = "public-start-adam"
        out = rt._execute_use_object("east_adam", {
            "target_object_id": "obj-1",
            "operation": "inspect",
        }, 100)
        assert out["status"] == "success"
        assert "contents" in out
        assert out["contents"].get("stone") == 2


class TestThePromptNamesIt:
    def test_available_actions_list_includes_use_object(self):
        assert "use_object" in m._AVAILABLE_ACTIONS_DESC, (
            "the prompt must list use_object so agents discover it")

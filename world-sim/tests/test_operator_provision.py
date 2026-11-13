"""Phase 10QJ - the operator can hand them water, and it survives.

Operator, 2026-11-13: "the agent in your spot is responsible to help them/
teach them/respond them/fix issues. you are their god. i am the viewer."

Two defects behind that, both measured the same day:

1. POLICY IMPERSONATING PHYSICS. The operator desk answered every request
   matching "provide|give me|feed me|send me|bring me" with the flat line
   "The operator does not hand out anything." Across both lanes the agents
   had asked for water, food, clay and emergency provision 100+ times (449
   of West's 560 questions carried a capability request) while three of four
   sat collapsed at thirst 100. The door was bolted by policy, not by the
   world.

2. A RACE. Writing the live world_state straight from the operator side does
   not work: a heartbeat that began before the write saves its own copy when
   it persists. Measured: eight provisions written directly into
   world_state.json were gone by the next completed heartbeat.

So the operator enqueues and the RUNTIME applies the queue inside the
read-modify-write it already owns. These tests pin both halves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import FirstPairPersistenceStore
from backend.world.first_pair_runtime import FirstPairRuntime

TILE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(
        heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._world_state.tick = 100
    return rt


def _queue(store_root: Path, acts: list[dict]) -> Path:
    p = store_root / "operator_provisions_pending.json"
    p.write_text(json.dumps({"acts": acts}, indent=1), encoding="utf-8",
                 newline="\n")
    return p


def test_a_queued_water_provision_becomes_an_object_on_the_tile(tmp_path):
    rt = _runtime(tmp_path)
    store_root = rt._store.root
    _queue(store_root, [{
        "object_id": "operator-provision-hb100-fresh_water-1",
        "agent_ref": "east_adam", "tile_id": TILE,
        "kind": "fresh_water", "amount": 3, "reason": "collapsed",
    }])

    applied = rt._apply_operator_provision_queue()

    assert applied == 1
    obj = rt._world_state.public_objects["operator-provision-hb100-fresh_water-1"]
    assert obj["tile_id"] == TILE
    assert obj["contents"]["fresh_water"] == 3
    assert obj["creator_agent_id"] == "the operator"
    assert obj["provenance"] == "operator-provision"


def test_a_queued_food_provision_lands_in_materials(tmp_path):
    """The world's downed-feed path reads materials, the downed-drink path
    reads contents.fresh_water. A provision must land where those read."""
    rt = _runtime(tmp_path)
    _queue(rt._store.root, [{
        "object_id": "operator-provision-hb100-edible_roots-1",
        "agent_ref": "east_adam", "tile_id": TILE,
        "kind": "edible_roots", "amount": 3, "reason": "starving",
    }])
    assert rt._apply_operator_provision_queue() == 1
    obj = rt._world_state.public_objects["operator-provision-hb100-edible_roots-1"]
    assert obj["materials"]["edible_roots"] == 3
    assert obj["contents"] == {}


def test_the_provision_is_drunk_and_eaten_by_a_downed_body(tmp_path):
    """End to end: the point of the cache is that a body on the ground uses it."""
    rt = _runtime(tmp_path)
    _queue(rt._store.root, [
        {"object_id": "w1", "agent_ref": "east_adam", "tile_id": TILE,
         "kind": "fresh_water", "amount": 2, "reason": "x"},
        {"object_id": "f1", "agent_ref": "east_adam", "tile_id": TILE,
         "kind": "edible_roots", "amount": 2, "reason": "x"},
    ])
    assert rt._apply_operator_provision_queue() == 2

    vitals = rt._vitals_for("east_adam")
    vitals["downed"] = True
    vitals["thirst"] = 100.0
    vitals["hunger"] = 100.0
    vitals["vitality"] = 0.0

    rt.apply_survival_to_all(101)

    assert rt._vitals_for("east_adam")["thirst"] < 100.0
    assert rt._vitals_for("east_adam")["hunger"] < 100.0
    assert rt._world_state.public_objects["w1"]["contents"]["fresh_water"] == 1
    assert rt._world_state.public_objects["f1"]["materials"]["edible_roots"] == 1


def test_applying_twice_does_not_duplicate_the_gift(tmp_path):
    """Idempotent by object_id, so a re-run cannot double a provision."""
    rt = _runtime(tmp_path)
    _queue(rt._store.root, [{
        "object_id": "w1", "agent_ref": "east_adam", "tile_id": TILE,
        "kind": "fresh_water", "amount": 3, "reason": "x",
    }])
    assert rt._apply_operator_provision_queue() == 1
    assert rt._apply_operator_provision_queue() == 0
    assert "w1" in rt._world_state.public_objects


def test_the_queue_is_drained_after_application(tmp_path):
    rt = _runtime(tmp_path)
    q = _queue(rt._store.root, [{
        "object_id": "w1", "agent_ref": "east_adam", "tile_id": TILE,
        "kind": "fresh_water", "amount": 3, "reason": "x",
    }])
    rt._apply_operator_provision_queue()
    remaining = json.loads(q.read_text(encoding="utf-8"))["acts"]
    assert remaining == []


def test_no_queue_is_not_an_error(tmp_path):
    rt = _runtime(tmp_path)
    assert rt._apply_operator_provision_queue() == 0


def test_a_malformed_queue_does_not_break_the_load(tmp_path):
    rt = _runtime(tmp_path)
    (rt._store.root / "operator_provisions_pending.json").write_text(
        "{ not json", encoding="utf-8")
    assert rt._apply_operator_provision_queue() == 0


def test_the_desk_escalates_a_provisioning_request_instead_of_refusing(tmp_path):
    """The behaviour, not the text: a request for help must come back as None
    (escalate to the operator, who can now act) rather than as a refusal."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "opdesk", str(WORLD_SIM / "scripts" / "operator_desk.py"))
    od = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(od)

    facts = {
        "food_on_hand": "nothing edible", "tile_food": [], "other_name": "Eve",
        "other_position": TILE, "other_food": "nothing edible",
        "hunger": 100.0, "warmth": 90.0, "vitality": 1.0, "position": TILE,
        "night": False, "weather": "clear", "season": "winter",
        "terms": "current",
    }
    for question in (
        "Please provide fresh water to my tile.",
        "Can you bring me food?",
        "I need emergency provision of water.",
        "Please deliver edible_roots to my tile.",
    ):
        answer = od.draft_answer(question, facts)
        assert answer is None, f"still refuses: {question!r} -> {answer!r}"


def test_the_provision_tool_never_writes_the_live_world_state():
    """It must ENQUEUE. Writing world_state directly is the race that lost
    eight provisions on 2026-11-13."""
    src = (WORLD_SIM / "scripts" / "operator_provide.py").read_text(encoding="utf-8")
    assert "operator_provisions_pending.json" in src
    assert "ws_path.write_text" not in src
    assert "save_world_state" not in src

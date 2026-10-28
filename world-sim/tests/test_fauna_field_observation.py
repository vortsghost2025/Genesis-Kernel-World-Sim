"""Phase 10JR: Fauna Field Observation and Multi-step Lifecycle tests.

Covers:
1. Sensory field prompt distance and adjacency affordance verbs per Section 4.2.
2. Multi-step cow taming and milking lifecycle (observe -> move -> offer food x4 -> milk -> eat).
3. Verification of fauna suites in .github/workflows/pure-tests.yml.
"""

from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import build_system_prompt
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    load_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime
from backend.world.fauna import (
    ANIMAL_FOOD_TRUST,
    COW_TRUST_THRESHOLD,
    MILK_READY_HEARTBEATS,
    advance_cow_milk,
)
from backend.world.survival import EAT_SATISFACTION


def test_fauna_field_observation_prompt_enhancement():
    context = AgentContext(
        agent_id="agent-1",
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=10,
        position="tile-center",
        observation={
            "self_body": {"hunger": 50.0, "vitality": 100.0, "warmth": 100.0, "wetness": 0.0, "downed": False},
            "fauna": {
                "nearby": [
                    {
                        "kind": "cow",
                        "id": "cow-6864-0",
                        "distance": 4,
                        "trust": 0,
                        "tamed": False,
                        "milk_ready": False,
                    },
                    {
                        "kind": "cow",
                        "id": "cow-adjacent",
                        "distance": 1,
                        "trust": 0,
                        "tamed": False,
                        "milk_ready": False,
                    },
                    {
                        "kind": "horse",
                        "id": "horse-adjacent",
                        "distance": 1,
                        "trust": 0,
                        "tamed": False,
                    },
                    {
                        "kind": "cow",
                        "id": "cow-milking",
                        "distance": 1,
                        "trust": 60,
                        "tamed": True,
                        "milk_ready": True,
                    },
                ]
            },
        },
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["tile-center"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-10-28T12:00:00Z",
        inventory={},
    )
    prompt = build_system_prompt(context)

    # 1. Nearby untamed cow (4 tiles away)
    assert "- A cow is nearby (4 tiles away); it is untamed [id: cow-6864-0]. You can move closer to interact." in prompt

    # 2. Adjacent untamed cow (1 tile away)
    assert "- A cow is nearby (adjacent); it is untamed [id: cow-adjacent]. You can offer animal foods (wild_berries, edible_roots, wild_apples, wild_grain, fiber_plants) using offer_food to build trust." in prompt

    # 3. Adjacent wary horse (1 tile away)
    assert "- A horse is nearby (adjacent); it is wary [id: horse-adjacent]. You can offer animal foods (wild_berries, edible_roots, wild_apples, wild_grain, fiber_plants) using offer_food to build trust." in prompt

    # 4. Adjacent tamed cow with milk ready
    assert "- A cow is nearby (adjacent); it is tamed and milk is ready [id: cow-milking]. You can milk it using milk_animal." in prompt


def test_multistep_cow_taming_and_milking_lifecycle(tmp_path: Path):
    store = FirstPairPersistenceStore(tmp_path / "store")
    runtime = FirstPairRuntime(heartbeat_limit=1, store=store)
    runtime._load_or_initialize()

    # Step 1: Agent observes wild cow at distance 2 (agent at [0, 0], cow at [0, 2])
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    cow = {
        "kind": "cow",
        "id": "cow-test-1",
        "tile": [0, 2],
        "hp": 4,
        "trust": 0,
        "tamed": False,
        "milk_ready": False,
        "milk_ready_at_hb": 0,
        "anchor_tile": None,
    }
    runtime._world_state.fauna = [cow]

    obs = runtime._fauna_visible("east_adam")
    assert len(obs["nearby"]) == 1
    assert obs["nearby"][0]["id"] == "cow-test-1"
    assert obs["nearby"][0]["distance"] == 2
    assert obs["nearby"][0]["tamed"] is False

    # Step 2: Agent moves to distance 1 (adjacent at [0, 1])
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_1"
    obs_adj = runtime._fauna_visible("east_adam")
    assert obs_adj["nearby"][0]["distance"] == 1

    # Step 3: Agent executes offer_food with wild_berries (trust increases from 0 to 15)
    add_to_inventory(runtime._store, "east_adam", "wild_berries", 4)
    outcome1 = runtime._execute_action("east_adam", {
        "action_type": "offer_food",
        "target_id": "cow-test-1",
        "resource_kind": "wild_berries",
        "reason": "tame cow step 1",
    }, 10)
    assert outcome1["status"] == "success"
    assert runtime._world_state.fauna[0]["trust"] == 15
    assert runtime._world_state.fauna[0]["tamed"] is False

    # Step 4: Agent executes offer_food 3 more times until trust reaches 60
    for i in range(2, 5):
        outcome = runtime._execute_action("east_adam", {
            "action_type": "offer_food",
            "target_id": "cow-test-1",
            "resource_kind": "wild_berries",
            "reason": f"tame cow step {i}",
        }, 10 + i)
        assert outcome["status"] == "success"

    # Step 5: Verify cow is tamed and anchor_tile is set to agent tile where taming completed
    assert runtime._world_state.fauna[0]["trust"] == COW_TRUST_THRESHOLD
    assert runtime._world_state.fauna[0]["tamed"] is True
    assert runtime._world_state.fauna[0]["anchor_tile"] == [0, 1]

    # Step 6: Advance heartbeat past milk cooldown (MILK_READY_HEARTBEATS = 144)
    tame_hb = 20
    # First tick initializes milk_ready_at_hb timer
    runtime._world_state.fauna = advance_cow_milk(runtime._world_state.fauna, tame_hb)
    assert runtime._world_state.fauna[0]["milk_ready_at_hb"] == tame_hb
    assert runtime._world_state.fauna[0]["milk_ready"] is False

    # Second tick after interval elapses sets milk_ready = True
    runtime._world_state.fauna = advance_cow_milk(runtime._world_state.fauna, tame_hb + MILK_READY_HEARTBEATS + 1)
    assert runtime._world_state.fauna[0]["milk_ready"] is True

    # Step 7: Agent executes milk_animal, receives 1 milk
    outcome_milk = runtime._execute_action("east_adam", {
        "action_type": "milk_animal",
        "target_id": "cow-test-1",
        "reason": "milk the tamed cow",
    }, tame_hb + MILK_READY_HEARTBEATS + 2)
    assert outcome_milk["status"] == "success"
    inv = load_inventory(runtime._store).get("east_adam", {})
    assert inv.get("milk", 0) >= 1
    assert runtime._world_state.fauna[0]["milk_ready"] is False

    # Step 8: Agent executes eat resource_kind milk, satisfying 28.0 hunger
    assert EAT_SATISFACTION["milk"] == 28.0
    outcome_eat = runtime._execute_action("east_adam", {
        "action_type": "eat",
        "resource_kind": "milk",
        "reason": "drink fresh milk",
    }, tame_hb + MILK_READY_HEARTBEATS + 3)
    assert outcome_eat["status"] == "success"


def test_github_ci_workflow_fauna_suites_present():
    workflow_path = WORLD_SIM.parent / ".github" / "workflows" / "pure-tests.yml"
    assert workflow_path.exists()
    content = workflow_path.read_text(encoding="utf-8")

    expected_suites = [
        "tests/test_fauna_pure.py",
        "tests/test_fauna_interactions.py",
        "tests/test_fauna_runtime.py",
        "tests/test_fauna_cognition.py",
    ]
    for suite in expected_suites:
        assert suite in content, f"Missing suite {suite} in pure-tests.yml"

"""Tests for Phase 10KX/10KZ: Goal Lifecycle, Deduplication & Settlement Awareness.

Verifies the 12 required test cases specified in Phase 10KX §5:
1. test_build_context_deduplicates_goal_descriptions (Adam's and Eve's real shapes)
2. test_build_context_still_slices_most_recent_when_all_distinct (20 distinct -> exactly 8 exposed, most recent)
3. test_dedupe_preserves_all_records_on_disk (self._goals and goals.json unchanged)
4. test_survey_goal_retires_when_region_covered
5. test_survey_goal_survives_with_partial_coverage
6. test_gather_goal_retires_at_threshold_only
7. test_fresh_test_goal_survives_age_rule
8. test_timber_fact_line_absent_when_timber_held
9. test_no_shelter_fact_line_absent_when_shelter_owned
10. test_belonging_counts_stated_as_facts
11. test_settlement_facts_contain_no_directives
12. test_agent_context_exposes_shelter_ownership
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_interface
from backend.world import first_pair_cognition_model
from backend.world import first_pair_fog_adapter
from backend.world import first_pair_persistence
from backend.world import first_pair_runtime
from backend.world.first_pair_persistence import GoalRecord


def _make_runtime_with_goals(tmp_path: Path, goals: list[GoalRecord], public_objects: dict | None = None) -> tuple[first_pair_runtime.FirstPairRuntime, str]:
    """Helper to initialize a FirstPairRuntime in a temporary directory with test goals."""
    store = first_pair_persistence.FirstPairPersistenceStore(tmp_path / "store")
    runtime = first_pair_runtime.FirstPairRuntime(heartbeat_limit=1, store=store)
    runtime._load_or_initialize()

    agent_ref = "east_adam"
    view = runtime._agent_view(agent_ref)
    real_agent_id = view["agent_id"]

    for g in goals:
        if not g.agent_id:
            g.agent_id = real_agent_id

    first_pair_persistence.save_goals(store, goals)
    runtime._goals = goals

    if public_objects is not None:
        runtime._world_state.public_objects = public_objects

    return runtime, real_agent_id


def test_build_context_deduplicates_goal_descriptions(tmp_path: Path):
    """Adam's and Eve's real shapes: duplicates must be collapsed before taking top 8.

    Adam has 15 active goals with 6 distinct descriptions. Context must expose all 6
    distinct descriptions and zero duplicate descriptions.
    """
    distinct_descs = [
        "Continue exploring uncharted hill terrain and gather resources",
        "Continue exploring uncharted hill terrain",
        "Explore new tile cont_a_gen_-12_2 for resources and mapping",
        "Continue exploring new tiles",
        "move to cont_a_gen_-13_3 to gather stone and continue exploring uncharted hill terrain",
        "Continue exploring uncharted hill terrain and gather stone",
    ]
    # Replicate Adam's real duplicate pattern: 15 active goals, 6 distinct
    goals = []
    for i in range(15):
        desc = distinct_descs[i % len(distinct_descs)]
        goals.append(GoalRecord(f"g-adam-{i}", "", desc, "in_progress", 5000 + i))

    runtime, _ = _make_runtime_with_goals(tmp_path, goals)
    ctx = runtime._build_context("east_adam", 6000)

    exposed_descs = [g["description"] for g in ctx.goals]
    assert len(exposed_descs) == 6, f"Expected 6 distinct goals, got {len(exposed_descs)}"
    assert len(set(exposed_descs)) == 6, "Exposed goals must contain zero duplicate descriptions"
    for d in distinct_descs:
        assert d in exposed_descs, f"Distinct goal '{d}' should be present in exposed context"


def test_build_context_still_slices_most_recent_when_all_distinct(tmp_path: Path):
    """When an agent holds 20 genuinely distinct goals, dedup preserves all and slices the 8 most recent."""
    goals = [
        GoalRecord(f"g-{i:02d}", "", f"Unique Goal {i}", "in_progress", 1000 + i)
        for i in range(1, 21)
    ]
    runtime, _ = _make_runtime_with_goals(tmp_path, goals)
    ctx = runtime._build_context("east_adam", 2000)

    exposed_descs = [g["description"] for g in ctx.goals]
    assert len(exposed_descs) == 8, f"Expected 8 exposed goals, got {len(exposed_descs)}"
    expected = [f"Unique Goal {i}" for i in range(13, 21)]
    assert exposed_descs == expected, f"Expected most recent 8 distinct goals, got {exposed_descs}"


def test_dedupe_preserves_all_records_on_disk(tmp_path: Path):
    """Deduplication at context build must be non-destructive: self._goals and disk are untouched."""
    goals = [
        GoalRecord(f"g-{i}", "", "Duplicate explore goal", "in_progress", 1000 + i)
        for i in range(10)
    ]
    runtime, _ = _make_runtime_with_goals(tmp_path, goals)
    ctx = runtime._build_context("east_adam", 2000)

    assert len(ctx.goals) == 1, "Context should only expose 1 deduped copy"
    assert len(runtime._goals) == 10, "runtime._goals in memory must retain all 10 records"

    # Reload from disk to verify disk storage is untouched
    disk_goals = first_pair_persistence.load_goals(runtime._store)
    assert len(disk_goals) == 10, "goals.json on disk must retain all 10 records"


def test_survey_goal_retires_when_region_covered(tmp_path: Path):
    """A survey goal referencing specific tiles retires when known_map covers them."""
    goal = GoalRecord(
        "g-survey-1", "",
        "Explore new tile cont_a_gen_-12_2 for resources and mapping",
        "in_progress", 5000
    )
    runtime, agent_id = _make_runtime_with_goals(tmp_path, [goal])

    # Populate known_map with the referenced tile
    km = first_pair_fog_adapter.create_empty_known_map("east_adam")
    km["known_tiles"]["cont_a_gen_-12_2"] = {"seen_at": 5050}
    first_pair_fog_adapter.persist_known_map(runtime._store.root, "east_adam", km)

    retired = runtime.retire_stale_goals("east_adam", 5100)
    assert any(g.goal_id == "g-survey-1" for g in retired), "Survey goal should be retired"
    assert runtime._goals[0].status == "retired"

    # Verify persisted to disk
    disk_goals = first_pair_persistence.load_goals(runtime._store)
    assert disk_goals[0].status == "retired"


def test_survey_goal_survives_with_partial_coverage(tmp_path: Path):
    """A survey goal referencing multiple tiles must NOT retire if coverage is partial."""
    goal = GoalRecord(
        "g-survey-2", "",
        "Survey tiles cont_a_gen_-12_2 and cont_a_gen_-13_2 for campsite",
        "in_progress", 5000
    )
    runtime, agent_id = _make_runtime_with_goals(tmp_path, [goal])

    # Populate known_map with only ONE of the two tiles
    km = first_pair_fog_adapter.create_empty_known_map("east_adam")
    km["known_tiles"]["cont_a_gen_-12_2"] = {"seen_at": 5050}
    first_pair_fog_adapter.persist_known_map(runtime._store.root, "east_adam", km)

    retired = runtime.retire_stale_goals("east_adam", 5100)
    assert not any(g.goal_id == "g-survey-2" for g in retired), "Partially covered survey goal must NOT retire"
    assert runtime._goals[0].status == "in_progress"


def test_gather_goal_retires_at_threshold_only(tmp_path: Path):
    """A gather goal retires only when inventory meets or exceeds the defined threshold."""
    goal = GoalRecord(
        "g-gather-1", "",
        "Continue exploring uncharted hill terrain and gather stone",
        "in_progress", 5000
    )
    runtime, agent_id = _make_runtime_with_goals(tmp_path, [goal])

    # Set inventory below threshold (e.g. 5 stone < 20 threshold)
    first_pair_persistence.add_to_inventory(runtime._store, "east_adam", "stone", 5)

    retired_under = runtime.retire_stale_goals("east_adam", 5100)
    assert not any(g.goal_id == "g-gather-1" for g in retired_under), "Gather goal should survive below threshold"

    # Set inventory above threshold (e.g. +35 stone -> 40 stone >= 20 threshold)
    first_pair_persistence.add_to_inventory(runtime._store, "east_adam", "stone", 35)

    retired_over = runtime.retire_stale_goals("east_adam", 5100)
    assert any(g.goal_id == "g-gather-1" for g in retired_over), "Gather goal should retire at/above threshold"
    assert runtime._goals[0].status == "retired"


def test_fresh_test_goal_survives_age_rule(tmp_path: Path):
    """A 'test whether...' goal survives if younger than STALE_GOAL_AGE_HB (500), retires if older."""
    fresh_goal = GoalRecord("g-test-fresh", "", "Test whether gather works for me under physics.epistemic.3", "in_progress", 5800)
    stale_goal = GoalRecord("g-test-stale", "", "Test whether gather works for me under physics.epistemic.2", "in_progress", 5000)

    runtime, agent_id = _make_runtime_with_goals(tmp_path, [fresh_goal, stale_goal])

    # At heartbeat 6000:
    # fresh_goal age = 6000 - 5800 = 200 (< 500) -> survives
    # stale_goal age = 6000 - 5000 = 1000 (>= 500) -> retires
    retired = runtime.retire_stale_goals("east_adam", 6000)
    retired_ids = {g.goal_id for g in retired}

    assert "g-test-fresh" not in retired_ids, "Fresh test goal (< 500 HB) must survive"
    assert "g-test-stale" in retired_ids, "Stale test goal (>= 500 HB) must retire"


def test_timber_fact_line_absent_when_timber_held():
    """Agent with 0 timber gets the timber fact line; agent with 5 timber sees held count."""
    ctx_no_timber = first_pair_cognition_interface.AgentContext(
        agent_id="agent-1", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=100, position="cont_a_gen_0_0",
        observation={"self_body": {"hunger": 0, "warmth": 100}},
        memory=[], goals=[], unanswered_questions=[],
        world_public_objects={}, habitat_allowed_tiles=[],
        habitat_movement_allowed=True, previous_action=None,
        timestamp_utc="", inventory={"wood": 2, "stone": 441, "timber": 0},
        owns_shelter=False,
    )
    prompt_no_timber = first_pair_cognition_model.build_system_prompt(ctx_no_timber)
    assert "Fact: you hold no structural timber" in prompt_no_timber
    assert "hew_timber with an axe or knapped blade" in prompt_no_timber

    ctx_has_timber = first_pair_cognition_interface.AgentContext(
        agent_id="agent-1", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=100, position="cont_a_gen_0_0",
        observation={"self_body": {"hunger": 0, "warmth": 100}},
        memory=[], goals=[], unanswered_questions=[],
        world_public_objects={}, habitat_allowed_tiles=[],
        habitat_movement_allowed=True, previous_action=None,
        timestamp_utc="", inventory={"wood": 2, "stone": 441, "timber": 5},
        owns_shelter=False,
    )
    prompt_has_timber = first_pair_cognition_model.build_system_prompt(ctx_has_timber)
    assert "Fact: you hold no structural timber" not in prompt_has_timber
    assert "Fact: you hold 5 structural timber" in prompt_has_timber


def test_no_shelter_fact_line_absent_when_shelter_owned():
    """Agent owning no shelter gets 'Fact: you own no shelter of your own.'; agent owning shelter does not."""
    ctx_unhoused = first_pair_cognition_interface.AgentContext(
        agent_id="agent-1", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=100, position="cont_a_gen_0_0",
        observation={"self_body": {"hunger": 0, "warmth": 100}},
        memory=[], goals=[], unanswered_questions=[],
        world_public_objects={}, habitat_allowed_tiles=[],
        habitat_movement_allowed=True, previous_action=None,
        timestamp_utc="", inventory={}, owns_shelter=False,
    )
    prompt_unhoused = first_pair_cognition_model.build_system_prompt(ctx_unhoused)
    assert "Fact: you own no shelter of your own." in prompt_unhoused

    ctx_housed = first_pair_cognition_interface.AgentContext(
        agent_id="agent-1", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=100, position="cont_a_gen_0_0",
        observation={"self_body": {"hunger": 0, "warmth": 100}},
        memory=[], goals=[], unanswered_questions=[],
        world_public_objects={}, habitat_allowed_tiles=[],
        habitat_movement_allowed=True, previous_action=None,
        timestamp_utc="", inventory={}, owns_shelter=True,
    )
    prompt_housed = first_pair_cognition_model.build_system_prompt(ctx_housed)
    assert "Fact: you own no shelter of your own." not in prompt_housed


def test_belonging_counts_stated_as_facts():
    """Agent holding 441 stone and 2 wood sees the exact factual summary line."""
    ctx = first_pair_cognition_interface.AgentContext(
        agent_id="agent-1", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=100, position="cont_a_gen_0_0",
        observation={"self_body": {"hunger": 0, "warmth": 100}},
        memory=[], goals=[], unanswered_questions=[],
        world_public_objects={}, habitat_allowed_tiles=[],
        habitat_movement_allowed=True, previous_action=None,
        timestamp_utc="", inventory={"stone": 441, "wood": 2},
        owns_shelter=False,
    )
    prompt = first_pair_cognition_model.build_system_prompt(ctx)
    assert "Fact: you hold 441 stone and 2 wood in your belongings." in prompt


def test_settlement_facts_contain_no_directives():
    """All settlement-awareness fact lines must be strictly factual with no banned directive phrases."""
    ctx = first_pair_cognition_interface.AgentContext(
        agent_id="agent-1", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=100, position="cont_a_gen_0_0",
        observation={"self_body": {"hunger": 0, "warmth": 100}},
        memory=[], goals=[], unanswered_questions=[],
        world_public_objects={}, habitat_allowed_tiles=[],
        habitat_movement_allowed=True, previous_action=None,
        timestamp_utc="", inventory={"stone": 441, "wood": 2, "timber": 0},
        owns_shelter=False,
    )
    prompt = first_pair_cognition_model.build_system_prompt(ctx)

    banned_phrases = [
        "build a",
        "go to",
        "you should",
        "move to",
        "try building",
        "head to",
        "i want you to",
        "your task is",
    ]
    lines = [line.lower() for line in prompt.splitlines() if "fact:" in line.lower()]
    for line in lines:
        for phrase in banned_phrases:
            assert phrase not in line, f"Settlement fact line '{line}' contains banned directive phrase '{phrase}'"


def test_agent_context_exposes_shelter_ownership(tmp_path: Path):
    """FirstPairRuntime._build_context sets owns_shelter=True when agent owns a shelter object."""
    runtime, agent_id = _make_runtime_with_goals(tmp_path, [])

    # Case A: no shelter owned
    runtime._world_state.public_objects = {}
    ctx_no = runtime._build_context("east_adam", 100)
    assert hasattr(ctx_no, "owns_shelter"), "AgentContext must expose owns_shelter"
    assert ctx_no.owns_shelter is False

    # Case B: shelter owned by this agent
    runtime._world_state.public_objects = {
        "shelter-01": {
            "object_id": "shelter-01",
            "object_type": "shelter",
            "creator_agent_id": agent_id,
            "tile_id": "cont_a_gen_0_0",
        }
    }
    ctx_yes = runtime._build_context("east_adam", 101)
    assert ctx_yes.owns_shelter is True

    # Case C: shelter owned by someone else
    runtime._world_state.public_objects = {
        "shelter-other": {
            "object_id": "shelter-other",
            "object_type": "shelter",
            "creator_agent_id": "other-agent-id",
            "tile_id": "cont_a_gen_0_0",
        }
    }
    ctx_other = runtime._build_context("east_adam", 102)
    assert ctx_other.owns_shelter is False

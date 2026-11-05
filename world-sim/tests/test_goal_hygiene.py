"""Phase 10JR goal-hygiene tests, updated to the Phase 10NX contract.

10JR verified that FirstPairRuntime._build_context() filters goals by status
in ("active", "in_progress") and caps exposed active goals to
MAX_ACTIVE_GOALS_EXPOSED (8). 10NX changed the cap semantics on purpose:
the window is now one goal per intent SIGNATURE (newest of each), so eight
restatements of one intent no longer fill all eight slots. These tests keep
the 10JR intent (status filtering, 8-slot cap, in_progress recognition)
with genuinely distinct goal descriptions, and add the 10NX restatement
collapse case that the old verbatim-slice tests could not express.
"""

from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    GoalRecord,
    save_goals,
)
from backend.world.first_pair_runtime import (
    FirstPairRuntime,
    MAX_ACTIVE_GOALS_EXPOSED,
)

# Distinct intents: different content tokens survive _goal_signature's
# stopword/stem filter, so each of these is its own signature.
DISTINCT_INTENTS = [
    "Gather stone from the ridge",
    "Gather wood near the creek",
    "Survey the northern hills",
    "Build a stone cache",
    "Milk the goat at dawn",
    "Explore the eastern valley",
    "Craft a stone axe",
    "Cook wild berries over the fire",
    "Map the river bend",
    "Sharpen flint tools",
    "Repair the hut roof",
    "Stockpile clay for pottery",
]


def _runtime_with_goals(tmp_path: Path, goals: list[GoalRecord]) -> tuple[FirstPairRuntime, str]:
    store = FirstPairPersistenceStore(tmp_path / "store")
    runtime = FirstPairRuntime(heartbeat_limit=1, store=store)
    runtime._load_or_initialize()
    adam_id = runtime._world_state.tile_occupancy.get("east_adam")
    agent_id = runtime._adam_ref  # "east_adam"
    view = runtime._agent_view(agent_id)
    real_agent_id = view["agent_id"]

    for g in goals:
        g.agent_id = real_agent_id

    save_goals(store, goals)
    runtime._goals = goals
    return runtime, real_agent_id


def test_build_context_filters_inactive_goals(tmp_path: Path):
    goals = [
        GoalRecord("g-act-1", "", DISTINCT_INTENTS[0], "active", 1),
        GoalRecord("g-inp-1", "", DISTINCT_INTENTS[1], "in_progress", 2),
        GoalRecord("g-act-2", "", DISTINCT_INTENTS[2], "active", 3),
        GoalRecord("g-inp-2", "", DISTINCT_INTENTS[3], "in_progress", 4),
        GoalRecord("g-comp-1", "", "Completed goal one", "completed", 5),
        GoalRecord("g-comp-2", "", "Completed goal two", "completed", 6),
        GoalRecord("g-comp-3", "", "Completed goal three", "completed", 7),
        GoalRecord("g-ret-1", "", "Retired goal one", "retired", 8),
        GoalRecord("g-ret-2", "", "Retired goal two", "retired", 9),
        GoalRecord("g-ab-1", "", "Abandoned goal one", "abandoned", 10),
    ]
    runtime, agent_id = _runtime_with_goals(tmp_path, goals)
    ctx = runtime._build_context("east_adam", 11)

    exposed_ids = [g["goal_id"] for g in ctx.goals]
    assert len(exposed_ids) == 4
    assert set(exposed_ids) == {"g-act-1", "g-inp-1", "g-act-2", "g-inp-2"}
    for g in ctx.goals:
        assert g["status"] in ("active", "in_progress")


def test_build_context_preserves_most_recent_active_goals(tmp_path: Path):
    assert MAX_ACTIVE_GOALS_EXPOSED == 8
    goals = [
        GoalRecord(f"g-{i:02d}", "", DISTINCT_INTENTS[i - 1], "in_progress", i)
        for i in range(1, 13)
    ]
    runtime, agent_id = _runtime_with_goals(tmp_path, goals)
    ctx = runtime._build_context("east_adam", 13)

    exposed_ids = [g["goal_id"] for g in ctx.goals]
    assert len(exposed_ids) == 8
    expected = [f"g-{i:02d}" for i in range(5, 13)]
    assert exposed_ids == expected


def test_active_goal_ids_recognizes_in_progress_status(tmp_path: Path):
    goals = [
        GoalRecord(f"g-inp-{i}", "", DISTINCT_INTENTS[i - 1], "in_progress", i)
        for i in range(1, 6)
    ]
    runtime, agent_id = _runtime_with_goals(tmp_path, goals)
    ctx = runtime._build_context("east_adam", 6)

    # All 5 in-progress goals must be exposed in ctx.goals
    exposed_ids = {g["goal_id"] for g in ctx.goals}
    assert exposed_ids == {f"g-inp-{i}" for i in range(1, 6)}


def test_build_context_collapses_restatements_to_newest_per_signature(tmp_path: Path):
    """Phase 10NX: same intent written differently fills ONE slot, not eight."""
    goals = [
        GoalRecord("g-old-1", "", "Continue exploring hill and grassland terrain", "in_progress", 1),
        GoalRecord("g-old-2", "", "Keep exploring hill terrain and grassland", "in_progress", 2),
        GoalRecord("g-new", "", "Continuing exploring hill terrain and grassland", "in_progress", 3),
        GoalRecord("g-other", "", "Gather wood near the creek", "active", 4),
    ]
    runtime, agent_id = _runtime_with_goals(tmp_path, goals)
    ctx = runtime._build_context("east_adam", 5)

    exposed_ids = {g["goal_id"] for g in ctx.goals}
    # The three restatements share one signature; only the newest survives.
    assert exposed_ids == {"g-new", "g-other"}

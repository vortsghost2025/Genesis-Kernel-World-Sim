"""Phase 10JR: Cognitive Goal Hygiene tests.

Verifies that FirstPairRuntime._build_context() filters goals by status
in ("active", "in_progress"), caps exposed active goals to MAX_ACTIVE_GOALS_EXPOSED (8),
and that active_goal_ids recognizes in_progress goals.
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
        GoalRecord("g-act-1", "", "Active goal 1", "active", 1),
        GoalRecord("g-inp-1", "", "In progress goal 1", "in_progress", 2),
        GoalRecord("g-act-2", "", "Active goal 2", "active", 3),
        GoalRecord("g-inp-2", "", "In progress goal 2", "in_progress", 4),
        GoalRecord("g-comp-1", "", "Completed goal 1", "completed", 5),
        GoalRecord("g-comp-2", "", "Completed goal 2", "completed", 6),
        GoalRecord("g-comp-3", "", "Completed goal 3", "completed", 7),
        GoalRecord("g-ret-1", "", "Retired goal 1", "retired", 8),
        GoalRecord("g-ret-2", "", "Retired goal 2", "retired", 9),
        GoalRecord("g-ab-1", "", "Abandoned goal 1", "abandoned", 10),
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
        GoalRecord(f"g-{i:02d}", "", f"Goal {i}", "in_progress", i)
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
        GoalRecord(f"g-inp-{i}", "", f"In progress {i}", "in_progress", i)
        for i in range(1, 6)
    ]
    runtime, agent_id = _runtime_with_goals(tmp_path, goals)
    ctx = runtime._build_context("east_adam", 6)

    # All 5 in-progress goals must be exposed in ctx.goals
    exposed_ids = {g["goal_id"] for g in ctx.goals}
    assert exposed_ids == {f"g-inp-{i}" for i in range(1, 6)}

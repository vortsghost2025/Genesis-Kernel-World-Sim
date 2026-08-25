"""Smallest safe First-Pair goal-read seam (read-only).

Builds the goal half of the goal→cognition path without running the full
actor loop. Reads one explicit agent's ACTIVE goals only, via the
authoritative ``FirstPairPersistenceStore``, deterministically ordered, and
fail-closed on any malformed/unsafe record.

Guarantees:
- no writes (never constructs or persists state),
- no movement, no memory/relationship mutation,
- no provider/network call merely to read a goal (this module imports no
  provider/model/network code),
- goal selection is exact by ``agent_id``,
- ordering is deterministic by ``goal_id``.

The full actor loop (``first_pair_runtime.run``) already wires goals into
``AgentContext.goals`` and `build_system_prompt`; this seam is the minimal
read-only consumer the mission's Phase 2 requires.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    GoalRecord,
    load_goals,
)

_SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")
_VALID_STATUSES = frozenset({"active", "completed", "abandoned", "in_progress"})


def _is_safe_id(value: str) -> bool:
    return isinstance(value, str) and bool(_SAFE_ID_PATTERN.match(value))


def _goal_field_error(g: Any) -> str | None:
    """Return an error string if a GoalRecord is not structurally valid."""
    try:
        gid = getattr(g, "goal_id")
        aid = getattr(g, "agent_id")
        desc = getattr(g, "description")
        status = getattr(g, "status")
        hb = getattr(g, "created_heartbeat")
    except Exception:
        return "malformed_goal_record"
    if not _is_safe_id(gid):
        return "unsafe_goal_id"
    if not _is_safe_id(aid):
        return "unsafe_agent_id"
    if not isinstance(desc, str) or not desc.strip():
        return "malformed_goal_description"
    if not isinstance(status, str) or status not in _VALID_STATUSES:
        return "invalid_goal_status"
    if not isinstance(hb, int):
        return "invalid_goal_heartbeat"
    return None


def read_active_goals_for_agent(
    store: FirstPairPersistenceStore, agent_id: str
) -> dict[str, Any]:
    """Return one agent's active goals, fail-closed, read-only.

    Returns:
      {
        "ok": bool,
        "agent_id": str,
        "active_goal_count": int,
        "active_goals": [ {goal_id, agent_id, description, status,
                           created_heartbeat, related_question_id, metadata} ... ],
        "errors": [str, ...],
      }
    On any malformed/unsafe record the whole read fails closed (ok=False) and
    no goals are returned. On success nothing is written.
    """
    if not _is_safe_id(agent_id):
        return {
            "ok": False,
            "agent_id": agent_id,
            "active_goal_count": 0,
            "active_goals": [],
            "errors": ["invalid_agent_id"],
        }

    try:
        all_goals = load_goals(store)
    except Exception as exc:  # load_goals may raise on a structurally bad record
        return {
            "ok": False,
            "agent_id": agent_id,
            "active_goal_count": 0,
            "active_goals": [],
            "errors": [f"malformed_goals_store: {type(exc).__name__}"],
        }

    errors: list[str] = []
    selected: list[dict[str, Any]] = []

    for g in all_goals:
        err = _goal_field_error(g)
        if err is not None:
            return {
                "ok": False,
                "agent_id": agent_id,
                "active_goal_count": 0,
                "active_goals": [],
                "errors": [err],
            }
        if g.agent_id != agent_id:
            continue  # other agent's goals are invisible to this read
        if g.status != "active":
            continue  # only active goals drive cognition
        selected.append(asdict(g))

    # deterministic ordering
    selected.sort(key=lambda d: d["goal_id"])

    return {
        "ok": True,
        "agent_id": agent_id,
        "active_goal_count": len(selected),
        "active_goals": selected,
        "errors": [],
    }
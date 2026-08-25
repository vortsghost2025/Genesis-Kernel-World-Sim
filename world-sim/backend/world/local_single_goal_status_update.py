"""Smallest reusable First-Pair goal-status mutation seam (production writer).

Mutations an EXISTING GoalRecord's status in-place, under a grounded single-use
operator authorization. This is the reusable production seam corresponding to
the runtime's ``FirstPairRuntime._apply_cognition_output`` goal-update branch
(first_pair_runtime.py:607-625), but exposed standalone and fail-closed so a
single existing goal's status can be advanced WITHOUT running the full actor
loop (which would also write heartbeats/memories/world state).

Background / source-proven:
- The runtime already mutates an existing GoalRecord's ``status`` in place when
  a CognitionOutput.goal_updates entry is emitted (first_pair_runtime.py:616,
  ``existing.status = gu.get("status", existing.status)``).
- Valid GoalRecord statuses are the src ``_VALID_STATUSES``
  = {active, completed, abandoned, in_progress} (first_pair_cognition_model.py:79).
- This module only mutates ``status`` of an existing goal and persists via the
  canonical SaveGoals + provenance append. It cannot create a goal.

Authorization model (mirrors local_single_goal_write.py):
- Consumes a single-use, operator-grounded, exact-action + exact-target-agent
  + exact-goal authorization artifact. Fail-closed, non-replayable.

Authority boundary:
- Exactly one existing goal's status change. No goal creation, no movement,
  no memory/ledger/world-state/relationship mutation, no provider/network, no
  Gate-7, no broad creation authority. Operator must authorize (Sean); this
  module never self-authorizes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.world.first_pair_persistence import FirstPairPersistenceStore, load_goals, save_goals
from backend.world.world_event_sanitizer import sanitize_public_text

_AUTH_SCHEMA = "single_goal_status_update_authorization.1"
_AUTH_DOMAIN = "GENESIS_FIRST_PAIR_SINGLE_GOAL_STATUS_AUTH_V1"
_AUTH_ACTION = "single_goal_status_update"
_OPERATOR = "Sean"
_VALID_STATUSES = frozenset({"active", "completed", "abandoned", "in_progress"})
_CLAIM_BOUNDARY = (
    "exactly one existing goal status change under an operator-grounded "
    "single-use authorization; no goal creation, movement, memory/ledger/"
    "world-state/relationship mutation, model, provider, network, or gate activity"
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _auth_material(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain_separator": _AUTH_DOMAIN,
        "operator": _OPERATOR,
        "action": _AUTH_ACTION,
        "target_agent_id": fields["target_agent_id"],
        "goal_id": fields["goal_id"],
        "new_status": fields["new_status"],
        "max_writes": 1,
        "operator_proof_ref": fields["operator_proof_ref"],
        "authorization_timestamp": fields["authorization_timestamp"],
    }


def seal_goal_status_authorization(
    *,
    target_agent_id: str,
    goal_id: str,
    new_status: str,
    operator_proof_ref: str,
    authorization_timestamp: str,
) -> dict[str, Any]:
    """Operator-side producer of a single-use goal-status-update authorization."""
    fields = {
        "target_agent_id": target_agent_id,
        "goal_id": goal_id,
        "new_status": new_status,
        "operator_proof_ref": operator_proof_ref,
        "authorization_timestamp": authorization_timestamp,
    }
    material = _auth_material(fields)
    authorization_id = "auth-" + _hash(material)[:16]
    return {
        "schema_version": _AUTH_SCHEMA,
        "domain_separator": _AUTH_DOMAIN,
        "operator": _OPERATOR,
        "action": _AUTH_ACTION,
        "target_agent_id": target_agent_id,
        "goal_id": goal_id,
        "new_status": new_status,
        "max_writes": 1,
        "operator_proof_ref": operator_proof_ref,
        "authorization_timestamp": authorization_timestamp,
        "authorization_id": authorization_id,
    }


def _authorization_id(auth: dict[str, Any]) -> str:
    return "auth-" + _hash(_auth_material(auth))[:16]


def _validate_authorization(
    auth: Any,
    *,
    target_agent_id: str,
    goal_id: str,
    new_status: str,
) -> list[str]:
    if type(auth) is not dict:
        return ["missing_authorization"]
    if auth.get("schema_version") != _AUTH_SCHEMA:
        return ["invalid_authorization"]
    if auth.get("domain_separator") != _AUTH_DOMAIN:
        return ["invalid_authorization"]
    if auth.get("operator") != _OPERATOR:
        return ["invalid_authorization"]
    if auth.get("action") != _AUTH_ACTION:
        return ["invalid_authorization"]
    if auth.get("max_writes") != 1:
        return ["invalid_authorization"]
    if _authorization_id(auth) != auth.get("authorization_id"):
        return ["authorization_tampered"]
    if auth.get("target_agent_id") != target_agent_id:
        return ["authorization_agent_mismatch"]
    if auth.get("goal_id") != goal_id:
        return ["authorization_goal_mismatch"]
    if auth.get("new_status") != new_status:
        return ["authorization_status_mismatch"]
    return []


def _provenance_records(store: FirstPairPersistenceStore) -> list[dict[str, Any]]:
    from pathlib import Path

    from backend.world.first_pair_persistence import _PROVENANCE_FILE

    path: Path = store._path(_PROVENANCE_FILE)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _is_consumed(store: FirstPairPersistenceStore, authorization_id: str) -> bool:
    return any(
        r.get("action") == "single_goal_status_update_consumed"
        and r.get("detail", {}).get("authorization_id") == authorization_id
        for r in _provenance_records(store)
    )


def apply_goal_status_update(
    store: FirstPairPersistenceStore,
    *,
    goal_id: str,
    target_agent_id: str,
    new_status: str,
    authorization: dict[str, Any],
    description: str = "",
) -> dict[str, Any]:
    """Change exactly one existing GoalRecord's status, fail-closed.

    Never creates a goal; the goal must already exist and belong to the target
    agent. Writes nothing on any validation/replay/missing-goal failure. This is
    read-only against canonical unless called with an authorized isolated store.
    """
    errors: list[str] = []

    errors += _validate_authorization(
        authorization, target_agent_id=target_agent_id, goal_id=goal_id, new_status=new_status
    )

    if not isinstance(new_status, str) or new_status not in _VALID_STATUSES:
        errors.append("invalid_status")
    if not isinstance(goal_id, str) or not goal_id:
        errors.append("invalid_goal_id")
    if not isinstance(target_agent_id, str) or not target_agent_id:
        errors.append("invalid_agent_id")

    if not errors:
        auth_id = authorization["authorization_id"]
        if _is_consumed(store, auth_id):
            errors.append("authorization_already_consumed")

    goals = []
    if not errors:
        try:
            goals = load_goals(store)
        except Exception as exc:  # structurally bad store -> fail closed
            errors.append(f"malformed_goals_store: {type(exc).__name__}")

    target = None
    if not errors:
        target = next((g for g in goals if g.goal_id == goal_id), None)
        if target is None:
            errors.append("goal_not_found")
        elif target.agent_id != target_agent_id:
            errors.append("goal_agent_mismatch")

    if not errors and description:
        stripped = description.strip()
        if stripped != description or sanitize_public_text(stripped) != stripped:
            errors.append("invalid_description")

    if errors:
        return {
            "ok": False,
            "errors": sorted(set(errors)),
            "persisted": False,
            "goal_id": goal_id,
            "new_status": new_status,
            "target_agent_id": target_agent_id,
            "goals_mutated": 0,
            "movement_performed": False,
            "memory_written": False,
            "world_state_mutated": False,
            "relationship_changed": False,
            "gate7_activity_allowed": False,
            "claim_boundary": _CLAIM_BOUNDARY,
        }

    auth_id = authorization["authorization_id"]
    # Single-use commit point: burn the authorization FIRST (an atomic provenance
    # append) so any later failure can never permit a retry of the same token to
    # produce a second effective status transition, a duplicated GoalRecord, or
    # an inconsistent authorization reuse. If a later step fails the caller must
    # obtain a fresh authorization (fail-closed).
    store._append_provenance(
        "single_goal_status_update_consumed",
        {
            "authorization_id": auth_id,
            "target_agent_id": target_agent_id,
            "goal_id": goal_id,
        },
    )
    old_status = target.status
    target.status = new_status
    if description:
        target.description = description

    save_goals(store, goals)
    store._append_provenance(
        "single_goal_status_update_applied",
        {
            "goal_id": goal_id,
            "agent_id": target_agent_id,
            "previous_status": old_status,
            "new_status": new_status,
        },
    )
    return {
        "ok": True,
        "errors": [],
        "persisted": True,
        "goal_id": goal_id,
        "new_status": new_status,
        "previous_status": old_status,
        "target_agent_id": target_agent_id,
        "goals_mutated": 1,
        "movement_performed": False,
        "memory_written": False,
        "world_state_mutated": False,
        "relationship_changed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _CLAIM_BOUNDARY,
    }
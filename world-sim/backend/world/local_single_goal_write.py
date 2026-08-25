"""Bounded single-goal First-Pair write path — grounded single-use auth.

Enables EXACTLY ONE validated ``GoalRecord`` for EXACTLY ONE target First-Pair
agent, persisted to the canonical goals store under a consumed single-use
operator authorization, fail-closed on all other writes.

This is intentionally narrower than ``first_pair_runtime``'s actor loop (whose
default runtime policy sets ``movement_allowed=True`` and a broader 3-tile
topology inconsistent with the 10IJ canonical movement-gated habitat). It
cannot touch movement, memory, world-state, relationship, or any non-goal
record.

Authority boundary (source-cited):
- ``goals.json`` lives in `.runtime/first-pair/`, which ``FirstPairPersistenceStore``
  scopes as "an isolated repository-local runtime directory that does not touch
  world-sim/data" (``first_pair_persistence.py``).
- 10CP is the append-only writer for the *runtime-adapter audit ledger* in
  ``world-sim/data`` (``phase_10cp_runtime_adapter_inert_ledger_writer_spec.md``)
  and does NOT govern ``goals.json``.
- Canonical boundaries: ``goal`` = "update or preserve intent; does not prove
  the goal's target exists" — an intent record, not a world-state mutation.
- Existing precedent: ``first_pair_runtime._apply_cognition_output`` already
  writes GoalRecords to ``.runtime/first-pair/goals.json`` via
  ``FirstPairPersistenceStore`` directly (never through 10CP).

Authorization model:
- ``FIRST_PAIR_CREATION_AUTHORIZED`` is a project governance constant, not a
  code-enforced gate (it is not referenced anywhere in ``backend/world``).
- The runtime consumer does NOT accept a caller boolean. It consumes a single
  use operator authorization artifact (`operator_proof`-grounded), bound to the
  exact action + exact target agent + exact goal material, and enforces
  one-time consumption. ``seal_authorization`` is an operator-side producer
  helper (Sean); the runtime only *validates* and *consumes*.

No movement, memory, ledger, world-state, model, provider, network, or gate
activity.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    GoalRecord,
    _PROVENANCE_FILE,
    load_goals,
    save_goals,
)
from backend.world.world_event_sanitizer import sanitize_public_text

_AUTH_SCHEMA = "single_goal_authorization.1"
_AUTH_DOMAIN = "GENESIS_FIRST_PAIR_SINGLE_GOAL_AUTH_V1"
_AUTH_ACTION = "single_goal_create"
_OPERATOR = "Sean"
_MAX_DESCRIPTION = 512
_CLAIM_BOUNDARY = (
    "exactly one goal write under an operator-grounded single-use "
    "authorization; no movement, memory write, ledger write, world-state "
    "mutation, relationship change, model, provider, network, or gate activity"
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
        "pair_id": fields["pair_id"],
        "goal_description": fields["goal_description"],
        "goal_status": fields["goal_status"],
        "created_heartbeat": fields["created_heartbeat"],
        "max_writes": 1,
        "operator_proof_ref": fields["operator_proof_ref"],
        "authorization_timestamp": fields["authorization_timestamp"],
    }


def seal_authorization(
    *,
    target_agent_id: str,
    pair_id: str,
    goal_description: str,
    goal_status: str,
    created_heartbeat: int,
    operator_proof_ref: str,
    authorization_timestamp: str,
) -> dict[str, Any]:
    """Operator-side producer of a single-use goal authorization artifact.

    Returns a sealed dict. This is a producer helper for Sean at
    authorization time; the runtime write path only validates/consumes it.
    """
    fields = {
        "target_agent_id": target_agent_id,
        "pair_id": pair_id,
        "goal_description": goal_description,
        "goal_status": goal_status,
        "created_heartbeat": created_heartbeat,
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
        "pair_id": pair_id,
        "goal_description": goal_description,
        "goal_status": goal_status,
        "created_heartbeat": created_heartbeat,
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
    pair_id: str,
    goal_description: str,
    goal_status: str,
    created_heartbeat: int,
) -> list[str]:
    """Validate a supplied authorization against the exact requested action."""
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
    if auth.get("pair_id") != pair_id:
        return ["authorization_pair_mismatch"]
    if auth.get("goal_description") != goal_description:
        return ["authorization_goal_mismatch"]
    if auth.get("goal_status") != goal_status:
        return ["authorization_status_mismatch"]
    if auth.get("created_heartbeat") != created_heartbeat:
        return ["authorization_heartbeat_mismatch"]
    return []


def _provenance_records(store: FirstPairPersistenceStore) -> list[dict[str, Any]]:
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
        r.get("action") == "single_goal_authorization_consumed"
        and r.get("detail", {}).get("authorization_id") == authorization_id
        for r in _provenance_records(store)
    )


def write_single_goal(
    store: FirstPairPersistenceStore,
    *,
    birth_candidate: dict,
    target_agent_id: str,
    goal_description: str,
    authorization: dict[str, Any],
    pair_id: str = "genesis-first-pair",
    goal_status: str = "active",
    created_heartbeat: int = 0,
) -> dict[str, Any]:
    """Write exactly one validated GoalRecord under a grounded single-use auth.

    Fail-closed (nothing written on failure):
      - no/malformed/tampered authorization -> missing|invalid|tampered
      - authorization bound to a different agent/goal/pair -> *_mismatch
      - authorization already consumed -> authorization_already_consumed
      - invalid birth candidate / unknown agent / wrong pair
      - invalid description/status/heartbeat
      - duplicate goal already persisted
    """
    errors: list[str] = []

    errors += _validate_authorization(
        authorization,
        target_agent_id=target_agent_id,
        pair_id=pair_id,
        goal_description=goal_description,
        goal_status=goal_status,
        created_heartbeat=created_heartbeat,
    )

    cand_ok = (
        type(birth_candidate) is dict
        and birth_candidate.get("ok") is True
        and type(birth_candidate.get("adam_identity")) is dict
        and type(birth_candidate.get("eve_identity")) is dict
        and type(birth_candidate.get("pair_id")) is str
    )
    if not cand_ok:
        errors.append("invalid_birth_candidate")
    elif pair_id != birth_candidate["pair_id"]:
        errors.append("pair_mismatch")
    elif target_agent_id not in (
        birth_candidate["adam_identity"].get("agent_id"),
        birth_candidate["eve_identity"].get("agent_id"),
    ):
        errors.append("unknown_agent")

    if not isinstance(goal_description, str):
        errors.append("invalid_description")
    else:
        stripped = goal_description.strip()
        if not stripped:
            errors.append("invalid_description")
        elif len(stripped) > 512:
            errors.append("invalid_description")
        elif sanitize_public_text(stripped) != stripped:
            errors.append("invalid_description")
        elif "/" in stripped or "\\" in stripped:
            errors.append("invalid_description")

    if not isinstance(goal_status, str) or not 1 <= len(goal_status) <= 12:
        errors.append("invalid_status")
    if not isinstance(created_heartbeat, int) or not 0 <= created_heartbeat <= (1 << 63) - 1:
        errors.append("invalid_heartbeat")

    if not errors:
        auth_id = authorization["authorization_id"]
        if _is_consumed(store, auth_id):
            errors.append("authorization_already_consumed")

    if not errors:
        gid = "goal-" + _hash(
            {
                "domain": "GENESIS_FIRST_PAIR_GOAL_V1",
                "pair_id": pair_id,
                "agent_id": target_agent_id,
                "description": stripped,
                "created_heartbeat": created_heartbeat,
            }
        )[:16]
        if any(g.goal_id == gid for g in load_goals(store)):
            errors.append("duplicate_goal")

    if errors:
        return {
            "ok": False,
            "errors": sorted(set(errors)),
            "persisted": False,
            "goals_written": 0,
            "target_agent_id": target_agent_id,
            "runtime_entity_created": False,
            "memory_written": False,
            "world_state_mutated": False,
            "relationship_changed": False,
            "movement_performed": False,
            "gate7_activity_allowed": False,
            "claim_boundary": _CLAIM_BOUNDARY,
        }

    auth_id = authorization["authorization_id"]
    record = GoalRecord(
        goal_id=gid,
        agent_id=target_agent_id,
        description=stripped,
        status=goal_status,
        created_heartbeat=created_heartbeat,
    )
    current = load_goals(store)
    save_goals(store, current + [record])
    store._append_provenance("single_goal_created", {"goal_id": gid, "agent_id": target_agent_id, "pair_id": pair_id})
    store._append_provenance(
        "single_goal_authorization_consumed",
        {
            "authorization_id": auth_id,
            "target_agent_id": target_agent_id,
            "pair_id": pair_id,
            "goal_id": gid,
        },
    )
    return {
        "ok": True,
        "errors": [],
        "persisted": True,
        "goals_written": len(current) + 1,
        "target_agent_id": target_agent_id,
        "pair_id": pair_id,
        "goal_id": gid,
        "authorization_id": auth_id,
        "goal_envelope": record.to_envelope(),
        "runtime_entity_created": False,
        "memory_written": False,
        "world_state_mutated": False,
        "relationship_changed": False,
        "movement_performed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _CLAIM_BOUNDARY,
    }
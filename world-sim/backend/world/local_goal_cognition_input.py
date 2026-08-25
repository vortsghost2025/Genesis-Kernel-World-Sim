"""Smallest goal-aware cognition input (Phase 3).

Builds a minimal, strictly-legitimate ``AgentContext`` that lets an agent's
persisted ACTIVE goal drive bounded cognition, WITHOUT smuggling in
unavailable memory, history, or relationship content.

Included (all source-supported):
- agent identity (agent_id, canonical_name, canonical_ref) from the canonical
  birth candidate,
- the other agent's identity (for the pair prompt),
- the agent's ACTIVE goals (via the read-only goal-read seam),
- the canonical starting observation for the agent's starting tile,
- canonical habitat (allowed tiles, movement_allowed=False) from
  ``canonical_first_pair_habitat_contract``,
- a bounded heartbeat/tick context.

Left empty (NOT fabricated): private memory, relationship events, human
answers, public objects/messages, capabilities.

The returned context feeds the existing ``build_system_prompt`` and
``CognitionBackend.observe_and_orient`` unchanged. It is read-only: it never
persists anything and never calls any provider/network.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.world.canonical_first_pair_habitat_contract import (
    _MOVEMENT_ALLOWED,
    _STARTING_TILE_IDS,
    _OBSERVATION_BOUNDARIES,
    _ALLOWED_TILE_IDS,
)
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_persistence import FirstPairPersistenceStore
from backend.world.local_first_pair_goal_read import read_active_goals_for_agent

IDENTITY_FIELD = "canonical_agent_ref"


def _require_canonical(cand: dict[str, Any]) -> None:
    if not (isinstance(cand, dict) and cand.get("ok") is True):
        raise ValueError("invalid canonical birth candidate")
    if not isinstance(cand.get("adam_identity"), dict) or not isinstance(
        cand.get("eve_identity"), dict
    ):
        raise ValueError("birth candidate missing adam_identity/eve_identity")


def build_goal_cognition_context(
    store: FirstPairPersistenceStore,
    *,
    birth_candidate: dict[str, Any],
    target_agent_ref: str,
    heartbeat_number: int,
) -> AgentContext:
    """Build a minimal goal-aware AgentContext for east_adam / east_eve.

    Raises ValueError on invalid birth candidate, unknown agent ref, or a
    goal-read failure. The returned context is read-only.
    """
    _require_canonical(birth_candidate)
    adam = birth_candidate["adam_identity"]
    eve = birth_candidate["eve_identity"]
    if target_agent_ref not in ("east_adam", "east_eve"):
        raise ValueError(f"unknown canonical_agent_ref: {target_agent_ref}")

    mine, other = (adam, eve) if target_agent_ref == "east_adam" else (eve, adam)

    # Canonical agent_id from the birth candidate identity record.
    mine_agent_id = mine.get("agent_id")
    other_agent_id = other.get("agent_id")
    if not isinstance(mine_agent_id, str) or not mine_agent_id:
        raise ValueError("birth candidate missing agent_id")

    # Active goals only, exact agent, read-only (zero writes).
    goals_result = read_active_goals_for_agent(store, mine_agent_id)
    if not goals_result["ok"]:
        raise ValueError(f"goal read failed: {'; '.join(goals_result['errors'])}")
    active_goals = goals_result["active_goals"]

    position = _STARTING_TILE_IDS[target_agent_ref]
    obs_boundary = list(_OBSERVATION_BOUNDARIES[target_agent_ref])
    observation = {
        "tile_id": position,
        "visible_tiles": obs_boundary,
        "objects_here": [],
    }

    name = "Adam" if target_agent_ref == "east_adam" else "Eve"
    other_name = "Eve" if target_agent_ref == "east_adam" else "Adam"

    return AgentContext(
        agent_id=mine_agent_id,
        canonical_name=name,
        canonical_ref=target_agent_ref,
        heartbeat_number=heartbeat_number,
        position=position,
        observation=observation,
        memory=[],
        goals=active_goals,
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=list(_ALLOWED_TILE_IDS),
        habitat_movement_allowed=bool(_MOVEMENT_ALLOWED),  # canonical False
        previous_action=None,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        other_agent_id=other_agent_id,
        other_agent_name=other_name,
        other_agent_ref="east_eve" if target_agent_ref == "east_adam" else "east_adam",
        # dynamic / human contexts intentionally empty at this stage
        answered_questions=[],
        available_moves=[],
        current_runtime_capabilities=[],
        current_tile_occupants=[],
        visible_public_messages=[],
        relevant_human_answers=[],
        selected_private_memories=[],
        derived_memory_summaries=[],
        public_relationship_events=[],
        memory_selection_manifest={},
    )
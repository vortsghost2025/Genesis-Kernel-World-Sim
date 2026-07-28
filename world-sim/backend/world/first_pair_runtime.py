"""Phase 10FM — First Pair Runtime Orchestrator.

Coordinates bounded heartbeat cycles for Adam and Eve. Mutations flow through
`FirstPairPersistenceStore`; the store and all its children are injected from
the outside — no module-global paths.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.world.first_pair_cognition_interface import (
    AgentContext,
    CognitionBackend,
    CognitiveCycle,
)
from backend.world.first_pair_cognition_model import (
    ModelCognitionBackend,
)
from backend.world.first_pair_cognition_stub import (
    AlternatingStubBackend,
    DeterministicStubBackend,
)
from backend.world.first_pair_persistence import (
    CapabilityGrantRecord,
    FirstPairPersistenceStore,
    GoalRecord,
    HeartbeatRecord,
    IdentityRecord,
    PublicObjectRecord,
    QuestionRecord,
    RuntimePolicyRecord,
    WorldStateRecord,
    append_heartbeat,
    append_memory_selection_manifest,
    create_default_runtime_policy,
    derive_relationship_event_ids,
    get_adjacent_tiles,
    get_persistence_root,
    initialize_first_pair_state,
    list_answered_questions_for_agent,
    list_unanswered_questions,
    load_capability_grant,
    load_goals,
    load_heartbeat_history,
    load_memory,
    load_memory_selection_manifests,
    load_questions,
    load_relationship_events,
    load_runtime_policy,
    load_summaries,
    maybe_record_relationship_event,
    save_goals,
    save_memory,
    save_questions,
    save_runtime_policy,
    save_world_state,
    select_private_memories,
    validate_persistence_integrity,
)
from backend.world.world_event_sanitizer import sanitize_public_text

_DEFAULT_HEARTBEAT_LIMIT = 10
_SAFE_OBJECT_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)
_ALLOWED_MUTABLE_FIELDS = frozenset({
    "public_description", "object_type", "tile_id",
})


def _is_safe_object_id(value: str) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        return False
    return all(c in _SAFE_OBJECT_ID_CHARS for c in value)


class FirstPairRuntime:
    """Bounded, reproducible First Pair runtime.

    State is bound to a `FirstPairPersistenceStore` supplied at construction
    time.  Two separate memory lists (`east_adam`, `east_eve`) live inside a
    single shared envelope and are written atomically each tick, so neither
    agent's entries are overwritten by the other.
    """

    def __init__(
        self,
        persistence_root: Path | None = None,
        heartbeat_limit: int = _DEFAULT_HEARTBEAT_LIMIT,
        backend: str = "stub",
        store: FirstPairPersistenceStore | None = None,
    ) -> None:
        if store is None:
            store = FirstPairPersistenceStore(persistence_root)
        self._store = store
        self._heartbeat_limit = heartbeat_limit
        self._backend = backend

        self._identity_record: IdentityRecord | None = None
        self._habitat: dict | None = None
        self._world_state: WorldStateRecord | None = None
        self._goals: list[GoalRecord] = []
        self._questions: list[QuestionRecord] = []

        self._adam_memory: list[dict] = []
        self._eve_memory: list[dict] = []
        self._runtime_policy: RuntimePolicyRecord | None = None
        self._capability_grant: CapabilityGrantRecord | None = None

    # ------------------------------------------------------------------
    # Identity helpers
    # ------------------------------------------------------------------

    def _agent_view(self, agent_ref: str) -> dict:
        assert self._identity_record is not None
        candidate = self._identity_record.birth_candidate
        if agent_ref == "east_adam":
            raw = candidate["adam_identity"]
            return {
                "agent_id": self._identity_record.adam_agent_id,
                "canonical_name": raw["canonical_name"],
                "canonical_agent_ref": agent_ref,
                "other_agent_id": self._identity_record.eve_agent_id,
                "other_agent_name": candidate["eve_identity"]["canonical_name"],
                "other_agent_ref": "east_eve",
            }
        raw = candidate["eve_identity"]
        return {
            "agent_id": self._identity_record.eve_agent_id,
            "canonical_name": raw["canonical_name"],
            "canonical_agent_ref": agent_ref,
            "other_agent_id": self._identity_record.adam_agent_id,
            "other_agent_name": candidate["adam_identity"]["canonical_name"],
            "other_agent_ref": "east_adam",
        }

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _load_or_initialize(self) -> bool:
        identity, world_state = initialize_first_pair_state(self._store)

        self._identity_record = identity
        self._world_state = world_state
        self._habitat = identity.habitat_boundary["habitat"]

        memory = load_memory(self._store)
        self._adam_memory = list(memory.get("east_adam", []))
        self._eve_memory = list(memory.get("east_eve", []))

        self._goals = load_goals(self._store)
        self._questions = load_questions(self._store)

        self._runtime_policy = load_runtime_policy(self._store)
        self._capability_grant = load_capability_grant(self._store)

        is_fresh = (
            world_state.tick == 0
            and not self._adam_memory
            and not self._eve_memory
            and not self._goals
        )
        return is_fresh

    # ------------------------------------------------------------------
    # Cognition backends
    # ------------------------------------------------------------------

    def _get_cognition_backend(self, agent_ref: str) -> CognitionBackend:
        if self._backend == "model":
            return ModelCognitionBackend(agent_ref)
        if self._backend == "deterministic_stub":
            return DeterministicStubBackend(agent_ref)
        return AlternatingStubBackend(agent_ref)

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    def _build_context(
        self, agent_ref: str, heartbeat_number: int
    ) -> AgentContext:
        view = self._agent_view(agent_ref)
        memory_list = (
            self._adam_memory if agent_ref == "east_adam" else self._eve_memory
        )

        agent_goals = [g for g in self._goals if g.agent_id == view["agent_id"]]
        agent_pending_questions = [
            q
            for q in self._questions
            if q.asking_agent_id == view["agent_id"] and q.status == "pending"
        ]
        agent_answered_questions = [
            q.__dict__
            for q in self._questions
            if q.asking_agent_id == view["agent_id"] and q.status == "answered"
        ]

        position = (
            self._world_state.tile_occupancy.get(
                agent_ref,
                self._habitat["starting_tile_ids"][agent_ref],
            )
        )

        # Objects whose tile_id matches current position
        current_tile_objects = [
            obj
            for obj in self._world_state.public_objects.values()
            if isinstance(obj, dict) and obj.get("tile_id") == position
        ]

        # Visible tiles: use runtime policy topology if grant active, else habitat
        if self._capability_grant and self._runtime_policy:
            available_moves = get_adjacent_tiles(self._runtime_policy, position)
            visible_tiles = [position] + available_moves
            policy_allowed = self._runtime_policy.topology.get("allowed_tile_ids", [])
            movement_allowed_flag = True
        else:
            available_moves = []
            visible_tiles = self._habitat.get("observation_boundaries", {}).get(
                agent_ref, [position]
            )
            policy_allowed = self._habitat.get("allowed_tile_ids", [])
            movement_allowed_flag = self._habitat.get("movement_allowed", False)

        # Visible public messages (addressed to this agent or public "all")
        visible_msgs = [
            m for m in self._world_state.public_messages
            if isinstance(m, dict) and (
                m.get("recipient") in (agent_ref, "all", "public")
                or m.get("recipient") == view["canonical_agent_ref"]
            )
        ]

        # Co-location: other agents at same tile
        other_agents_here = []
        if self._world_state.tile_occupancy:
            for ref, tid in self._world_state.tile_occupancy.items():
                if ref != agent_ref and tid == position:
                    other_view = self._agent_view(ref) if self._identity_record else {}
                    other_agents_here.append({
                        "agent_ref": ref,
                        "agent_name": other_view.get("canonical_name", ref),
                    })

        # Current runtime capabilities
        caps = []
        if self._capability_grant:
            caps.append(self._capability_grant.capability_id)

        # Relevant human answers (already in agent_answered_questions)
        relevant_answers = agent_answered_questions

        observation = {
            "tile_id": position,
            "visible_tiles": visible_tiles,
            "objects_here": current_tile_objects,
        }

        # --- Bounded memory selection ---
        # Compute recent cutoff (last 4 heartbeats)
        history = load_heartbeat_history(self._store)
        recent_cutoff = max(0, heartbeat_number - 4) if history else 0

        # Get visible object IDs and message IDs
        visible_object_ids = {o.get("object_id", "") for o in current_tile_objects}
        visible_message_ids = {m.get("message_id", "") for m in visible_msgs}

        # Get relationship event memory IDs for relevance boosting
        rel_events = load_relationship_events(self._store)
        rel_memory_ids = derive_relationship_event_ids(rel_events)

        # Select bounded memories
        selected_mems, sel_manifest = select_private_memories(
            memories=memory_list,
            agent_id=view["agent_id"],
            goals=[g.__dict__ for g in agent_goals],
            position=position,
            visible_tiles=set(visible_tiles),
            visible_object_ids=visible_object_ids,
            visible_message_ids=visible_message_ids,
            relationship_event_memory_ids=rel_memory_ids,
            recent_cutoff_hb=recent_cutoff,
        )

        # Attach agent_id to manifest for per-agent tracking
        sel_manifest["requesting_agent_id"] = view["agent_id"]
        sel_manifest["heartbeat"] = heartbeat_number

        # Persist the manifest (append-only log)
        if self._store:
            append_memory_selection_manifest(self._store, sel_manifest)

        # Load summaries and relationship events for context
        summaries = load_summaries(self._store)
        agent_summaries = [
            asdict(s) for s in summaries
            if s.owner_agent_id == view["agent_id"]
        ]
        rel_events_export = [
            asdict(e) for e in rel_events
            if e.actor_agent_id == view["agent_id"] or e.other_agent_id == view["agent_id"]
        ]

        return AgentContext(
            agent_id=view["agent_id"],
            canonical_name=view["canonical_name"],
            canonical_ref=agent_ref,
            heartbeat_number=heartbeat_number,
            position=position,
            observation=observation,
            memory=list(memory_list),
            goals=[g.__dict__ for g in agent_goals],
            unanswered_questions=[q.__dict__ for q in agent_pending_questions],
            world_public_objects=self._world_state.public_objects,
            habitat_allowed_tiles=policy_allowed,
            habitat_movement_allowed=movement_allowed_flag,
            previous_action=None,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            # Dynamic pair identity
            other_agent_id=view["other_agent_id"],
            other_agent_name=view["other_agent_name"],
            other_agent_ref=view["other_agent_ref"],
            # Answered questions for this agent
            answered_questions=agent_answered_questions,
            # Dynamic context for movement grant era
            available_moves=available_moves,
            current_runtime_capabilities=caps,
            current_tile_occupants=other_agents_here,
            visible_public_messages=visible_msgs,
            relevant_human_answers=relevant_answers,
            # Bounded memory selection fields
            selected_private_memories=selected_mems,
            derived_memory_summaries=agent_summaries,
            public_relationship_events=rel_events_export,
            memory_selection_manifest=sel_manifest,
        )

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def _execute_action(self, agent_ref: str, action: dict | None, heartbeat_number: int) -> dict:
        if action is None:
            return {"status": "no_action", "detail": "No action chosen"}
        action_type = action.get("action_type")
        if action_type == "move":
            return self._execute_move(agent_ref, action)
        if action_type == "create_public_object":
            return self._execute_create_public_object(agent_ref, action, heartbeat_number)
        if action_type == "inspect_public_object":
            return self._execute_inspect_public_object(action)
        if action_type == "modify_owned_public_object":
            return self._execute_modify_owned_public_object(agent_ref, action, heartbeat_number)
        if action_type == "leave_public_message":
            return self._execute_leave_public_message(agent_ref, action, heartbeat_number)
        if action_type == "ask_human":
            return self._execute_ask_human(agent_ref, action, heartbeat_number)
        if action_type == "request_capability":
            return self._execute_request_capability(agent_ref, action, heartbeat_number)
        return {"status": "unknown_action", "action": action}

    def _execute_move(self, agent_ref: str, action: dict) -> dict:
        if not self._habitat or not self._world_state:
            return {"status": "error", "reason": "Runtime not initialized"}
        if not self._capability_grant or not self._runtime_policy:
            return {"status": "blocked", "reason": "No active movement grant. Request capability from human operator."}
        if self._capability_grant.status != "granted":
            return {"status": "blocked", "reason": f"Grant status is {self._capability_grant.status}"}

        target = action.get("target_tile")
        allowed = self._runtime_policy.topology.get("allowed_tile_ids", [])
        if target not in allowed:
            return {"status": "blocked", "reason": f"Tile {target} not in runtime policy allowed tiles"}

        current_pos = self._world_state.tile_occupancy.get(agent_ref)
        if current_pos is None:
            current_pos = self._habitat["starting_tile_ids"].get(agent_ref)

        # Adjacent-only movement
        adjacent = get_adjacent_tiles(self._runtime_policy, current_pos)
        if target not in adjacent:
            return {"status": "blocked", "reason": f"Cannot move from {current_pos} to {target}: not adjacent (adjacent: {adjacent})"}

        # Co-location allowed only in shared-center
        other_ref = "east_eve" if agent_ref == "east_adam" else "east_adam"
        other_pos = self._world_state.tile_occupancy.get(other_ref)
        if target == other_pos and target != "public-shared-center":
            return {"status": "blocked", "reason": f"Tile {target} already occupied by the other agent (co-location only allowed in public-shared-center)"}

        self._world_state.tile_occupancy[agent_ref] = target
        return {"status": "success", "from": current_pos, "to": target}

    def _execute_create_public_object(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        object_id = action.get("object_id")
        object_type = action.get("object_type", "generic")
        raw_description = action.get("description", "")
        tile_id = action.get("tile_id") or self._habitat["starting_tile_ids"][agent_ref]

        if not _is_safe_object_id(str(object_id or "")):
            return {"status": "rejected", "reason": "Invalid object_id"}
        if object_id in self._world_state.public_objects:
            return {"status": "rejected", "reason": f"Duplicate object_id: {object_id}"}
        # Must place on current tile
        current_pos = self._world_state.tile_occupancy.get(
            agent_ref, self._habitat["starting_tile_ids"][agent_ref]
        )
        if tile_id != current_pos:
            return {"status": "rejected", "reason": f"Cannot place object on tile {tile_id}: you are at {current_pos}"}
        allowed = self._habitat.get("allowed_tile_ids", [])
        if self._runtime_policy:
            allowed = self._runtime_policy.topology.get("allowed_tile_ids", allowed)
        if tile_id not in allowed:
            return {"status": "rejected", "reason": f"Tile {tile_id} not in allowed tiles"}

        sanitized = sanitize_public_text(raw_description)
        if not sanitized.strip():
            return {"status": "rejected", "reason": "Empty public_description after sanitization"}

        record = PublicObjectRecord(
            object_id=object_id,
            creator_agent_id=view["agent_id"],
            tile_id=tile_id,
            object_type=object_type,
            public_description=sanitized,
            created_heartbeat=heartbeat_number,
        )
        self._world_state.public_objects[object_id] = record.to_envelope()
        return {
            "status": "success",
            "object_id": object_id,
            "tile_id": tile_id,
            "object_type": object_type,
            "sanitized_description": sanitized[:200],
        }

    def _execute_inspect_public_object(self, action: dict) -> dict:
        obj_id = action.get("target_object_id")
        if not obj_id or not isinstance(obj_id, str):
            return {"status": "rejected", "reason": "Missing or invalid target_object_id"}
        obj = self._world_state.public_objects.get(obj_id)
        if obj is None or not isinstance(obj, dict):
            return {"status": "rejected", "reason": f"Object not found: {obj_id}"}
        return {"status": "success", "object": obj}

    def _execute_modify_owned_public_object(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        obj_id = action.get("target_object_id")
        if not obj_id or not isinstance(obj_id, str):
            return {"status": "rejected", "reason": "Missing or invalid target_object_id"}
        obj = self._world_state.public_objects.get(obj_id)
        if obj is None or not isinstance(obj, dict):
            return {"status": "rejected", "reason": f"Object not found: {obj_id}"}
        if obj.get("creator_agent_id") != view["agent_id"]:
            return {"status": "rejected", "reason": "Not the owner of this object"}
        modifications = action.get("modifications")
        if not isinstance(modifications, dict):
            return {"status": "rejected", "reason": "Missing or invalid modifications"}
        applied: dict[str, Any] = {}
        for key, value in modifications.items():
            if key not in _ALLOWED_MUTABLE_FIELDS:
                return {"status": "rejected", "reason": f"Cannot modify field: {key}"}
            if isinstance(value, str):
                sanitized = sanitize_public_text(value)
                if not sanitized.strip():
                    return {"status": "rejected", "reason": f"Empty text after sanitization for {key}"}
                obj[key] = sanitized
                applied[key] = sanitized
            else:
                obj[key] = value
                applied[key] = value
        obj["modified_heartbeat"] = heartbeat_number
        applied["modified_heartbeat"] = heartbeat_number
        return {
            "status": "success",
            "object_id": obj_id,
            "updates": list(modifications.keys()),
            "applied_values": applied,
        }

    def _execute_leave_public_message(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        message = action.get("message", "")
        if not isinstance(message, str) or not message.strip():
            return {"status": "rejected", "reason": "Missing or empty message"}
        sanitized = sanitize_public_text(message)
        if not sanitized.strip():
            return {"status": "rejected", "reason": "Empty after sanitization"}
        recipient = action.get("recipient", "all")
        from hashlib import sha256
        message_id = f"msg-{sha256(f'{agent_ref}{heartbeat_number}{sanitized[:50]}'.encode()).hexdigest()[:12]}"
        msg_record = {
            "message_id": message_id,
            "sender_agent_id": view["agent_id"],
            "message": sanitized[:2000],
            "recipient": recipient,
            "heartbeat": heartbeat_number,
            "sent_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        self._world_state.public_messages.append(msg_record)
        return {
            "status": "success",
            "message_id": message_id,
            "message_preview": sanitized[:200],
        }

    def _execute_ask_human(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        question_id = action.get("question_id")
        question = action.get("question", "")
        reason = action.get("reason_for_asking", "")
        if not question_id or not question or not reason:
            return {"status": "rejected", "reason": "Missing question_id, question, or reason_for_asking"}
        if not _is_safe_object_id(str(question_id)):
            return {"status": "rejected", "reason": "Invalid question_id"}
        # Deduplicate
        for existing in self._questions:
            if existing.question_id == question_id:
                return {"status": "rejected", "reason": f"Duplicate question_id: {question_id}"}
        agent_id = (
            self._identity_record.adam_agent_id
            if agent_ref == "east_adam"
            else self._identity_record.eve_agent_id
        )
        urgency = action.get("urgency", "low")
        if urgency not in ("low", "medium", "high"):
            return {"status": "rejected", "reason": "Invalid urgency value"}
        self._questions.append(QuestionRecord(
            question_id=question_id,
            asking_agent_id=agent_id,
            heartbeat=heartbeat_number,
            question=question,
            reason_for_asking=reason,
            related_goal_id=action.get("related_goal_id"),
            requested_human_capability=action.get("requested_human_capability", ""),
            urgency=urgency,
            status="pending",
        ))
        return {"status": "success", "question_id": question_id}

    def _execute_request_capability(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        cap_id = action.get("capability_id")
        cap_reason = action.get("capability_reason", "")
        if not cap_id or not isinstance(cap_id, str) or not cap_id.strip():
            return {"status": "rejected", "reason": "Missing or empty capability_id"}
        if not cap_reason or not isinstance(cap_reason, str) or not cap_reason.strip():
            return {"status": "rejected", "reason": "Missing or empty capability_reason"}
        record = {
            "capability_id": cap_id,
            "requesting_agent_id": view["agent_id"],
            "reason": cap_reason,
            "heartbeat": heartbeat_number,
            "status": "pending",
            "requested_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        self._world_state.capability_requests.append(record)
        return {
            "status": "success",
            "capability_id": cap_id,
            "reason": cap_reason,
        }

    def _execute_modify_world(self, agent_ref: str, action: dict) -> dict:
        return {"status": "not_implemented", "action": action}

    # ------------------------------------------------------------------
    # Cognition output application
    # ------------------------------------------------------------------

    def _apply_cognition_output(
        self, agent_ref: str, output: Any, heartbeat_number: int
    ) -> None:
        if output.goal_updates:
            for gu in output.goal_updates:
                existing = next(
                    (g for g in self._goals if g.goal_id == gu.get("goal_id")), None
                )
                if existing:
                    existing.status = gu.get("status", existing.status)
                    existing.description = gu.get("description", existing.description)
                else:
                    self._goals.append(GoalRecord(
                        goal_id=gu["goal_id"],
                        agent_id=gu["agent_id"],
                        description=gu["description"],
                        status=gu.get("status", "active"),
                        created_heartbeat=gu.get("created_heartbeat", heartbeat_number),
                    ))

        if output.memory_write:
            target_list = (
                self._adam_memory if agent_ref == "east_adam" else self._eve_memory
            )
            for mw in output.memory_write:
                target_list.append({
                    **mw,
                    "heartbeat": heartbeat_number,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                })

        if output.questions_raised:
            for q in output.questions_raised:
                qid = q["question_id"]
                # Deduplicate against existing questions
                if any(existing.question_id == qid for existing in self._questions):
                    continue
                agent_id = (
                    self._identity_record.adam_agent_id
                    if agent_ref == "east_adam"
                    else self._identity_record.eve_agent_id
                )
                self._questions.append(QuestionRecord(
                    question_id=qid,
                    asking_agent_id=agent_id,
                    heartbeat=heartbeat_number,
                    question=q["question"],
                    reason_for_asking=q["reason_for_asking"],
                    related_goal_id=q.get("related_goal_id"),
                    requested_human_capability=q.get("requested_human_capability", ""),
                    urgency=q.get("urgency", "low"),
                    status="pending",
                ))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, start_heartbeat: int | None = None) -> dict:
        self._load_or_initialize()
        self._current_run_cognition: dict[str, dict] = {
            "east_adam": {"observation_summary": "", "decision_summary": "", "uncertainty": ""},
            "east_eve": {"observation_summary": "", "decision_summary": "", "uncertainty": ""},
        }

        history = load_heartbeat_history(self._store)
        if start_heartbeat is not None:
            current = start_heartbeat
        elif history:
            current = history[-1].heartbeat_number + 1
        else:
            current = 1

        # Capture pre-run state for evidence export
        from backend.world.first_pair_persistence import (
            load_memory_selection_manifests as _load_manifests,
            load_summaries as _load_summaries,
            load_relationship_events as _load_rel_events,
        )
        self._evidence_pre = {
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "adam_mem_before": len(self._adam_memory),
            "eve_mem_before": len(self._eve_memory),
            "cumulative_hb_before": len(history),
            "final_hb_before": history[-1].heartbeat_number if history else 0,
            "manifest_count_before": len(_load_manifests(self._store)),
            "summary_count_before": len(_load_summaries(self._store)),
            "rel_event_count_before": len(_load_rel_events(self._store)),
            "run_start_hb": current,
        }
        self._run_backend_label = self._backend

        results: dict = {"heartbeats_completed": 0, "errors": []}

        for hb in range(current, current + self._heartbeat_limit):
            adam_action: dict | None = None
            adam_outcome: dict = {}
            eve_action: dict | None = None
            eve_outcome: dict = {}
            world_mutations: list[dict] = []

            for agent_ref in ("east_adam", "east_eve"):
                backend = self._get_cognition_backend(agent_ref)
                cycle = CognitiveCycle(backend)
                ctx = self._build_context(agent_ref, hb)
                output = cycle.run_cycle(ctx)
                outcome = self._execute_action(agent_ref, output.action, hb)

                if agent_ref == "east_adam":
                    adam_action = output.action
                    adam_outcome = outcome
                    self._current_run_cognition["east_adam"]["observation_summary"] = output.observation_summary
                    self._current_run_cognition["east_adam"]["decision_summary"] = output.decision_summary
                    self._current_run_cognition["east_adam"]["uncertainty"] = output.uncertainty
                else:
                    eve_action = output.action
                    eve_outcome = outcome
                    self._current_run_cognition["east_eve"]["observation_summary"] = output.observation_summary
                    self._current_run_cognition["east_eve"]["decision_summary"] = output.decision_summary
                    self._current_run_cognition["east_eve"]["uncertainty"] = output.uncertainty

                reflection = cycle.reflect(ctx, output.action, outcome)
                self._apply_cognition_output(agent_ref, output, hb)

                memory_list = (
                    self._adam_memory if agent_ref == "east_adam" else self._eve_memory
                )
                memory_list.append({
                    "type": "reflection",
                    "content": reflection,
                    "heartbeat": hb,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                })

                # Structured mutation evidence — only actual state mutations
                if outcome.get("status") == "success":
                    action_type = (output.action or {}).get("action_type", "unknown")
                    # Only world-changing actions count as mutations
                    if action_type in (
                        "create_public_object",
                        "modify_owned_public_object",
                        "leave_public_message",
                        "request_capability",
                        "move",
                    ):
                        view = self._agent_view(agent_ref)
                        mutation = {
                            "acting_agent_id": view["agent_id"],
                            "heartbeat": hb,
                            "action_type": action_type,
                            "target": outcome.get("object_id") or outcome.get("target_tile") or outcome.get("message_id", ""),
                            "input": dict(output.action) if output.action else {},
                            "outcome": outcome,
                        }
                        world_mutations.append(mutation)

                    # Record social continuity event for validated public interactions
                    if action_type in (
                        "leave_public_message", "move", "create_public_object",
                        "inspect_public_object",
                    ):
                        view = self._agent_view(agent_ref)
                        other_id = view["other_agent_id"]
                        maybe_record_relationship_event(
                            self._store, hb, agent_ref,
                            view["agent_id"], other_id,
                            action_type, outcome, view,
                            self._world_state,
                        )

            # Set world_state.tick to actual heartbeat before saving
            self._world_state.tick = hb
            self._world_state.updated_at_utc = datetime.now(timezone.utc).isoformat()

            # End-of-tick persistence
            self._persist_shared_state(
                hb, adam_action, adam_outcome, eve_action, eve_outcome, world_mutations
            )
            results["heartbeats_completed"] += 1

        return results

    def _persist_shared_state(
        self,
        heartbeat_number: int,
        adam_action: dict | None = None,
        adam_outcome: dict | None = None,
        eve_action: dict | None = None,
        eve_outcome: dict | None = None,
        world_mutations: list[dict] | None = None,
    ) -> None:
        save_world_state(self._store, self._world_state)

        shared_memory = {
            "east_adam": list(self._adam_memory),
            "east_eve": list(self._eve_memory),
        }
        save_memory(self._store, shared_memory)
        save_goals(self._store, self._goals)
        save_questions(self._store, self._questions)

        actions_taken = {}
        if adam_action:
            actions_taken["east_adam"] = adam_action
        if eve_action:
            actions_taken["east_eve"] = eve_action

        hb_record = HeartbeatRecord(
            heartbeat_number=heartbeat_number,
            agent_id="both",
            position="",
            observation={},
            action_taken=actions_taken if actions_taken else None,
            world_mutations=world_mutations or [],
            goals_updated=[g.goal_id for g in self._goals],
            questions_raised=[
                q.question_id for q in self._questions if q.status == "pending"
            ],
        )
        append_heartbeat(self._store, hb_record)

    # ------------------------------------------------------------------
    # Evidence / inspection
    # ------------------------------------------------------------------

    def export_evidence(self, output_path: Path, run_id: str = "") -> dict[str, Any]:
        history = load_heartbeat_history(self._store)
        process_start = datetime.now(timezone.utc)

        adam_view = self._agent_view("east_adam") if self._identity_record else {}
        eve_view = self._agent_view("east_eve") if self._identity_record else {}

        # --- Resolve run boundaries from pre-run state ---
        pre = getattr(self, "_evidence_pre", None)
        if pre is not None and pre.get("run_start_hb"):
            new_count = history[-1].heartbeat_number - pre["final_hb_before"] if history else 0
            start_hb = pre["run_start_hb"]
            end_hb = pre["run_start_hb"] + new_count - 1 if new_count > 0 else None
        else:
            new_count = 0
            start_hb = None
            end_hb = None

        cumulative_count = len(history)
        adam_mem_before = pre["adam_mem_before"] if pre else len(self._adam_memory)
        eve_mem_before = pre["eve_mem_before"] if pre else len(self._eve_memory)

        # --- Run-specific records (by count slicing) ---
        all_manifests = load_memory_selection_manifests(self._store)
        all_summaries = load_summaries(self._store)
        all_rel_events = load_relationship_events(self._store)

        manifest_before = pre["manifest_count_before"] if pre else len(all_manifests)
        summary_before = pre["summary_count_before"] if pre else len(all_summaries)
        rel_before = pre["rel_event_count_before"] if pre else len(all_rel_events)

        run_manifests = list(all_manifests[manifest_before:])
        run_summaries = list(all_summaries[summary_before:])
        run_rel_events = list(all_rel_events[rel_before:])

        # --- Cumulative heartbeat detail ---
        heartbeats_export: list[dict] = []
        for h in history:
            entry: dict = {"heartbeat_number": h.heartbeat_number}
            actions = h.action_taken or {}
            entry["adam_action"] = actions.get("east_adam")
            entry["eve_action"] = actions.get("east_eve")
            entry["questions_raised"] = h.questions_raised
            entry["goals_updated"] = h.goals_updated
            entry["world_mutations"] = [
                m for m in (h.world_mutations or [])
                if m.get("action_type") in (
                    "create_public_object", "modify_owned_public_object",
                    "leave_public_message", "request_capability", "move",
                ) and m.get("outcome", {}).get("status") == "success"
            ]
            hb_manifests = [m for m in all_manifests if m.get("heartbeat", 0) == h.heartbeat_number]
            if hb_manifests:
                entry["memory_selection_manifests"] = hb_manifests
            heartbeats_export.append(entry)

        # --- Run-specific heartbeat list ---
        run_heartbeats = [h for h in heartbeats_export
                          if start_hb is not None and end_hb is not None
                          and start_hb <= h["heartbeat_number"] <= end_hb]

        # --- Privacy manifest ---
        privacy_manifest = {
            "requesting_agent_id_adam": adam_view.get("agent_id", ""),
            "requesting_agent_id_eve": eve_view.get("agent_id", ""),
            "adam_private_memory_count": len(self._adam_memory),
            "eve_private_memory_count": len(self._eve_memory),
            "other_agent_private_memory_included": 0,
            "public_evidence_count": len(self._world_state.public_objects) + len(self._world_state.public_messages) if self._world_state else 0,
            "answered_question_count": len([q for q in self._questions if q.status == "answered"]) if self._questions else 0,
            "canonical_request_hash": hashlib.sha256(
                json.dumps({
                    "adam_mem_count": len(self._adam_memory),
                    "eve_mem_count": len(self._eve_memory),
                    "public_obj_count": len(self._world_state.public_objects) if self._world_state else 0,
                    "goal_count": len(self._goals),
                }, sort_keys=True).encode()
            ).hexdigest()[:16],
        }

        # --- Provider / backend label ---
        provider_type = ""
        model_name = ""
        backend_label = getattr(self, "_run_backend_label", self._backend)
        try:
            backend = self._get_cognition_backend("east_adam")
            if hasattr(backend, "provider_type"):
                provider_type = backend.provider_type
            if hasattr(backend, "model_name"):
                model_name = backend.model_name
        except Exception:
            pass

        bundle: dict[str, Any] = {
            "evidence_schema_version": "10FN.2",
            "run_id": run_id,
            "backend_label": backend_label,
            "provider_type": provider_type,
            "model_name": model_name,
            "root": str(self._store.root) if self._store else "",
            "process_started_at_utc": pre["started_at_utc"] if pre else "",
            "process_finished_at_utc": process_start.isoformat(),
            "start_heartbeat": start_hb,
            "end_heartbeat": end_hb,
            "new_heartbeat_count": new_count,
            "cumulative_heartbeat_count": cumulative_count,
            "initialized_or_resumed": "resumed" if cumulative_count > 1 else "initialized",
            "adam_id": adam_view.get("agent_id", ""),
            "eve_id": eve_view.get("agent_id", ""),
            "adam_memory_count_before": adam_mem_before,
            "adam_memory_count_after": len(self._adam_memory),
            "eve_memory_count_before": eve_mem_before,
            "eve_memory_count_after": len(self._eve_memory),
            "adam_selected_memory_count": len([m for m in run_manifests if m.get("requesting_agent_id") == adam_view.get("agent_id", "")]),
            "eve_selected_memory_count": len([m for m in run_manifests if m.get("requesting_agent_id") == eve_view.get("agent_id", "")]),
            "summary_count": len(all_summaries),
            "relationship_event_count": len(all_rel_events),
            "goals_before": [],
            "goals_after": [g.__dict__ for g in self._goals],
            "questions_answered_during_run": [
                q.__dict__ for q in self._questions if q.status == "answered"
            ],
            "active_capability_grants": [
                self._capability_grant.__dict__
            ] if self._capability_grant else [],
            "adam_observation_summary": getattr(self, "_current_run_cognition", {}).get("east_adam", {}).get("observation_summary", ""),
            "adam_decision_summary": getattr(self, "_current_run_cognition", {}).get("east_adam", {}).get("decision_summary", ""),
            "adam_uncertainty": getattr(self, "_current_run_cognition", {}).get("east_adam", {}).get("uncertainty", ""),
            "eve_observation_summary": getattr(self, "_current_run_cognition", {}).get("east_eve", {}).get("observation_summary", ""),
            "eve_decision_summary": getattr(self, "_current_run_cognition", {}).get("east_eve", {}).get("decision_summary", ""),
            "eve_uncertainty": getattr(self, "_current_run_cognition", {}).get("east_eve", {}).get("uncertainty", ""),
            # Run-specific sections
            "heartbeats": run_heartbeats,
            "memory_selection_manifests": run_manifests,
            "memory_summaries": [asdict(s) for s in run_summaries],
            "relationship_events": [asdict(e) for e in run_rel_events],
            # Cumulative state
            "cumulative": {
                "heartbeats": heartbeats_export,
                "memory_selection_manifests": all_manifests,
                "memory_summaries": [asdict(s) for s in all_summaries],
                "relationship_events": [asdict(e) for e in all_rel_events],
            },
            "privacy_manifest": privacy_manifest,
            "adam_memory": self._adam_memory,
            "eve_memory": self._eve_memory,
            "goals": [g.__dict__ for g in self._goals],
            "questions": [q.__dict__ for q in self._questions],
            "exported_at_utc": process_start.isoformat(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2, default=str, sort_keys=True)
        return bundle

    def validate_state(self) -> dict:
        return validate_persistence_integrity(self._store)


def run_first_pair_demo(
    heartbeats: int = 5,
    persistence_root: Path | None = None,
    export_path: Path | None = None,
    backend: str = "stub",
) -> dict:
    """Convenience harness — builds a fresh runtime and runs it once."""
    runtime = FirstPairRuntime(
        persistence_root=persistence_root,
        heartbeat_limit=heartbeats,
        backend=backend,
    )
    results = runtime.run()
    if export_path:
        runtime.export_evidence(export_path)
    return results

"""Phase 10FM — First Pair Runtime Orchestrator.

Coordinates bounded heartbeat cycles for Adam and Eve. Mutations flow through
`FirstPairPersistenceStore`; the store and all its children are injected from
the outside — no module-global paths.
"""

from __future__ import annotations

import json
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
    FirstPairPersistenceStore,
    GoalRecord,
    HeartbeatRecord,
    IdentityRecord,
    PublicObjectRecord,
    QuestionRecord,
    WorldStateRecord,
    append_heartbeat,
    get_persistence_root,
    initialize_first_pair_state,
    list_answered_questions_for_agent,
    list_unanswered_questions,
    load_goals,
    load_heartbeat_history,
    load_memory,
    load_questions,
    save_goals,
    save_memory,
    save_questions,
    save_world_state,
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

        observation = {
            "tile_id": position,
            "visible_tiles": self._habitat.get("observation_boundaries", {}).get(
                agent_ref, []
            ),
            "objects_here": current_tile_objects,
        }

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
            habitat_allowed_tiles=self._habitat.get("allowed_tile_ids", []),
            habitat_movement_allowed=self._habitat.get("movement_allowed", False),
            previous_action=None,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            # Dynamic pair identity
            other_agent_id=view["other_agent_id"],
            other_agent_name=view["other_agent_name"],
            other_agent_ref=view["other_agent_ref"],
            # Answered questions for this agent
            answered_questions=agent_answered_questions,
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
        if not self._habitat.get("movement_allowed"):
            return {"status": "blocked", "reason": "Movement not allowed by habitat boundary"}
        target = action.get("target_tile")
        allowed = self._habitat.get("allowed_tile_ids", [])
        if target not in allowed:
            return {"status": "blocked", "reason": f"Tile {target} not in allowed tiles"}

        current_pos = self._world_state.tile_occupancy.get(agent_ref)
        if current_pos is None:
            current_pos = self._habitat["starting_tile_ids"].get(agent_ref)

        if target in self._world_state.tile_occupancy.values():
            return {
                "status": "blocked",
                "reason": f"Tile {target} already occupied",
            }

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
        if tile_id not in self._habitat.get("allowed_tile_ids", []):
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

        history = load_heartbeat_history(self._store)
        if start_heartbeat is not None:
            current = start_heartbeat
        elif history:
            current = history[-1].heartbeat_number + 1
        else:
            current = 1

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
                else:
                    eve_action = output.action
                    eve_outcome = outcome

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

    def export_evidence(self, output_path: Path) -> dict[str, Any]:
        bundle: dict[str, Any] = {
            "adam_identity": (
                self._agent_view("east_adam") if self._identity_record else None
            ),
            "eve_identity": (
                self._agent_view("east_eve") if self._identity_record else None
            ),
            "habitat": self._habitat,
            "world_state": self._world_state.__dict__ if self._world_state else None,
            "adam_memory": self._adam_memory,
            "eve_memory": self._eve_memory,
            "goals": [g.__dict__ for g in self._goals],
            "questions": [q.__dict__ for q in self._questions],
            "heartbeat_log": [
                {
                    "heartbeat_number": h.heartbeat_number,
                    "agent_id": h.agent_id,
                    "action_taken": h.action_taken,
                    "world_mutations": h.world_mutations[:3],
                }
                for h in load_heartbeat_history(self._store)
            ],
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
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

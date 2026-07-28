"""Phase 10FM — First Pair Persistence Layer.

Provides versioned, validated persistence envelopes and atomic writes for the
First Pair minimum viable life system. All data persists to an isolated
repository-local runtime directory that survives process restarts but does
not touch world-sim/data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.world.local_first_pair_birth_candidate import (
    create_first_pair_birth_candidate,
)
from backend.world.local_first_pair_habitat_boundary import (
    create_first_pair_habitat_boundary,
)
from backend.world.local_first_pair_memory_boundary import (
    create_first_pair_memory_boundary,
)

_RUNTIME_POLICY_SCHEMA_VERSION = "10FN.1"
_CAPABILITY_GRANT_SCHEMA_VERSION = "10FN.1"
_PERSISTENCE_SCHEMA_VERSION = "10FM.1"
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent / ".runtime" / "first-pair"
_IDENTITY_FILE = "identity.json"
_HABITAT_FILE = "habitat.json"
_MEMORY_FILE = "memory.json"
_WORLD_STATE_FILE = "world_state.json"
_GOALS_FILE = "goals.json"
_QUESTIONS_FILE = "questions.json"
_HEARTBEAT_FILE = "heartbeat.json"
_RUNTIME_POLICY_FILE = "runtime_policy.json"
_CAPABILITY_GRANT_FILE = "capability_grant.json"
_PROVENANCE_FILE = "provenance.jsonl"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_canonical(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class FirstPairPersistenceStore:
    """Explicit root-bound persistence store for the First Pair.

    All reads and writes go through this object. No module-global mutation.
    """

    def __init__(self, root: Path | None = None):
        self.root = (root or _DEFAULT_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, filename: str) -> Path:
        return self.root / filename

    def _atomic_write(self, path: Path, data: dict) -> None:
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        tmp_path.replace(path)

    def _read_json(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _append_jsonl(self, path: Path, record: dict) -> None:
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(_canonical_json(record) + "\n")

    def _append_provenance(self, action: str, detail: dict) -> None:
        record = {
            "event_id": f"prov-{_hash_canonical({'action': action, 'detail': detail, 'ts': datetime.now(timezone.utc).isoformat()})[:16]}",
            "action": action,
            "detail": detail,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        self._append_jsonl(self._path(_PROVENANCE_FILE), record)


@dataclass
class PublicObjectRecord:
    object_id: str
    creator_agent_id: str
    tile_id: str
    object_type: str
    public_description: str
    created_heartbeat: int
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_envelope(self) -> dict:
        return {
            "object_id": self.object_id,
            "creator_agent_id": self.creator_agent_id,
            "tile_id": self.tile_id,
            "object_type": self.object_type,
            "public_description": self.public_description,
            "created_heartbeat": self.created_heartbeat,
            "created_at_utc": self.created_at_utc,
        }


@dataclass
class PersistenceEnvelope:
    schema_version: str = _PERSISTENCE_SCHEMA_VERSION
    persisted_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    envelope_hash: str = ""

    def seal(self) -> PersistenceEnvelope:
        material = asdict(self)
        material.pop("envelope_hash", None)
        self.envelope_hash = _hash_canonical(material)
        return self


@dataclass
class IdentityRecord:
    birth_candidate: dict
    habitat_boundary: dict
    memory_boundary: dict
    adam_agent_id: str
    eve_agent_id: str
    pair_id: str = "genesis-first-pair"
    provenance_commitment_adam: str = ""
    provenance_commitment_eve: str = ""

    def to_envelope(self) -> dict:
        return {
            "type": "identity_record",
            "schema_version": _PERSISTENCE_SCHEMA_VERSION,
            "data": asdict(self),
        }


@dataclass
class WorldStateRecord:
    world_state_id: str = ""
    habitat: dict = field(default_factory=dict)
    public_objects: dict[str, dict] = field(default_factory=dict)
    public_messages: list[dict] = field(default_factory=list)
    capability_requests: list[dict] = field(default_factory=list)
    tile_occupancy: dict[str, str] = field(default_factory=dict)
    tick: int = 0
    updated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "world_state.1"

    def to_envelope(self) -> dict:
        return {
            "type": "world_state_record",
            "schema_version": _PERSISTENCE_SCHEMA_VERSION,
            "data": asdict(self),
        }


@dataclass
class GoalRecord:
    goal_id: str
    agent_id: str
    description: str
    status: str
    created_heartbeat: int
    related_question_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_envelope(self) -> dict:
        return {
            "type": "goal_record",
            "schema_version": _PERSISTENCE_SCHEMA_VERSION,
            "data": asdict(self),
        }


@dataclass
class QuestionRecord:
    question_id: str
    asking_agent_id: str
    heartbeat: int
    question: str
    reason_for_asking: str
    related_goal_id: str | None
    requested_human_capability: str
    urgency: str
    status: str = "pending"
    provenance: dict = field(default_factory=dict)
    asked_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_envelope(self) -> dict:
        return {
            "type": "question_record",
            "schema_version": _PERSISTENCE_SCHEMA_VERSION,
            "data": asdict(self),
        }


@dataclass
class PublicMessageRecord:
    message_id: str
    sender_agent_id: str
    message: str
    recipient: str
    heartbeat: int
    sent_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_envelope(self) -> dict:
        return {
            "type": "public_message_record",
            "schema_version": _PERSISTENCE_SCHEMA_VERSION,
            "data": {
                "message_id": self.message_id,
                "sender_agent_id": self.sender_agent_id,
                "message": self.message,
                "recipient": self.recipient,
                "heartbeat": self.heartbeat,
                "sent_at_utc": self.sent_at_utc,
            },
        }


@dataclass
class CapabilityRequestRecord:
    capability_id: str
    requesting_agent_id: str
    reason: str
    heartbeat: int
    status: str = "pending"
    requested_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_envelope(self) -> dict:
        return {
            "type": "capability_request_record",
            "schema_version": _PERSISTENCE_SCHEMA_VERSION,
            "data": {
                "capability_id": self.capability_id,
                "requesting_agent_id": self.requesting_agent_id,
                "reason": self.reason,
                "heartbeat": self.heartbeat,
                "status": self.status,
                "requested_at_utc": self.requested_at_utc,
            },
        }


@dataclass
class HeartbeatRecord:
    heartbeat_number: int
    agent_id: str
    position: str
    observation: dict
    action_taken: dict | None
    world_mutations: list = field(default_factory=list)
    goals_updated: list = field(default_factory=list)
    questions_raised: list = field(default_factory=list)
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_envelope(self) -> dict:
        return {
            "type": "heartbeat_record",
            "schema_version": _PERSISTENCE_SCHEMA_VERSION,
            "data": asdict(self),
        }


@dataclass
class RuntimePolicyRecord:
    """Versioned runtime-policy overlay that supersedes historical habitat boundary."""
    policy_id: str
    schema_version: str = _RUNTIME_POLICY_SCHEMA_VERSION
    pair_id: str = "genesis-first-pair"
    topology: dict = field(default_factory=dict)
    movement_grant_ref: str = ""
    allowed_observation_rules: dict = field(default_factory=dict)
    co_location_rules: dict = field(default_factory=dict)
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "active"
    integrity_commitment: str = ""

    def seal(self) -> RuntimePolicyRecord:
        material = asdict(self)
        material.pop("integrity_commitment", None)
        self.integrity_commitment = _hash_canonical(material)
        return self

    def to_envelope(self) -> dict:
        return {
            "type": "runtime_policy_record",
            "schema_version": _RUNTIME_POLICY_SCHEMA_VERSION,
            "data": asdict(self),
        }


@dataclass
class CapabilityGrantRecord:
    """Governed operator capability-grant record."""
    grant_id: str
    capability_id: str
    scope: str
    reason: str
    granted_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    operator_provenance: str = ""
    status: str = "granted"
    policy_version: str = _RUNTIME_POLICY_SCHEMA_VERSION
    integrity_commitment: str = ""

    def seal(self) -> CapabilityGrantRecord:
        material = asdict(self)
        material.pop("integrity_commitment", None)
        self.integrity_commitment = _hash_canonical(material)
        return self

    def to_envelope(self) -> dict:
        return {
            "type": "capability_grant_record",
            "schema_version": _CAPABILITY_GRANT_SCHEMA_VERSION,
            "data": asdict(self),
        }


def create_default_runtime_policy() -> RuntimePolicyRecord:
    """Create the default runtime policy overlay with shared habitat topology."""
    return RuntimePolicyRecord(
        policy_id="runtime-policy-first-pair-001",
        topology={
            "tiles": [
                {"tile_id": "public-start-adam", "adjacent": ["public-shared-center"]},
                {"tile_id": "public-shared-center", "adjacent": ["public-start-adam", "public-start-eve"]},
                {"tile_id": "public-start-eve", "adjacent": ["public-shared-center"]},
            ],
            "allowed_tile_ids": ["public-start-adam", "public-shared-center", "public-start-eve"],
            "movement_allowed": True,
            "one_edge_per_heartbeat": True,
        },
        movement_grant_ref="grant-movement-001",
        allowed_observation_rules={
            "current_tile_visible": True,
            "adjacent_tile_ids_visible": True,
            "co_location_visible": True,
        },
        co_location_rules={
            "shared_center_allows_both": True,
            "starting_tile_single_occupancy": True,
        },
    ).seal()


def load_runtime_policy(store: FirstPairPersistenceStore) -> RuntimePolicyRecord | None:
    data = store._read_json(store._path(_RUNTIME_POLICY_FILE))
    if data and data.get("type") == "runtime_policy_record":
        return RuntimePolicyRecord(**data["data"])
    return None


def save_runtime_policy(store: FirstPairPersistenceStore, policy: RuntimePolicyRecord) -> None:
    store._atomic_write(store._path(_RUNTIME_POLICY_FILE), policy.to_envelope())
    store._append_provenance("runtime_policy_update", {"policy_id": policy.policy_id, "status": policy.status})


def load_capability_grant(store: FirstPairPersistenceStore) -> CapabilityGrantRecord | None:
    data = store._read_json(store._path(_CAPABILITY_GRANT_FILE))
    if data and data.get("type") == "capability_grant_record":
        return CapabilityGrantRecord(**data["data"])
    return None


def grant_capability(
    store: FirstPairPersistenceStore,
    capability_id: str,
    scope: str,
    reason: str,
    operator_provenance: str = "operator_script",
) -> CapabilityGrantRecord:
    """Governed operator capability-grant operation. Runs zero heartbeats.

    Also creates a default runtime policy if none exists, so the grant
    takes immediate effect.
    """
    if load_runtime_policy(store) is None:
        policy = create_default_runtime_policy()
        save_runtime_policy(store, policy)
        store._append_provenance("runtime_policy_created", {
            "policy_id": policy.policy_id,
            "capability_id": capability_id,
        })
    grant = CapabilityGrantRecord(
        grant_id=f"grant-{capability_id}-001",
        capability_id=capability_id,
        scope=scope,
        reason=reason,
        operator_provenance=operator_provenance,
    ).seal()
    store._atomic_write(store._path(_CAPABILITY_GRANT_FILE), grant.to_envelope())
    store._append_provenance("capability_grant", {
        "grant_id": grant.grant_id,
        "capability_id": capability_id,
        "scope": scope,
    })
    return grant


def get_adjacent_tiles(policy: RuntimePolicyRecord, tile_id: str) -> list[str]:
    """Get adjacent tiles for a given tile from runtime policy topology."""
    for tile in policy.topology.get("tiles", []):
        if tile["tile_id"] == tile_id:
            return list(tile.get("adjacent", []))
    return []


def initialize_first_pair_state(
    store: FirstPairPersistenceStore,
    declaration: dict | None = None,
) -> tuple[IdentityRecord, WorldStateRecord]:
    """Initialize or load the First Pair persistent state from the store."""
    identity_path = store._path(_IDENTITY_FILE)
    world_path = store._path(_WORLD_STATE_FILE)

    existing_identity = store._read_json(identity_path)
    if existing_identity and existing_identity.get("type") == "identity_record":
        identity = IdentityRecord(**existing_identity["data"])
        world_state = _load_world_state(store)
        return identity, world_state

    if declaration is None:
        declaration = _default_declaration()

    birth_candidate = create_first_pair_birth_candidate(declaration)
    if birth_candidate.get("ok") is not True:
        raise RuntimeError(f"Birth candidate creation failed: {birth_candidate.get('errors')}")

    habitat_request = {
        "habitat_boundary_schema_version": "10ID.1",
        "birth_candidate": birth_candidate,
        "authorized_declaration": declaration,
        "observation_radius": 1,
    }
    habitat_boundary = create_first_pair_habitat_boundary(habitat_request)
    if habitat_boundary.get("within_bounds") is not True:
        raise RuntimeError(f"Habitat boundary failed: {habitat_boundary.get('errors')}")

    memory_boundary_request = {
        "memory_boundary_schema_version": "10IE.1",
        "habitat_boundary": habitat_boundary,
        "authorized_declaration": declaration,
        "adam_memory_refs": [],
        "eve_memory_refs": [],
    }
    memory_boundary = create_first_pair_memory_boundary(memory_boundary_request)
    if memory_boundary.get("ok") is not True:
        raise RuntimeError(f"Memory boundary failed: {memory_boundary.get('errors')}")
    if memory_boundary.get("within_bounds") is not True:
        raise RuntimeError(f"Memory boundary not within bounds: {memory_boundary.get('errors')}")

    adam_id = birth_candidate["adam_identity"]["agent_id"]
    eve_id = birth_candidate["eve_identity"]["agent_id"]
    prov_adam = declaration["adam_identity"]["provenance_commitment"]
    prov_eve = declaration["eve_identity"]["provenance_commitment"]

    identity = IdentityRecord(
        birth_candidate=birth_candidate,
        habitat_boundary=habitat_boundary,
        memory_boundary=memory_boundary,
        adam_agent_id=adam_id,
        eve_agent_id=eve_id,
        provenance_commitment_adam=prov_adam,
        provenance_commitment_eve=prov_eve,
    )

    habitat = habitat_boundary["habitat"]
    start_adam = habitat["starting_tile_ids"]["east_adam"]
    start_eve = habitat["starting_tile_ids"]["east_eve"]

    world_state = WorldStateRecord(
        habitat=habitat,
        tile_occupancy={"east_adam": start_adam, "east_eve": start_eve},
        public_objects={},
    )

    store._atomic_write(identity_path, identity.to_envelope())
    store._atomic_write(world_path, world_state.to_envelope())
    store._atomic_write(
        store._path(_MEMORY_FILE),
        {
            "type": "memory_record",
            "schema_version": _PERSISTENCE_SCHEMA_VERSION,
            "data": {"east_adam": [], "east_eve": []},
        },
    )
    store._atomic_write(
        store._path(_GOALS_FILE),
        {"type": "goals_record", "schema_version": _PERSISTENCE_SCHEMA_VERSION, "data": []},
    )
    store._atomic_write(
        store._path(_QUESTIONS_FILE),
        {"type": "questions_record", "schema_version": _PERSISTENCE_SCHEMA_VERSION, "data": []},
    )
    store._atomic_write(
        store._path(_HEARTBEAT_FILE),
        {"type": "heartbeat_record", "schema_version": _PERSISTENCE_SCHEMA_VERSION, "data": []},
    )

    store._append_provenance("initialize", {"identity": identity.adam_agent_id, "eve": identity.eve_agent_id})
    return identity, world_state


def _default_declaration() -> dict:
    return {
        "identity_schema_version": "first_pair_identity.1",
        "id_derivation_version": "sha256-full-v1",
        "pair_id": "genesis-first-pair",
        "adam_identity": {
            "canonical_name": "Adam",
            "canonical_agent_ref": "east_adam",
            "founding_role": "founding_agent",
            "provenance_commitment": "a" * 64,
        },
        "eve_identity": {
            "canonical_name": "Eve",
            "canonical_agent_ref": "east_eve",
            "founding_role": "founding_agent",
            "provenance_commitment": "b" * 64,
        },
        "habitat": {
            "habitat_schema_version": "first_habitat.1",
            "habitat_id": "genesis-first-habitat",
            "allowed_tile_ids": ["public-start-adam", "public-start-eve"],
            "starting_tile_ids": {"east_adam": "public-start-adam", "east_eve": "public-start-eve"},
            "observation_boundaries": {"east_adam": ["public-start-adam"], "east_eve": ["public-start-eve"]},
            "movement_allowed": False,
        },
        "rollback_anchor": {
            "rollback_anchor_schema_version": "first_rollback_anchor.1",
            "rollback_anchor_id": "genesis-first-pair-anchor",
            "habitat_id": "genesis-first-habitat",
            "claim_scope": "operator_proof",
            "state_commitment": "c" * 64,
        },
    }


def _load_world_state(store: FirstPairPersistenceStore) -> WorldStateRecord:
    data = store._read_json(store._path(_WORLD_STATE_FILE))
    if data and data.get("type") == "world_state_record":
        return WorldStateRecord(**data["data"])
    return WorldStateRecord()


def save_world_state(store: FirstPairPersistenceStore, state: WorldStateRecord) -> None:
    store._atomic_write(store._path(_WORLD_STATE_FILE), state.to_envelope())
    store._append_provenance("world_state_update", {"objects": len(state.public_objects)})


def load_memory(store: FirstPairPersistenceStore) -> dict:
    data = store._read_json(store._path(_MEMORY_FILE))
    if data and data.get("type") == "memory_record":
        return data["data"]
    return {"east_adam": [], "east_eve": []}


def save_memory(store: FirstPairPersistenceStore, memory: dict) -> None:
    store._atomic_write(
        store._path(_MEMORY_FILE),
        {"type": "memory_record", "schema_version": _PERSISTENCE_SCHEMA_VERSION, "data": memory},
    )


def load_goals(store: FirstPairPersistenceStore) -> list[GoalRecord]:
    data = store._read_json(store._path(_GOALS_FILE))
    if data and data.get("type") == "goals_record":
        return [GoalRecord(**g) for g in data["data"]]
    return []


def save_goals(store: FirstPairPersistenceStore, goals: list[GoalRecord]) -> None:
    store._atomic_write(
        store._path(_GOALS_FILE),
        {"type": "goals_record", "schema_version": _PERSISTENCE_SCHEMA_VERSION, "data": [asdict(g) for g in goals]},
    )


def load_questions(store: FirstPairPersistenceStore) -> list[QuestionRecord]:
    data = store._read_json(store._path(_QUESTIONS_FILE))
    if data and data.get("type") == "questions_record":
        return [QuestionRecord(**q) for q in data["data"]]
    return []


def save_questions(store: FirstPairPersistenceStore, questions: list[QuestionRecord]) -> None:
    store._atomic_write(
        store._path(_QUESTIONS_FILE),
        {"type": "questions_record", "schema_version": _PERSISTENCE_SCHEMA_VERSION, "data": [asdict(q) for q in questions]},
    )


def load_heartbeat_history(store: FirstPairPersistenceStore) -> list[HeartbeatRecord]:
    data = store._read_json(store._path(_HEARTBEAT_FILE))
    if data and data.get("type") == "heartbeat_record":
        return [HeartbeatRecord(**h) for h in data["data"]]
    return []


def append_heartbeat(store: FirstPairPersistenceStore, record: HeartbeatRecord) -> None:
    history = load_heartbeat_history(store)
    history.append(record)
    store._atomic_write(
        store._path(_HEARTBEAT_FILE),
        {"type": "heartbeat_record", "schema_version": _PERSISTENCE_SCHEMA_VERSION, "data": [asdict(h) for h in history]},
    )


def list_unanswered_questions(store: FirstPairPersistenceStore) -> list[QuestionRecord]:
    return [q for q in load_questions(store) if q.status == "pending"]


def mark_question_answered(
    store: FirstPairPersistenceStore,
    question_id: str,
    answer: str,
    provenance: str = "",
) -> dict | None:
    questions = load_questions(store)
    for q in questions:
        if q.question_id == question_id:
            q.status = "answered"
            q.provenance["answer"] = answer
            q.provenance["answered_at_utc"] = datetime.now(timezone.utc).isoformat()
            q.provenance["operator_provenance"] = provenance
            save_questions(store, questions)
            store._append_provenance("answer_question", {
                "question_id": question_id,
                "asking_agent_id": q.asking_agent_id,
            })
            return asdict(q)
    return None


def list_answered_questions_for_agent(
    store: FirstPairPersistenceStore, agent_id: str
) -> list[QuestionRecord]:
    return [
        q for q in load_questions(store)
        if q.asking_agent_id == agent_id and q.status == "answered"
    ]


def append_public_message(
    store: FirstPairPersistenceStore,
    state: WorldStateRecord,
    message: dict,
) -> None:
    state.public_messages.append(message)
    state.updated_at_utc = datetime.now(timezone.utc).isoformat()


def persist_capability_request(
    store: FirstPairPersistenceStore,
    state: WorldStateRecord,
    request: dict,
) -> None:
    state.capability_requests.append(request)
    state.updated_at_utc = datetime.now(timezone.utc).isoformat()


def validate_persistence_integrity(store: FirstPairPersistenceStore) -> dict:
    results = {
        "identity": False,
        "world_state": False,
        "memory": False,
        "goals": False,
        "questions": False,
        "heartbeat": False,
    }
    identity_path = store._path(_IDENTITY_FILE)
    if identity_path.exists():
        data = store._read_json(identity_path)
        if data and data.get("type") == "identity_record":
            results["identity"] = True
    results["world_state"] = store._path(_WORLD_STATE_FILE).exists()
    results["memory"] = store._path(_MEMORY_FILE).exists()
    results["goals"] = store._path(_GOALS_FILE).exists()
    results["questions"] = store._path(_QUESTIONS_FILE).exists()
    results["heartbeat"] = store._path(_HEARTBEAT_FILE).exists()
    return results


def get_persistence_root() -> Path:
    return _DEFAULT_ROOT

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
_MEMORY_SELECTION_SCHEMA_VERSION = "10IN.1"
_SUMMARY_SCHEMA_VERSION = "10IN.1"
_RELATIONSHIP_SCHEMA_VERSION = "10IN.1"
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
_SUMMARY_FILE = "memory_summaries.json"
_RELATIONSHIP_FILE = "relationship_ledger.json"
_MEMORY_SELECTION_MANIFEST_FILE = "memory_selection_manifest.json"
_PROVENANCE_FILE = "provenance.jsonl"

# --- Bounded memory selection limits ---
_MAX_SELECTED_RECENT_MEMORIES = 6
_MAX_SELECTED_RELEVANT_MEMORIES = 6
_MAX_SELECTED_HUMAN_ANSWERS = 4
_MAX_SELECTED_TOTAL_DETAILED_MEMORIES = 16
_MAX_SELECTED_TOTAL_CHARS = 12000


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


# ---------------------------------------------------------------------------
# Memory selection, summary store, social continuity ledger
# ---------------------------------------------------------------------------


def _assign_memory_id(memory_entry: dict, index: int) -> str:
    """Derive a deterministic, stable memory ID from an entry and its position.

    Legacy entries that lack a ``memory_id`` key receive one through this
    function.  The ID is a function of the entry content and the storage index,
    so it remains stable across repeated derivation runs as long as the raw
    memory list is not re-ordered.
    """
    content = memory_entry.get("content", "")
    hb = memory_entry.get("heartbeat", 0)
    raw = f"{hb}:{index}:{content[:80]}"
    return f"mem-{_hash_canonical(raw)[:16]}"


def _ensure_memory_ids(memory_list: list[dict]) -> list[dict]:
    """Assign deterministic memory IDs to any entry that lacks one.

    The returned list is a shallow copy; the original entries are not mutated.
    """
    result = []
    for i, entry in enumerate(memory_list):
        if "memory_id" not in entry:
            entry = dict(entry)
            entry["memory_id"] = _assign_memory_id(entry, i)
        result.append(entry)
    return result


def _score_relevance(
    memory: dict,
    active_goal_ids: set[str],
    position: str,
    visible_tiles: set[str],
    visible_object_ids: set[str],
    visible_message_ids: set[str],
    relationship_event_memory_ids: set[str],
) -> int:
    """Score a memory entry for relevance (higher = more important).

    Priority tiers (from spec):
      1. connected to active goals           -> +100
      2. current location / visible objects    -> +50
      3. visible messages / other agent        -> +30
      4. human answers / capability outcomes   -> +20
      5. recent (within last 4 heartbeats)     -> +10
      6. default base                          -> +1
    """
    score = 0
    content = str(memory.get("content", ""))
    mem_type = memory.get("type", "")
    mem_hb = memory.get("heartbeat", 0)
    mem_id = memory.get("memory_id", "")

    # Tier 1: active goals
    for gid in active_goal_ids:
        if gid in content or gid in mem_id:
            score += 100
            break
    # Tier 1 also: goal-related type
    if mem_type == "goal_update":
        score += 100

    # Tier 2: current location or visible objects
    if position in content:
        score += 50
    for oid in visible_object_ids:
        if oid in content:
            score += 50
            break
    for tid in visible_tiles:
        if tid in content:
            score += 50
            break

    # Tier 3: visible messages or other agent
    for mid in visible_message_ids:
        if mid in content:
            score += 30
            break
    if "eve" in content.lower() or "east_eve" in content or "contact-adam" in content:
        score += 30

    # Tier 4: human answers
    if mem_type == "human_answer":
        score += 20

    # Tier 5: recent (last 4 heartbeats from max)
    # (handled externally via _recent_cutoff)

    # Relationship event referenced
    if mem_id and mem_id in relationship_event_memory_ids:
        score += 60

    # Tier 6: base
    if score == 0:
        score = 1

    return score


def select_private_memories(
    memories: list[dict],
    agent_id: str,
    goals: list[dict],
    position: str,
    visible_tiles: set[str],
    visible_object_ids: set[str],
    visible_message_ids: set[str],
    relationship_event_memory_ids: set[str],
    recent_cutoff_hb: int = 0,
) -> tuple[list[dict], dict]:
    """Select a bounded subset of private memories for a model request.

    Returns (selected_memories, manifest) where manifest is a dict of metadata.
    Selection is deterministic for identical state and context.
    """
    ensured = _ensure_memory_ids(memories)
    active_goal_ids = {g["goal_id"] for g in goals if g.get("status") == "active"}
    scored: list[tuple[int, int, dict]] = []

    for i, mem in enumerate(ensured):
        score = _score_relevance(
            mem, active_goal_ids, position, visible_tiles,
            visible_object_ids, visible_message_ids,
            relationship_event_memory_ids,
        )
        # Recent bonus
        hb = mem.get("heartbeat", 0)
        if recent_cutoff_hb > 0 and hb >= recent_cutoff_hb:
            score += 10
        scored.append((-score, -hb if recent_cutoff_hb > 0 else 0, i, mem))

    # Sort by score descending, then recency
    scored.sort()

    # Select recent memories first (cap at 6)
    recent: list[dict] = []
    relevant: list[dict] = []
    seen_ids: set[str] = set()
    total_chars = 0

    def _add(m: dict) -> bool:
        nonlocal total_chars
        mid = m.get("memory_id", "")
        if mid in seen_ids:
            return False
        c = len(str(m.get("content", "")))
        if total_chars + c > _MAX_SELECTED_TOTAL_CHARS:
            return False
        seen_ids.add(mid)
        total_chars += c
        return True

    # First pass: recent (high recency)
    for _, _, _, mem in scored:
        if len(recent) >= _MAX_SELECTED_RECENT_MEMORIES:
            break
        hb = mem.get("heartbeat", 0)
        if recent_cutoff_hb > 0 and hb >= recent_cutoff_hb:
            if _add(mem):
                recent.append(mem)

    # Second pass: relevant (high relevance, skip already included)
    for _, _, _, mem in scored:
        if len(relevant) >= _MAX_SELECTED_RELEVANT_MEMORIES:
            break
        if mem.get("memory_id", "") in seen_ids:
            continue
        if _add(mem):
            relevant.append(mem)

    # Fill remaining slots from recent if not enough
    for _, _, _, mem in scored:
        if len(recent) + len(relevant) >= _MAX_SELECTED_TOTAL_DETAILED_MEMORIES:
            break
        if mem.get("memory_id", "") in seen_ids:
            continue
        if _add(mem):
            relevant.append(mem)

    selected = recent + relevant
    selected = selected[:_MAX_SELECTED_TOTAL_DETAILED_MEMORIES]

    manifest = {
        "requesting_agent_id": agent_id,
        "raw_private_memory_count": len(ensured),
        "selected_private_memory_ids": [m.get("memory_id", "") for m in selected],
        "selected_private_memory_count": len(selected),
        "selected_private_memory_character_count": total_chars,
        "summary_ids": [],
        "omitted_private_memory_count": len(ensured) - len(selected),
        "other_agent_private_memory_count_included": 0,
        "selection_reason_categories": {
            "active_goal_count": len(active_goal_ids),
            "position_relevant": position,
            "recent_cutoff_heartbeat": recent_cutoff_hb,
        },
        "canonical_selection_hash": _hash_canonical({
            "agent_id": agent_id,
            "ids": [m.get("memory_id", "") for m in selected],
        }),
    }

    return selected, manifest


# ---------------------------------------------------------------------------
# Derived Memory Summary Store
# ---------------------------------------------------------------------------


@dataclass
class MemorySummaryRecord:
    summary_id: str
    owner_agent_id: str
    covered_memory_ids: list[str]
    covered_heartbeat_range: list[int]
    summary: str
    salient_entities: list[str]
    related_goal_ids: list[str]
    related_public_object_ids: list[str]
    related_message_ids: list[str]
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    derivation_method: str = "deterministic_stub"
    source_commitment: str = ""
    integrity_commitment: str = ""

    def seal(self) -> MemorySummaryRecord:
        material = asdict(self)
        material.pop("integrity_commitment", None)
        material.pop("source_commitment", None)
        self.integrity_commitment = _hash_canonical(material)
        return self

    def to_envelope(self) -> dict:
        return {
            "type": "memory_summary_record",
            "schema_version": _SUMMARY_SCHEMA_VERSION,
            "data": asdict(self),
        }


def load_summaries(store: FirstPairPersistenceStore) -> list[MemorySummaryRecord]:
    data = store._read_json(store._path(_SUMMARY_FILE))
    if data and data.get("type") == "memory_summary_record":
        # The file stores the full list as data["data"] returning a list
        raw_list = data.get("data", [])
        if isinstance(raw_list, list):
            return [MemorySummaryRecord(**s) for s in raw_list]
    return []


def save_summaries(store: FirstPairPersistenceStore, summaries: list[MemorySummaryRecord]) -> None:
    store._atomic_write(
        store._path(_SUMMARY_FILE),
        {
            "type": "memory_summary_record",
            "schema_version": _SUMMARY_SCHEMA_VERSION,
            "data": [asdict(s) for s in summaries],
        },
    )


def append_summary(store: FirstPairPersistenceStore, summary: MemorySummaryRecord) -> None:
    summaries = load_summaries(store)
    summaries.append(summary)
    save_summaries(store, summaries)


# ---------------------------------------------------------------------------
# Social Continuity Ledger
# ---------------------------------------------------------------------------


@dataclass
class RelationshipEventRecord:
    event_id: str
    heartbeat: int
    actor_agent_id: str
    other_agent_id: str
    event_type: str
    public_evidence_references: list[str]
    resulting_public_state_commitment: str
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    integrity_commitment: str = ""

    def seal(self) -> RelationshipEventRecord:
        material = asdict(self)
        material.pop("integrity_commitment", None)
        self.integrity_commitment = _hash_canonical(material)
        return self

    def to_envelope(self) -> dict:
        return {
            "type": "relationship_event_record",
            "schema_version": _RELATIONSHIP_SCHEMA_VERSION,
            "data": asdict(self),
        }


def load_relationship_events(store: FirstPairPersistenceStore) -> list[RelationshipEventRecord]:
    data = store._read_json(store._path(_RELATIONSHIP_FILE))
    if data and data.get("type") == "relationship_event_record":
        raw_list = data.get("data", [])
        if isinstance(raw_list, list):
            return [RelationshipEventRecord(**e) for e in raw_list]
    return []


def save_relationship_events(
    store: FirstPairPersistenceStore, events: list[RelationshipEventRecord]
) -> None:
    store._atomic_write(
        store._path(_RELATIONSHIP_FILE),
        {
            "type": "relationship_event_record",
            "schema_version": _RELATIONSHIP_SCHEMA_VERSION,
            "data": [asdict(e) for e in events],
        },
    )


def append_relationship_event(
    store: FirstPairPersistenceStore, event: RelationshipEventRecord
) -> None:
    events = load_relationship_events(store)
    events.append(event)
    save_relationship_events(store, events)


def derive_relationship_event_ids(events: list[RelationshipEventRecord]) -> set[str]:
    """Collect memory IDs referenced by relationship events."""
    ids: set[str] = set()
    for ev in events:
        for ref in ev.public_evidence_references:
            if ref.startswith("mem-"):
                ids.add(ref)
    return ids


def maybe_record_relationship_event(
    store: FirstPairPersistenceStore,
    heartbeat_number: int,
    actor_ref: str,
    actor_agent_id: str,
    other_agent_id: str,
    action_type: str,
    outcome: dict,
    agent_view: dict,
    world_state: WorldStateRecord,
) -> RelationshipEventRecord | None:
    """Record an observed social interaction event.

    Only validated persisted outcomes create ledger entries.  Rejected actions
    never enter the ledger.  No emotional/trust/social scores are assigned.
    """
    if outcome.get("status") != "success":
        return None
    valid_event_types = {
        "leave_public_message": "message_sent",
        "move": "co_location",
        "create_public_object": "public_object_creation",
        "inspect_public_object": "inspect_other_object",
    }
    if action_type not in valid_event_types:
        return None

    # Co-location events: only record when moving to the other agent's tile
    if action_type == "move" and outcome.get("to"):
        other_pos = world_state.tile_occupancy.get(
            "east_eve" if actor_ref == "east_adam" else "east_adam"
        )
        if outcome["to"] != other_pos:
            return None

    evidence_refs = []
    if outcome.get("object_id"):
        oid = outcome["object_id"]
        # Find the memory_id of the creation memory for this object
        evidence_refs.append(f"obj-{oid}")
    if outcome.get("message_id"):
        evidence_refs.append(f"msg-{outcome['message_id']}")
    if outcome.get("from") and outcome.get("to"):
        evidence_refs.append(f"move-{outcome['from']}-{outcome['to']}")

    event = RelationshipEventRecord(
        event_id=_hash_canonical({
            "actor": actor_agent_id, "hb": heartbeat_number, "type": action_type,
        })[:16],
        heartbeat=heartbeat_number,
        actor_agent_id=actor_agent_id,
        other_agent_id=other_agent_id,
        event_type=valid_event_types[action_type],
        public_evidence_references=evidence_refs,
        resulting_public_state_commitment=_hash_canonical({
            "action_type": action_type,
            "outcome": outcome,
            "objects": list(world_state.public_objects.keys()),
        })[:16],
    ).seal()
    append_relationship_event(store, event)
    return event


def load_memory_selection_manifests(store: FirstPairPersistenceStore) -> list[dict]:
    """Load the append-only memory selection manifest log."""
    data = store._read_json(store._path(_MEMORY_SELECTION_MANIFEST_FILE))
    if data and isinstance(data, dict):
        raw_list = data.get("data", [])
        if isinstance(raw_list, list):
            return raw_list
    return []


def append_memory_selection_manifest(store: FirstPairPersistenceStore, manifest: dict) -> None:
    manifests = load_memory_selection_manifests(store)
    manifests.append(manifest)
    store._atomic_write(
        store._path(_MEMORY_SELECTION_MANIFEST_FILE),
        {"type": "memory_selection_manifest_log", "schema_version": _MEMORY_SELECTION_SCHEMA_VERSION, "data": manifests},
    )


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

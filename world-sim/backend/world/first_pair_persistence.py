"""Phase 10FM — First Pair Persistence Layer.

Provides versioned, validated persistence envelopes and atomic writes for the
First Pair minimum viable life system. All data persists to an isolated
repository-local runtime directory that survives process restarts but does
not touch world-sim/data.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
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
from backend.world.question_proposal import (
    canonicalize_proposal_material,
    material_commitment,
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

# --- Signed question-creation authority ---
RECEIPT_DIR_NAME = "question-create-receipts"
# --- Signed answer authority ---
ANSWER_RECEIPT_DIR_NAME = "answer-authorization-receipts"
_STORE_LOCK_FILE = ".question.store.lock"
_LOCK_ACQUIRE_TIMEOUT_SECONDS = 30.0
_LOCK_POLL_INTERVAL_SECONDS = 0.05

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

    def _receipt_dir(self) -> Path:
        return self._path(RECEIPT_DIR_NAME)

    def _answer_receipt_dir(self) -> Path:
        return self._path(ANSWER_RECEIPT_DIR_NAME)

    def _atomic_write(self, path: Path, data: dict) -> None:
        """Durable atomic write: temp file in same dir → flush → fsync → replace.

        Process-crash durability is guaranteed (a completed write is visible to a
        subsequent open and a torn write leaves only the .tmp file). OS/power-loss
        durability beyond os.replace is NOT claimed (no directory-entry fsync).
        """
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

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

    # ------------------------------------------------------------------
    # Cross-process store lock (msvcrt byte-range on Windows; fcntl on POSIX)
    # ------------------------------------------------------------------

    def _lock_path(self) -> Path:
        return self._path(_STORE_LOCK_FILE)

    @contextmanager
    def _store_lock(self):
        """Serialize the entire logical creation transaction across processes.

        Byte-range lock on a stable dedicated file. The lock file is NOT deleted
        (deleting introduces a delete/recreate race); byte-range locks are
        released by the OS when the owning handle closes (including on crash).
        """
        lock_path = self._lock_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        f = open(lock_path, "a+", encoding="utf-8")
        try:
            if f.tell() == 0:
                f.write("\n")
            f.flush()
            self._acquire_lock(f)
            try:
                yield
            finally:
                self._release_lock(f)
        finally:
            f.close()

    def _acquire_lock(self, f) -> None:
        deadline = time.monotonic() + _LOCK_ACQUIRE_TIMEOUT_SECONDS
        try:
            import msvcrt

            _lock = msvcrt
        except ImportError:
            _lock = None

        while True:
            try:
                if _lock is not None:
                    _lock.locking(f.fileno(), _lock.LK_NBLCK, 1)
                    return
                else:
                    import fcntl

                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("store_lock_unavailable")
                time.sleep(_LOCK_POLL_INTERVAL_SECONDS)

    def _release_lock(self, f) -> None:
        try:
            import msvcrt
        except ImportError:
            msvcrt = None
        try:
            if msvcrt is not None:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except OSError:
            # Unlock best-effort; the OS releases byte-range locks on close anyway.
            pass


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


_MEMORY_ID_DERIVATION_VERSION = "v2-owner-bound"

def _derive_memory_id(owner_agent_id: str, memory_entry: dict) -> str:
    """Versioned owner-bound memory-ID derivation.

    Uses the full raw-memory canonical material plus the owner identity so
    identical content belonging to different agents produces different IDs.
    No list index or content truncation is used.
    """
    material = dict(memory_entry)
    material.pop("memory_id", None)
    material["_owner_agent_id"] = owner_agent_id
    return f"mem-{_hash_canonical(material)[:16]}"


def _ensure_memory_ids(memory_list: list[dict], owner_agent_id: str = "") -> list[dict]:
    """Assign versioned owner-bound memory IDs to any entry that lacks one.

    The returned list is a shallow copy; the original entries are not mutated.
    When owner_agent_id is empty (legacy path), derivations use only the
    material content but the ID is still a function of all canonical data.
    """
    result = []
    for entry in memory_list:
        if "memory_id" not in entry:
            entry = dict(entry)
            entry["memory_id"] = _derive_memory_id(owner_agent_id, entry)
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
    other_agent_ref: str = "",
    other_agent_name: str = "",
) -> int:
    """Score a memory entry for relevance (higher = more important).

    Priority tiers (from spec):
      1. connected to active goals           -> +100
      2. current location / visible objects    -> +50
      3. visible messages / other agent        -> +30
      4. human answers / capability outcomes   -> +20
      5. recent (within last 4 heartbeats)     -> +10
      6. default base                          -> +1

    No agent name or reference is hard-coded. The other-agent relevance
    boost uses the dynamic other_agent_ref and other_agent_name.
    """
    score = 0
    content = str(memory.get("content", ""))
    mem_type = memory.get("type", "")
    mem_id = memory.get("memory_id", "")

    # Tier 1: active goals
    for gid in active_goal_ids:
        if gid in content or gid in mem_id:
            score += 100
            break
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

    # Tier 3: visible messages or other agent (dynamic identities)
    for mid in visible_message_ids:
        if mid in content:
            score += 30
            break
    if other_agent_ref and other_agent_ref in content:
        score += 30
    elif other_agent_name and other_agent_name.lower() in content.lower():
        score += 30

    # Tier 4: human answers
    if mem_type == "human_answer":
        score += 20

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
    owner_agent_id: str = "",
    goals: list[dict] | None = None,
    position: str = "",
    visible_tiles: set[str] | None = None,
    visible_object_ids: set[str] | None = None,
    visible_message_ids: set[str] | None = None,
    relationship_event_memory_ids: set[str] | None = None,
    recent_cutoff_hb: int = 0,
    other_agent_ref: str = "",
    other_agent_name: str = "",
) -> tuple[list[dict], dict]:
    """Select a bounded subset of private memories for a model request.

    Returns (selected_memories, manifest) where manifest is a dict of metadata.
    Selection is deterministic for identical state and context.
    Uses dynamically provided other-agent identities — no hard-coded names.
    """
    ensured = _ensure_memory_ids(memories, owner_agent_id=owner_agent_id)
    active_goal_ids = {g["goal_id"] for g in (goals or []) if g.get("status") == "active"}
    scored: list[tuple[int, int, int, dict]] = []

    for i, mem in enumerate(ensured):
        score = _score_relevance(
            mem, active_goal_ids, position,
            visible_tiles or set(), visible_object_ids or set(),
            visible_message_ids or set(),
            relationship_event_memory_ids or set(),
            other_agent_ref=other_agent_ref,
            other_agent_name=other_agent_name,
        )
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
        "memory_id_derivation_version": _MEMORY_ID_DERIVATION_VERSION,
        "raw_private_memory_count": len(ensured),
        "selected_private_memory_ids": [m.get("memory_id", "") for m in selected],
        "selected_private_memory_count": len(selected),
        "selected_private_memory_character_count": total_chars,
        "summary_ids": [],
        "omitted_private_memory_count": len(ensured) - len(selected),
        "other_agent_private_memory_count_included": 0,
        "human_context_count": 0,
        "human_context_answered_ids": [],
        "human_context_unresolved_ids": [],
        "human_context_omitted_count": 0,
        "selection_reason_categories": {
            "active_goal_count": len(active_goal_ids),
            "position_relevant": position,
            "recent_cutoff_heartbeat": recent_cutoff_hb,
        },
        "canonical_selection_hash": _hash_canonical({
            "agent_id": agent_id,
            "derivation_version": _MEMORY_ID_DERIVATION_VERSION,
            "ids": [m.get("memory_id", "") for m in selected],
        }),
    }

    return selected, manifest


# ---------------------------------------------------------------------------
# Bounded Human Context Selection
# ---------------------------------------------------------------------------

_MAX_COMBINED_HUMAN_RECORDS = 4


def _score_human_context(
    question: dict,
    active_goal_ids: set[str],
) -> int:
    """Score a human-context record for deterministic selection."""
    score = 0
    qid = question.get("question_id", "")
    text = str(question.get("question", "")) + str(question.get("reason_for_asking", ""))
    for gid in active_goal_ids:
        if gid in text or gid in qid:
            score += 100
            break
    if question.get("status") == "pending":
        score += 10  # unresolved before answered
    return score


def select_human_context(
    answered_questions: list[dict],
    unresolved_questions: list[dict],
    active_goal_ids: set[str],
) -> tuple[list[dict], list[str], list[str], int]:
    """Select at most four combined answered and unresolved human-context records.

    Returns (selected_records, answered_ids, unresolved_ids, omitted_count).
    Selection is deterministic:
      1. connection to an active goal or capability;
      2. addressed agent ownership (pre-filtered by caller);
      3. unresolved before answered when both are equally relevant;
      4. recency (heartbeat);
      5. stable question ID tie-break.
    """
    scored: list[tuple[int, int, str, dict]] = []
    for q in answered_questions:
        s = _score_human_context(q, active_goal_ids)
        hb = q.get("heartbeat", 0)
        scored.append((-s, -hb, q.get("question_id", ""), q))
    for q in unresolved_questions:
        s = _score_human_context(q, active_goal_ids)
        hb = q.get("heartbeat", 0)
        scored.append((-s, -hb, q.get("question_id", ""), q))

    scored.sort(key=lambda x: (x[0], x[1], x[2]))

    selected = scored[:_MAX_COMBINED_HUMAN_RECORDS]
    omitted = scored[_MAX_COMBINED_HUMAN_RECORDS:]

    selected_records = [s[3] for s in selected]
    all_answered_ids = [s[3].get("question_id", "") for s in selected if s[3].get("status") == "answered"]
    all_unresolved_ids = [s[3].get("question_id", "") for s in selected if s[3].get("status") == "pending"]

    return selected_records, all_answered_ids, all_unresolved_ids, len(omitted)


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

    def semantic_commitment(self) -> str:
        """Canonical identity of the summary's semantic content.

        Excludes summary_id (itself derived from this commitment),
        created_at_utc and integrity_commitment so that semantically
        identical summaries produce the same commitment regardless of
        when they were created or whether an ID has been assigned.
        """
        material = {
            "semantic_commitment_version": "v1",
            "owner_agent_id": self.owner_agent_id,
            "covered_memory_ids": self.covered_memory_ids,
            "covered_heartbeat_range": self.covered_heartbeat_range,
            "summary": self.summary,
            "salient_entities": self.salient_entities,
            "related_goal_ids": self.related_goal_ids,
            "related_public_object_ids": self.related_public_object_ids,
            "related_message_ids": self.related_message_ids,
            "derivation_method": self.derivation_method,
            "source_commitment": self.source_commitment,
        }
        return _hash_canonical(material)

    def seal(self) -> MemorySummaryRecord:
        material = asdict(self)
        material.pop("integrity_commitment", None)
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


_ALLOWED_DERIVATION_METHODS = frozenset({
    "deterministic_stub",
    "deterministic_extractive",
})


def compute_summary_source_commitment(
    owner_agent_id: str,
    covered_raw_memories: list[dict],
) -> str:
    """Canonical one-shot source commitment for a summary.

    Both derivation and validation call this same function.  The input is a
    raw dict/list, not a pre-serialised string, so the hash is computed
    consistently.
    """
    return _hash_canonical({
        "memories": covered_raw_memories,
        "owner": owner_agent_id,
    })


def validate_summary_record(
    summary: MemorySummaryRecord,
    memory_list: list[dict],
) -> list[str]:
    """Validate one summary record independently of any summary store.

    Checks owner, covered IDs, raw-memory resolution, heartbeat range,
    source commitment, derivation allow-list, derived label, integrity
    commitment, and semantic-derived summary ID.
    Returns a list of error strings (empty = valid).
    """
    errors: list[str] = []
    if not summary.owner_agent_id:
        errors.append("owner_agent_id is required")
    if not summary.summary or not summary.summary.strip():
        errors.append("summary text must be non-empty")
    if len(summary.summary) > 2000:
        errors.append("summary text exceeds 2000 characters")
    if not summary.summary.startswith("[derived"):
        errors.append("summary text must be visibly labelled as derived")
    if not summary.covered_memory_ids:
        errors.append("covered_memory_ids is required")
    else:
        if len(summary.covered_memory_ids) != len(set(summary.covered_memory_ids)):
            errors.append("covered_memory_ids contains duplicates")
        if len(summary.covered_heartbeat_range) != 2:
            errors.append("covered_heartbeat_range must have exactly 2 values")
        if not memory_list:
            errors.append("memory_list is required for covered_memory_ids validation")
        else:
            ensured = _ensure_memory_ids(memory_list, owner_agent_id=summary.owner_agent_id)
            id_map = {m["memory_id"]: m for m in ensured}
            resolved: list[dict] = []
            for mid in summary.covered_memory_ids:
                if mid not in id_map:
                    errors.append(f"covered_memory_id {mid} not found in raw memories")
                else:
                    resolved.append(id_map[mid])
            if resolved:
                hbs = [m.get("heartbeat", 0) for m in resolved]
                expected_range = [min(hbs), max(hbs)]
                if summary.covered_heartbeat_range != expected_range:
                    errors.append(
                        f"covered_heartbeat_range {summary.covered_heartbeat_range} "
                        f"does not match raw evidence {expected_range}"
                    )
                expected_source = compute_summary_source_commitment(
                    summary.owner_agent_id, resolved
                )
                if not summary.source_commitment:
                    errors.append("source_commitment is required")
                elif summary.source_commitment != expected_source:
                    errors.append(
                        f"source_commitment mismatch: got {summary.source_commitment}, "
                        f"expected {expected_source}"
                    )
    if not summary.derivation_method:
        errors.append("derivation_method is required")
    elif summary.derivation_method not in _ALLOWED_DERIVATION_METHODS:
        errors.append(f"derivation_method '{summary.derivation_method}' not in allow-list")
    if not summary.integrity_commitment:
        errors.append("integrity_commitment is required")
    else:
        check = MemorySummaryRecord(
            summary_id=summary.summary_id,
            owner_agent_id=summary.owner_agent_id,
            covered_memory_ids=list(summary.covered_memory_ids),
            covered_heartbeat_range=list(summary.covered_heartbeat_range),
            summary=summary.summary,
            salient_entities=list(summary.salient_entities),
            related_goal_ids=list(summary.related_goal_ids),
            related_public_object_ids=list(summary.related_public_object_ids),
            related_message_ids=list(summary.related_message_ids),
            created_at_utc=summary.created_at_utc,
            derivation_method=summary.derivation_method,
            source_commitment=summary.source_commitment,
        ).seal()
        if check.integrity_commitment != summary.integrity_commitment:
            errors.append("integrity_commitment validation failed")
    # Semantic-derived summary ID check
    if summary.summary_id:
        expected_id = "sum-derived-" + summary.semantic_commitment()[:16]
        if summary.summary_id != expected_id:
            errors.append(
                f"summary_id {summary.summary_id} does not match "
                f"semantic-derived ID {expected_id}"
            )
    return errors


def validate_summary(
    summary: MemorySummaryRecord,
    memory_list: list[dict],
    existing_summaries: list[MemorySummaryRecord],
) -> list[str]:
    """Fail-closed validation for a summary before append.

    Composes validate_summary_record with duplicate-store checks.
    Returns a list of error strings (empty = valid).
    """
    errors = validate_summary_record(summary, memory_list)

    # Duplicate handling: compare semantic commitments
    for existing in existing_summaries:
        if existing.summary_id == summary.summary_id:
            if existing.semantic_commitment() == summary.semantic_commitment():
                pass  # semantically identical — idempotent reuse
            else:
                errors.append(f"duplicate summary_id with conflicting material: {summary.summary_id}")
            break

    return errors


def append_summary(
    store: FirstPairPersistenceStore,
    summary: MemorySummaryRecord,
    memory_list: list[dict] | None = None,
) -> dict:
    """Append a validated summary. Fail-closed: leaves store unchanged on error.

    Returns structured result:
      {"ok": bool, "summary_id": str, "status": "appended"|"reused"|"rejected",
       "errors": list[str]}
    """
    if not memory_list:
        return {"ok": False, "summary_id": summary.summary_id,
                "status": "rejected",
                "errors": ["memory_list is required"]}

    existing = load_summaries(store)
    candidate_sem = summary.semantic_commitment()

    # Check for idempotent reuse: semantically identical summary already exists.
    for exist in existing:
        if exist.summary_id == summary.summary_id:
            if exist.semantic_commitment() != candidate_sem:
                return {"ok": False, "summary_id": summary.summary_id,
                        "status": "rejected",
                        "errors": [f"duplicate summary_id with conflicting material: {summary.summary_id}"]}
            # Semantic match — validate BOTH sides before allowing reuse
            exist_errors = validate_summary_record(exist, memory_list)
            if exist_errors:
                return {"ok": False, "summary_id": summary.summary_id,
                        "status": "rejected",
                        "errors": [f"existing persisted summary failed integrity validation: {exist_errors[0]}"]}
            cand_errors = validate_summary_record(summary, memory_list)
            if cand_errors:
                return {"ok": False, "summary_id": summary.summary_id,
                        "status": "rejected", "errors": cand_errors}
            return {"ok": True, "summary_id": summary.summary_id,
                    "status": "reused", "errors": []}

    errors = validate_summary(summary, memory_list, existing)
    if errors:
        return {"ok": False, "summary_id": summary.summary_id,
                "status": "rejected", "errors": errors}

    existing.append(summary)
    save_summaries(store, existing)
    return {"ok": True, "summary_id": summary.summary_id,
            "status": "appended", "errors": []}


def derive_summaries_for_omitted(
    memory_list: list[dict],
    selected_ids: set[str],
    owner_agent_id: str,
    max_summaries: int = 4,
    max_chars: int = 4000,
) -> tuple[list[MemorySummaryRecord], list[str]]:
    """Deterministically derive extractive summaries for older omitted memories.

    Groups omitted memories by heartbeat ranges and produces concise factual
    excerpts. Returns (summaries, included_summary_ids). No emotions, beliefs
    or intentions are ascribed.
    """
    ensured = _ensure_memory_ids(memory_list, owner_agent_id=owner_agent_id)
    omitted = [m for m in ensured if m.get("memory_id", "") not in selected_ids]
    if not omitted:
        return [], []

    # Sort by heartbeat
    omitted.sort(key=lambda m: m.get("heartbeat", 0))

    summaries: list[MemorySummaryRecord] = []
    included_ids: list[str] = []
    total_chars = 0
    used_memory_ids: set[str] = set()

    for mem in omitted:
        if len(summaries) >= max_summaries:
            break
        mid = mem.get("memory_id", "")
        if mid in used_memory_ids:
            continue
        content = str(mem.get("content", ""))
        hb = mem.get("heartbeat", 0)
        mem_type = mem.get("type", "unknown")
        excerpt = content[:300]
        summary_text = f"[derived from heartbeat {hb} ({mem_type})] {excerpt}"
        if total_chars + len(summary_text) > max_chars:
            break
        covered_ids = [mid]
        covered_range = [hb, hb]
        summ = MemorySummaryRecord(
            summary_id="",  # placeholder — set below from semantic commitment
            owner_agent_id=owner_agent_id,
            covered_memory_ids=covered_ids,
            covered_heartbeat_range=covered_range,
            summary=summary_text,
            salient_entities=[],
            related_goal_ids=[],
            related_public_object_ids=[],
            related_message_ids=[],
            derivation_method="deterministic_extractive",
            source_commitment=compute_summary_source_commitment(
                owner_agent_id, [mem]
            ),
        )
        # Derive summary_id from full semantic commitment (no truncated content)
        sem = summ.semantic_commitment()
        summ.summary_id = f"sum-derived-{sem[:16]}"
        summ.seal()
        summaries.append(summ)
        included_ids.append(summ.summary_id)
        used_memory_ids.add(mid)
        total_chars += len(summary_text)

    return summaries, included_ids


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
) -> bool:
    """Idempotent append: when event_id already exists, do nothing.

    Returns True when the event was actually appended, False when skipped
    (duplicate).
    """
    events = load_relationship_events(store)
    for existing in events:
        if existing.event_id == event.event_id:
            return False
    events.append(event)
    save_relationship_events(store, events)
    return True


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

    Only validated persisted outcomes create ledger entries.
    Event includes the target message, object or movement commitment in the
    deterministic event-ID material so distinct same-heartbeat interactions
    do not collide.

    Recording conditions:
      - message_sent: successful persisted message to other agent or public.
      - co_location: successful move; actor and other actually co-located
        after persistence.
      - public_object_creation: successful creation; both agents co-located
        at that tile during that heartbeat.
      - inspect_other_object: successful inspection of an object whose
        creator_agent_id equals the other agent's persistent ID.

    Does NOT record:
      - creation while alone
      - inspection of the actor's own object
      - no_action, rejected actions, proposed actions
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

    event_type = valid_event_types[action_type]

    # --- Per-type semantic checks ---
    other_ref = "east_eve" if actor_ref == "east_adam" else "east_adam"

    if action_type == "create_public_object":
        # Only record when both agents are co-located at that tile
        actor_pos = outcome.get("tile_id") or world_state.tile_occupancy.get(actor_ref)
        other_pos = world_state.tile_occupancy.get(other_ref)
        if not actor_pos or not other_pos or actor_pos != other_pos:
            return None

    if action_type == "move":
        target = outcome.get("to")
        if not target:
            return None
        other_pos = world_state.tile_occupancy.get(other_ref)
        if target != other_pos:
            return None

    if action_type == "inspect_public_object":
        obj_id = outcome.get("target_object_id") or (outcome.get("object") or {}).get("object_id", "")
        if not obj_id:
            return None
        obj = world_state.public_objects.get(obj_id)
        if not obj or not isinstance(obj, dict):
            return None
        if obj.get("creator_agent_id") != other_agent_id:
            return None

    if action_type == "leave_public_message":
        recipient = outcome.get("recipient", "")
        if recipient not in (other_ref, other_agent_id, "all", "public"):
            return None

    # --- Build evidence references ---
    evidence_refs: list[str] = []
    if outcome.get("object_id"):
        evidence_refs.append(f"obj-{outcome['object_id']}")
    if outcome.get("message_id"):
        evidence_refs.append(f"msg-{outcome['message_id']}")
    if outcome.get("from") and outcome.get("to"):
        evidence_refs.append(f"move-{outcome['from']}-{outcome['to']}")
    if outcome.get("target_object_id"):
        evidence_refs.append(f"inspect-{outcome['target_object_id']}")

    # Include target commitment in event-ID material
    target_commitment = _hash_canonical({
        "action": action_type,
        "outcome": outcome,
    })[:16]

    event = RelationshipEventRecord(
        event_id=_hash_canonical({
            "actor": actor_agent_id,
            "hb": heartbeat_number,
            "type": action_type,
            "target": target_commitment,
        })[:16],
        heartbeat=heartbeat_number,
        actor_agent_id=actor_agent_id,
        other_agent_id=other_agent_id,
        event_type=event_type,
        public_evidence_references=evidence_refs,
        resulting_public_state_commitment=_hash_canonical({
            "action_type": action_type,
            "outcome": outcome,
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
    _initialize_questions_if_absent(store)
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


def _save_questions_raw(store: FirstPairPersistenceStore, questions: list[QuestionRecord]) -> None:
    """Internal unguarded write. Used ONLY by the signed creation transaction so
    it may add exactly one new id inside the lock. External callers must go
    through save_questions (guarded)."""
    store._atomic_write(
        store._path(_QUESTIONS_FILE),
        {"type": "questions_record", "schema_version": _PERSISTENCE_SCHEMA_VERSION, "data": [asdict(q) for q in questions]},
    )


def _initialize_questions_if_absent(store: FirstPairPersistenceStore) -> None:
    """Check-and-create questions.json under the SAME store lock, no overwrite.

    Initialization must NEVER overwrite an already-existing questions.json (which
    could erase a created/answered canonical question). It only creates the
    empty seed when the file is absent, and it participates in the common
    ``_store_lock`` so it cannot race a concurrent creation transaction.
    """
    with store._store_lock():
        qpath = store._path(_QUESTIONS_FILE)
        if qpath.exists():
            return  # never overwrite an existing canonical questions file
        store._atomic_write(
            qpath,
            {"type": "questions_record", "schema_version": _PERSISTENCE_SCHEMA_VERSION, "data": []},
        )


def _validate_question_ids(questions: list[QuestionRecord]) -> list[str]:
    """Fail-closed structural validation of a proposed question collection.

    Every record must have a non-empty string ``question_id``, and IDs must be
    unique in the collection. Designed so a malformed/coerced ID cannot smuggle
    through set-based comparison.
    """
    errors: list[str] = []
    seen: set[str] = set()
    for q in questions:
        qid = q.question_id
        if not isinstance(qid, str):
            errors.append(f"non_string_question_id:{qid!r}")
            continue
        if not qid:
            errors.append("empty_question_id")
            continue
        if qid in seen:
            errors.append(f"duplicate_question_id:{qid}")
            continue
        seen.add(qid)
    return errors


def _question_record_semantics(q: QuestionRecord) -> str:
    """Canonical bytes of a record's full semantic content (all fields)."""
    return _canonical_json(asdict(q))


def save_questions(store: FirstPairPersistenceStore, questions: list[QuestionRecord]) -> None:
    """Guarded public question save: NO new IDs, NO deletions, NO mutation.

    Fail-closed on the ordinary persistence path. A NEW_ID (present in the
    proposed list but absent from canonical state), a REMOVED existing id, and
    ANY content/status/answer/owner/binding difference on an existing id are all
    rejected. Generic save is therefore a no-op that may only succeed when the
    proposed collection is semantically identical to canonical state.

    Canonical creation happens ONLY inside the locked, signed
    ``create_authorized_question`` transaction; the only existing-id mutation
    path is the governed answer transaction.
    """
    result = save_questions_guarded(store, questions)
    if not result.get("ok"):
        raise ValueError(
            "save_questions rejected: " + "; ".join(result.get("errors", []))
        )


def save_questions_guarded(
    store: FirstPairPersistenceStore, questions: list[QuestionRecord]
) -> dict:
    """Guarded question save returning a structured result rather than raising.

    - NEW_ID  = present in proposed state AND absent from current canonical state
    - REMOVED = present in current canonical state AND absent from proposed state
    - MUTATED = an existing id whose record content differs from canonical state

    New IDs, removals, and ANY existing-id mutation are rejected. Generic save
    only succeeds when the proposed collection is semantically identical to the
    stored collection (i.e. it performs no mutation).
    """
    structural = _validate_question_ids(questions)
    if structural:
        return {"ok": False, "errors": structural}

    current = load_questions(store)
    current_by_id = {q.question_id: q for q in current}
    proposed_by_id = {q.question_id: q for q in questions}

    existing_ids = set(current_by_id)
    proposed_ids = set(proposed_by_id)

    new_ids = proposed_ids - existing_ids
    removed_ids = existing_ids - proposed_ids

    if new_ids:
        return {"ok": False, "errors": [f"unauthorized_new_id:{sorted(new_ids)}"]}
    if removed_ids:
        return {"ok": False, "errors": [f"unauthorized_deletion:{sorted(removed_ids)}"]}

    # Existing-id mutation check: any content difference is a governed mutation.
    mutated: list[str] = []
    for qid in sorted(existing_ids & proposed_ids):
        if _question_record_semantics(proposed_by_id[qid]) != _question_record_semantics(current_by_id[qid]):
            mutated.append(qid)
    if mutated:
        return {"ok": False, "errors": [
            f"existing_question_mutation_requires_governed_transaction:{sorted(mutated)}"
        ]}

    # Semantically identical -> no mutation needed.
    return {"ok": True}


def question_requires_creation_receipt(
    store: FirstPairPersistenceStore, existing_question_id: str
) -> bool:
    """Grandfather rule: an already-persisted question never requires a receipt.

    The authority requirement applies to NEW IDs (present in a proposed state and
    absent from canonical state at the start of a write). An ID that already
    exists canonically — including the historical ``q1-habitat-structure`` — is
    not a new addition and therefore requires no creation receipt, and no
    retroactive receipt/signature is synthesized.
    """
    current = load_questions(store)
    present = any(q.question_id == existing_question_id for q in current)
    # Existing IDs do not require a receipt (grandfather); only NEW additions do.
    return not present


def _receipt_path(store: FirstPairPersistenceStore, auth_id: str, stage: str) -> Path:
    return store._receipt_dir() / f"auth-{auth_id}.{stage}.json"


# --- Signed answer authority receipts ---

def answer_receipt_path(store: FirstPairPersistenceStore, authorization_id: str) -> Path:
    """Dedicated consumed-answer-authorization receipt path (NOT provenance)."""
    return store._answer_receipt_dir() / f"auth-{authorization_id}.consumed.json"


def write_answer_consumed_receipt(
    store: FirstPairPersistenceStore,
    *,
    authorization_id: str,
    question_id: str,
    asking_agent_id: str,
    formatted_answer_hash: str,
    signed_envelope: dict,
    consumed_at_utc: str,
) -> None:
    """Persist the FULL SIGNED answer-authorization envelope as the authority
    receipt. The receipt's authority derives from the valid signature contained
    in ``signed_envelope``; the receipt itself is not secret.

    This MUST be called only AFTER successful cryptographic verification of
    ``signed_envelope``. It is not a generic authority grant.
    """
    store._answer_receipt_dir().mkdir(parents=True, exist_ok=True)
    store._atomic_write(
        answer_receipt_path(store, authorization_id),
        {
            "authorization_id": authorization_id,
            "question_id": question_id,
            "asking_agent_id": asking_agent_id,
            "formatted_answer_hash": formatted_answer_hash,
            "consumed_at_utc": consumed_at_utc,
            "signed_envelope": signed_envelope,
        },
    )


def load_answer_consumed_receipt(
    store: FirstPairPersistenceStore, authorization_id: str
) -> dict | None:
    """Read the consumed answer-authorization receipt (best-effort)."""
    path = answer_receipt_path(store, authorization_id)
    if not path.exists():
        return None
    try:
        return store._read_json(path)
    except OSError:
        return None


def _load_public_keys() -> dict[str, bytes] | None:
    """Load the trusted operator public key(s) from the ENV trust root ONLY.

    Production trust = ``GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX``. This is
    the sole authorized trust source. There is NO source-tree key-file fallback
    and NO caller-supplied key accepted here.

    Returns ``None`` when the env var is absent (absence fails closed).
    Malformed material raises ``ValueError`` (a clean, explicit fail-closed
    signal) — never silently yields an empty or bogus key.
    """

    keys: dict[str, bytes] = {}
    env_hex = os.environ.get("GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX", "").strip()
    if not env_hex:
        return None
    try:
        raw = bytes.fromhex(env_hex)
    except ValueError as exc:
        raise ValueError("malformed_operator_public_key_env") from exc
    if len(raw) != 32:
        raise ValueError("malformed_operator_public_key_env")
    keys["opk-" + hashlib.sha256(raw).hexdigest()[:16]] = raw
    return keys


def create_authorized_question(
    store: FirstPairPersistenceStore,
    *,
    authorization: dict,
) -> dict:
    """Store-owned, locked recoverable transaction for signed question-creation.

    Trust resolves ONLY from the process env ``GENESIS_FIRST_PAIR_OPERATOR_PUBLIC_KEY_HEX``.
    No caller parameter or envelope field can select the verification key.

    NOT atomic in the cross-file sense: the transaction builds durable evidence
    in stages (intent receipt → canonical question → applied marker → provenance)
    and recovers deterministically from any crash point via the intent/applied
    receipts. This is a *locked recoverable transaction*.

    Authority contract (explicit):
      - signed authorization + intent + canonical matching question + applied
        marker establish that the authorization was consumed and the canonical
        creation was applied (the applied marker is the consumption gate).
      - ``single_question_create_consumed`` provenance is derived audit evidence
        and is recoverable/idempotent (never left stranded when applied exists).

    Recovery cases (all under the shared store lock):

      CASE 1  intent absent, applied absent, question absent → normal create
      CASE 2  intent present, applied absent, question absent → resume same txn
      CASE 3  intent present, applied absent, question present + exact material
              match → finalize the SAME transaction (write applied + provenance)
      CASE 4  intent present, applied absent, question present but MISMATCH →
              fail closed (ambiguous/corrupt)
      CASE 5  applied present → ensure provenance, then already-consumed result
    """
    from backend.world import local_single_question_create as _create

    # --- Resolve trust from ENV only. No caller key, no envelope key. ---
    try:
        keys = _load_public_keys()
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if not keys:
        return {"ok": False, "error": "operator_public_key_unconfigured"}
    verify_key: bytes = next(iter(keys.values()))

    auth_id = _create.authorization_id(authorization)
    question_id = authorization.get("question_id")
    if not isinstance(question_id, str) or not question_id:
        return {"ok": False, "error": "invalid_question_id"}
    # Bound commitment of the authorized material, for recovery identity.
    auth_material_hash = material_commitment(
        pair_id=authorization.get("pair_id"),
        asking_agent_id=authorization.get("asking_agent_id"),
        question_id=question_id,
        related_goal_id=authorization.get("related_goal_id"),
        question=authorization.get("question"),
        reason_for_asking=authorization.get("reason_for_asking"),
        requested_human_capability=authorization.get("requested_human_capability"),
        urgency=authorization.get("urgency"),
    )

    with store._store_lock():
        intent_path = _receipt_path(store, auth_id, "intent")
        applied_path = _receipt_path(store, auth_id, "applied")

        # 1. expiry / timestamp enforcement (fail closed before any write).
        expiry_ok, expiry_err = _create.validate_authorization_times(authorization)
        if not expiry_ok:
            return {"ok": False, "error": expiry_err}

        # 2. verify signature BEFORE any receipt is created.
        ok, err = _create.verify_question_creation_authorization(verify_key, authorization)
        if not ok:
            return {"ok": False, "error": err or "invalid_signature"}

        # 5. already fully consumed? Under lock, repair any missing derived
        #    provenance idempotently, then report consumed.
        if applied_path.exists():
            _ensure_create_provenance(store, auth_id, question_id)
            return {
                "ok": False,
                "error": "authorization_already_consumed",
                "recovered": True,
            }

        # Recovery inspection: load canonical question state + prior intent.
        existing = load_questions(store)
        existing_q = next((q for q in existing if q.question_id == question_id), None)
        prior_intent = None
        if intent_path.exists():
            try:
                prior_intent = store._read_json(intent_path)
            except OSError:
                prior_intent = None

        # CASE 5 (already-consumed) handled above.
        # CASE 2/3: an intent already exists for THIS authorization.
        if prior_intent is not None:
            # The intent must belong to THIS exact authorization.
            if prior_intent.get("authorization_id") != auth_id:
                return {"ok": False, "error": "intent_authorization_mismatch"}
            if prior_intent.get("material_commitment") != auth_material_hash:
                return {"ok": False, "error": "intent_authorization_mismatch"}

        # CASE 1/2: question absent -> normal create or resume.
        if existing_q is None:
            record = _build_question_record(authorization, question_id, auth_id)
            intent = {
                "authorization_id": auth_id,
                "public_key_id": _create.public_key_id(verify_key),
                "question_id": question_id,
                "material_commitment": auth_material_hash,
                "consumed_at_utc": datetime.now(timezone.utc).isoformat(),
                "signed_authorization": authorization,
            }
            store._receipt_dir().mkdir(parents=True, exist_ok=True)
            store._atomic_write(intent_path, intent)
            _save_questions_raw(store, existing + [record])
            store._atomic_write(
                applied_path,
                {
                    "authorization_id": auth_id,
                    "question_id": question_id,
                    "applied_at_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
            _ensure_create_provenance(store, auth_id, question_id)
            return {
                "ok": True,
                "authorization_id": auth_id,
                "question_id": question_id,
                "record": asdict(record),
                "audit_trail_incomplete": False,
            }

        # Question already present canonically.
        # CASE 3: present + prior intent + exact material match -> finalize same txn.
        if prior_intent is not None and _question_material_matches(existing_q, authorization):
            store._atomic_write(
                applied_path,
                {
                    "authorization_id": auth_id,
                    "question_id": question_id,
                    "applied_at_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
            _ensure_create_provenance(store, auth_id, question_id)
            return {
                "ok": True,
                "authorization_id": auth_id,
                "question_id": question_id,
                "recovered": True,
                "record": asdict(existing_q),
                "audit_trail_incomplete": False,
            }

        # CASE 4: question present but no matching intent/material -> ambiguous.
        if prior_intent is not None:
            return {"ok": False, "error": "ambiguous_recovery_question_mismatch"}
        # No prior intent but question already exists -> duplicate id.
        return {"ok": False, "error": "question_id_already_exists"}


def _build_question_record(
    authorization: dict, question_id: str, auth_id: str
) -> QuestionRecord:
    material = canonicalize_proposal_material(
        pair_id=authorization.get("pair_id"),
        asking_agent_id=authorization.get("asking_agent_id"),
        question_id=question_id,
        related_goal_id=authorization.get("related_goal_id"),
        question=authorization.get("question"),
        reason_for_asking=authorization.get("reason_for_asking"),
        requested_human_capability=authorization.get("requested_human_capability"),
        urgency=authorization.get("urgency"),
    )
    return QuestionRecord(
        question_id=material["question_id"],
        asking_agent_id=material["asking_agent_id"],
        heartbeat=0,
        question=material["question"],
        reason_for_asking=material["reason_for_asking"],
        related_goal_id=material["related_goal_id"],
        requested_human_capability=material["requested_human_capability"],
        urgency=material["urgency"],
        status="pending",
        provenance={"creation_authorization_id": auth_id},
    )


def _question_material_matches(q: QuestionRecord, authorization: dict) -> bool:
    return (
        q.question_id == authorization.get("question_id")
        and q.asking_agent_id == authorization.get("asking_agent_id")
        and q.question == authorization.get("question")
        and q.reason_for_asking == authorization.get("reason_for_asking")
        and q.related_goal_id == authorization.get("related_goal_id")
        and q.requested_human_capability == authorization.get("requested_human_capability")
        and q.urgency == authorization.get("urgency")
    )


def _provenance_records(store: FirstPairPersistenceStore) -> list[dict]:
    """Read the JSON-lines provenance ledger (best-effort, tolerant of torn lines)."""
    path = store._path(_PROVENANCE_FILE)
    if not path.exists():
        return []
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _ensure_create_provenance(
    store: FirstPairPersistenceStore, auth_id: str, question_id: str
) -> None:
    """Idempotently ensure EXACTLY ONE ``single_question_create_consumed`` event.

    Stable identity = (action == "single_question_create_consumed") AND
    (detail.authorization_id == auth_id) AND (detail.question_id == question_id).
    Repeated calls do not append duplicate events.
    """
    action = "single_question_create_consumed"
    for r in _provenance_records(store):
        if r.get("action") == action and r.get("detail", {}).get("authorization_id") == auth_id and r.get("detail", {}).get("question_id") == question_id:
            return  # already present exactly once
    store._append_provenance(action, {"authorization_id": auth_id, "question_id": question_id})


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
    """LEGACY / DEPRECATED. No longer a production mutation path.

    Retained only for import compatibility. It MUST NOT write status or answer,
    MUST NOT call generic save, and MUST NOT mutate canonical question state.
    The governed answer path is
    ``local_single_question_answer.apply_question_answer`` (which itself uses the
    narrow ``governed_answer_transaction``).
    """
    return {
        "ok": False,
        "error": "mark_question_answered_deprecated",
        "question_id": question_id,
        "detail": (
            "Legacy answer mutation is disabled; use the governed answer seam "
            "(local_single_question_answer.apply_question_answer)."
        ),
        "questions_mutated": 0,
    }


def governed_answer_transaction(
    store: FirstPairPersistenceStore,
    *,
    question_id: str,
    answer_material: str,
    operator_provenance: str = "",
    authorized_agent_id: str,
    authorization_id: str,
) -> dict:
    """Narrow, locked, cryptographically-reverified answer mutation.

    The ONLY existing-id mutation the store permits. Its authority predicate is
    the VALID SIGNED answer envelope stored in the consumed receipt — never a
    provenance line and never caller-asserted strings. Under the SAME store lock
    as ``create_authorized_question`` it:

      1. re-reads canonical questions and locates the exact question_id
      2. requires status == pending
      3. requires canonical asking_agent_id == authorized_agent_id
      4. loads the consumed answer-authorization RECEIPT for authorization_id
      5. obtains the env-only operator public key (fail-closed if absent)
      6. cryptographically re-verifies the STORED signed envelope's Ed25519
         signature against that trust root
      7. recomputes authorization_id from the signed material and requires an
         exact match (never trusts a mere label)
      8. verifies answer-specific schema/domain/action and max_writes == 1
      9. verifies issued/expires time validity (production "now" not caller-set)
     10. verifies the signed question_id/asking_agent_id/formatted_answer_hash
         match the canonical/requested question, agent, and the answer being
         applied
     11. only then performs pending -> answered

    A forged provenance line grants ZERO authority (provenance is not consulted).
    A forged receipt whose stored envelope has an invalid signature grants ZERO
    authority. A replay of another question/agent/answer's authorization fails.
    """
    if not isinstance(question_id, str) or not question_id:
        return {"ok": False, "error": "invalid_question_id"}
    if not isinstance(answer_material, str) or not answer_material:
        return {"ok": False, "error": "invalid_answer"}
    if not isinstance(authorized_agent_id, str) or not authorized_agent_id:
        return {"ok": False, "error": "missing_authorized_agent_id"}
    if not isinstance(authorization_id, str) or not authorization_id:
        return {"ok": False, "error": "missing_authorization_id"}

    # The answer-material commitment MUST equal the answer module's binding hash
    # (identical canonical JSON: sort_keys, compact separators, ensure_ascii=False).
    answer_hash = _hash_canonical({"answer_material": answer_material})

    with store._store_lock():
        from backend.world import local_single_question_answer as _answer

        # 4. Load the consumed answer-authorization RECEIPT (authority evidence).
        receipt = load_answer_consumed_receipt(store, authorization_id)
        if receipt is None:
            return {"ok": False, "error": "answer_authorization_receipt_missing"}
        signed_envelope = receipt.get("signed_envelope")
        if not isinstance(signed_envelope, dict):
            return {"ok": False, "error": "answer_authorization_receipt_corrupt"}

        # 5. Obtain the env-only operator public key (fail closed).
        try:
            keys = _load_public_keys()
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if not keys:
            return {"ok": False, "error": "operator_public_key_unconfigured"}
        verify_key: bytes = next(iter(keys.values()))

        # 6. Cryptographically re-verify the STORED signed envelope.
        sig_ok, sig_err = _answer.verify_question_answer_authorization(verify_key, signed_envelope)
        if not sig_ok:
            return {"ok": False, "error": sig_err or "invalid_answer_signature"}

        # 9. Time validity (production "now" is internal, not caller-controlled).
        time_ok, time_err = _answer.validate_authorization_times(signed_envelope)
        if not time_ok:
            return {"ok": False, "error": time_err}

        # 7. Recompute authorization_id from the signed material (never trust a
        #    label). Must equal both the caller arg and the receipt's own label.
        recomputed_id = _answer.authorization_id(signed_envelope)
        if recomputed_id != authorization_id:
            return {"ok": False, "error": "answer_authorization_id_mismatch"}
        if receipt.get("authorization_id") != authorization_id:
            return {"ok": False, "error": "answer_authorization_id_mismatch"}

        # 10. Signed bindings must match canonical/requested material EXACTLY.
        if signed_envelope.get("question_id") != question_id:
            return {"ok": False, "error": "answer_authorization_question_mismatch"}
        if signed_envelope.get("asking_agent_id") != authorized_agent_id:
            return {"ok": False, "error": "answer_authorization_agent_mismatch"}
        if signed_envelope.get("formatted_answer_hash") != answer_hash:
            return {"ok": False, "error": "answer_authorization_answer_mismatch"}

        # 1/2/3. Canonical state checks, re-read AFTER the signature gate.
        questions = load_questions(store)
        target = next((q for q in questions if q.question_id == question_id), None)
        if target is None:
            return {"ok": False, "error": "question_not_found"}
        # Owner binding is mandatory, never skippable.
        if target.asking_agent_id != authorized_agent_id:
            return {"ok": False, "error": "question_agent_mismatch"}
        if target.status != "pending":
            return {"ok": False, "error": "question_already_answered"}

        # 11. Immutable-field spine is preserved by construction: we mutate only
        # the transition fields below, never question text/owner/goal/capability/
        # urgency/reason/asked_at/identity.
        target.status = "answered"
        target.provenance["answer"] = answer_material
        target.provenance["answered_at_utc"] = datetime.now(timezone.utc).isoformat()
        target.provenance["operator_provenance"] = operator_provenance
        target.provenance["answer_authorization_id"] = authorization_id

        _save_questions_raw(store, questions)

    return {
        "ok": True,
        "question_id": question_id,
        "asking_agent_id": target.asking_agent_id,
        "status": "answered",
        "record": asdict(target),
    }


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

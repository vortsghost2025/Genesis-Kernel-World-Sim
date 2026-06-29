'''World event candidate mapper for Phase 10L (pure, no side effects).

Provides functions that translate executor/decision results into candidate ledger events
that satisfy backend.world.world_event_ledger.validate_event.

All functions return a dictionary suitable for validation; they never write files.
'''

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

# Import validation helper and allowed categories (no runtime objects)
from backend.world.world_event_ledger import ALLOWED_EVIDENCE_CATEGORIES, ALLOWED_CLAIM_SCOPES


def _make_event(*, actor_id: str, action_type: str, summary: str, claim_scope: str, evidence_refs: List[Dict[str, Any]], lens: str, territory_ref: str = "", before_ref: str = "", after_ref: str = "", affected_agents: Optional[List[str]] = None, artifacts_created_or_changed: Optional[List[Any]] = None, relationship_delta: Optional[List[Any]] = None, consequence: str = "", verification_status: str = "candidate", tick: Optional[int] = None, timestamp_utc: Optional[str] = None) -> Dict[str, Any]:
    """Create minimal event dict required by ``validate_event``.

    The function does not perform validation; callers should invoke ``validate_event``.
    """
    event_id = str(uuid.uuid4())
    schema_version = "10L.1"
    if timestamp_utc is None:
        timestamp_utc = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "event_id": event_id,
        "schema_version": schema_version,
        "actor_id": actor_id,
        "lens": lens,
        "territory_ref": territory_ref,
        "action_type": action_type,
        "summary": summary,
        "evidence_refs": evidence_refs,
        "claim_scope": claim_scope,
        "before_ref": before_ref,
        "after_ref": after_ref,
        "affected_agents": affected_agents or [],
        "artifacts_created_or_changed": artifacts_created_or_changed or [],
        "relationship_delta": relationship_delta or [],
        "consequence": consequence,
        "verification_status": verification_status,
        "tick": tick,
        "timestamp_utc": timestamp_utc,
    }


def infer_lens(actor_id: str) -> str:
    """Infer the lens (region) from an actor ID.

    Returns the part before the first underscore, or the whole ID if no underscore.
    """
    if "_" in actor_id:
        return actor_id.split("_")[0]
    return actor_id


def candidate_from_observe_result(actor_id: str, action_text: str, result: dict, *, tick: Optional[int] = None, timestamp_utc: Optional[str] = None) -> dict:
    """Map an ``observe`` executor result into a candidate event."""
    lens = infer_lens(actor_id)
    territory_ref = result.get("territory_ref", "")
    evidence_used = result.get("evidence_used", [])
    evidence_refs: List[Dict[str, Any]] = []
    for ev in evidence_used:
        if isinstance(ev, dict) and ev.get("category") in ALLOWED_EVIDENCE_CATEGORIES:
            evidence_refs.append(ev)
    claim_scope = "observed" if any(ev.get("category") == "observed_world_fact" for ev in evidence_refs) else "hypothesis"
    return _make_event(actor_id=actor_id, action_type="observe", summary=action_text, claim_scope=claim_scope, evidence_refs=evidence_refs, lens=lens, territory_ref=territory_ref, before_ref="", after_ref="", tick=tick, timestamp_utc=timestamp_utc)


def candidate_from_rest_result(actor_id: str, decision: dict, result: Optional[dict] = None, *, tick: Optional[int] = None, timestamp_utc: Optional[str] = None) -> dict:
    """Map a ``rest`` decision (and optional result) into a candidate event."""
    lens = infer_lens(actor_id)
    action_type = decision.get("action_type", "rest")
    summary = decision.get("summary", f"REST decision {action_type}")
    evidence_refs: List[Dict[str, Any]] = []
    if isinstance(result, dict):
        evidence_refs = [ev for ev in result.get("evidence_used", []) if isinstance(ev, dict) and ev.get("category") in ALLOWED_EVIDENCE_CATEGORIES]
    claim_scope = "observed" if any(ev.get("category") == "observed_world_fact" for ev in evidence_refs) else "hypothesis"
    consequence = decision.get("block_reason", "")
    return _make_event(actor_id=actor_id, action_type=action_type, summary=summary, claim_scope=claim_scope, evidence_refs=evidence_refs, lens=lens, territory_ref=decision.get("territory_ref", ""), before_ref="", after_ref="", consequence=consequence, tick=tick, timestamp_utc=timestamp_utc)


def candidate_from_gather_result(actor_id: str, action_text: str, result: dict, *, tick: Optional[int] = None, timestamp_utc: Optional[str] = None) -> Optional[dict]:
    """Map a ``gather`` result into a mutating candidate event.

    Returns ``None`` for rejected or unsafe gathers.
    """
    if not result.get("ok"):
        return None
    before_md5 = result.get("before_md5")
    after_md5 = result.get("after_md5")
    if not before_md5 or not after_md5:
        return None
    # Disallow unsafe textual hints
    unsafe_phrases = ["hidden water source", "dove", "lamb", "animal", "movement", "guide", "guiding"]
    lowered = action_text.lower()
    if any(p in lowered for p in unsafe_phrases):
        return None
    lens = infer_lens(actor_id)
    evidence_refs: List[Dict[str, Any]] = []
    for ev in result.get("evidence_used", []):
        if isinstance(ev, dict) and ev.get("category") in ALLOWED_EVIDENCE_CATEGORIES:
            evidence_refs.append(ev)
    claim_scope = "observed"
    consequence = result.get("consequence", "")
    before_ref = f"md5:{before_md5}"
    after_ref = f"md5:{after_md5}"
    return _make_event(actor_id=actor_id, action_type="gather", summary=action_text, claim_scope=claim_scope, evidence_refs=evidence_refs, lens=lens, territory_ref=result.get("territory_ref", ""), before_ref=before_ref, after_ref=after_ref, consequence=consequence, tick=tick, timestamp_utc=timestamp_utc)


def candidate_from_whisper_decision(actor_id: str, decision: dict, *, target_resolved: bool, target_actor_id: Optional[str] = None, delivered: bool = False, dry_run: bool = True, tick: Optional[int] = None, timestamp_utc: Optional[str] = None) -> dict:
    """Map a ``whisper`` (speech) decision into a candidate event."""
    lens = infer_lens(actor_id)
    summary = decision.get("content", decision.get("message", "whisper"))
    evidence_refs: List[Dict[str, Any]] = []
    for ev in decision.get("evidence_used", []):
        if isinstance(ev, dict) and ev.get("category") in ALLOWED_EVIDENCE_CATEGORIES:
            evidence_refs.append(ev)
    if not any(ev.get("category") == "agent_speech" for ev in evidence_refs):
        evidence_refs.append({"category": "agent_speech", "reference": "whisper"})
    claim_scope = "speech"
    affected = []
    if target_resolved and target_actor_id:
        affected.append(target_actor_id)
    consequence = "delivered" if delivered else ""
    return _make_event(actor_id=actor_id, action_type="whisper", summary=summary, claim_scope=claim_scope, evidence_refs=evidence_refs, lens=lens, territory_ref=decision.get("territory_ref", ""), before_ref="", after_ref="", affected_agents=affected, consequence=consequence, tick=tick, timestamp_utc=timestamp_utc)


def candidate_from_goal_decision(actor_id: str, decision: dict, *, tick: Optional[int] = None, timestamp_utc: Optional[str] = None) -> dict:
    """Map a ``goal`` decision into a candidate event.

    Uses ``new_goal`` if present; otherwise falls back to ``goal``.
    """
    lens = infer_lens(actor_id)
    summary = decision.get("new_goal", decision.get("goal", "set goal"))
    evidence_refs: List[Dict[str, Any]] = []
    for ev in decision.get("evidence_used", []):
        if isinstance(ev, dict) and ev.get("category") in ALLOWED_EVIDENCE_CATEGORIES:
            evidence_refs.append(ev)
    claim_scope = "observed" if any(ev.get("category") == "observed_world_fact" for ev in evidence_refs) else "hypothesis"
    return _make_event(actor_id=actor_id, action_type="goal", summary=summary, claim_scope=claim_scope, evidence_refs=evidence_refs, lens=lens, territory_ref=decision.get("territory_ref", ""), before_ref="", after_ref="", tick=tick, timestamp_utc=timestamp_utc)


def candidate_from_help_decision(actor_id: str, decision: dict, *, tick: Optional[int] = None, timestamp_utc: Optional[str] = None) -> dict:
    """Map a ``help`` request decision into a candidate event (speech)."""
    lens = infer_lens(actor_id)
    summary = decision.get("content", decision.get("request", "help request"))
    evidence_refs: List[Dict[str, Any]] = []
    for ev in decision.get("evidence_used", []):
        if isinstance(ev, dict) and ev.get("category") in ALLOWED_EVIDENCE_CATEGORIES:
            evidence_refs.append(ev)
    if not any(ev.get("category") == "agent_speech" for ev in evidence_refs):
        evidence_refs.append({"category": "agent_speech", "reference": "help"})
    claim_scope = "speech"
    return _make_event(actor_id=actor_id, action_type="help", summary=summary, claim_scope=claim_scope, evidence_refs=evidence_refs, lens=lens, territory_ref=decision.get("territory_ref", ""), before_ref="", after_ref="", tick=tick, timestamp_utc=timestamp_utc)

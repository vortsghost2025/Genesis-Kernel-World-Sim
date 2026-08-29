"""Noncanonical question proposal semantics for the First Pair.

A ``QuestionProposal`` carries the EXACT material a model/runtime routes
produce when an agent wants to ask a question. A proposal is deliberately
NONCANONICAL: it is never a persisted ``QuestionRecord``, it grants no
authority, and it cannot trigger canonical creation on its own.

Canonical question creation is gated behind a signed operator authorization
(authority) consumed by the governed store transaction (see
``first_pair_persistence.create_authorized_question``). This module only
describes proposal material and its deterministic canonicalization, so that an
operator can review and sign the exact bytes that were proposed.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from typing import Any


# The fields an authorization binds. Order here is presentation only; the
# canonical bytes are produced with sort_keys=True.
_AUTHORIZED_FIELDS = (
    "pair_id",
    "asking_agent_id",
    "question_id",
    "related_goal_id",
    "question",
    "reason_for_asking",
    "requested_human_capability",
    "urgency",
)


def _normalize_free_text(value: str) -> str:
    """NFC-normalize and strip a free-text field; interior whitespace preserved."""
    return unicodedata.normalize("NFC", value.strip())


@dataclass
class QuestionProposal:
    """A noncanonical, authority-free question proposal."""

    question_id: str
    asking_agent_id: str
    related_goal_id: str | None
    question: str
    reason_for_asking: str
    requested_human_capability: str
    urgency: str
    pair_id: str = "genesis-first-pair"

    def canonical_material(self) -> dict[str, Any]:
        """Return the normalized, authorized material as an ordered-able dict."""
        return {
            "pair_id": self.pair_id,
            "asking_agent_id": self.asking_agent_id,
            "question_id": self.question_id,
            "related_goal_id": self.related_goal_id,
            "question": _normalize_free_text(self.question),
            "reason_for_asking": _normalize_free_text(self.reason_for_asking),
            "requested_human_capability": self.requested_human_capability,
            "urgency": self.urgency,
        }


def canonicalize_proposal_material(**fields: Any) -> dict[str, Any]:
    """Deterministically normalize the exact authorized fields.

    Accepts the same keyword fields an authorization binds. Free text is
    NFC-normalized and stripped; interior whitespace is preserved. Returns a
    dict of the normalized material (ordering-independent; canonical bytes are
    produced separately with sort_keys=True).
    """
    normalized = {}
    for key in _AUTHORIZED_FIELDS:
        value = fields.get(key)
        if key in ("question", "reason_for_asking") and isinstance(value, str):
            value = _normalize_free_text(value)
        normalized[key] = value
    return normalized


def canonicalize_proposal_json(material: dict[str, Any]) -> str:
    """Canonical JSON bytes-source for a material dict (sort_keys, tight separators)."""
    return json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def material_commitment(**fields: Any) -> str:
    """SHA-256 commitment over the canonical bytes of the authorized material.

    Any material change (including whitespace/Unicode drift that survives
    normalization) changes the commitment, which invalidates an operator
    signature bound to the prior bytes.
    """
    material = canonicalize_proposal_material(**fields)
    canonical = canonicalize_proposal_json(material)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
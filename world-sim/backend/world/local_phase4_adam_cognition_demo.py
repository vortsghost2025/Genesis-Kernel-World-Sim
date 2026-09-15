"""Phase 4: one bounded Adam cognition step (in-memory / report only, zero writes).

Runs the real ``ModelCognitionBackend.observe_and_orient`` pipeline against a
goal-aware Adam context built from the canonical persisted goal, using the
documented ``with_client`` injection point (no real provider transport is
attempted). The fake OpenAI-compatible client returns a deterministic, valid
cognition payload for Adam; the output is validated by the existing model
validation and returned as a real ``CognitionOutput``.

The result is classified into the existing repo's semantic types only (see
the printed CLASSIFICATION block): ACTION/INTENTION, GOAL state, memory
writes, questions. Nothing is written to canonical or to any store.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# run from world-sim/
sys.path.insert(0, ".")

from backend.world.first_pair_cognition_model import (
    ModelCognitionBackend,
    ProviderConfig,
    validate_model_output,
)
from backend.world.first_pair_persistence import FirstPairPersistenceStore
from backend.world.local_goal_cognition_input import build_goal_cognition_context

ADAM = "genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d"
EVE = "genesis-agent-1864f0bed1b4c501fa76067186115cc42c43b77992ec8cffb4b2801984743211"

ROOT = Path(".runtime/first-pair")

# Canonical birth candidate (deterministic identities from 10IC).
CANDIDATE = {
    "ok": True,
    "adam_identity": {"agent_id": ADAM, "canonical_agent_ref": "east_adam", "identity_valid": True},
    "eve_identity": {"agent_id": EVE, "canonical_agent_ref": "east_eve", "identity_valid": True},
}

# Deterministic, schema-valid cognition payload for Adam (bounded: no_action,
# no goal state change, no memory candidates, no questions — pure observation).
VALID_OUTPUT = {
    "observation_summary": "I perceive the shared starting habitat from the public-start-adam tile. Movement is not permitted in this first habitat.",
    "self_model_update": None,
    "goal_updates": [],
    "proposed_action": {"action_type": "no_action"},
    "memory_candidates": [],
    "questions_for_humans": [],
    "uncertainty": "low",
    "decision_summary": "Continue observing the shared starting habitat without attempting movement.",
    "confidence": 0.92,
}


class _Choice:
    def __init__(self, content: str):
        self.message = type("M", (), {"content": content})()


class _Completions:
    calls = 0

    def create(self, **kwargs):
        self.__class__.calls += 1
        return type("R", (), {"choices": [_Choice(json.dumps(VALID_OUTPUT))]})()


class _Chat:
    def __init__(self):
        self.completions = _Completions()


class FakeClient:
    """OpenAI-compatible fake: in-memory only, no network."""

    def __init__(self):
        self.chat = _Chat()


def main():
    store = FirstPairPersistenceStore(ROOT)
    ctx = build_goal_cognition_context(
        store, birth_candidate=CANDIDATE, target_agent_ref="east_adam", heartbeat_number=1
    )
    print("GOAL_DRIVES_CONTEXT=", len(ctx.goals) == 1 and ctx.goals[0]["description"] == "Understand the shared starting habitat.")
    print("MOVEMENT_ALLOWED=", ctx.habitat_movement_allowed, "(must be False)")

    client = FakeClient()
    # ProviderConfig(provider_type, base_url, model, api_key) — positional per
    # resolve_provider. The fake client makes the config inert (no network).
    config = ProviderConfig("fake", "http://fake.invalid/unused", "deterministic-fake", None)
    backend = ModelCognitionBackend.with_client("east_adam", client, config)
    out = backend.observe_and_orient(ctx)

    print("TRANSPORT_CALLS=", _Completions.calls, "(must be 1: no repair needed)")
    print("OUTPUT_TYPE=", type(out).__name__)
    print("ACTION_TYPE=", (out.action or {}).get("action_type"))
    print("GOAL_UPDATES=", out.goal_updates)
    print("QUESTIONS_RAISED=", out.questions_raised)
    print("MEMORY_WRITE=", out.memory_write)
    print("CONFIDENCE=", out.confidence)

    # Classification into existing semantic types only
    print("--- CLASSIFICATION (existing repo types only) ---")
    intention = out.decision_summary or (out.observation_summary or "")
    print("INTENTION=", repr(intention))
    print("CLASS_ACTION_OR_INTENTION=", "ACTION_PROPOSAL" if out.action else "INTENTION")
    print("CLASS_GOAL_STATE=", "GOAL_STATUS_UNCHANGED_ACTIVE" if (out.goal_updates is None or out.goal_updates == []) else "GOAL_PROGRESS")
    print("CLASS_QUESTION=", "QUESTION" if out.questions_raised else "NO_QUESTION")
    print("CLASS_MEMORY=", "MEMORY_WRITE" if out.memory_write else "NO_MEMORY")
    print("CLASS_ACTION_ENGAGES_MOVEMENT=", (out.action or {}).get("action_type") == "move")
    # no_action is represented by action=None by design (see observe_and_orient);
    # a clean bounded no-op step = 1 transport call, no error, no goal change.
    no_error = out.memory_write is None
    print("PHASE4_OK=", _Completions.calls == 1 and no_error and out.action is None and (out.goal_updates is None or out.goal_updates == []))


if __name__ == "__main__":
    main()
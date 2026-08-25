"""Phase 3: smallest goal-aware cognition input - focused tests.

Builds a valid ``AgentContext`` from ONLY legitimate source-supported material
(canonical identity, canonical habitat, persisted active goal). Asserts the
goal is present, movement is False, memory/relationship/human contexts are
empty, and that the whole construction + prompt build is zero-write on the
isolated scratch store.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import shutil

import pytest

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    GoalRecord,
    save_goals,
)
from backend.world.local_goal_cognition_input import (
    build_goal_cognition_context,
)
from backend.world.first_pair_cognition_model import build_system_prompt

ADAM = "genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d"
EVE = "genesis-agent-1864f0bed1b4c501fa76067186115cc42c43b77992ec8cffb4b2801984743211"

_SCRATCH = Path(__file__).resolve().parent.parent / ".goal-cognition-scratch"


def _cand(ok: bool = True) -> dict:
    return {
        "ok": ok,
        "adam_identity": {"agent_id": ADAM, "canonical_agent_ref": "east_adam", "identity_valid": True},
        "eve_identity": {"agent_id": EVE, "canonical_agent_ref": "east_eve", "identity_valid": True},
    }


@pytest.fixture()
def store():
    shutil.rmtree(_SCRATCH, ignore_errors=True)
    s = FirstPairPersistenceStore(Path(_SCRATCH))
    s.root.mkdir(parents=True, exist_ok=True)
    save_goals(s, [
        GoalRecord(goal_id="goal-b0971f2a04c4c41b", agent_id=ADAM,
                   description="Understand the shared starting habitat.", status="active", created_heartbeat=0),
    ])
    yield s
    shutil.rmtree(_SCRATCH, ignore_errors=True)


def test_builds_adam_context_with_real_goal(store):
    ctx = build_goal_cognition_context(store, birth_candidate=_cand(), target_agent_ref="east_adam", heartbeat_number=1)
    assert ctx.agent_id == ADAM
    assert ctx.position == "public-start-adam"
    assert len(ctx.goals) == 1
    assert ctx.goals[0]["description"] == "Understand the shared starting habitat."
    assert ctx.goals[0]["agent_id"] == ADAM


def test_movement_forbidden_and_habitat_canonical(store):
    ctx = build_goal_cognition_context(store, birth_candidate=_cand(), target_agent_ref="east_adam", heartbeat_number=1)
    assert ctx.habitat_movement_allowed is False
    assert sorted(ctx.habitat_allowed_tiles) == ["public-start-adam", "public-start-eve"]


def test_no_smuggled_memory_or_relationship(store):
    ctx = build_goal_cognition_context(store, birth_candidate=_cand(), target_agent_ref="east_adam", heartbeat_number=1)
    assert ctx.memory == []
    assert ctx.answered_questions == []
    assert ctx.selected_private_memories == []
    assert ctx.derived_memory_summaries == []
    assert ctx.public_relationship_events == []
    assert ctx.visible_public_messages == []
    assert ctx.current_runtime_capabilities == []
    assert ctx.available_moves == []


def test_other_agent_identity_for_pair(store):
    ctx = build_goal_cognition_context(store, birth_candidate=_cand(), target_agent_ref="east_adam", heartbeat_number=1)
    assert ctx.other_agent_id == EVE
    assert ctx.other_agent_ref == "east_eve"
    assert ctx.other_agent_name == "Eve"


def test_goal_reaches_system_prompt(store):
    ctx = build_goal_cognition_context(store, birth_candidate=_cand(), target_agent_ref="east_adam", heartbeat_number=1)
    ssp = build_system_prompt(ctx)
    assert "Understand the shared starting habitat." in ssp


def test_zero_writes_on_scratch(store):
    def snap():
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(_SCRATCH).rglob("*") if p.is_file()
        }
    before = snap()
    for _ in range(3):
        ctx = build_goal_cognition_context(store, birth_candidate=_cand(), target_agent_ref="east_adam", heartbeat_number=1)
        build_system_prompt(ctx)
    assert snap() == before


def test_invalid_candidate_rejected(store):
    with pytest.raises(ValueError):
        build_goal_cognition_context(store, birth_candidate=_cand(ok=False), target_agent_ref="east_adam", heartbeat_number=1)


def test_unknown_agent_ref_rejected(store):
    with pytest.raises(ValueError):
        build_goal_cognition_context(store, birth_candidate=_cand(), target_agent_ref="bogus", heartbeat_number=1)
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_candidate_mapper import candidate_from_whisper_decision, candidate_from_goal_decision, candidate_from_help_decision
from backend.world.world_event_ledger import validate_event


def test_whisper_decision_speech():
    decision = {
        "decision": "whisper",
        "target": "east_eve",
        "content": "Water is low; can you observe?",
        "evidence_used": [{"category": "agent_speech", "reference": "msg1"}],
    }
    ev = candidate_from_whisper_decision('east_adam', decision, target_resolved=True, target_actor_id='east_eve')
    v = validate_event(ev)
    assert v["ok"]
    assert ev["action_type"] == "whisper"
    assert ev["claim_scope"] == "speech"
    assert "east_eve" in ev["affected_agents"]
    # ensure no relationship_delta containing trust/hostility
    for rel in ev["relationship_delta"]:
        assert rel not in {"trust", "hostility", "consent", "reconciliation"}


def test_unresolved_whisper_affects_only_actor():
    decision = {
        "decision": "whisper",
        "target": "east_eve",
        "content": "Need water levels.",
        "evidence_used": [{"category": "agent_speech", "reference": "msg2"}],
    }
    ev = candidate_from_whisper_decision('east_adam', decision, target_resolved=False, target_actor_id='east_eve')
    v = validate_event(ev)
    assert v["ok"]
    assert ev["claim_scope"] == "speech"
    # only actor should be present, target not added
    assert ev["affected_agents"] == []


def test_goal_decision_hypothesis():
    decision = {
        "decision": "goal",
        "new_goal": "verify whether a hidden water source exists",
        "content": "Maybe there is water",
        "evidence_used": [{"category": "agent_memory", "reference": "mem1"}],
    }
    ev = candidate_from_goal_decision('east_adam', decision)
    v = validate_event(ev)
    assert v["ok"]
    assert ev["action_type"] == "goal"
    assert ev["claim_scope"] == "hypothesis"


def test_goal_decision_observed_fact():
    decision = {
        "decision": "goal",
        "new_goal": "observe current world facts",
        "evidence_used": [{"category": "observed_world_fact", "reference": "obs_water"}],
    }
    ev = candidate_from_goal_decision('east_adam', decision)
    v = validate_event(ev)
    assert v["ok"]
    assert ev["claim_scope"] == "observed"


def test_help_decision_speech():
    decision = {
        "decision": "help",
        "content": "I need assistance verifying the water situation",
        "evidence_used": [{"category": "agent_speech", "reference": "msg_help"}],
    }
    ev = candidate_from_help_decision('east_adam', decision)
    v = validate_event(ev)
    assert v["ok"]
    assert ev["action_type"] == "help"
    assert ev["claim_scope"] == "speech"
    # consequence should be empty (no delivery claim)
    assert ev["consequence"] == ""

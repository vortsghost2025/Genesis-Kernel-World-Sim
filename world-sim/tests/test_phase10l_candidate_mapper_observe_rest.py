from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_candidate_mapper import infer_lens, candidate_from_observe_result, candidate_from_rest_result
from backend.world.world_event_ledger import validate_event


def test_infer_lens():
    assert infer_lens('east_adam') == 'east'
    assert infer_lens('west_eve') == 'west'
    assert infer_lens('unknown') == 'unknown'


def test_canonical_observe_candidate():
    result = {
        "territory_ref": "territoryA",
        "evidence_used": [
            {"category": "observed_world_fact", "reference": "obs1"},
            {"category": "territory_record", "reference": "terr1"},
            {"category": "agent_action", "reference": "act1"},
        ],
    }
    ev = candidate_from_observe_result('east_adam', 'observe something', result, tick=1)
    v = validate_event(ev)
    assert v["ok"]
    assert ev["action_type"] == "observe"
    assert ev["claim_scope"] == "observed"
    # evidence categories should be allowed and no private paths
    for e in ev["evidence_refs"]:
        assert e["category"] in {"observed_world_fact", "territory_record", "agent_action"}


def test_legacy_observe_candidate_no_private():
    # No evidence, minimal result
    result = {}
    ev = candidate_from_observe_result('west_eve', 'legacy observe', result)
    v = validate_event(ev)
    assert v["ok"]
    # claim_scope should be hypothesis when no observed evidence
    assert ev["claim_scope"] == "hypothesis"
    # ensure no evidence refs contain private/runtime paths
    for e in ev["evidence_refs"]:
        for val in e.values():
            if isinstance(val, str):
                assert "world-sim/data" not in val


def test_rest_candidate_with_block_reason():
    decision = {"action_type": "rest", "block_reason": "no-llm", "summary": "Rest blocked", "territory_ref": "territoryB"}
    result = {"evidence_used": [{"category": "agent_speech", "reference": "msg"}]}
    ev = candidate_from_rest_result('east_adam', decision, result, tick=2)
    v = validate_event(ev)
    assert v["ok"]
    assert ev["action_type"] == "rest"
    assert ev["claim_scope"] == "hypothesis"
    assert ev["consequence"] == "no-llm"
    # ensure evidence category is agent_speech
    assert any(e["category"] == "agent_speech" for e in ev["evidence_refs"])

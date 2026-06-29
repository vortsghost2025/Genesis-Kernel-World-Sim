from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_candidate_mapper import candidate_from_gather_result
from backend.world.world_event_ledger import validate_event


def test_accepted_gather_candidate():
    result = {
        "ok": True,
        "before_md5": "abc123",
        "after_md5": "def456",
        "territory_ref": "territoryC",
        "consequence": "resources updated",
        "evidence_used": [],
    }
    ev = candidate_from_gather_result('east_adam', 'gather resources', result, tick=3)
    assert ev is not None
    v = validate_event(ev)
    assert v["ok"]
    assert ev["before_ref"] == "md5:abc123"
    assert ev["after_ref"] == "md5:def456"
    assert ev["action_type"] == "gather"
    # No private paths in evidence_refs (list empty)
    for e in ev["evidence_refs"]:
        for val in e.values():
            if isinstance(val, str):
                assert "world-sim/data" not in val


def test_rejected_gather_candidate():
    result = {"ok": False}
    ev = candidate_from_gather_result('west_eve', 'gather fail', result)
    assert ev is None


def test_unsafe_gather_text_returns_none():
    result = {"ok": True, "before_md5": "a1", "after_md5": "b2"}
    ev = candidate_from_gather_result('east_adam', 'follow dove and lamb movements to hidden water source', result)
    assert ev is None

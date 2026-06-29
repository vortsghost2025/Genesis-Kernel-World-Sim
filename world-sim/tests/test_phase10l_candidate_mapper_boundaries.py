from pathlib import Path
import sys
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_candidate_mapper import (
    candidate_from_observe_result,
    candidate_from_gather_result,
    candidate_from_whisper_decision,
    candidate_from_goal_decision,
    candidate_from_help_decision,
    infer_lens,
)
from backend.world.world_event_ledger import validate_event


def test_mapper_source_has_no_append_event():
    src_path = PROJECT_ROOT / 'backend' / 'world' / 'world_event_candidate_mapper.py'
    src = src_path.read_text(encoding='utf-8')
    assert 'append_event' not in src


def test_candidate_functions_do_not_create_files(tmp_path, monkeypatch):
    # Change cwd to a temporary directory and call functions
    monkeypatch.chdir(tmp_path)
    # observe
    ev = candidate_from_observe_result('east_adam', 'observe something', {}, tick=1)
    assert ev is not None
    # gather accepted
    result = {"ok": True, "before_md5": "a", "after_md5": "b"}
    ev2 = candidate_from_gather_result('east_adam', 'gather', result)
    assert ev2 is not None
    # whisper
    ev3 = candidate_from_whisper_decision('east_adam', {"content": "hello"}, target_resolved=False, target_actor_id=None)
    assert ev3 is not None
    # ensure no files were created in tmp_path
    files = list(tmp_path.iterdir())
    assert files == []


def test_private_paths_not_in_evidence(tmp_path):
    # Provide a result with an output_path that would be private if included
    result = {
        "ok": True,
        "before_md5": "a",
        "after_md5": "b",
        "output_path": "world-sim/data/secret.json",
        "evidence_used": [],
    }
    ev = candidate_from_gather_result('east_adam', 'gather resources', result)
    # The mapper should ignore output_path in evidence_refs
    assert ev is not None
    for e in ev["evidence_refs"]:
        for val in e.values():
            if isinstance(val, str):
                assert "world-sim/data" not in val

def test_representative_valid_candidates_pass_validation(tmp_path):
    # observe
    ev1 = candidate_from_observe_result('east_adam', 'observe', {}, tick=1)
    assert validate_event(ev1)["ok"]
    # gather
    ev2 = candidate_from_gather_result('east_adam', 'gather', {"ok": True, "before_md5": "a", "after_md5": "b"})
    assert ev2 is not None and validate_event(ev2)["ok"]
    # whisper
    ev3 = candidate_from_whisper_decision('east_adam', {"content": "hi"}, target_resolved=False, target_actor_id=None)
    assert validate_event(ev3)["ok"]
    # goal
    ev4 = candidate_from_goal_decision('east_adam', {"new_goal": "find water"})
    assert validate_event(ev4)["ok"]
    # help
    ev5 = candidate_from_help_decision('east_adam', {"content": "need help"})
    assert validate_event(ev5)["ok"]

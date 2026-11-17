"""An unusable model response gets exactly one bounded re-ask, and our own prompt
must not name a field the validator will reject.

Two defects, both measured live on 2026-11-16 over east's 4,727 model errors and
its heartbeat records.

1. THE PHANTOM KEY (480 errors, 10.2%). The system prompt's field list read:

       "- proposed_action (object or null): a single action object with
        action_type and type-specific fields, or null to take no action"

   "type-specific fields" is a DESCRIPTION, but it is shaped like a key, and the
   model echoed it literally as ``"type-specific"`` / ``"type_specific"``.
   ``validate_action_exact`` rejects unknown fields, so every such response
   failed validation and was repaired into the same mistake:
   ``repair_failed: actionunknown_field:type-specific``.

2. THE MISSING RE-ASK (1,866 errors, 39.5%). ``no_valid_json_in_response`` was
   the single largest failure class, and it received NO repair at all: the one
   bounded re-ask only fired when JSON was extracted and then failed validation.
   A response with prose and no JSON returned early. 82% of east's ``no_action``
   heartbeats coincide with a model error, so this class was being recorded as
   "the agent chose to do nothing".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

import pytest

import backend.world.first_pair_cognition_model as fpcm
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import (
    ModelCognitionBackend,
    ProviderConfig,
)

FAKE_KEY = "nvapi-FAKE-SECRET-TEST-456"


def _ctx() -> AgentContext:
    return AgentContext(
        agent_id="genesis-agent-test",
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=1,
        position="public-start-adam",
        observation={},
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["public-start-adam"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-09-16T00:00:00Z",
    )


def _valid_payload(action=None) -> str:
    return json.dumps({
        "observation_summary": "test observation",
        "self_model_update": None,
        "goal_updates": [],
        "proposed_action": action,
        "memory_candidates": [],
        "questions_for_humans": [],
        "uncertainty": "low",
        "decision_summary": "test decision",
        "confidence": 0.9,
    })


class _Msg:
    def __init__(self, content):
        self.content = content

    def __getattr__(self, name):
        return None


class _Choice:
    def __init__(self, content, finish_reason=None):
        self.message = _Msg(content)
        self.finish_reason = finish_reason


class _Resp:
    def __init__(self, content, finish_reason=None):
        self.choices = [_Choice(content, finish_reason)]


class _EmptyResp:
    choices = []


def _scripted(script, calls_log):
    def create(**kwargs):
        calls_log.append(kwargs)
        if not script:
            return _Resp(_valid_payload())
        nxt = script.pop(0)
        if callable(nxt):
            return nxt()
        return _Resp(nxt)
    return create


class FakeChat:
    def __init__(self, create):
        self.completions = self
        self._create = create

    @property
    def chat(self):
        return self

    def create(self, **kwargs):
        return self._create(**kwargs)


def _backend(script):
    log: list = []
    create = _scripted(script, log)
    completions = FakeChat(create)
    config = ProviderConfig("nvidia", "https://test.invalid/v1", "test-model", FAKE_KEY)
    backend = ModelCognitionBackend.with_client("east_adam", completions, config)
    return backend, log


@pytest.fixture(autouse=True)
def _zero_backoff(monkeypatch):
    monkeypatch.setattr(fpcm, "_TRANSPORT_BACKOFF_SECONDS", (0.0, 0.0))


# --- the missing re-ask -----------------------------------------------------

def test_prose_with_no_json_gets_one_re_ask_and_can_recover():
    """The measured case: the model answered with prose, so nothing was
    extracted. It must get one bounded re-ask, and a valid answer on the re-ask
    is a SUCCESS -- not a lost heartbeat."""
    backend, log = _backend([
        "I will continue mapping the western hill cluster tile by tile.",
        _valid_payload(None),
    ])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert err is None, err
    assert raw is not None and raw["proposed_action"] is None
    assert len(log) == 2, "one call, then exactly one re-ask"


def test_prose_twice_still_fails_closed_with_the_historical_string():
    backend, log = _backend([
        "prose with no json at all",
        "still prose, still no json",
    ])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err == "no_valid_json_in_response", err
    assert len(log) == 2, "bounded: never more than one re-ask"


def test_a_recovered_re_ask_can_also_be_rejected_by_validation():
    """A re-ask that returns JSON which is still invalid reports the repair
    failure, exactly as the malformed-JSON path always has."""
    backend, log = _backend([
        "prose",
        json.dumps({"observation_summary": 123}),   # wrong type, missing fields
    ])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err is not None and err.startswith("repair_failed:"), err


def test_a_valid_first_response_is_never_re_requested():
    backend, log = _backend([_valid_payload(None)])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert err is None and raw is not None
    assert len(log) == 1


def test_an_empty_choices_response_is_not_treated_as_prose():
    """Empty choices stays a content failure (its own class), not a re-ask."""
    backend, log = _backend([lambda: _EmptyResp(), _valid_payload(None)])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    # With no fallback lane configured the empty-choices response fails closed.
    assert raw is None
    assert err is not None and "no_choices_in_response" in err, err


# --- the phantom key --------------------------------------------------------

def test_the_prompt_never_names_a_field_the_validator_rejects():
    """The literal token that produced 480 phantom-key errors must not come
    back, and it must not appear anywhere in the assembled system prompt."""
    src = Path(fpcm.__file__).read_text(encoding="utf-8")
    assert "type-specific fields" not in src, (
        "the prompt must not describe action fields with a key-shaped token")
    assert '"type-specific"' not in src


def test_the_action_field_description_names_the_real_rule():
    src = Path(fpcm.__file__).read_text(encoding="utf-8")
    assert ("action_type plus exactly the fields that action's line in "
            '"Available actions" lists') in src


def test_a_phantom_key_in_a_response_is_still_rejected():
    """The validator keeps rejecting unknown fields; we fixed the PROMPT, not
    the rule, so a model that still emits the phantom key is caught."""
    from backend.world.first_pair_cognition_model import validate_action_exact
    errs = validate_action_exact(
        {"action_type": "move", "target_tile": "public-shared-center",
         "reason": "go", "type-specific": {}}, "genesis-agent-test")
    assert any("unknown_field:type-specific" in e for e in errs), errs


# --- the goal_updates vocabulary -------------------------------------------
#
# Same family as the phantom key, found in the same audit: the world defines a
# controlled vocabulary of statuses and never told the model. east's single
# remaining post-10SJ error was
#     "repair_failed: goal_updates[0]:invalid_status:in progress"
# -- the human spelling of `in_progress`. An invalid goal_update fails the WHOLE
# response, so the typo also discarded the action.

def test_the_prompt_names_every_valid_goal_status():
    src = Path(fpcm.__file__).read_text(encoding="utf-8")
    for status in fpcm._VALID_STATUSES:
        assert status in src, status


def test_the_prompt_status_list_cannot_drift_from_the_validator():
    """The four tokens in the prompt must be exactly `_VALID_STATUSES`."""
    prompt = fpcm.build_system_prompt(_ctx())
    line = next(l for l in prompt.splitlines() if "goal_updates (list)" in l)
    for status in fpcm._VALID_STATUSES:
        assert status in line, (status, line)
    assert "\"in progress\" with a space is not a status" in line, line


def test_the_prompt_says_goal_updates_carries_no_other_keys():
    prompt = fpcm.build_system_prompt(_ctx())
    line = next(l for l in prompt.splitlines() if "goal_updates (list)" in l)
    assert "no other keys" in line, line


def test_the_human_spelling_of_the_status_is_still_rejected():
    """Disclosure, not relaxation: `in progress` is still not a status."""
    from backend.world.first_pair_cognition_model import validate_model_output
    bad = json.loads(_valid_payload())
    bad["goal_updates"] = [{"goal_id": "g1", "agent_id": "genesis-agent-test",
                            "description": "d", "status": "in progress"}]
    out = validate_model_output(bad, "genesis-agent-test")
    assert not out.is_valid
    assert any("invalid_status" in e for e in out.validation_errors), \
        out.validation_errors


def test_the_documented_token_is_accepted():
    from backend.world.first_pair_cognition_model import validate_model_output
    good = json.loads(_valid_payload())
    good["goal_updates"] = [{"goal_id": "g1", "agent_id": "genesis-agent-test",
                             "description": "d", "status": "in_progress"}]
    out = validate_model_output(good, "genesis-agent-test")
    assert out.is_valid, out.validation_errors

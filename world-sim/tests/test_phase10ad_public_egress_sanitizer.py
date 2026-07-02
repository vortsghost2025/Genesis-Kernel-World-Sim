"""Phase 10AD — public egress sanitizer tests.

All tests verify deterministic, side-effect-free behaviour with no
filesystem, network, or environment dependency.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.world_event_sanitizer import (
    REDACTED_PATH,
    REDACTED_SECRET,
    REDACTED_RUNTIME,
    REDACTED_AGENT_TRACE,
    REDACTED_SKILL_REF,
    sanitize_public_mapping,
    sanitize_public_text,
)

# ===================================================================
# 1.  Windows path redaction
# ===================================================================


def test_redacts_windows_drive_letter_path():
    text = "Found config at C:\\Users\\example\\AppData\\Local\\program\\config.ini"
    result = sanitize_public_text(text)
    assert REDACTED_PATH in result
    assert "C:\\Users" not in result
    assert "AppData" not in result


def test_redacts_windows_path_with_spaces():
    text = "Repo cloned to Z:\\Example Project\\world-sim\\data"
    result = sanitize_public_text(text)
    assert REDACTED_PATH in result
    assert "Z:\\Example" not in result


def test_redacts_bare_windows_tokens():
    text = "Path fragment: Users\\example\\something and %LOCALAPPDATA%"
    result = sanitize_public_text(text)
    assert REDACTED_PATH in result
    assert "Users\\" not in result
    assert "AppData" not in result.lower()


# ===================================================================
# 2.  Secret / token / API-key phrase redaction
# ===================================================================


def test_redacts_api_key_equals_value():
    text = "SERVICE_API_KEY=dummy-key-value"
    result = sanitize_public_text(text)
    assert REDACTED_SECRET in result
    assert "dummy-key-value" not in result


def test_redacts_token_colon_value():
    text = "AUTH_TOKEN:dummy-token-value"
    result = sanitize_public_text(text)
    assert REDACTED_SECRET in result
    assert "dummy-token-value" not in result


def test_redacts_bare_secret_label():
    text = "The SECRET was stored in a config file."
    result = sanitize_public_text(text)
    assert REDACTED_SECRET in result
    # The replacement marker literally contains "SECRET" so use a precise check
    assert "The SECRET was" not in result
    assert "SECRET " not in result


def test_redacts_api_key_spaced():
    text = "need to configure API Key before running"
    result = sanitize_public_text(text)
    assert REDACTED_SECRET in result
    assert "API Key" not in result


# ===================================================================
# 3.  localhost / IP / runtime marker redaction
# ===================================================================


def test_redacts_localhost():
    text = "Server listening on http://localhost:8080/api"
    result = sanitize_public_text(text)
    assert REDACTED_RUNTIME in result
    assert "localhost" not in result


def test_redacts_loopback_ip():
    text = "Bound to 127.0.0.1:3000"
    result = sanitize_public_text(text)
    assert REDACTED_RUNTIME in result
    assert "127.0.0.1" not in result


def test_redacts_generic_ipv4():
    text = "Resolved upstream to 10.20.30.40"
    result = sanitize_public_text(text)
    assert REDACTED_RUNTIME in result
    assert "10.20.30.40" not in result


def test_redacts_ssh_hostinger_tailscale():
    text = "Connected via ssh to hostinger, also using Tailscale"
    result = sanitize_public_text(text)
    assert REDACTED_RUNTIME in result


def test_redacts_dot_env():
    text = "Loaded variables from .env.production"
    result = sanitize_public_text(text)
    assert REDACTED_PATH in result
    assert ".env" not in result


# ===================================================================
# 4.  Slash-skill contamination redaction
# ===================================================================


def test_redacts_slash_skill_contamination():
    text = "Used /agent-tools:skill and /ab-test-setup:skill references"
    result = sanitize_public_text(text)
    assert REDACTED_SKILL_REF in result
    assert "/agent-tools:skill" not in result
    assert "/ab-test-setup:skill" not in result


# ===================================================================
# 5.  Thought / agent trace marker redaction
# ===================================================================


def test_redacts_thought_prefix():
    text = "Thought: Let me check the config file"
    result = sanitize_public_text(text)
    assert REDACTED_AGENT_TRACE in result
    assert "Thought:" not in result


def test_redacts_chain_of_thought():
    text = "The model used chain-of-thought reasoning"
    result = sanitize_public_text(text)
    assert REDACTED_AGENT_TRACE in result
    assert "chain-of-thought" not in result.lower()


def test_redacts_model_names():
    text = "DeepSeek, MiniMax, GPT-5, and Orchestrator are internal"
    result = sanitize_public_text(text)
    assert REDACTED_AGENT_TRACE in result
    assert "DeepSeek" not in result
    assert "MiniMax" not in result
    assert "GPT-5" not in result
    assert "Orchestrator" not in result


# ===================================================================
# 6.  Preserves normal world-event JSON-ish text
# ===================================================================


def test_preserves_world_language():
    text = (
        'event_id: evt_10ad_001, actor_id: east_adam, '
        'claim_scope: observed, category: observed_world_fact, '
        'territory_ref: territory_east, observed: water at basin edge, '
        'speech: hello, whisper: echo, world_event: evt_10aa_002, '
        'evidence_refs: [{"category": "agent_speech"}]'
    )
    result = sanitize_public_text(text)
    assert "east_adam" in result
    assert "evt_10ad_001" in result
    assert "observed" in result
    assert "claim_scope" in result
    assert "observed_world_fact" in result
    assert "territory_east" in result
    assert "speech" in result
    assert "whisper" in result
    assert "world_event" in result
    assert "evidence_refs" in result
    assert "agent_speech" in result


def test_preserves_safe_json_event():
    import json
    event = {
        "event_id": "evt_10ad_preserve_001",
        "schema_version": "10K.1",
        "actor_id": "east_adam",
        "claim_scope": "observed",
        "summary": "Water is visible at the basin edge.",
        "evidence_refs": [
            {"category": "observed_world_fact", "ref": "world.observe.basin"}
        ],
        "affected_agents": ["east_adam"],
        "artifacts_created_or_changed": [],
    }
    text = json.dumps(event, indent=2)
    result = sanitize_public_text(text)
    parsed = json.loads(result)
    assert parsed["event_id"] == "evt_10ad_preserve_001"
    assert parsed["actor_id"] == "east_adam"
    assert parsed["claim_scope"] == "observed"
    assert parsed["summary"] == "Water is visible at the basin edge."


# ===================================================================
# 7.  Recursive mapping sanitizer handles dict/list nesting
# ===================================================================


def test_sanitize_mapping_nested_dict():
    data = {
        "event_id": "evt_nested_001",
        "summary": "Path used: C:\\Users\\placeholder\\config",
        "evidence": [
            {"category": "observed_world_fact", "ref": "world.path"},
            {"category": "agent_action", "details": "ssh to hostinger"},
        ],
        "meta": {
            "nested": "TOKEN=dummy-value",
            "tracing": "Thought: check this",
        },
    }
    result = sanitize_public_mapping(data)
    assert result["event_id"] == "evt_nested_001"
    assert REDACTED_PATH in result["summary"]
    assert REDACTED_SECRET in result["meta"]["nested"]
    assert REDACTED_AGENT_TRACE in result["meta"]["tracing"]
    assert REDACTED_RUNTIME in result["evidence"][1]["details"]
    assert result["evidence"][0]["category"] == "observed_world_fact"


def test_sanitize_mapping_list_of_strings():
    data = ["C:\\path\\to\\file", "TOKEN=dummy-value", "normal text"]
    result = sanitize_public_mapping(data)
    assert REDACTED_PATH in result[0]
    assert REDACTED_SECRET in result[1]
    assert result[2] == "normal text"


def test_sanitize_mapping_tuple():
    data = ("C:\\path", "safe", "SECRET=dummy-value")
    result = sanitize_public_mapping(data)
    assert REDACTED_PATH in result[0]
    assert result[1] == "safe"
    assert REDACTED_SECRET in result[2]
    assert isinstance(result, tuple)


# ===================================================================
# 8.  Dict key sanitization
# ===================================================================


def test_sanitize_mapping_sanitizes_path_key():
    data = {"C:\\Users\\example\\config": "value"}
    result = sanitize_public_mapping(data)
    for key in result:
        assert REDACTED_PATH in key
    assert "C:\\Users\\example" not in str(list(result.keys()))


def test_sanitize_mapping_sanitizes_secret_key():
    data = {"TOKEN=dummy-value": "should be redacted"}
    result = sanitize_public_mapping(data)
    for key in result:
        assert REDACTED_SECRET in key
    assert "TOKEN" not in str(list(result.keys()))


def test_sanitize_mapping_sanitizes_nested_dict_keys():
    data = {
        "outer_key": {
            "C:\\Users\\example\\path": "deep value",
            "SECRET=dummy-value": "also deep",
        }
    }
    result = sanitize_public_mapping(data)
    outer_keys = list(result["outer_key"].keys())
    key_text = str(outer_keys)
    assert REDACTED_PATH in key_text
    assert REDACTED_SECRET in key_text
    assert "C:\\Users" not in key_text
    assert result["outer_key"][outer_keys[0]] == "deep value"


def test_sanitize_mapping_preserves_non_string_keys():
    data = {42: "number key", None: "none key", True: "bool key"}
    result = sanitize_public_mapping(data)
    assert 42 in result
    assert None in result
    assert True in result


def test_sanitize_mapping_does_not_mutate_keys_in_original():
    original = {"C:\\Users\\example\\config": "value", "TOKEN=dummy-value": "secret"}
    original_copy = copy.deepcopy(original)
    _ = sanitize_public_mapping(original)
    assert original == original_copy, "Original dict keys were mutated"


# ===================================================================
# 9.  Idempotence test
# ===================================================================


def test_sanitize_text_is_idempotent():
    inputs = [
        "C:\\Users\\example\\AppData\\Local\\test.ini",
        "SERVICE_API_KEY=dummy-key-value",
        "Server at localhost:8080",
        "Thought: I should check the TOKEN=dummy-value",
        "Used /agent-tools:skill reference",
        "ssh to hostinger with Tailscale",
        "127.0.0.1 bound",
        "chain-of-thought reasoning DeepSeek MiniMax GPT-5",
        "normal world event text with observed and speech",
    ]
    for text in inputs:
        once = sanitize_public_text(text)
        twice = sanitize_public_text(once)
        assert once == twice, f"Not idempotent for: {text!r}"


# ===================================================================
# 10.  Empty string and non-string primitive handling
# ===================================================================


def test_empty_string():
    assert sanitize_public_text("") == ""


def test_non_string_primitives():
    assert sanitize_public_text(None) is None
    assert sanitize_public_text(42) == 42
    assert sanitize_public_text(3.14) == 3.14
    assert sanitize_public_text(True) is True
    assert sanitize_public_text(False) is False


def test_non_string_in_mapping():
    data = {"a": None, "b": 42, "c": 3.14, "d": True, "e": [1, 2, 3]}
    result = sanitize_public_mapping(data)
    assert result["a"] is None
    assert result["b"] == 42
    assert result["c"] == 3.14
    assert result["d"] is True
    assert result["e"] == [1, 2, 3]


# ===================================================================
# 11.  Does not mutate input dict
# ===================================================================


def test_does_not_mutate_input_dict():
    original = {
        "event_id": "evt_no_mut_001",
        "summary": "Used C:\\Users\\placeholder\\file and TOKEN=dummy-value",
        "nested": {"key": "SECRET:dummy-value"},
    }
    original_copy = copy.deepcopy(original)
    _ = sanitize_public_mapping(original)
    assert original == original_copy, "Input dict was mutated"


def test_does_not_mutate_input_list():
    original = ["C:\\path", {"inner": "TOKEN=dummy-value"}]
    original_copy = copy.deepcopy(original)
    _ = sanitize_public_mapping(original)
    assert original == original_copy, "Input list was mutated"

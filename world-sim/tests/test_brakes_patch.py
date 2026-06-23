"""No-LLM tests for Phase 4B — Brakes Patch: runtime counter sanitization."""

import time
import os

# The daemon expects CWD = project root
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

import pytest
from backend.daemon.agent_daemon import AgentDaemon


@pytest.fixture
def daemon():
    return AgentDaemon(dry_run=True, no_llm=True)


# ── Legacy stale: whisper_cooldown > 0, no timestamp metadata ──────────────


def test_legacy_stale_cooldown_reset(daemon):
    """cooldown>0 with no timestamp metadata → reset to 0 (legacy state)."""
    state = {"whisper_cooldown": 60}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["whisper_cooldown"] == 0


def test_zero_cooldown_noop(daemon):
    """cooldown=0 with no timestamp → unchanged."""
    state = {"whisper_cooldown": 0}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["whisper_cooldown"] == 0


def test_missing_cooldown_key(daemon):
    """No whisper_cooldown key at all → default 0, unchanged."""
    state = {}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result.get("whisper_cooldown", 0) == 0


# ── Fresh cooldown: whisper_cooldown > 0 with recent timestamp ─────────────


def test_fresh_cooldown_preserved(daemon):
    """cooldown>0 with recent timestamp → preserved."""
    state = {"whisper_cooldown": 60, "whisper_cooldown_set_at_utc": time.time() - 30}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["whisper_cooldown"] == 60


def test_fresh_cooldown_almost_expired(daemon):
    """cooldown>0 with timestamp near but under 7200s → preserved."""
    state = {"whisper_cooldown": 60, "whisper_cooldown_set_at_utc": time.time() - 7100}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["whisper_cooldown"] == 60


# ── Expired cooldown: whisper_cooldown > 0 with old timestamp ──────────────


def test_expired_cooldown_reset(daemon):
    """cooldown>0 with timestamp >7200s old → reset to 0."""
    state = {"whisper_cooldown": 60, "whisper_cooldown_set_at_utc": time.time() - 7300}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["whisper_cooldown"] == 0


def test_very_old_expired_cooldown(daemon):
    """cooldown>0 with very old timestamp (days) → reset to 0."""
    state = {"whisper_cooldown": 60, "whisper_cooldown_set_at_utc": time.time() - 172800}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["whisper_cooldown"] == 0


# ── ISO string timestamp format ────────────────────────────────────────────


def test_iso_timestamp_fresh(daemon):
    """ISO format string timestamp, recent → preserved."""
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    state = {"whisper_cooldown": 60, "whisper_cooldown_set_at_utc": now_iso}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["whisper_cooldown"] == 60


def test_iso_timestamp_expired(daemon):
    """ISO format string timestamp, old → reset."""
    state = {"whisper_cooldown": 60, "whisper_cooldown_set_at_utc": "2020-01-01T00:00:00+00:00"}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["whisper_cooldown"] == 0


def test_iso_timestamp_zulu(daemon):
    """ISO format with Z suffix, fresh → preserved."""
    state = {"whisper_cooldown": 60, "whisper_cooldown_set_at_utc": "2026-06-23T20:00:00Z"}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    # The age will be ~24 minutes from the test timestamp, so preserved
    assert result["whisper_cooldown"] == 60


# ── Malformed / unexpected timestamp types ─────────────────────────────────


def test_unparseable_string_cooldown(daemon):
    """Unparseable timestamp string → reset."""
    state = {"whisper_cooldown": 60, "whisper_cooldown_set_at_utc": "not_a_timestamp"}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["whisper_cooldown"] == 0


def test_none_timestamp_not_legacy(daemon):
    """Explicit None timestamp → treated as missing, reset."""
    state = {"whisper_cooldown": 60, "whisper_cooldown_set_at_utc": None}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["whisper_cooldown"] == 0


def test_bool_timestamp(daemon):
    """Boolean timestamp → unexpected type, reset."""
    state = {"whisper_cooldown": 60, "whisper_cooldown_set_at_utc": True}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["whisper_cooldown"] == 0


# ── model_calls_used_this_hour is never touched by sanitize ────────────────


def test_model_calls_field_untouched(daemon):
    """model_calls_used_this_hour is derived/display; sanitize ignores it."""
    state = {"whisper_cooldown": 0, "model_calls_used_this_hour": 999}
    result = daemon._sanitize_runtime_counters(state, "test_agent")
    assert result["model_calls_used_this_hour"] == 999
    assert result["whisper_cooldown"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

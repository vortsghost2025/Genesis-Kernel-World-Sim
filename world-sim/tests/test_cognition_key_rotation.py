"""Key rotation on the COGNITION path, not just the synthesis path.

The 2026-09-30 freeze, in one line: the heartbeat loop built ONE client
from the singular OPENROUTER_API_KEY, retried it three times, and when its
daily free cap ran out the pair went silent for 46 heartbeats. The key
pool built in abdf106/a2b89e5/3ec1b17 was wired into
`run_memory_synthesis.py` only - `load_key_pool` and
`call_with_key_rotation` were never called from the heartbeat path at all.
Three healthy keys sat unused in the plural pool while the one key in use
was quota-exhausted.

These pin the wiring: the cognition transport must rotate its credential
across a pool, must skip fingerprints already denylisted, must persist a
credential it discovers dead, and must stay fail-closed and bounded.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m  # noqa: E402


def _status_error(status: int, message: str = "boom"):
    import httpx
    from openai import APIStatusError

    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return APIStatusError(message, response=httpx.Response(status, request=req),
                          body=None)


class _FakeCompletions:
    """Fails per-key with a scripted error, succeeds on a healthy key."""

    def __init__(self, script, tracker):
        self.script = dict(script)
        self.tracker = tracker
        self.n = 0

    def create(self, **kwargs):
        self.n += 1
        key = self.tracker["key"]
        self.tracker["calls"].append(key)
        err = self.script.get(key)
        if err is not None:
            raise err
        return _FakeResponse()


class _FakeMessage:
    content = '{"ok": true}'


class _FakeChoice:
    finish_reason = "stop"
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]


def _tracker():
    return {"key": None, "calls": []}


def _make_backend(monkeypatch, keys, script, denylist_path=None):
    """A backend whose client factory is driven by the pool under test."""
    tracker = _tracker()

    class _Chat:
        def __init__(self):
            self.completions = _FakeCompletions(script, tracker)

    class _Client:
        def __init__(self, key=None, **kwargs):
            tracker["key"] = key if key is not None else kwargs.get("api_key")
            self.chat = _Chat()

    monkeypatch.setattr(m, "OpenAI", _Client)
    cfg = m.ProviderConfig("openrouter", "https://openrouter.ai/api/v1",
                           "some/model:free", "primary-key")
    backend = object.__new__(m.ModelCognitionBackend)
    backend._config = cfg
    backend._model = "some/model:free"
    backend._client = _Client(cfg.api_key)
    backend._fallback_config = None
    backend._fallback_client = None
    backend._key_pool = list(keys)
    backend._key_pool_denylist = set()
    backend._key_pool_dead = []
    backend._last_serving_provider_type = "openrouter"
    backend._last_fallback_used = False
    backend._last_primary_failure = ""
    if denylist_path is not None:
        backend._denylist_path = denylist_path
    else:
        backend._denylist_path = None
    return backend, tracker


class TestRotation:
    def test_quota_exhausted_key_rotates_to_a_live_one(self, monkeypatch):
        keys = ["k-dead-quota", "k-live"]
        backend, tracker = _make_backend(
            monkeypatch, keys, {"k-dead-quota": _status_error(429, "rate")})
        resp, err = backend._call_with_transport_retry(
            [{"role": "system", "content": "x"}], temperature=0.3,
            max_tokens=16, budget=[3])
        assert err is None and resp is not None
        assert tracker["calls"] == ["k-dead-quota", "k-live"], (
            "a spent key must rotate, not be retried")

    def test_dead_key_is_recorded_and_skipped_next_time(self, monkeypatch):
        keys = ["k-dead-401", "k-live"]
        backend, tracker = _make_backend(
            monkeypatch, keys, {"k-dead-401": _status_error(401, "nope")})
        backend._call_with_transport_retry(
            [{"role": "system", "content": "x"}], temperature=0.3,
            max_tokens=16, budget=[3])
        assert backend._key_pool_dead, "a 401 credential is dead, must persist"
        fp = m.key_fingerprint("k-dead-401")
        assert fp in backend._key_pool_denylist

    def test_already_denylisted_fingerprints_never_enter_the_pool(self):
        pool = ["live-key", "dead-key"]
        dead = {m.key_fingerprint("dead-key")}
        kept, skipped = m._filter_denied(pool, dead)
        assert kept == ["live-key"] and skipped == 1

    def test_denied_keys_are_never_sent_to_the_network(self, monkeypatch):
        keys = ["k-live"]
        backend, tracker = _make_backend(monkeypatch, keys, {})
        backend._key_pool_denylist = {m.key_fingerprint("k-live")}
        resp, err = backend._call_with_transport_retry(
            [{"role": "system", "content": "x"}], temperature=0.3,
            max_tokens=16, budget=[3])
        assert resp is None and err is not None, (
            "an entirely denied pool fails closed without a network call")
        assert tracker["calls"] == []


class TestBoundedAndFailClosed:
    def test_attempts_stay_bounded_across_a_large_pool(self, monkeypatch):
        keys = [f"k{i}" for i in range(10)]
        script = {k: _status_error(429, "rate") for k in keys}
        backend, tracker = _make_backend(monkeypatch, keys, script)
        resp, err = backend._call_with_transport_retry(
            [{"role": "system", "content": "x"}], temperature=0.3,
            max_tokens=16, budget=[3])
        assert resp is None
        assert len(tracker["calls"]) <= 3, (
            "the transport budget bounds attempts; a big pool is not a "
            "licence to hammer the provider")

    def test_single_key_behaves_exactly_as_before(self, monkeypatch):
        """No pool, no behaviour change: the one key is retried on a
        transient, not rotated away."""
        backend, tracker = _make_backend(
            monkeypatch, ["only"], {"only": _status_error(503, "down")})
        resp, err = backend._call_with_transport_retry(
            [{"role": "system", "content": "x"}], temperature=0.3,
            max_tokens=16, budget=[2])
        assert resp is None and err is not None
        assert set(tracker["calls"]) == {"only"}

    def test_all_denylisted_pool_fails_closed(self, monkeypatch):
        """Every credential on the lane is known dead: do not spend a
        request on one we have already written off."""
        backend, tracker = _make_backend(monkeypatch, ["k1", "k2"], {})
        backend._key_pool_denylist = {m.key_fingerprint("k1"),
                                     m.key_fingerprint("k2")}
        resp, err = backend._call_with_transport_retry(
            [{"role": "system", "content": "x"}], temperature=0.3,
            max_tokens=16, budget=[3])
        assert resp is None
        assert "pool" in err.lower()
        assert tracker["calls"] == []

    def test_empty_pool_keeps_the_historical_single_key_path(self, monkeypatch):
        """No vault credentials in this process is not a dead lane - it is a
        lane running on its one configured key, exactly as before."""
        backend, tracker = _make_backend(monkeypatch, [], {})
        resp, err = backend._call_with_transport_retry(
            [{"role": "system", "content": "x"}], temperature=0.3,
            max_tokens=16, budget=[3])
        assert err is None and resp is not None
        assert tracker["calls"] == ["primary-key"]


class TestNoSecretLeak:
    def test_key_material_never_appears_in_the_error(self, monkeypatch):
        """With rotation the ACTIVE key is usually not the configured one.
        A provider error that echoes it must not reach the store with live
        key material in it."""
        secret = "sk-or-v1-SECRETVALUE0123456789"
        backend, tracker = _make_backend(
            monkeypatch, [secret], {secret: _status_error(401, f"bad {secret}")})
        resp, err = backend._call_with_transport_retry(
            [{"role": "system", "content": "x"}], temperature=0.3,
            max_tokens=16, budget=[1])
        assert err is not None
        assert secret not in err
        assert "SECRETVALUE" not in err

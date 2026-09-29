"""Provider key pool + rotate-on-429.

The free tier caps ~1,000 calls/day/key. The operator holds hundreds of keys;
this pool distributes load across them instead of parking work at the ceiling.
Policy is untouched: same pinned models, same endpoints, same free-only
gates — rotation happens strictly at the credential layer.

Fail-closed throughout: pool exhausted → error, never a paid lane, never a
different model. Key material never appears in errors, reports, or logs —
redaction covers every pool key, not just the active one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_model import (  # noqa: E402
    call_with_key_rotation,
    load_key_pool,
)


def _status_error(status: int, message: str = "boom"):
    import httpx
    from openai import APIStatusError

    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return APIStatusError(message, response=httpx.Response(status, request=req),
                          body=None)


class _FakeCompletions:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        item = self.script[min(self.calls - 1, len(self.script) - 1)]
        if isinstance(item, Exception):
            raise item
        return item


class _FakeResp:
    def __init__(self, text):
        self.choices = [type("C", (), {"message": type(
            "M", (), {"content": text})()})()]


class _Client:
    def __init__(self, script, seen):
        self.chat = self
        self.completions = _FakeCompletions(script)
        self._seen = seen

    def note(self, key_index):
        self._seen.append(key_index)


def _factory(scripts, seen):
    def make(key_index):
        client = _Client(scripts[key_index], seen)
        client.note(key_index)
        return client
    return make


class TestPoolParsing:
    def test_comma_and_newline_separated(self):
        pool = load_key_pool({"OPENROUTER_API_KEYS": "k1,k2\nk3\r\nk1,, "},
                             "OPENROUTER_API_KEYS", "OPENROUTER_API_KEY")
        assert pool == ["k1", "k2", "k3"]

    def test_legacy_single_key_is_pool_of_one(self):
        pool = load_key_pool({"OPENROUTER_API_KEY": "solo"},
                             "OPENROUTER_API_KEYS", "OPENROUTER_API_KEY")
        assert pool == ["solo"]

    def test_union_prefers_list_then_legacy(self):
        pool = load_key_pool({"OPENROUTER_API_KEYS": "k1",
                              "OPENROUTER_API_KEY": "k2"},
                             "OPENROUTER_API_KEYS", "OPENROUTER_API_KEY")
        assert pool == ["k1", "k2"]

    def test_empty_is_empty(self):
        assert load_key_pool({}, "OPENROUTER_API_KEYS",
                             "OPENROUTER_API_KEY") == []


class TestRotation:
    def test_429_rotates_immediately(self, monkeypatch):
        import backend.world.first_pair_cognition_model as cm
        monkeypatch.setattr(cm.time, "sleep", lambda s: None)
        seen: list = []
        scripts = [[_status_error(429)], [_FakeResp('{"a":1}')]]
        text, err = call_with_key_rotation(
            _factory(scripts, seen), "m", [{"role": "user", "content": "x"}],
            ["k1", "k2"], temperature=0.0, max_tokens=10)
        assert err is None
        assert text == '{"a":1}'
        assert seen == [0, 1], "429 blames the key: move on, don't retry it"

    def test_timeout_retries_same_key_once(self, monkeypatch):
        import httpx
        from openai import APITimeoutError
        import backend.world.first_pair_cognition_model as cm
        monkeypatch.setattr(cm.time, "sleep", lambda s: None)
        seen: list = []
        clients: list = []
        scripts = [[APITimeoutError(httpx.Request("POST", "https://x")),
                    _FakeResp("ok")]]

        def make(key_index):
            client = _Client(scripts[key_index], seen)
            client.note(key_index)
            clients.append(client)
            return client

        text, err = call_with_key_rotation(
            make, "m", [{"role": "user", "content": "x"}],
            ["k1"], temperature=0.0, max_tokens=10)
        assert err is None and text == "ok"
        assert seen == [0], "same key: client built once"
        assert clients[0].completions.calls == 2, "retried on that key"

    def test_exhaustion_fails_closed(self, monkeypatch):
        import backend.world.first_pair_cognition_model as cm
        monkeypatch.setattr(cm.time, "sleep", lambda s: None)
        seen: list = []
        scripts = [[_status_error(429)], [_status_error(429)]]
        text, err = call_with_key_rotation(
            _factory(scripts, seen), "m", [{"role": "user", "content": "x"}],
            ["k1", "k2"], temperature=0.0, max_tokens=10)
        assert text is None
        assert err, "exhaustion must report, not pretend"
        assert seen == [0, 1]

    def test_auth_error_fails_fast_without_rotation(self, monkeypatch):
        import backend.world.first_pair_cognition_model as cm
        monkeypatch.setattr(cm.time, "sleep", lambda s: None)
        seen: list = []
        scripts = [[_status_error(401)], [_FakeResp("ok")]]
        text, err = call_with_key_rotation(
            _factory(scripts, seen), "m", [{"role": "user", "content": "x"}],
            ["k1", "k2"], temperature=0.0, max_tokens=10)
        assert text is None
        assert seen == [0], "auth failure is config, not congestion"

    def test_key_material_never_in_errors(self, monkeypatch):
        import backend.world.first_pair_cognition_model as cm
        monkeypatch.setattr(cm.time, "sleep", lambda s: None)
        seen: list = []
        scripts = [[_status_error(429, message="key sk-live-SECRET rejected")],
                   [_status_error(429, message="also sk-live-SECRET here")]]
        text, err = call_with_key_rotation(
            _factory(scripts, seen), "m", [{"role": "user", "content": "x"}],
            ["sk-live-SECRET", "k2"], temperature=0.0, max_tokens=10)
        assert text is None
        assert "sk-live-SECRET" not in (err or "")
        assert "[REDACTED]" in (err or "")

    def test_empty_choices_is_retryable_then_rotates(self, monkeypatch):
        import backend.world.first_pair_cognition_model as cm
        monkeypatch.setattr(cm.time, "sleep", lambda s: None)

        class Empty:
            choices = []

        seen: list = []
        scripts = [[Empty()], [_FakeResp("recovered")]]
        text, err = call_with_key_rotation(
            _factory(scripts, seen), "m", [{"role": "user", "content": "x"}],
            ["k1", "k2"], temperature=0.0, max_tokens=10)
        assert err is None and text == "recovered"

    def test_single_key_empty_retries_before_exhausting(self, monkeypatch):
        """Regression: with nowhere to rotate to, an empty response must
        retry the same key instead of failing after one attempt."""
        import backend.world.first_pair_cognition_model as cm
        monkeypatch.setattr(cm.time, "sleep", lambda s: None)

        class Empty:
            choices = []

        seen: list = []
        scripts = [[Empty(), _FakeResp("recovered")]]
        text, err = call_with_key_rotation(
            _factory(scripts, seen), "m", [{"role": "user", "content": "x"}],
            ["k1"], temperature=0.0, max_tokens=10)
        assert err is None and text == "recovered"
        assert seen == [0]

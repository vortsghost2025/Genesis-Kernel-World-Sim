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


class TestCleanEnvPropagation:
    """The pool must survive build_clean_env: the proof child and the live
    process both consume the clean env, so a plural stuck in the vault file
    is a pool of one at runtime. Measured live."""

    def test_plurals_ride_from_vault_only(self, tmp_path):
        from backend.world.canonical_heartbeat_runner import build_clean_env

        vault = tmp_path / ".env"
        vault.write_text(
            "NVIDIA_NIM_API_KEY=nv-single\n"
            "OPENROUTER_API_KEY=or-single\n"
            "OPENROUTER_API_KEYS=or-a,or-b\n"
            "NVIDIA_API_KEYS=nv-a,nv-b,nv-c\n",
            encoding="utf-8")
        env = build_clean_env(vault)
        assert load_key_pool(env, "OPENROUTER_API_KEYS",
                             "OPENROUTER_API_KEY") == ["or-a", "or-b",
                                                       "or-single"]
        assert load_key_pool(env, "NVIDIA_API_KEYS",
                             "NVIDIA_API_KEY") == ["nv-a", "nv-b", "nv-c",
                                                   "nv-single"]

    def test_absent_plurals_leave_singles_unchanged(self, tmp_path):
        from backend.world.canonical_heartbeat_runner import build_clean_env

        vault = tmp_path / ".env"
        vault.write_text(
            "NVIDIA_NIM_API_KEY=nv-single\n"
            "OPENROUTER_API_KEY=or-single\n",
            encoding="utf-8")
        env = build_clean_env(vault)
        assert "OPENROUTER_API_KEYS" not in env
        assert load_key_pool(env, "OPENROUTER_API_KEYS",
                             "OPENROUTER_API_KEY") == ["or-single"]


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

    def test_auth_error_rotates_dead_key(self, monkeypatch):
        """A 401 on one key is a dead credential, not a config error — the
        pool exists so one dead key never stops the run. Measured live:
        harvested keys 401'd ('User not found') while the legacy key worked."""
        import backend.world.first_pair_cognition_model as cm
        monkeypatch.setattr(cm.time, "sleep", lambda s: None)
        seen: list = []
        scripts = [[_status_error(401)], [_FakeResp("ok")]]
        text, err = call_with_key_rotation(
            _factory(scripts, seen), "m", [{"role": "user", "content": "x"}],
            ["dead-key", "live-key"], temperature=0.0, max_tokens=10)
        assert err is None and text == "ok"
        assert seen == [0, 1]

    def test_all_dead_pool_fails_closed(self, monkeypatch):
        import backend.world.first_pair_cognition_model as cm
        monkeypatch.setattr(cm.time, "sleep", lambda s: None)
        seen: list = []
        scripts = [[_status_error(401)], [_status_error(401)]]
        text, err = call_with_key_rotation(
            _factory(scripts, seen), "m", [{"role": "user", "content": "x"}],
            ["dead-1", "dead-2"], temperature=0.0, max_tokens=10)
        assert text is None
        assert seen == [0, 1]
        assert err


class TestDenylist:
    def test_fingerprint_is_stable_hex(self):
        from backend.world.first_pair_cognition_model import key_fingerprint

        fp = key_fingerprint("sk-or-test")
        assert len(fp) == 64
        assert fp == key_fingerprint("sk-or-test")
        assert all(c in "0123456789abcdef" for c in fp)

    def test_fingerprint_reveals_nothing(self):
        from backend.world.first_pair_cognition_model import key_fingerprint

        fp = key_fingerprint("sk-or-test")
        assert "sk-or-test" not in fp
        assert "test" not in fp.replace("e", "").replace("t", "")

    def test_denied_keys_filtered_silently(self):
        from backend.world.first_pair_cognition_model import (
            key_fingerprint,
            load_key_pool,
        )

        env = {"OPENROUTER_API_KEYS": "live-1,dead-1,live-2"}
        denied = {key_fingerprint("dead-1")}
        assert load_key_pool(env, "OPENROUTER_API_KEYS",
                             denylist=denied) == ["live-1", "live-2"]

    def test_dead_callback_fires_only_on_dead_status(self, monkeypatch):
        import backend.world.first_pair_cognition_model as cm
        monkeypatch.setattr(cm.time, "sleep", lambda s: None)
        dead: list = []
        seen: list = []
        scripts = [[_status_error(429)], [_status_error(401)],
                   [_FakeResp("ok")]]
        text, err = call_with_key_rotation(
            _factory(scripts, seen), "m", [{"role": "user", "content": "x"}],
            ["spent", "dead", "live"], temperature=0.0, max_tokens=10,
            on_dead_key=dead.append)
        assert err is None and text == "ok"
        assert dead == [1], "429 is spent quota, not death; 401 is death"

    def test_no_callback_no_crash(self, monkeypatch):
        import backend.world.first_pair_cognition_model as cm
        monkeypatch.setattr(cm.time, "sleep", lambda s: None)
        seen: list = []
        scripts = [[_status_error(401)], [_FakeResp("ok")]]
        text, err = call_with_key_rotation(
            _factory(scripts, seen), "m", [{"role": "user", "content": "x"}],
            ["dead", "live"], temperature=0.0, max_tokens=10)
        assert err is None and text == "ok"

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

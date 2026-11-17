"""Phase 10SS: the heartbeat actually spends a POOL of credentials, and an agent
can be given its own model and its own key by editing vault lines.

Two defects, one of them the reason "add another key" could never have helped.

1. THE POOL WAS NEVER WIRED INTO THE HEARTBEAT. `build_lane_key_pool` existed
   and `_call_with_transport_retry` rotated correctly, but the pool was only
   built in `with_client`. Production reaches this class through
   `_get_cognition_backend` -> `ModelCognitionBackend(ref)`, whose `__init__`
   never set `_key_pool` at all -- so `getattr(self, "_key_pool", None)` was
   None and NOTHING rotated. Every heartbeat spent the single
   `GENESIS_FIRST_PAIR_API_KEY` while the vault's key pools sat inert.
   `test_cognition_key_rotation` did not catch it because it assigns
   `backend._key_pool` BY HAND: the suite proved rotation WORKS and never that
   it is WIRED.

2. THE POOL HAD NO FAMILY. `build_lane_key_pool` keys off the provider TYPE,
   and a vault-configured lane resolves as `explicit_url`, which maps to no pool
   names -- so even a wired pool would have found nothing. The runner knows the
   family and now exports it.

Every environment write here goes through `monkeypatch`: this file first leaked
`NVIDIA_API_KEYS` through `os.environ`, which diverted eight unrelated transport
tests onto the network.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")

import pytest

import backend.world.first_pair_cognition_model as fpcm
from backend.world.canonical_heartbeat_runner import (
    build_clean_env,
    resolve_primary_lane,
)
from backend.world.first_pair_cognition_model import (
    ModelCognitionBackend,
    ProviderConfig,
    _lane_key_family,
)

LANE = dict(
    GENESIS_FIRST_PAIR_BASE_URL="https://integrate.api.nvidia.com/v1",
    GENESIS_FIRST_PAIR_MODEL="nvidia/nemotron-3-ultra-550b-a55b",
    GENESIS_FIRST_PAIR_API_KEY="nvapi-primary",
)
TOUCHED = list(LANE) + [
    "GENESIS_FIRST_PAIR_KEY_KIND",
    "GENESIS_FIRST_PAIR_API_KEY_EAST_ADAM",
    "GENESIS_FIRST_PAIR_API_KEY_EAST_EVE",
    "GENESIS_FIRST_PAIR_MODEL_EAST_ADAM",
    "GENESIS_FIRST_PAIR_MODEL_EAST_EVE",
    "NVIDIA_API_KEYS", "NVIDIA_API_KEY", "OPENROUTER_API_KEYS",
    "OPENROUTER_API_KEY", "GENESIS_FIRST_PAIR_FALLBACK_MODEL",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for k in TOUCHED:
        monkeypatch.delenv(k, raising=False)
    for k, v in LANE.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(fpcm, "_DEADKEYS_PATH", tmp_path / "deadkeys.json")


# --- 1. the pool is actually wired ------------------------------------------

def test_production_backend_builds_the_key_pool(monkeypatch):
    """The whole point: `ModelCognitionBackend(ref)` -- the production path --
    must come up with the vault's credentials available for rotation."""
    monkeypatch.setenv("GENESIS_FIRST_PAIR_KEY_KIND", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEYS", "nvapi-a,nvapi-b,nvapi-c")
    backend = ModelCognitionBackend("east_adam")
    assert set(backend._key_pool) >= {"nvapi-a", "nvapi-b", "nvapi-c"}, \
        backend._key_pool


def test_an_injected_client_gets_no_pool(monkeypatch):
    """A fake transport must never be silently replaced by a real client built
    from ambient credentials (the invariant `with_client` documents)."""
    monkeypatch.setenv("GENESIS_FIRST_PAIR_KEY_KIND", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEYS", "nvapi-a,nvapi-b")
    fake = object()
    backend = ModelCognitionBackend("east_adam", client=fake)
    assert backend._key_pool == []
    assert backend._client is fake


def test_with_client_never_lets_ambient_keys_replace_a_fake(monkeypatch):
    """The latent bug the leak exposed: a non-empty pool makes
    `_call_with_transport_retry` construct a REAL OpenAI client, replacing the
    injected fake."""
    monkeypatch.setenv("GENESIS_FIRST_PAIR_KEY_KIND", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEYS", "nvapi-a,nvapi-b")
    fake = object()
    cfg = ProviderConfig("nvidia", "https://test.invalid/v1", "m", "k")
    backend = ModelCognitionBackend.with_client("east_adam", fake, cfg)
    assert backend._key_pool == []
    assert backend._client is fake


def test_an_explicit_key_pool_passed_to_with_client_is_honoured(monkeypatch):
    fake = object()
    cfg = ProviderConfig("nvidia", "https://test.invalid/v1", "m", "k")
    backend = ModelCognitionBackend.with_client(
        "east_adam", fake, cfg, key_pool=["k1", "k2"])
    assert backend._key_pool == ["k1", "k2"]


class _Msg:
    def __init__(self, content):
        self.content = content
        self.role = "assistant"


class _Choice:
    message = None
    finish_reason = "stop"


class _Resp:
    def __init__(self, content):
        c = _Choice()
        c.message = _Msg(content)
        self.choices = [c]


class _FakeCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        import json as _json
        self.calls += 1
        return _Resp(_json.dumps({
            "observation_summary": "x", "self_model_update": None,
            "goal_updates": [], "proposed_action": None,
            "memory_candidates": [], "questions_for_humans": [],
            "uncertainty": "u", "decision_summary": "d", "confidence": 0.5,
        }))


class _FakeClient:
    def __init__(self):
        self.completions = _FakeCompletions()

    @property
    def chat(self):
        return self


def test_a_pool_holding_only_the_configured_key_does_not_refuse():
    """The LIVE configuration: the vault's NVIDIA pool holds exactly the key the
    lane is configured with. Rotation excludes it, so the pool listed nothing to
    rotate to -- and the fail-closed guard read that as "every credential is
    dead" and refused every heartbeat. Wiring the pool exposed it."""
    fake = _FakeClient()
    backend = ModelCognitionBackend("east_adam", client=fake)
    backend._key_pool = ["nvapi-primary"]          # == the configured key
    backend._key_pool_denylist = set()
    raw, err = backend._call_with_transport_retry(
        [{"role": "user", "content": "hi"}],
        temperature=0.0, max_tokens=16, budget=[3])
    assert err != "no usable provider keys in pool: refusing network call", err
    assert fake.completions.calls == 1, "the configured key must still be spent"


def test_a_fully_denylisted_pool_still_fails_closed():
    """The case the guard EXISTS for: every credential known dead."""
    fake = _FakeClient()
    backend = ModelCognitionBackend("east_adam", client=fake)
    backend._key_pool = ["nvapi-dead"]
    backend._key_pool_denylist = {fpcm.key_fingerprint("nvapi-dead")}
    raw, err = backend._call_with_transport_retry(
        [{"role": "user", "content": "hi"}],
        temperature=0.0, max_tokens=16, budget=[3])
    assert err == "no usable provider keys in pool: refusing network call", err
    assert fake.completions.calls == 0


def test_the_pool_family_comes_from_the_exported_kind(monkeypatch):
    monkeypatch.setenv("GENESIS_FIRST_PAIR_KEY_KIND", "nvidia")
    cfg = ProviderConfig("explicit_url", "https://integrate.api.nvidia.com/v1",
                         "m", "k")
    assert _lane_key_family(cfg) == "nvidia"


def test_the_pool_family_falls_back_to_the_endpoint(monkeypatch):
    """A lane configured outside build_clean_env must still find its pool."""
    monkeypatch.delenv("GENESIS_FIRST_PAIR_KEY_KIND", raising=False)
    assert _lane_key_family(ProviderConfig(
        "explicit_url", "https://integrate.api.nvidia.com/v1", "m", "k")) == "nvidia"
    assert _lane_key_family(ProviderConfig(
        "explicit_url", "https://openrouter.ai/api/v1", "m", "k")) == "openrouter"


def test_an_explicit_url_lane_no_longer_resolves_to_no_pool(monkeypatch):
    """The exact gap: provider_type 'explicit_url' maps to no pool names, so a
    wired pool would STILL have found nothing."""
    monkeypatch.delenv("GENESIS_FIRST_PAIR_KEY_KIND", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEYS", "nvapi-z")
    cfg = ProviderConfig("explicit_url", "https://integrate.api.nvidia.com/v1",
                         "m", "k")
    assert fpcm.build_lane_key_pool(cfg.provider_type) == [], (
        "the provider TYPE alone finds nothing -- this is the gap")
    assert fpcm.build_lane_key_pool(_lane_key_family(cfg)) == ["nvapi-z"], (
        "the resolved family finds the pool")


# --- 2. per-agent model and key ---------------------------------------------

def test_a_per_agent_model_overrides_only_that_agent(monkeypatch):
    monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL_EAST_ADAM",
                       "mistralai/mistral-large-4-1t-a52b")
    mine = ModelCognitionBackend("east_adam")
    theirs = ModelCognitionBackend("east_eve")
    assert mine._config.model == "mistralai/mistral-large-4-1t-a52b"
    assert theirs._config.model == "nvidia/nemotron-3-ultra-550b-a55b"


def test_a_per_agent_key_spends_only_its_own_credential(monkeypatch):
    monkeypatch.setenv("GENESIS_FIRST_PAIR_KEY_KIND", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEYS", "nvapi-shared-a,nvapi-shared-b")
    monkeypatch.setenv("GENESIS_FIRST_PAIR_API_KEY_EAST_ADAM", "nvapi-adam-only")
    mine = ModelCognitionBackend("east_adam")
    assert mine._config.api_key == "nvapi-adam-only"
    assert mine._key_pool == [], "it must not be able to spend another's key"
    # the agent without its own key still rotates the shared pool
    theirs = ModelCognitionBackend("east_eve")
    assert theirs._config.api_key == "nvapi-primary"
    assert set(theirs._key_pool) >= {"nvapi-shared-a", "nvapi-shared-b"}


def test_per_agent_model_and_key_compose(monkeypatch):
    monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL_EAST_EVE",
                       "stepfun-ai/step-5-preview")
    monkeypatch.setenv("GENESIS_FIRST_PAIR_API_KEY_EAST_EVE", "nvapi-eve-only")
    b = ModelCognitionBackend("east_eve")
    assert b._config.model == "stepfun-ai/step-5-preview"
    assert b._config.api_key == "nvapi-eve-only"
    assert b._key_pool == []


# --- 3. the runner builds those env values from the vault -------------------

def _vault(tmp_path: Path, extra: str = "") -> Path:
    p = tmp_path / ".env"
    p.write_text(
        "NVIDIA_NIM_API_KEY=nvapi-primary\r\n"
        "OPENROUTER_API_KEY=or-primary\r\n"
        f"{extra}",
        encoding="utf-8", newline="")
    return p


def test_the_runner_exports_the_key_kind(tmp_path):
    vault = _vault(tmp_path,
                   "NVIDIA_PRIMARY_MODEL=mistralai/mistral-large-4-1t-a52b\r\n")
    env = build_clean_env(vault)
    _, _, kind = resolve_primary_lane(
        {"NVIDIA_PRIMARY_MODEL": "mistralai/mistral-large-4-1t-a52b"})
    assert kind == "nvidia"
    assert env["GENESIS_FIRST_PAIR_KEY_KIND"] == "nvidia"


def test_the_runner_reads_per_agent_lines_from_the_vault(tmp_path):
    vault = _vault(tmp_path, (
        "NVIDIA_MODEL_EAST_ADAM=mistralai/mistral-large-4-1t-a52b\r\n"
        "NVIDIA_MODEL_EAST_EVE=stepfun-ai/step-5-preview\r\n"
        "NVIDIA_API_KEY_EAST_ADAM=nvapi-adam\r\n"
        "NVIDIA_API_KEY_EAST_EVE=nvapi-eve\r\n"))
    env = build_clean_env(vault)
    assert env["GENESIS_FIRST_PAIR_MODEL_EAST_ADAM"] == "mistralai/mistral-large-4-1t-a52b"
    assert env["GENESIS_FIRST_PAIR_MODEL_EAST_EVE"] == "stepfun-ai/step-5-preview"
    assert env["GENESIS_FIRST_PAIR_API_KEY_EAST_ADAM"] == "nvapi-adam"
    assert env["GENESIS_FIRST_PAIR_API_KEY_EAST_EVE"] == "nvapi-eve"
    # the west agents are untouched and keep the shared primary
    assert env["GENESIS_FIRST_PAIR_MODEL_WEST_ADAM"] == \
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
    assert "GENESIS_FIRST_PAIR_API_KEY_WEST_ADAM" not in env


def test_an_unchanged_vault_changes_nothing(tmp_path):
    env = build_clean_env(_vault(tmp_path))
    for ref in ("EAST_ADAM", "EAST_EVE", "WEST_ADAM", "WEST_EVE"):
        assert "GENESIS_FIRST_PAIR_API_KEY_" + ref not in env


def test_ambient_per_agent_values_cannot_hijack(tmp_path, monkeypatch):
    """The per-agent key comes from the VAULT or not at all."""
    monkeypatch.setenv("GENESIS_FIRST_PAIR_API_KEY_WEST_ADAM", "nvapi-ambient")
    env = build_clean_env(_vault(tmp_path))
    assert "GENESIS_FIRST_PAIR_API_KEY_WEST_ADAM" not in env


def test_the_key_kind_is_recomputed_from_the_vault_not_taken_from_ambient(
        tmp_path, monkeypatch):
    monkeypatch.setenv("GENESIS_FIRST_PAIR_KEY_KIND", "openrouter")  # a lie
    env = build_clean_env(_vault(
        tmp_path, "NVIDIA_PRIMARY_MODEL=nvidia/nemotron-3-ultra-550b-a55b\r\n"))
    assert env["GENESIS_FIRST_PAIR_KEY_KIND"] == "nvidia", (
        "the vault says NVIDIA; an ambient value must not override it")

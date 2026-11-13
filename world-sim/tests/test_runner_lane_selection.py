"""Phase 10QE: the primary lane is chosen by the vault, not by code.

Measured 2026-11-13 on a live agent prompt (261,071 chars, 112,803 tokens)
with the operator's NVIDIA key:

    NVIDIA nemotron-3-ultra-550b-a55b      17.5s   contract-VALID
    NVIDIA nemotron-3-nano-omni-30b        28.0s   contract-VALID
    OpenRouter 30b (the lane running today) 68.1s   contract-VALID

The 550B is bigger AND four times faster than the lane the sim was on, and
it acted on a partner's public plea that the 30B ignored. The point of this
suite is that moving the agents onto it is a VAULT EDIT, not a code change:
one line added, one line removed, and the fallback lane keeps the heartbeat
alive if the big model starts rate-limiting.

These tests live in their own file rather than in
test_canonical_heartbeat_runner.py because that suite is excluded from CI
(it exercises Windows-only process behaviour). This one is pure and portable.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.canonical_heartbeat_runner import (
    FALLBACK_MODEL,
    NVIDIA_BASE_URL,
    OPENROUTER_BASE_URL,
    build_clean_env,
    resolve_primary_lane,
)

FAKE_VAULT = """\
NVIDIA_NIM_API_KEY=nvapi-fake-nvidia-key-value-0000000000000000000000000
OPENROUTER_API_KEY=sk-or-v1-fake-openrouter-key-000000000000000000000
OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b:free
OPENROUTER_MODEL_FALLBACK=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free
"""


def _vault(tmp_path: Path, extra: str = "") -> Path:
    p = tmp_path / ".env"
    p.write_text(FAKE_VAULT + extra, encoding="utf-8", newline="\n")
    return p


# ---------------------------------------------------------------------------
# lane selection
# ---------------------------------------------------------------------------

def test_default_vault_keeps_the_openrouter_lane(tmp_path):
    """An unchanged vault must not change the sim's behaviour by accident."""
    base, model, kind = resolve_primary_lane({})
    assert base == OPENROUTER_BASE_URL
    assert kind == "openrouter"
    assert model.endswith(":free"), model


def test_vault_can_move_the_lane_to_nvidia(tmp_path):
    base, model, kind = resolve_primary_lane({
        "NVIDIA_PRIMARY_MODEL": "nvidia/nemotron-3-ultra-550b-a55b"})
    assert kind == "nvidia"
    assert model == "nvidia/nemotron-3-ultra-550b-a55b"
    assert base == NVIDIA_BASE_URL


def test_vault_can_also_set_the_nvidia_base_url(tmp_path):
    base, _model, _kind = resolve_primary_lane({
        "NVIDIA_PRIMARY_MODEL": "nvidia/nemotron-3-ultra-550b-a55b",
        "NVIDIA_PRIMARY_BASE_URL": "https://integrate.api.nvidia.com/v1"})
    assert base == "https://integrate.api.nvidia.com/v1"


def test_removing_the_vault_line_restores_the_old_lane():
    """The revert is the whole point: one line out, behaviour back."""
    vault = {"NVIDIA_PRIMARY_MODEL": "nvidia/nemotron-3-ultra-550b-a55b"}
    assert resolve_primary_lane(vault)[2] == "nvidia"
    vault.pop("NVIDIA_PRIMARY_MODEL")
    assert resolve_primary_lane(vault)[2] == "openrouter"


# ---------------------------------------------------------------------------
# the environment the runner actually hands to the heartbeat
# ---------------------------------------------------------------------------

def test_clean_env_writes_the_vault_selected_lane(tmp_path):
    vault = _vault(tmp_path, "NVIDIA_PRIMARY_MODEL=nvidia/nemotron-3-ultra-550b-a55b\n")
    env = build_clean_env(vault)
    assert env["GENESIS_FIRST_PAIR_MODEL"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert env["GENESIS_FIRST_PAIR_BASE_URL"] == NVIDIA_BASE_URL
    # the NVIDIA credential is the one the lane spends
    assert env["GENESIS_FIRST_PAIR_API_KEY"] == env["NVIDIA_API_KEY"]
    assert env["GENESIS_FIRST_PAIR_API_KEY"] != env["OPENROUTER_API_KEY"]


def test_clean_env_defaults_to_openrouter(tmp_path):
    env = build_clean_env(_vault(tmp_path))
    assert env["GENESIS_FIRST_PAIR_MODEL"].endswith(":free")
    assert env["GENESIS_FIRST_PAIR_BASE_URL"] == OPENROUTER_BASE_URL
    assert env["GENESIS_FIRST_PAIR_API_KEY"] == env["OPENROUTER_API_KEY"]


def test_the_fallback_lane_is_always_openrouter_and_always_free(tmp_path):
    """The free-only guard depends on this, and it is what keeps a 429 on
    the big model from killing the heartbeat."""
    for extra in ("", "NVIDIA_PRIMARY_MODEL=nvidia/nemotron-3-ultra-550b-a55b\n"):
        env = build_clean_env(_vault(tmp_path, extra))
        fallback = env["GENESIS_FIRST_PAIR_FALLBACK_MODEL"]
        assert fallback.endswith(":free"), fallback
        assert fallback == FALLBACK_MODEL
        # and the OpenRouter credential is present for that lane to use
        assert env["OPENROUTER_API_KEY"]


def test_per_agent_model_vars_follow_the_selected_lane(tmp_path):
    """The four per-agent variables are written with the lane's model, so a
    future per-agent selection has one source of truth to read."""
    env = build_clean_env(_vault(
        tmp_path, "NVIDIA_PRIMARY_MODEL=nvidia/nemotron-3-ultra-550b-a55b\n"))
    for name in ("EAST_ADAM", "EAST_EVE", "WEST_ADAM", "WEST_EVE"):
        assert env[f"GENESIS_FIRST_PAIR_MODEL_{name}"] == "nvidia/nemotron-3-ultra-550b-a55b"


def test_ambient_environment_cannot_hijack_the_lane(tmp_path, monkeypatch):
    """An ambient GENESIS_FIRST_PAIR_MODEL must not win over the vault."""
    monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "attacker/paid-model")
    monkeypatch.setenv("GENESIS_FIRST_PAIR_BASE_URL", "https://attacker.invalid/v1")
    env = build_clean_env(_vault(
        tmp_path, "NVIDIA_PRIMARY_MODEL=nvidia/nemotron-3-ultra-550b-a55b\n"))
    assert env["GENESIS_FIRST_PAIR_MODEL"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert env["GENESIS_FIRST_PAIR_BASE_URL"] == NVIDIA_BASE_URL

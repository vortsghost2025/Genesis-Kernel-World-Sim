"""
Key management for World Sim — writes to .env only, never exposes keys.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = PROJECT_ROOT / "world-sim" / ".env"

# Key environment variables
KEY_VARS = {
    "east_adam_key": "AGENT_EAST_ADAM_NIM_KEY",
    "east_eve_key": "AGENT_EAST_EVE_NIM_KEY",
    "west_adam_key": "AGENT_WEST_ADAM_NIM_KEY",
    "west_eve_key": "AGENT_WEST_EVE_NIM_KEY",
}


def _read_env() -> dict[str, str]:
    """Read existing .env file into a dict."""
    if not ENV_PATH.exists():
        return {}
    env_vars: dict[str, str] = {}
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env_vars[key.strip()] = value.strip()
    return env_vars


def _write_env(env_vars: dict[str, str]) -> None:
    """Write env vars to .env file."""
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("# World Sim — Environment\n")
        f.write("# NEVER commit this file to version control.\n\n")
        f.write("# Provider mode: mock, nim-dry-run, nim-live\n")
        f.write("WORLD_PROVIDER_MODE=mock\n")
        f.write("WORLD_TICK_INTERVAL=5000\n")
        f.write("WORLD_MAX_TICKS=0\n")
        f.write("WORLD_SAVE_INTERVAL=10\n\n")
        f.write("# Agent NIM Keys\n")
        for key, value in sorted(env_vars.items()):
            f.write(f"{key}={value}\n")


def save_keys(keys: dict[str, str]) -> dict[str, str]:
    """Save NIM keys to .env. Does NOT enable live mode."""
    env_vars = _read_env()
    saved = []

    for form_key, env_key in KEY_VARS.items():
        value = keys.get(form_key, "").strip()
        if value:
            env_vars[env_key] = value
            os.environ[env_key] = value
            saved.append(env_key)

    _write_env(env_vars)

    return {
        "status": "ok",
        "message": f"Keys saved to local .env. Live mode NOT enabled. Saved: {', '.join(saved) if saved else 'none'}",
        "saved_keys": saved,
    }


def clear_keys() -> dict[str, str]:
    """Clear all NIM keys from .env and environment."""
    env_vars = _read_env()
    for env_key in KEY_VARS.values():
        if env_key in env_vars:
            del env_vars[env_key]
        if env_key in os.environ:
            del os.environ[env_key]

    _write_env(env_vars)

    return {
        "status": "ok",
        "message": "All NIM keys cleared from local .env and environment.",
    }


def get_key_status() -> dict[str, bool]:
    """Return key presence status only — never key values."""
    return {
        "east_adam_key_present": bool(os.environ.get("AGENT_EAST_ADAM_NIM_KEY", "")),
        "east_eve_key_present": bool(os.environ.get("AGENT_EAST_EVE_NIM_KEY", "")),
        "west_adam_key_present": bool(os.environ.get("AGENT_WEST_ADAM_NIM_KEY", "")),
        "west_eve_key_present": bool(os.environ.get("AGENT_WEST_EVE_NIM_KEY", "")),
    }


def test_dry_run() -> dict[str, str]:
    """Test dry-run for all 4 agents."""
    from backend.providers.base import NvidiaNimProvider, call_log

    results = {}
    agents = [
        ("east_adam", "AGENT_EAST_ADAM_NIM_KEY"),
        ("east_eve", "AGENT_EAST_EVE_NIM_KEY"),
        ("west_adam", "AGENT_WEST_ADAM_NIM_KEY"),
        ("west_eve", "AGENT_WEST_EVE_NIM_KEY"),
    ]

    for agent_key, env_key in agents:
        key = os.environ.get(env_key, "")
        if not key:
            results[f"{agent_key}_dry_run"] = "skipped"
            continue

        provider = NvidiaNimProvider(
            name=f"{agent_key}_test",
            api_key_env=env_key,
            mode="nim-dry-run",
        )
        response = provider.generate("test", agent_key, 0)
        results[f"{agent_key}_dry_run"] = "success" if "dry-run" in response.lower() else "failed"

    return results

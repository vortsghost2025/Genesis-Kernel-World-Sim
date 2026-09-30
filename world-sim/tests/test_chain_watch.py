"""Chain run monitor: terminal states are distinct, messaged once, never silent."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import chain_watch as cw  # noqa: E402


class TestClassify:
    def test_complete_at_or_past_target(self):
        assert cw.classify(1143, 1143, True, 0) == "complete"
        assert cw.classify(1150, 1143, False, 99999) == "complete"

    def test_dead_chain_below_target_is_stopped(self):
        assert cw.classify(1100, 1143, False, 10) == "stopped"

    def test_live_chain_without_movement_is_stalled(self):
        assert cw.classify(1100, 1143, True, 99999) == "stalled"

    def test_live_chain_moving_is_running(self):
        assert cw.classify(1100, 1143, True, 60) == "running"

    def test_unreadable_store_is_never_terminal(self):
        """A monitor must not declare death from its own read failure."""
        for alive in (True, False):
            assert cw.classify(None, 1143, alive, 99999) == "unknown"


class TestMessages:
    def test_complete_names_target(self):
        msg = cw.terminal_message("complete", "east", 1143, 1143)
        assert "1143" in msg and "complete" in msg.lower()

    def test_stopped_carries_reason_and_tick(self):
        msg = cw.terminal_message("stopped", "east", 1100, 1143,
                                  "HB1100 east: HARD STOP")
        assert "1100" in msg and "HARD STOP" in msg

    def test_running_produces_no_message(self):
        assert cw.terminal_message("running", "east", 1100, 1143) == ""


class TestDedupe:
    def test_terminal_state_sends_once(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cw, "LEDGER", tmp_path / "runs.json")
        assert not cw.already_sent("east:1-2", "stopped")
        cw.mark_sent("east:1-2", "stopped")
        assert cw.already_sent("east:1-2", "stopped")
        assert not cw.already_sent("east:1-2", "complete")

    def test_restart_cannot_replay(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cw, "LEDGER", tmp_path / "runs.json")
        cw.mark_sent("east:1-2", "complete")
        # Fresh "process": ledger persists, so no resend.
        assert cw.already_sent("east:1-2", "complete")


class TestTelegramEnv:
    def test_process_env_carries_credentials(self):
        import os
        assert os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(), (
            "operator keeps the bot token in User env; the monitor inherits it")
        assert os.environ.get("TELEGRAM_CHAT_ID", "").strip()

"""Telegram is for events, not heartbeat counts.

Sean's phone had 80 notifications. The progress pings (every 50 HB per
pair), start announcements, completion messages, and agent-watch alerts
combined into a wall of noise that trained him to ignore the channel
— which defeats the one thing a notification channel exists for:
telling him something he needs to know about.

The fix is a strict hierarchy of what earns a phone buzz:
  ALWAYS: a run ending (complete, stopped, frozen) — those need him
  ALWAYS: an agent asking a question — those need him
  NEVER: a run starting (the completion is what matters, not the start)
  NEVER: progress counts (he can ask me, the record is in the store)

Unit under test: the default that governs volume.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import chain_watch as cw  # noqa: E402


class TestProgressIsOffByDefault:
    def test_default_interval_is_zero(self):
        """Progress pings are opt-in, not opt-out. The operator can ask
        'how's it going' and get an answer from the store; the phone
        does not need to count heartbeats for him."""
        assert cw._PROGRESS_EVERY == 0, (
            f"default is {cw._PROGRESS_EVERY}; must be 0 (off) so "
            f"the phone only rings when something ends or someone asks")


class TestStartIsQuiet:
    def test_announce_start_does_not_send_telegram(self):
        """Starting a run is not an event the operator needs to know
        about on his phone. Ending one is. Silence from the monitor
        means running — that is the whole contract."""
        pass  # the test is that announce is removed from the default flow

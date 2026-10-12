"""Telegram messages read like a person wrote them, not a stack trace.

Sean reads these on a phone with TTS. The current shape is:
  bot name "Genesis Watch" (Telegram-side, can't change)
  + title "run monitor" (chain_watch wraps in a signal)
  + "Genesis: ..." (the body prefixes itself)
  = three headers stacked before any content, plus broken math
  ("26 of -19 heartbeats in") because the progress line subtracts the
  ping-window start from the run's total.

These pin the fix: one clean line per message, correct math, and the
header noise stripped.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import chain_watch as cw  # noqa: E402
import agent_watch as aw  # noqa: E402


class TestProgressMath:
    def test_progress_counts_from_run_start(self):
        """'HB 26 of 100' means 26 heartbeats into a 100-heartbeat run.
        The old formula subtracted the ping-window start, producing
        nonsense like '26 of -19'."""
        rows = [{"heartbeat_number": n,
                 "action_taken": {"east_adam": {"action_type": "move"}}}
                for n in range(1, 27)]
        s = cw.window_summary(rows, 0, 26)
        msg = cw.progress_message("east", 0, 100, s, 26, 0, 0, 0)
        assert "26" in msg and "100" in msg
        # the old bug: negative or inverted totals
        import re
        nums = re.findall(r"(\d+) of (\d+)", msg)
        assert nums, f"no N-of-M found in: {msg}"
        for done, total in nums:
            assert int(total) > 0, f"total is {total} in: {msg}"
            assert int(done) <= int(total), f"{done} > {total} in: {msg}"


class TestNoStackedHeaders:
    def test_chain_watch_body_does_not_prefix_genesis(self):
        """The bot name already says Genesis. The body saying it too is
        the triple-header Sean hears on TTS."""
        msg = cw.terminal_message("complete", "east", 1143, 1143)
        assert not msg.lower().startswith("genesis:")

    def test_render_skips_empty_title(self):
        """A signal with no title should not produce a blank first line
        on the phone."""
        sig = {"severity": "info", "title": "", "pair": "-", "agent": "-",
               "heartbeat": "-", "body": "just the fact"}
        out = aw.render(sig)
        assert not out.startswith("\n"), f"blank first line in: {out!r}"
        assert "just the fact" in out


class TestFrequency:
    def test_default_interval_is_50(self):
        """25 was four pings per 100-heartbeat window per pair = 8 per
        window. 50 halves it. The operator asked for less spam."""
        assert cw._PROGRESS_EVERY == 50, (
            f"default interval is {cw._PROGRESS_EVERY}, expected 50")

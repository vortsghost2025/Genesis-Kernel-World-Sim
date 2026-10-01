"""Wake target routing: local opencode, headless Kilo, or preserve-quench.

The bridge that already exists (`watch_bridge`) opens the current session
with opencode run. The Kilo headless server at the control-plane endpoint
answers POSTs the same way, but runs on a machine that survives this one's
restarts. The routing decision is one env var, and the failure semantics
must be exact because a wake that silently fails is worse than no wake.

Three rules under test:
  1. The env var picks the target; unset means local.
  2. A target that fails falls back to local - every wake that wanted to
     happen has to wake SOME process, or the monitor has to say it failed
     to.
  3. The brief is the budget on the headless side: Kilo answers
     immediately, auto-approved, which means the text is the only
     authority for what it may do. A report brief carries no mutation
     verbs.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import chain_watch as cw  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_wake_ledger(monkeypatch):
    """The dedupe ledger is a real file with a real memory; the tests are
    about the decision, so it must be reseedable per test rather than
    'already sent' because an old test wrote it."""
    state = {}
    monkeypatch.setattr(cw, "already_sent",
                        lambda k, s: state.get(k, {}).get(s, False))
    monkeypatch.setattr(cw, "mark_sent",
                        lambda k, s: state.setdefault(k, {}) \
                        .__setitem__(s, True))


class TestTargetIsChosenByEnv:
    def test_unset_routes_to_local_opencode(self, monkeypatch):
        monkeypatch.delenv("GENESIS_WAKE_TARGET", raising=False)
        monkeypatch.setattr(cw, "spawn_local_opencode",
                            lambda b, r: {"woken": True, "target": "local"})
        monkeypatch.setattr(cw, "spawn_headless_kilo", lambda b, r: None)
        assert cw.wake_operator("x", "east:1-100")["target"] == "local"

    def test_headless_env_routes_to_kilo(self, monkeypatch):
        monkeypatch.setenv("GENESIS_WAKE_TARGET", "headless")
        monkeypatch.setattr(cw, "spawn_headless_kilo",
                            lambda b, r: {"woken": True, "target": "headless"})
        monkeypatch.setattr(cw, "spawn_local_opencode", lambda b, r:
                            AttributeError("must not try local first"))
        assert cw.wake_operator("x", "east:1-100")["target"] == "headless"

    def test_unknown_value_falls_back_to_local(self, monkeypatch):
        """A typo must not change semantics; it lands on local and it's in
        the result so the operator can see what the var did."""
        monkeypatch.setenv("GENESIS_WAKE_TARGET", "space-shuttle")
        monkeypatch.setattr(cw, "spawn_local_opencode",
                            lambda b, r: {"woken": True, "target": "local"})
        out = cw.wake_operator("x", "east:1-100")
        assert out["target"] == "local"
        assert "space-shuttle" in out.get("note", "")


class TestHeadlessFallsBackToLocal:
    def test_unreachable_headless_falls_back(self, monkeypatch):
        monkeypatch.setenv("GENESIS_WAKE_TARGET", "headless")
        monkeypatch.setattr(cw, "spawn_headless_kilo",
                            lambda b, r: {"woken": False,
                                          "reason": "connection refused"})
        monkeypatch.setattr(cw, "spawn_local_opencode",
                            lambda b, r: {"woken": True, "target": "local"})
        out = cw.wake_operator("x", "east:1-100")
        assert out["target"] == "local"
        assert out.get("via_fallback") is True


class TestHeadlessBriefIsReadOnly:
    """The brief is the budget. Kilo answers immediately, auto-approved,
    which means the text is the only authority for what it may do."""

    def test_headless_brief_forbids_writes(self):
        brief = cw.wake_brief_headless(
            "east", 1447, 1546, "complete",
            "they sent 2 messages.")
        low = brief.lower()
        for banned in ("resume the chain", "start a heartbeat",
                       "run a heartbeat", "restart the chain",
                       "run a census"):
            assert banned not in low, f"brief tells Kilo to: {banned!r}"
        # Prohibitions MUST be stated positively: "do not X" is not the
        # same thing as never containing X. A brief that says exactly
        # nothing about what to change stays quieter than one that names
        # the fields it guards.
        assert "report" in low or "answer" in low
        assert "read" in low or "look" in low

    def test_execution_verbs_are_absent(self):
        brief = cw.wake_brief_headless(
            "east", 1447, 1546, "complete",
            "they sent 2 messages.")
        low = brief.lower()
        for verb in ("write(", "edit(", "append(", "Start-Process",
                     "python world-sim/scripts/lockstep"):
            assert verb not in low, f"brief contains a write verb: {verb!r}"

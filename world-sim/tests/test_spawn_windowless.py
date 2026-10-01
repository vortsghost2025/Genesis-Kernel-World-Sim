"""The heartbeat path must not open a window.

Sean reported console windows flashing on screen between this session's
checks. Every sim-side process spawn carries CREATE_NO_WINDOW except one:
the heartbeat chain's own runner launches (`lockstep_chain.py`) - the
highest-frequency spawner in the stack, launching every heartbeat. A
flash every 40 seconds is a foreground bug, not a background process.

These pin the flags on every subprocess spawn in the lockstep chain.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import lockstep_chain as lc  # noqa: E402


def _has_no_window(kw):
    flags = kw.get("creationflags")
    return flags is not None and \
        bool(flags & getattr(subprocess, "CREATE_NO_WINDOW", 0))


class TestRunnerLaunchesAreWindowless:
    def test_launch_detached_runner(self, monkeypatch):
        calls = []
        monkeypatch.setattr(lc.subprocess, "run",
                            lambda cmd, **kw: (calls.append(kw) or type(
                                "R", (), {"returncode": 0, "stderr": ""})()))
        monkeypatch.setattr(lc, "RUNNER", Path("inert.py"))
        lc.attempt_heartbeat(99, "east")
        assert calls, "no launches recorded"
        for kw in calls:
            assert _has_no_window(kw), (
                f"runner launch without CREATE_NO_WINDOW "
                f"(flags={kw.get('creationflags')!r})")

    def test_push_snapshot(self, monkeypatch):
        calls = []
        monkeypatch.setattr(lc.subprocess, "run",
                            lambda cmd, **kw: (calls.append(kw) or type(
                                "R", (), {"returncode": 0, "stderr": ""})()))
        lc.push_snapshot()
        assert calls
        for kw in calls:
            assert _has_no_window(kw), (
                f"snapshot launch created a flash: {kw.get('creationflags')!r}")

    def test_inbox_check(self, monkeypatch):
        calls = []
        monkeypatch.setattr(lc.subprocess, "run",
                            lambda cmd, **kw: (calls.append(kw) or type(
                                "R", (), {"returncode": 0, "stderr": ""})()))
        lc.print_inbox()
        assert calls
        for kw in calls:
            assert _has_no_window(kw), (
                f"inbox check created a flash: {kw.get('creationflags')!r}")

"""Agent-watch launcher — process supervision without the process.

TDD suite for scripts/start_agent_watch.py. The launcher starts a
detached watcher, records a pidfile, and can stop it deliberately. What
matters is that it never lies: it reports a pid only when that pid is
alive and actually looks like the watcher, and --stop is honoured
instead of being fought by a respawn.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import start_agent_watch as launcher


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Point every module path at tmp so tests never touch the real run."""
    scratch = tmp_path / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(launcher, "SCRATCH", scratch)
    monkeypatch.setattr(launcher, "PIDFILE", scratch / "watcher.pid")
    monkeypatch.setattr(launcher, "LOGFILE", scratch / "watcher.out")
    monkeypatch.setattr(launcher, "STOP_GUARD", scratch / "watcher.stopped")
    yield scratch


class TestStatus:
    def test_not_running_without_pidfile(self):
        status = launcher.status()
        assert status["running"] is False
        assert status["pid"] is None

    def test_garbage_pidfile_is_not_a_process(self, isolated):
        isolated.joinpath("watcher.pid").write_text("not-a-pid", encoding="utf-8")
        assert launcher.running_pid() is None
        assert launcher.status()["running"] is False

    def test_dead_pid_is_not_running(self, isolated):
        # pid 0 is never a real process id
        isolated.joinpath("watcher.pid").write_text("0", encoding="utf-8")
        assert launcher.running_pid() is None

    def test_stop_guard_reported(self, isolated):
        assert launcher.status()["stop_guard"] is False
        isolated.joinpath("watcher.stopped").write_text("x", encoding="utf-8")
        assert launcher.status()["stop_guard"] is True


class TestStop:
    def test_stop_when_not_running_is_idempotent(self, isolated):
        result = launcher.stop()
        assert result["status"] == "not-running"
        assert not isolated.joinpath("watcher.stopped").exists() is False

    def test_stop_sets_the_guard(self, isolated):
        launcher.stop()
        assert isolated.joinpath("watcher.stopped").is_file()

    def test_stop_clears_a_stale_pidfile(self, isolated):
        isolated.joinpath("watcher.pid").write_text("999999", encoding="utf-8")
        launcher.stop()
        assert not isolated.joinpath("watcher.pid").exists()


class TestStart:
    def test_start_records_metadata(self, isolated, monkeypatch):
        class FakeProc:
            pid = 4242

        # not running before the spawn, alive after it
        state = {"up": False}

        def fake_pid():
            return 4242 if state["up"] else None

        def fake_popen(*a, **k):
            state["up"] = True
            return FakeProc()

        monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(launcher, "running_pid", fake_pid)
        result = launcher.start(interval=30)
        assert result["status"] == "started"
        assert result["pid"] == 4242
        assert result["interval_seconds"] == 30
        meta = json.loads(
            isolated.joinpath("watcher.meta.json").read_text(encoding="utf-8"))
        assert meta["pid"] == 4242
        assert meta["interval_seconds"] == 30

    def test_start_is_idempotent(self, isolated, monkeypatch):
        monkeypatch.setattr(launcher, "running_pid", lambda: 777)

        def explode(*a, **k):
            raise AssertionError("must not spawn a second watcher")

        monkeypatch.setattr(launcher.subprocess, "Popen", explode)
        result = launcher.start()
        assert result == {"status": "already-running", "pid": 777}

    def test_start_clears_a_leftover_stop_guard(self, isolated, monkeypatch):
        isolated.joinpath("watcher.stopped").write_text("old", encoding="utf-8")

        class FakeProc:
            pid = 5150

        state = {"up": False}

        def fake_popen(*a, **k):
            state["up"] = True
            return FakeProc()

        monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(
            launcher, "running_pid", lambda: 5150 if state["up"] else None)
        launcher.start()
        assert not isolated.joinpath("watcher.stopped").exists()

    def test_start_reports_unconfirmed_rather_than_lying(self, isolated, monkeypatch):
        class FakeProc:
            pid = 6001

        monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: FakeProc())
        monkeypatch.setattr(launcher, "running_pid", lambda: None)
        result = launcher.start()
        # a pid was spawned but we could not confirm it: say so
        assert result["status"] == "started-but-not-confirmed"
        assert result["pid"] == 6001


class TestCli:
    def test_status_flag_prints_json(self, capsys):
        assert launcher.main(["--status"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["running"] is False

    def test_stop_flag(self, capsys, isolated):
        assert launcher.main(["--stop"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] in ("stopped", "not-running")

    def test_restart_flag_stops_then_starts(self, capsys, monkeypatch):
        calls = []

        class FakeProc:
            pid = 7000

        state = {"up": False}

        def fake_popen(*a, **k):
            state["up"] = True
            return FakeProc()

        monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(
            launcher, "running_pid", lambda: 7000 if state["up"] else None)
        assert launcher.main(["--restart"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert "stop" in payload and "start" in payload
        assert payload["start"]["status"] == "started"

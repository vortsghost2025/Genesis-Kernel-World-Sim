"""The steward must never pile up.

Oct 19 2026: GenesisWorldSteward fired every 15 min with --loop 900,
and daemon mode is `while True` with no exit and no instance guard.
Eighty immortal stewards accumulated in a day, each racing to spawn
chains — 107 python processes, a crawling machine. These tests pin the
three invariants that make that impossible again:

1. a fresh lock held by a live pid -> a second steward exits WITHOUT
   polling (single instance, any mode)
2. a stale lock (dead pid) -> takeover, the sim is not left unguarded
3. daemon mode honors --max-polls and refreshes the lock heartbeat so
   a crashed steward's lock cannot block its successor forever
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import world_steward as ws  # noqa: E402


def _fresh_lock(pid: int) -> None:
    ws.LOCK_DIR.mkdir(parents=True, exist_ok=True)
    ws.STEWARD_LOCK.write_text(
        json.dumps({"pid": pid, "ts": time.time()}), encoding="utf-8",
        newline="\n")


def _stale_lock() -> None:
    ws.LOCK_DIR.mkdir(parents=True, exist_ok=True)
    # pid 999999 is alive-by-tuple trickery we avoid: use a pid that
    # cannot exist on Windows (negative pids always fail os.kill(,0))
    ws.STEWARD_LOCK.write_text(
        json.dumps({"pid": -1, "ts": time.time()}), encoding="utf-8",
        newline="\n")


class _PollSpy:
    def __init__(self):
        self.calls = 0

    def __call__(self, digest=False):
        self.calls += 1
        return {"at_utc": "t", "actions": []}


def test_second_instance_exits_without_polling(monkeypatch, capsys):
    spy = _PollSpy()
    monkeypatch.setattr(ws, "poll_once", spy)
    _fresh_lock(os.getpid())  # a live, fresh holder
    rc = ws.main(["--once"])
    assert rc == 0
    assert spy.calls == 0, "a locked-out steward must not poll"
    assert "ALREADY-RUNNING" in capsys.readouterr().out
    # the existing holder's lock must survive the rejected takeover
    assert ws.STEWARD_LOCK.exists()


def test_stale_lock_is_taken_over(monkeypatch, capsys):
    spy = _PollSpy()
    monkeypatch.setattr(ws, "poll_once", spy)
    _stale_lock()
    rc = ws.main(["--once"])
    assert rc == 0
    assert spy.calls == 1, "a dead holder's lock must not block the sim"
    out = json.loads(capsys.readouterr().out)
    assert "at_utc" in out
    # lock now belongs to this process and is cleaned up on exit
    assert not ws.STEWARD_LOCK.exists()


def test_once_mode_releases_lock(monkeypatch):
    spy = _PollSpy()
    monkeypatch.setattr(ws, "poll_once", spy)
    rc = ws.main(["--once"])
    assert rc == 0
    assert not ws.STEWARD_LOCK.exists(), \
        "an exited steward must not leave its lock behind"


def test_loop_mode_bounded_by_max_polls_and_refreshes_lock(monkeypatch, capsys):
    spy = _PollSpy()
    sleeps = []

    monkeypatch.setattr(ws, "poll_once", spy)
    monkeypatch.setattr(ws.time, "sleep", lambda s: sleeps.append(s))

    rc = ws.main(["--loop", "1", "--max-polls", "3"])
    assert rc == 0
    assert spy.calls == 3, "daemon must exit after --max-polls polls"
    assert len(sleeps) == 2, "no sleep after the final poll"
    assert "STEWARD=UP" in capsys.readouterr().out
    assert not ws.STEWARD_LOCK.exists()


def test_lock_heartbeat_advances_in_loop_mode(monkeypatch):
    spy = _PollSpy()
    monkeypatch.setattr(ws, "poll_once", spy)
    monkeypatch.setattr(ws.time, "sleep", lambda s: None)

    seen = []

    def fake_refresh():
        data = ws._read_steward_lock()
        if data:
            seen.append(data["ts"])

    monkeypatch.setattr(ws, "refresh_steward_lock", fake_refresh)
    ws.main(["--loop", "1", "--max-polls", "3"])
    assert len(seen) == 3, "lock must be refreshed every poll"
    # monotonic-ish: heartbeats never go backwards
    assert seen == sorted(seen)


def test_auto_digest_cadence_every_fourth_fire(monkeypatch, capsys):
    """The scheduled task runs --once every 15 min; the hourly digest
    cadence must live in the steward via a fire counter, not in the
    daemon loop that no longer exists."""
    spy = _PollSpy()
    monkeypatch.setattr(ws, "poll_once", spy)
    monkeypatch.setattr(ws, "send_telegram", lambda text: True)
    monkeypatch.setattr(ws, "build_narrative_summary",
                        lambda pair, since: {"summary": "quiet"})
    counter = ws.LOCK_DIR / "steward_fires.json"
    if counter.exists():
        counter.unlink()

    for i in range(1, 5):
        capsys.readouterr()
        ws.main(["--once"])
    assert spy.calls == 4
    data = json.loads(counter.read_text(encoding="utf-8"))
    assert data["count"] == 4
    # fourth fire = hourly mark
    assert data["count"] % 4 == 0
    counter.unlink(missing_ok=True)


def test_ensure_running_recreates_missing_lock_dir(monkeypatch, tmp_path):
    """Oct 19: .scratch was deleted out from under the sim. The steward
    must recreate its lock directory before spawning chains — a missing
    directory silently turns every restart into FAILED-TO-RESTART and
    the world freezes while the task keeps firing."""
    monkeypatch.setattr(ws, "LOCK_DIR", tmp_path / "lockstep")
    monkeypatch.setattr(ws, "chain_alive", lambda: {"east": False, "west": False})
    monkeypatch.setattr(ws, "forward_repair", lambda pair: None)
    monkeypatch.setattr(ws, "start_chain", lambda pair, s, e: 4242)
    monkeypatch.setattr(ws, "_count_heartbeat_records", lambda p: 100)
    monkeypatch.setattr(ws, "_read_tick", lambda store: 100)

    actions = ws.ensure_running("east")
    assert ws.LOCK_DIR.exists(), "lock dir must be recreated before spawn"
    assert any("restarted HB101" in a for a in actions)

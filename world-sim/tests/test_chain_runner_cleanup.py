"""Hard-stopped chains must not leave orphaned runners behind.

Oct 19 2026: every chain hard-stop left its in-flight detached runner
alive. Orphans finished their model calls minutes later and appended
to the ledger with stale snapshots — the writers behind the duplicate
and lost records found in both stores. kill_runner_pids is the chain's
exit cleanup; these tests pin its selectivity.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import lockstep_chain as lc  # noqa: E402


def _status(tmp_path: Path, name: str, status: str, pid) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps({"status": status, "pid": pid}),
                 encoding="utf-8", newline="\n")
    return p


def test_kills_only_inflight_runners(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        class _R:
            returncode = 0
        return _R()

    monkeypatch.setattr(lc.subprocess, "run", fake_run)
    statuses = [
        _status(tmp_path, "a.json", "running", 111),      # in flight -> kill
        _status(tmp_path, "b.json", "not-started", 222),  # launched -> kill
        _status(tmp_path, "c.json", "persisted", 333),    # done -> spare
        _status(tmp_path, "d.json", "evidence-exported", 444),  # spare
        _status(tmp_path, "e.json", "failed", None),      # no pid -> skip
    ]
    killed = lc.kill_runner_pids(statuses)
    assert killed == [111, 222]
    assert len(calls) == 2
    assert all("111" in c or "222" in c for c in calls)
    assert all(c[0] == "taskkill" and "/T" in c and "/F" in c for c in calls)


def test_survives_unreadable_status_files(tmp_path, monkeypatch):
    monkeypatch.setattr(lc.subprocess, "run",
                        lambda cmd, **kw: type("R", (), {"returncode": 0})())
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    missing = tmp_path / "missing.json"
    killed = lc.kill_runner_pids([bad, missing])
    assert killed == []


def test_kill_swallows_taskkill_failures(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("taskkill exploded")

    monkeypatch.setattr(lc.subprocess, "run", fake_run)
    sp = _status(tmp_path, "x.json", "running", 555)
    killed = lc.kill_runner_pids([sp])
    assert killed == [], "a failed kill must not raise out of cleanup"


def test_retry_kills_the_timed_out_runner_before_relaunch(tmp_path, monkeypatch):
    """A timeout is not permission for two writers to share one heartbeat."""
    store = tmp_path / "store"
    store.mkdir()
    state = store / "world_state.json"

    def set_tick(tick: int) -> None:
        state.write_text(json.dumps({"data": {
            "tick": tick, "tile_occupancy": {},
        }}), encoding="utf-8", newline="\n")

    set_tick(4)
    monkeypatch.setattr(lc, "STORES", {"east": store})
    monkeypatch.setattr(lc, "PAIRS", ("east",))
    monkeypatch.setattr(lc, "MAX_RETRIES", 2)
    monkeypatch.setattr(lc, "RETRY_DELAY_S", 0)
    monkeypatch.setattr(lc, "EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setattr(lc, "RUNNER_STATUS_PATHS", [])
    events = []
    attempts = []

    def fake_attempt(pair: str, hb: int) -> bool:
        attempts.append(hb)
        events.append(f"launch-{len(attempts)}")
        if len(attempts) == 2:
            set_tick(5)
        return True

    waits = iter((False, True))
    monkeypatch.setattr(lc, "attempt_heartbeat", fake_attempt)

    def fake_wait(pair: str, hb: int) -> bool:
        result = next(waits)
        events.append("wait-failed" if not result else "wait-exported")
        return result

    monkeypatch.setattr(lc, "wait_for_status", fake_wait)
    kills = []

    def fake_kill(paths):
        kills.append(list(paths))
        events.append("kill-old-writer")
        return [111]

    monkeypatch.setattr(lc, "kill_runner_pids", fake_kill)
    assert lc.run_tick(5) is True
    assert attempts == [5, 5]
    assert kills == [[lc.status_path("east", 5)]]
    assert events == [
        "launch-1", "wait-failed", "kill-old-writer", "launch-2", "wait-exported",
    ]

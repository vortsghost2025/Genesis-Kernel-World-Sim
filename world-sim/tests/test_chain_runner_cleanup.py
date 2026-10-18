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

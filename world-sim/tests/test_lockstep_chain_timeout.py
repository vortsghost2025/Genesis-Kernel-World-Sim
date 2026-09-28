"""The lockstep chain must fail closed when a detached runner dies.

Found by running a chain for real. The launcher wrote its initial
"not-started" status and then spawned a runner that died immediately at
argparse - the runner's parser has no `--log`. `wait_for_status` polled
forever, so the chain spun silently: it looked alive, reported nothing, and
never stopped. That is the worst behaviour available to an unattended run.

The invariant under test: a heartbeat that never reaches a terminal status
becomes a retryable failure, not an infinite wait.
"""

from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

lockstep = importlib.import_module("lockstep_chain")


@pytest.fixture
def evdir(tmp_path, monkeypatch):
    d = tmp_path / "ev"
    d.mkdir()
    monkeypatch.setattr(lockstep, "EVIDENCE_DIR", d)
    return d


def _write(evdir: Path, hb: int, payload: dict) -> None:
    lockstep.status_path("east", hb).write_text(
        json.dumps(payload), encoding="utf-8"
    )


class TestTerminalStatuses:
    def test_exported_is_success(self, evdir):
        _write(evdir, 944, {"status": "evidence-exported"})
        assert lockstep.wait_for_status("east", 944, timeout_s=5, poll_s=1)

    def test_failed_is_a_failure(self, evdir, capsys):
        _write(evdir, 944, {"status": "failed", "detail": "empty_response"})
        assert not lockstep.wait_for_status("east", 944, timeout_s=5, poll_s=1)
        assert "empty_response" in capsys.readouterr().out


class TestNonTerminalStatusTimesOut:
    """The exact failure observed: status stuck at the initial write."""

    def test_not_started_times_out(self, evdir):
        _write(evdir, 944, {"status": "not-started", "pid": 89596})
        start = time.monotonic()
        ok = lockstep.wait_for_status("east", 944, timeout_s=1, poll_s=1)
        assert not ok
        assert time.monotonic() - start < 30, "must not block indefinitely"

    def test_running_times_out(self, evdir):
        _write(evdir, 944, {"status": "running"})
        assert not lockstep.wait_for_status("east", 944, timeout_s=1, poll_s=1)

    def test_missing_status_file_times_out(self, evdir):
        assert not lockstep.wait_for_status("east", 944, timeout_s=1, poll_s=1)

    def test_unreadable_status_times_out(self, evdir):
        lockstep.status_path("east", 944).write_text(
            "{not json", encoding="utf-8"
        )
        assert not lockstep.wait_for_status("east", 944, timeout_s=1, poll_s=1)

    def test_timeout_reports_the_last_status_it_saw(self, evdir, capsys):
        """A silent timeout is undiagnosable. Name what it saw."""
        _write(evdir, 944, {"status": "not-started", "pid": 89596})
        lockstep.wait_for_status("east", 944, timeout_s=1, poll_s=1)
        out = capsys.readouterr().out
        assert "TIMEOUT" in out
        assert "not-started" in out


class TestTimeoutIsConfigured:
    def test_default_timeout_is_finite(self):
        assert 0 < lockstep.STATUS_TIMEOUT_S < 3600, (
            "an unbounded wait is the defect being fixed"
        )

    def test_default_is_generous_enough_for_a_slow_free_tier(self):
        assert lockstep.STATUS_TIMEOUT_S >= 300

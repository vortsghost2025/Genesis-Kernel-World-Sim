"""Phase 10QK - a stopped lane is not a quiet one.

Operator, 2026-11-13: "the freeze was silent ... the steward's digest
cheerfully reported 'East: adam explored; eve sent a message. West: quiet.'
while the lanes hadn't moved in five hours on a quota wall. A stall alarm
('no heartbeat completed in N minutes') belongs in that digest."

Measured that day: the NVIDIA lane hit its free-tier wall at 18:07 and no
heartbeat completed until 23:36. Every heartbeat died on the chain's own
1200s budget and retried, so the chain process stayed ALIVE the whole time,
the status files said "running", and the steward - which only restarts a lane
whose process is GONE - left it wedged for five hours.

These tests pin the three behaviours and the thresholds.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))


def _steward():
    spec = importlib.util.spec_from_file_location(
        "wsmod", str(WORLD_SIM / "scripts" / "world_steward.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _store_with_age(tmp_path: Path, minutes: float) -> Path:
    store = tmp_path / "store"
    store.mkdir(parents=True, exist_ok=True)
    state = store / "world_state.json"
    state.write_text("{}", encoding="utf-8")
    when = time.time() - minutes * 60.0
    os.utime(state, (when, when))
    return store


def _digest(mod, tmp_path, age_minutes: float) -> str:
    mod.STORES = {"east": _store_with_age(tmp_path / "e", age_minutes),
                  "west": _store_with_age(tmp_path / "w", age_minutes)}
    return mod.build_digest(
        {"summary": "adam explored", "quote": None, "question": None},
        {"summary": "quiet", "quote": None, "question": None},
    )


# ---------------------------------------------------------------------------
# the measurement
# ---------------------------------------------------------------------------

def test_a_fresh_lane_is_not_stalled(tmp_path):
    mod = _steward()
    mod.STORES = {"east": _store_with_age(tmp_path, 0.5)}
    assert mod.lane_stall_minutes("east") < 2.0
    assert mod.lane_is_stalled("east") is False


def test_a_quiet_lane_past_the_threshold_is_stalled(tmp_path):
    mod = _steward()
    mod.STORES = {"east": _store_with_age(tmp_path, 90.0)}
    minutes = mod.lane_stall_minutes("east")
    assert minutes >= 89.0
    assert mod.lane_is_stalled("east") is True


def test_an_unmeasurable_lane_is_not_reported_as_stalled(tmp_path):
    """Fail open on the REPORT: a missing store must not cry wolf."""
    mod = _steward()
    mod.STORES = {"east": tmp_path / "does-not-exist"}
    assert mod.lane_stall_minutes("east") is None
    assert mod.lane_is_stalled("east") is False


def test_the_restart_threshold_is_beyond_the_chain_budget():
    """The chain gives a heartbeat 1200s and retries once. Calling a lane
    wedged below that would interrupt a legitimate long attempt."""
    mod = _steward()
    assert mod.STALL_RESTART_MINUTES > mod.STALL_REPORT_MINUTES
    assert mod.STALL_RESTART_MINUTES * 60 > 1200 * 2


# ---------------------------------------------------------------------------
# the digest
# ---------------------------------------------------------------------------

def test_the_digest_says_stalled_instead_of_quiet(tmp_path):
    mod = _steward()
    text = _digest(mod, tmp_path, 300.0)  # five hours, as measured
    assert "STALLED" in text
    assert "no heartbeat" in text
    assert "East: adam explored" in text  # the old content is still there


def test_a_healthy_digest_is_unchanged(tmp_path):
    mod = _steward()
    text = _digest(mod, tmp_path, 1.0)
    assert "STALLED" not in text
    assert text == "East: adam explored. West: quiet."


def test_the_stall_clause_comes_first(tmp_path):
    """A frozen sim must not be readable as merely uneventful."""
    mod = _steward()
    text = _digest(mod, tmp_path, 300.0)
    assert text.index("STALLED") < text.index("East: adam explored")


# ---------------------------------------------------------------------------
# the recovery path exists and finds the right processes
# ---------------------------------------------------------------------------

def test_the_recovery_helper_exists_and_is_conservative():
    mod = _steward()
    assert callable(mod.kill_chain)
    # it must be a no-op for a lane with no processes of its own
    assert mod.kill_chain("east") >= 0


def test_ensure_running_treats_a_wedged_lane_as_down(tmp_path):
    """The behaviour that was missing: alive-but-not-advancing is restarted.

    Nothing is actually started here - the interpreter check or the store
    will refuse - but the action text must say WEDGED, which is the signal
    the old code never produced.
    """
    mod = _steward()
    mod.STORES = {"east": _store_with_age(tmp_path, 90.0),
                  "west": _store_with_age(tmp_path, 90.0)}
    mod.chain_alive = lambda: {"east": True, "west": False}
    killed = {"n": 0}

    def _fake_kill(pair):
        killed["n"] += 1
        return 1

    mod.kill_chain = _fake_kill
    actions = mod.ensure_running("east")
    assert any("WEDGED" in a for a in actions), actions
    assert killed["n"] == 1

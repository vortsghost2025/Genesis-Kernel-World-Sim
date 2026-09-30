"""Frozen-run detection: a chain that ticks but does nothing is not success.

HB1198-1243 (2026-09-30): the model route was dead upstream. The chain
logged "OK" for all 46 heartbeats, the tick advanced, and chain_watch
classified the run "complete" and told Sean the census was done. The
agents had taken zero actions for 46 consecutive heartbeats. Every human
surface said the run was fine.

The tick measures the clock, not the world. A heartbeat where NO agent
acted is a heartbeat of the plumbing, not of the sim. This pins the
distinction as a pure function so it cannot regress.

Unit under test: `run_health` - inert-heartbeat accounting and its verdict.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

from chain_watch import (  # noqa: E402
    INERT_TAIL_THRESHOLD, run_health,
)


def _hb(n, adam=None, eve=None):
    """One heartbeat record. None action = the agent did nothing."""
    acts = {}
    outcomes = {}
    for who, act in (("east_adam", adam), ("east_eve", eve)):
        if act is not None:
            acts[who] = {"action_type": act}
            outcomes[who] = {"status": "success"}
        else:
            outcomes[who] = {"status": "no_action"}
    return {"heartbeat_number": n, "action_taken": acts or None,
            "action_outcomes": outcomes}


class TestInertAccounting:
    def test_counting_only_counts_fully_inert_heartbeats(self):
        rows = [_hb(n) for n in range(1, 6)]
        assert run_health(rows)["inert_tail"] == 5

    def test_one_acting_agent_breaks_the_inert_run(self):
        """A heartbeat is not inert if EITHER agent moved. Half-alive is
        alive - this must not over-report a stall."""
        rows = [_hb(n, adam="gather" if n == 3 else None) for n in range(1, 6)]
        h = run_health(rows)
        assert h["inert_tail"] == 2, "counts backward from the last real action"

    def test_acting_on_both_sides_ends_the_run(self):
        rows = [_hb(n, adam="gather", eve="move") for n in range(1, 4)]
        assert run_health(rows)["inert_tail"] == 0

    def test_empty_history_is_not_a_stall(self):
        """No evidence is not evidence of failure. A store that cannot be
        read must not be reported as a frozen world."""
        assert run_health([])["inert_tail"] == 0
        assert run_health([])["verdict"] == "unknown"

    def test_single_heartbeat_never_trips(self):
        assert run_health([_hb(1)])["verdict"] != "frozen"


class TestVerdicts:
    def test_long_inert_tail_is_frozen(self):
        rows = [_hb(n) for n in range(1, 1 + INERT_TAIL_THRESHOLD)]
        h = run_health(rows)
        assert h["inert_tail"] == INERT_TAIL_THRESHOLD
        assert h["verdict"] == "frozen"

    def test_one_short_of_the_threshold_is_healthy(self):
        """A couple of dead heartbeats happen (a 429 on one key). It is
        not a frozen world and must not cry wolf."""
        rows = [_hb(n) for n in range(1, INERT_TAIL_THRESHOLD)]
        h = run_health(rows)
        assert h["inert_tail"] == INERT_TAIL_THRESHOLD - 1
        assert h["verdict"] == "healthy"

    def test_healthy_run_reports_its_last_real_heartbeat(self):
        rows = [_hb(n, adam="move") for n in range(1, 6)]
        rows += [_hb(n) for n in range(6, 8)]
        h = run_health(rows)
        assert h["verdict"] == "healthy"
        assert h["last_active_heartbeat"] == 5


class TestWhyItMatters:
    def test_the_real_incident_is_now_frozen(self):
        """Replay the shape of HB1198-1243: 46 inert heartbeats behind a
        run that reported OK. This test is the regression guard for the
        exact failure Sean was not told about."""
        rows = [_hb(n, adam="gather", eve="move") for n in range(1, 20)]
        rows += [_hb(n) for n in range(20, 66)]
        h = run_health(rows)
        assert h["inert_tail"] == 46
        assert h["verdict"] == "frozen"
        assert h["last_active_heartbeat"] == 19

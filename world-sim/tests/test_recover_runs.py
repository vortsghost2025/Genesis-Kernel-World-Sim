"""Decide what a boot should do with a run that was interrupted.

The machine rebooted overnight on 2026-09-30 and took a census with it.
Nobody found out for hours. The recovery decision is unattended, so it
has to be a pure function that can be pinned: given the store's tick, the
run's target, and whether a chain is alive, what is the correct action?

Failure modes this must not have:
  * resume a run that already finished (double-counted heartbeats)
  * resume from the wrong heartbeat (gap in the record, or a re-run)
  * declare failure when it merely cannot tell
  * act at all when a chain is already running (duplicate processes)
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

from recover_runs import plan_recovery  # noqa: E402


class TestAlreadyDone:
    def test_finished_run_is_left_alone(self):
        p = plan_recovery(tick=200, target_end=200, chain_alive=False)
        assert p["action"] == "none"
        assert p["reason"].startswith("run already reached")

    def test_overshoot_is_also_left_alone(self):
        """A tick past the target means the run finished; never rewind."""
        p = plan_recovery(tick=205, target_end=200, chain_alive=False)
        assert p["action"] == "none"

    def test_live_chain_is_never_duplicated(self):
        p = plan_recovery(tick=150, target_end=200, chain_alive=True)
        assert p["action"] == "none"
        assert "already running" in p["reason"]


class TestResume:
    def test_interrupted_run_resumes_from_the_next_heartbeat(self):
        p = plan_recovery(tick=149, target_end=200, chain_alive=False)
        assert p["action"] == "resume"
        assert p["start"] == 150, "must resume AT the next heartbeat"
        assert p["end"] == 200

    def test_one_heartbeat_left_still_resumes(self):
        p = plan_recovery(tick=199, target_end=200, chain_alive=False)
        assert p["action"] == "resume"
        assert (p["start"], p["end"]) == (200, 200)

    def test_resume_carries_the_remaining_count(self):
        p = plan_recovery(tick=100, target_end=200, chain_alive=False)
        assert p["remaining"] == 100


class TestCannotTell:
    def test_unreadable_store_does_not_start_anything(self):
        """Absence of evidence is not evidence of a broken run. Starting a
        chain on a guess is how you get two chains writing one store."""
        p = plan_recovery(tick=None, target_end=200, chain_alive=False)
        assert p["action"] == "none"
        assert "cannot read" in p["reason"].lower()

    def test_no_target_means_nothing_to_resume(self):
        p = plan_recovery(tick=150, target_end=0, chain_alive=False)
        assert p["action"] == "none"

    def test_nonsense_tick_is_refused(self):
        p = plan_recovery(tick="oops", target_end=200, chain_alive=False)
        assert p["action"] == "none"

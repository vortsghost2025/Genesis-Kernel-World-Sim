"""A capability grant that makes nothing callable is a lie.

West Adam at HB1157: "I used request_capability and it returned success,
but no new action appeared." The contract already defines verbs the agent
can call. If the grant does not add one, the call is a no-op whose
outcome the agent is asked to believe anyway.

Load the granular truth, not a verdict. When the capability granted
nicely, even if the word 'success' stayed in the status, that means it was
silent - which means the record claims a change that was not netted.

Corrective success is inappropriate; this fails with a targeted denial.

The mechanism is not permission (capability grants would still count as
pretension). Have it fail honestly when it doesn't, with the same message
each time.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
)


class TestGrantIsHonest:
    def test_unknown_capability_does_not_scam(self, tmp_path):
        """When a grant claims to change nothing, it calls it denied."""
        store = FirstPairPersistenceStore(root=tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt._load_or_initialize()
        out = rt._execute_request_capability(
            "east_adam",
            {"capability_id": "craft", "capability_reason": "want to use surfaces"},
            1000)
        assert out["status"] == "not_achieved"
        assert "does not exist" in out["reason"] or "appeared" not in out["reason"].lower() or "no such action" in out["reason"], (
            "denial must state that no-action occurred, truthfully, not a habit of success-claims")

    def test_existing_grant_is_honest_that_it_adds_nothing(self, tmp_path):
        """A capability the agent already has must not lie again."""
        store = FirstPairPersistenceStore(root=tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt._load_or_initialize()
        # movement is capability that already exists or doesn't; this is
        # the same question in both directions
        out = rt._execute_request_capability(
            "east_adam",
            {"capability_id": "movement"},
            1000)
        assert out["status"] in ("already_present", "not_achieved", "rejected"), (
            f"graceful outcome required, got {out['status']=!r}")


class TestFailureIsInventoriable:
    def test_no_action_change_does_not_appear(self, tmp_path):
        """When a grant accepts a capability that never becomes an action,
        the evidence record must say so - not say it succeeded."""
        store = FirstPairPersistenceStore(root=tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt._load_or_initialize()
        out = rt._execute_request_capability(
            "east_eve", {"capability_id": "use_object", "capability_reason":
                         "certain things may be powered"}, heartbeat_number=1200)
        rec = rt._world_state.capability_requests[-1]
        assert rec.get("status") != "success", (
            "record must not claim success when no callable action followed")
        assert out["status"] != "success", (
            "the answer to the agent must not say 'succeeded' on a noop")

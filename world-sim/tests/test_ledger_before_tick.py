"""The heartbeat ledger must be written BEFORE the tick advances.

The split-brain has now happened twice (HB1328, HB1646): the runtime
persists world_state (tick forward) first and appends the heartbeat
record second. A crash between those two writes leaves the tick ahead
of the ledger - the world claims a heartbeat the record cannot prove,
and the only repair is to roll history back, hoping nothing was
double-applied.

The correct order is the reverse: append the heartbeat record FIRST,
then save the world state. A crash between writes then leaves the
ledger ahead of the tick - the truthful direction. Recovery rolls the
tick forward to match a record that provably exists; it never has to
un-write history.

Unit under test: the write order inside _persist_shared_state.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

import backend.world.first_pair_persistence as persistence  # noqa: E402
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402


class TestLedgerBeforeTick:
    def test_heartbeat_is_written_before_world_state(self, tmp_path):
        """The invariant that would have prevented both split-brains:
        whatever happens, the ledger never trails the tick it names."""
        calls: list[str] = []
        original_save = persistence.save_world_state
        original_append = persistence.append_heartbeat

        def spy_save(store, ws):
            calls.append("world_state")
            return original_save(store, ws)

        def spy_append(store, record):
            calls.append("heartbeat")
            return original_append(store, record)

        persistence.save_world_state = spy_save
        persistence.append_heartbeat = spy_append
        try:
            import backend.world.first_pair_runtime as rt
            rt.save_world_state = spy_save
            rt.append_heartbeat = spy_append
            store = persistence.FirstPairPersistenceStore(root=tmp_path)
            rt_runtime = FirstPairRuntime(heartbeat_limit=1, store=store)
            rt_runtime._load_or_initialize()
            rt_runtime._persist_shared_state(
                42,
                adam_action={"action_type": "no_action"},
                adam_outcome={"status": "success"},
            )
        finally:
            persistence.save_world_state = original_save
            persistence.append_heartbeat = original_append
            rt.save_world_state = original_save
            rt.append_heartbeat = original_append

        assert calls, "no writes recorded - the spy did not attach"
        assert calls.index("heartbeat") < calls.index("world_state"), (
            f"world_state written before the heartbeat record: {calls}. "
            f"A crash between these writes is exactly the HB1328/HB1646 "
            f"split-brain: tick ahead of the ledger, history rolled back.")

    def test_repair_direction_is_forward_after_the_fix(self, tmp_path):
        """With ledger-first ordering, the crash residue is count > tick.
        Rolling FORWARD to the record is safe: the record proves the
        heartbeat happened; nothing has to be un-written."""
        store = persistence.FirstPairPersistenceStore(root=tmp_path)
        ws = persistence.WorldStateRecord(
            world_state_id="ws", schema_version="1", tick=9)
        persistence.save_world_state(store, ws)
        rec = persistence.HeartbeatRecord(
            heartbeat_number=10, agent_id="both", position="",
            observation={}, action_taken=None)
        persistence.append_heartbeat(store, rec)
        # simulate: ledger ahead of tick (crash after append, before save)
        hist = persistence.load_heartbeat_history(store)
        assert len(hist) == 1 and hist[0].heartbeat_number == 10
        assert store._read_json(store._path("world_state.json"))["data"]["tick"] == 9
        # forward repair: tick := last record's number
        ws.tick = 10
        persistence.save_world_state(store, ws)
        assert store._read_json(store._path("world_state.json"))["data"]["tick"] == 10

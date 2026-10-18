"""The heartbeat ledger must never lose or duplicate a record.

Oct 19 2026, ground truth from the live stores: east held triple
duplicates of 3840/3841 and had "lost" 3845-3846; west duplicated 3677
and lost 3686-3688. The mechanism: detached runner orphans outlive
their chain, then append_heartbeat does read-full/append/write-full
with NO store lock and NO idempotence — concurrent writers clobber,
duplicates inflate the count, and the inflated count masks the lost
tail records in the chain's count==tick invariant.

These tests pin: idempotent append (an orphan's late write is a no-op,
not a duplicate) and fresh-read-under-lock (a writer holding a stale
snapshot cannot erase records that landed after its read).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_persistence as fp  # noqa: E402


@dataclass
class _Rec:
    heartbeat_number: int
    agent_id: str = "test-adam"
    position: str = "public-start"
    observation: dict = None
    action_taken: dict = None

    def __post_init__(self):
        self.observation = self.observation or {}
        self.action_taken = self.action_taken or {}


def _store(tmp_path: Path):
    store = fp.FirstPairPersistenceStore(tmp_path)
    return store


def test_append_is_idempotent_same_heartbeat(tmp_path):
    """Appending the same heartbeat twice must leave ONE record. This
    is what stops orphaned runners from duplicating the ledger."""
    store = _store(tmp_path)
    fp.append_heartbeat(store, _Rec(3846))
    fp.append_heartbeat(store, _Rec(3846))
    history = fp.load_heartbeat_history(store)
    assert len(history) == 1, f"expected 1 record, got {len(history)}"
    assert history[0].heartbeat_number == 3846


def test_append_rejects_older_heartbeat_than_ledger_tail(tmp_path):
    """An orphan finishing a stale run must not wind the ledger back."""
    store = _store(tmp_path)
    for n in (1, 2, 3):
        fp.append_heartbeat(store, _Rec(n))
    fp.append_heartbeat(store, _Rec(2))
    history = fp.load_heartbeat_history(store)
    assert [r.heartbeat_number for r in history] == [1, 2, 3], (
        "a late stale append must be a no-op"
    )


def test_append_sees_records_that_landed_after_its_load(tmp_path):
    """Writer B must not erase writer A's record: append re-reads the
    ledger inside the store lock, so a stale in-memory snapshot cannot
    win the final write."""
    store = _store(tmp_path)
    fp.append_heartbeat(store, _Rec(1))
    fp.append_heartbeat(store, _Rec(2))
    fp.append_heartbeat(store, _Rec(3))
    history = fp.load_heartbeat_history(store)
    assert [r.heartbeat_number for r in history] == [1, 2, 3]


def test_append_still_persists_new_records(tmp_path):
    """The guard must not swallow legitimate forward progress."""
    store = _store(tmp_path)
    for n in (1, 2):
        fp.append_heartbeat(store, _Rec(n))
    fp.append_heartbeat(store, _Rec(3))
    history = fp.load_heartbeat_history(store)
    assert [r.heartbeat_number for r in history] == [1, 2, 3]

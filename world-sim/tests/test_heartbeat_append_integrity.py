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

import json
import multiprocessing as mp
import os
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


def test_atomic_write_tmp_name_is_pid_unique(tmp_path):
    """Oct 18: two writers sharing `memory.tmp` interleaved their writes
    and produced valid-JSON-plus-garbage — the east pair froze at the
    next startup on 'Extra data'. The tmp file must carry the writer's
    pid so concurrent writers never share one."""
    store = _store(tmp_path)
    store._atomic_write(tmp_path / "memory.json", {"data": [1, 2, 3]})
    expected = tmp_path / f"memory.{os.getpid()}.tmp"
    assert not expected.exists(), "tmp file must be consumed by replace"
    assert json.loads((tmp_path / "memory.json").read_text(encoding="utf-8")) == {"data": [1, 2, 3]}


def _atomic_writer_worker(store_dir: str, file_name: str, worker_id: int, iters: int):
    store = fp.FirstPairPersistenceStore(Path(store_dir))
    target = Path(store_dir) / file_name
    for i in range(iters):
        store._atomic_write(target, {"worker": worker_id, "iter": i, "payload": "x" * 50})


def _atomic_reader_worker(store_dir: str, file_name: str, num_reads: int):
    import time
    store = fp.FirstPairPersistenceStore(Path(store_dir))
    target = Path(store_dir) / file_name
    for _ in range(num_reads):
        res = store._read_json(target)
        if res is not None:
            assert "worker" in res and "iter" in res and "payload" in res
        time.sleep(0.002)


def test_concurrent_multiprocess_atomic_writes(tmp_path):
    """Stress test concurrent multiprocess atomic writes on Windows.
    Verifies that pid-unique tmp files and PermissionError backoff handle
    multiple concurrent writer processes contending on the same file without
    tearing, JSON corruption ('Extra data'), or leaked tmp files."""
    store_dir = str(tmp_path)
    file_name = "contested.json"
    num_workers = 4
    iters_per_worker = 15

    ctx = mp.get_context("spawn")
    processes = [
        ctx.Process(target=_atomic_writer_worker, args=(store_dir, file_name, w_id, iters_per_worker))
        for w_id in range(num_workers)
    ]
    for p in processes:
        p.start()
    for p in processes:
        p.join()
        assert p.exitcode == 0, f"Worker process failed with exit code {p.exitcode}"

    target_file = tmp_path / file_name
    assert target_file.exists(), "Target file must exist after writes"
    content = json.loads(target_file.read_text(encoding="utf-8"))
    assert "worker" in content and "iter" in content and content["payload"] == "x" * 50

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert not tmp_files, f"Leaked tmp files found: {tmp_files}"


def test_concurrent_multiprocess_readers_and_writers(tmp_path):
    """Stress test concurrent readers and writers under multiprocess contention.
    Verifies that simultaneous os.replace writes with fsync and json.load reads
    succeed without sharing violations or unhandled PermissionErrors."""
    store_dir = str(tmp_path)
    file_name = "rw_contested.json"
    ctx = mp.get_context("spawn")

    writers = [
        ctx.Process(target=_atomic_writer_worker, args=(store_dir, file_name, w_id, 15))
        for w_id in range(2)
    ]
    readers = [
        ctx.Process(target=_atomic_reader_worker, args=(store_dir, file_name, 30))
        for _ in range(2)
    ]
    all_procs = writers + readers
    for p in all_procs:
        p.start()
    for p in all_procs:
        p.join()
        assert p.exitcode == 0, f"Process {p} failed with exit code {p.exitcode}"

    target = tmp_path / file_name
    assert target.exists()
    final_data = json.loads(target.read_text(encoding="utf-8"))
    assert "worker" in final_data and "payload" in final_data


def test_atomic_write_calls_fsync(tmp_path, monkeypatch):
    """Verify that os.fsync is explicitly called on the file descriptor before replace."""
    store = _store(tmp_path)
    fsync_called = []
    orig_fsync = os.fsync

    def mock_fsync(fd):
        fsync_called.append(fd)
        return orig_fsync(fd)

    monkeypatch.setattr(os, "fsync", mock_fsync)
    store._atomic_write(tmp_path / "fsync_test.json", {"durable": True})
    assert len(fsync_called) == 1, "os.fsync must be called exactly once per atomic write"


def test_atomic_write_failure_path_raises_after_retries(tmp_path, monkeypatch):
    """Verify failure path: if os.replace permanently fails, atomic_write raises PermissionError after retries."""
    import pytest
    store = _store(tmp_path)
    attempts = []

    def mock_replace(src, dst):
        attempts.append(src)
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", mock_replace)
    with pytest.raises(PermissionError):
        store._atomic_write(tmp_path / "fail_test.json", {"fail": True})
    assert len(attempts) == 6, "Must retry exactly 6 times before re-raising"

"""Two chains must never write one store.

On 2026-09-30 a chain died at HB1393 (runner failure, retries exhausted)
and the boot recovery picked it up correctly. But the guard that decides
"is a chain already running" is a heuristic - a recorded pid plus a
process scan - and heuristics are exactly what let a duplicate through
earlier that day. A lock makes the guarantee structural instead of
probable: the second writer is refused, not queued.

Interleaving two writers into one heartbeat ledger produces a record that
looks plausible and is wrong, and no later check can detect it. That is
the whole reason this exists.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import recover_runs as rr  # noqa: E402


class TestSecondWriterIsRefused:
    def test_live_holder_blocks_a_new_lock(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rr, "LOCKS", tmp_path)
        monkeypatch.setattr(rr, "_pid_alive", lambda pid: pid == 111)
        first = rr.acquire_store_lock("east", 111)
        assert first is not None
        assert rr.acquire_store_lock("east", 222) is None, (
            "a second writer must be refused, not queued")

    def test_holder_pid_can_relock(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rr, "LOCKS", tmp_path)
        monkeypatch.setattr(rr, "_pid_alive", lambda pid: True)
        first = rr.acquire_store_lock("east", 111)
        assert rr.acquire_store_lock("east", 111) == first

    def test_stale_lock_is_taken_over(self, tmp_path, monkeypatch):
        """The holder died; its lock must not block the next run forever.
        This is the case that actually happens after a crash."""
        monkeypatch.setattr(rr, "LOCKS", tmp_path)
        monkeypatch.setattr(rr, "_pid_alive", lambda pid: False)
        path = tmp_path / "chain_east.lock"
        path.write_text("999", encoding="utf-8")
        assert rr.acquire_store_lock("east", 222) is not None

    def test_garbage_lock_is_treated_as_stale(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rr, "LOCKS", tmp_path)
        path = tmp_path / "chain_east.lock"
        path.write_text("not-a-pid", encoding="utf-8")
        assert rr.acquire_store_lock("east", 222) is not None

    def test_locks_are_per_pair(self, tmp_path, monkeypatch):
        """East and west are separate stores with separate chains; a lock
        on one must not block the other."""
        monkeypatch.setattr(rr, "LOCKS", tmp_path)
        monkeypatch.setattr(rr, "_pid_alive", lambda pid: True)
        assert rr.acquire_store_lock("east", 111) is not None
        assert rr.acquire_store_lock("west", 222) is not None

    def test_release_frees_the_lock(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rr, "LOCKS", tmp_path)
        monkeypatch.setattr(rr, "_pid_alive", lambda pid: pid == 111)
        path = rr.acquire_store_lock("east", 111)
        rr.release_store_lock(path)
        assert rr.acquire_store_lock("east", 222) is not None


class TestLivenessFailsSafe:
    def test_detection_failure_means_do_not_start(self, tmp_path,
                                                  monkeypatch):
        """If we cannot tell whether a chain is alive, we must not start
        one. A missed resume is recoverable in a minute; two writers are
        not recoverable at all."""
        monkeypatch.setattr(rr, "RUN_STATE", tmp_path / "missing.json")
        real_import = __builtins__["__import__"] if isinstance(
            __builtins__, dict) else __builtins__.__import__

        def boom(name, *a, **k):
            if name == "psutil":
                raise ImportError("simulated: psutil unavailable")
            return real_import(name, *a, **k)

        monkeypatch.setitem(__builtins__ if isinstance(
            __builtins__, dict) else __builtins__.__dict__,
            "__import__", boom)
        assert rr.chain_alive() is True, (
            "unknown liveness must be treated as ALIVE")

"""Phase 10TW: the heartbeat ledger is append-only; heartbeat.json is a window.

`heartbeat.json` was ONE JSON object read in full and rewritten in full on every
heartbeat. Measured 2026-11-21 it reached 330MB for the west lane (~4.3s of a
~216s heartbeat) and a plain analysis process could no longer read it at all
(MemoryError). The hot path only ever wants the last few records, so:

  * `heartbeat_ledger.jsonl` is the FULL history, appended O(1);
  * `heartbeat.json` is a bounded WINDOW of the most recent records;
  * the hot callers read the tail; the exports still read everything.
"""
from __future__ import annotations

import json
import sys

import pytest
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

import backend.world.first_pair_persistence as persistence  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    HeartbeatRecord,
    _HEARTBEAT_WINDOW,
    append_heartbeat,
    load_heartbeat_history,
    load_recent_heartbeats,
    read_heartbeat_records,
)


# The window size is irrelevant to the invariant and 540 appends each
# rewriting a 500-record window cost 18s; pin it small instead.
WINDOW = 10


@pytest.fixture(autouse=True)
def _small_window(monkeypatch):
    monkeypatch.setattr(persistence, "_HEARTBEAT_WINDOW", WINDOW)


def _store(tmp_path: Path) -> FirstPairPersistenceStore:
    return FirstPairPersistenceStore(tmp_path / "store")


def _rec(n: int) -> HeartbeatRecord:
    return HeartbeatRecord(heartbeat_number=n, agent_id="genesis-agent-test",
                           position="cont_a_gen_0_0", observation={},
                           action_taken=None)


def _fill(store, count: int, start: int = 1) -> None:
    for n in range(start, start + count):
        append_heartbeat(store, _rec(n))


# --- the ledger is the full history -----------------------------------------

def test_every_heartbeat_reaches_the_ledger(tmp_path):
    store = _store(tmp_path)
    _fill(store, 5)
    assert (tmp_path / "store" / "heartbeat_ledger.jsonl").is_file()
    got = [r["heartbeat_number"] for r in read_heartbeat_records(store.root)]
    assert got == [1, 2, 3, 4, 5]


def test_the_ledger_keeps_growing_past_the_window(tmp_path):
    """The exact defect: the old file was the whole history and the whole file."""
    store = _store(tmp_path)
    _fill(store, WINDOW + 40)
    full = load_heartbeat_history(store)
    assert len(full) == WINDOW + 40, len(full)
    assert full[0].heartbeat_number == 1
    assert full[-1].heartbeat_number == WINDOW + 40


# --- the window is bounded ---------------------------------------------------

def test_the_window_file_is_bounded(tmp_path):
    store = _store(tmp_path)
    _fill(store, WINDOW + 40)
    raw = json.loads((tmp_path / "store" / "heartbeat.json").read_text(encoding="utf-8"))
    assert len(raw["data"]) == WINDOW, len(raw["data"])
    # and it is the TAIL of the history, not the head
    assert raw["data"][-1]["heartbeat_number"] == WINDOW + 40


def test_recent_heartbeats_returns_the_tail_without_losing_it(tmp_path):
    store = _store(tmp_path)
    _fill(store, WINDOW + 40)
    recent = load_recent_heartbeats(store)
    assert len(recent) == WINDOW
    assert recent[-1].heartbeat_number == WINDOW + 40
    assert recent[0].heartbeat_number == 41


def test_recent_heartbeats_honours_a_small_limit(tmp_path):
    store = _store(tmp_path)
    _fill(store, WINDOW + 10)
    got = load_recent_heartbeats(store, limit=4)
    assert [r.heartbeat_number for r in got] == [WINDOW + 7, WINDOW + 8,
                                              WINDOW + 9, WINDOW + 10]


# --- idempotence is preserved ------------------------------------------------

def test_a_duplicate_is_still_skipped(tmp_path):
    store = _store(tmp_path)
    _fill(store, 3)
    append_heartbeat(store, _rec(3))
    assert len(load_heartbeat_history(store)) == 3
    assert read_heartbeat_records(store.root)[-1]["heartbeat_number"] == 3


def test_a_stale_record_is_still_skipped(tmp_path):
    store = _store(tmp_path)
    _fill(store, 5)
    append_heartbeat(store, _rec(2))
    assert [r.heartbeat_number for r in load_heartbeat_history(store)] == [1, 2, 3, 4, 5]


def test_the_full_history_is_deduplicated_and_in_order(tmp_path):
    """A duplicate that DID slip into the ledger must not inflate the count --
    the reader dedupes so a bounded dup check cannot corrupt the record."""
    store = _store(tmp_path)
    _fill(store, 3)
    ledger = tmp_path / "store" / "heartbeat_ledger.jsonl"
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"heartbeat_number": 2, "agent_id": "x",
                             "position": "p", "observation": {},
                             "action_taken": None}) + "\n")
    got = [r.heartbeat_number for r in load_heartbeat_history(store)]
    assert got == [1, 2, 3], got


# --- preflight uses the TICK, because the count is no longer a position ------

def test_preflight_no_longer_requires_count_to_equal_the_tick(tmp_path):
    """With a bounded window the count is stuck at the window size. Requiring
    count == expect-1 would have refused EVERY run."""
    from backend.world.canonical_heartbeat_runner import preflight
    store = _store(tmp_path)
    _fill(store, WINDOW + 40)
    tick = WINDOW + 40
    (tmp_path / "store" / "world_state.json").write_text(
        json.dumps({"data": {"tick": tick}}), encoding="utf-8")
    ok, detail = preflight(store.root, tick + 1)
    assert ok, detail
    assert f"tick {tick}" in detail


def test_preflight_still_refuses_when_the_tick_is_wrong(tmp_path):
    from backend.world.canonical_heartbeat_runner import preflight
    store = _store(tmp_path)
    _fill(store, 5)
    (tmp_path / "store" / "world_state.json").write_text(
        json.dumps({"data": {"tick": 3}}), encoding="utf-8")
    ok, detail = preflight(store.root, 6)
    assert not ok and "tick 3" in detail


# --- backward compatibility --------------------------------------------------

def test_a_store_without_a_ledger_still_reads(tmp_path):
    """Pre-ledger stores must keep working, from the window file alone."""
    store = _store(tmp_path)
    (tmp_path / "store").mkdir(parents=True, exist_ok=True)
    (tmp_path / "store" / "heartbeat.json").write_text(json.dumps({
        "type": "heartbeat_record", "schema_version": "x",
        "data": [{"heartbeat_number": n, "agent_id": "x", "position": "p",
                  "observation": {}, "action_taken": None} for n in (1, 2, 3)],
    }), encoding="utf-8")
    assert [r.heartbeat_number for r in load_heartbeat_history(store)] == [1, 2, 3]
    assert [r.heartbeat_number for r in load_recent_heartbeats(store)] == [1, 2, 3]
    assert [r["heartbeat_number"] for r in read_heartbeat_records(store.root)] == [1, 2, 3]

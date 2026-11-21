"""A ledger created mid-history must not truncate the history.

The live store's ledger was born after 14,800 heartbeats, so returning the ledger
alone silently cut the viewer's timeline to the handful appended since.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    read_heartbeat_records,
)


def _hb(n: int) -> dict:
    return {"heartbeat_number": n, "agent_id": "x", "position": "p",
            "observation": {}, "action_taken": None}


def test_the_ledger_and_the_window_are_merged(tmp_path):
    store = tmp_path / "store"
    store.mkdir(parents=True)
    # the window holds the OLD history and the NEW record
    (store / "heartbeat.json").write_text(json.dumps({
        "type": "heartbeat_record", "data": [_hb(n) for n in (1, 2, 3, 4)]}),
        encoding="utf-8")
    # the ledger was born later: only record 4 is in it
    (store / "heartbeat_ledger.jsonl").write_text(
        json.dumps(_hb(4)) + "\n", encoding="utf-8")

    got = [r["heartbeat_number"] for r in read_heartbeat_records(store)]
    assert got == [1, 2, 3, 4], got


def test_a_record_in_both_files_is_not_duplicated(tmp_path):
    store = tmp_path / "store"
    store.mkdir(parents=True)
    (store / "heartbeat.json").write_text(json.dumps({
        "type": "heartbeat_record", "data": [_hb(1), _hb(2)]}), encoding="utf-8")
    (store / "heartbeat_ledger.jsonl").write_text(
        json.dumps(_hb(1)) + "\n" + json.dumps(_hb(2)) + "\n", encoding="utf-8")
    got = [r["heartbeat_number"] for r in read_heartbeat_records(store)]
    assert got == [1, 2], got


def test_the_ledger_wins_for_a_number_it_holds(tmp_path):
    """If the same heartbeat_number appears in both, the ledger's copy is newer."""
    store = tmp_path / "store"
    store.mkdir(parents=True)
    (store / "heartbeat.json").write_text(json.dumps({
        "type": "heartbeat_record", "data": [dict(_hb(7), agent_id="old")]}),
        encoding="utf-8")
    (store / "heartbeat_ledger.jsonl").write_text(
        json.dumps(dict(_hb(7), agent_id="new")) + "\n", encoding="utf-8")
    got = read_heartbeat_records(store)
    assert len(got) == 1 and got[0]["agent_id"] == "new", got


def test_the_result_is_ordered(tmp_path):
    store = tmp_path / "store"
    store.mkdir(parents=True)
    (store / "heartbeat_ledger.jsonl").write_text(
        "\n".join(json.dumps(_hb(n)) for n in (5, 3, 4)) + "\n", encoding="utf-8")
    assert [r["heartbeat_number"] for r in read_heartbeat_records(store)] == [3, 4, 5]


def test_an_empty_store_is_empty_not_an_error(tmp_path):
    store = tmp_path / "store"
    store.mkdir(parents=True)
    assert read_heartbeat_records(store) == []

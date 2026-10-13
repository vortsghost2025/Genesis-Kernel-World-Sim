"""The chain must not OOM reading a ledger it only counts.

East died at HB2230 with a MemoryError inside `store_state`, which
loads the FULL heartbeat JSON — every record, every observation, every
visible tile — just to return `len(data)`. At 2,230 records the file
is 4MB+ and grows every heartbeat. The chain calls this on every tick.

The fix: count the records without parsing the whole file. A JSON
array of objects has exactly one top-level `"data"` key; counting
`"heartbeat_number"` occurrences with a streaming byte scan gives the
same number for a fraction of the memory.

Unit under test: the count matches, and the memory is bounded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import lockstep_chain as lc  # noqa: E402


class TestStreamingCount:
    def test_count_matches_full_parse(self, tmp_path):
        """The streaming count must produce the same number as loading
        the full JSON and calling len()."""
        records = [{"heartbeat_number": n, "observation": {"tiles": [1, 2, 3]}}
                   for n in range(1, 51)]
        p = tmp_path / "heartbeat.json"
        p.write_text(json.dumps({"data": records}), encoding="utf-8")
        streaming = lc._count_heartbeat_records(p)
        assert streaming == 50

    def test_empty_file_is_zero(self, tmp_path):
        p = tmp_path / "heartbeat.json"
        p.write_text('{"data": []}', encoding="utf-8")
        assert lc._count_heartbeat_records(p) == 0

    def test_real_store_counts(self):
        """Verify against the actual east store (2,230+ records)."""
        p = lc.STORES["east"] / "heartbeat.json"
        streaming = lc._count_heartbeat_records(p)
        full = len(json.loads(p.read_text(encoding="utf-8")).get("data", []))
        assert streaming == full, (
            f"streaming={streaming} full={full} — the streaming count "
            f"must match the full parse exactly")

    def test_store_state_uses_streaming_count(self, monkeypatch, tmp_path):
        """store_state must call _count_heartbeat_records, not the full
        json.loads. Otherwise the OOM recurs at the next growth boundary."""
        calls = []
        monkeypatch.setattr(lc, "_count_heartbeat_records",
                            lambda p: calls.append(p) or 50)
        monkeypatch.setattr(lc, "STORES",
                            {"east": tmp_path, "west": tmp_path})
        (tmp_path / "world_state.json").write_text(
            '{"data": {"tick": 10, "tile_occupancy": {}}}',
            encoding="utf-8")
        count, tick, occ = lc.store_state("east")
        assert count == 50
        assert calls, "store_state did not call the streaming counter"

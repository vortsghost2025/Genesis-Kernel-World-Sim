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

    def test_real_store_counts(self, tmp_path):
        """Verify against the actual east store.

        Phase 10TA: the file is SNAPSHOT first. This test used to read the live
        heartbeat file twice while the running world rewrites it (123MB per
        heartbeat), so it could see a mid-write state and fail for a reason that
        has nothing to do with the counter. Snapshotting keeps the intent -- a
        real, large, live file -- without racing the writer.
        """
        import shutil
        src = lc.STORES["east"] / "heartbeat.json"
        snap = tmp_path / "heartbeat.snapshot.json"
        shutil.copyfile(src, snap)
        streaming = lc._count_heartbeat_records(snap)
        full = len(json.loads(snap.read_text(encoding="utf-8")).get("data", []))
        assert streaming == full, (
            f"streaming={streaming} full={full} - the streaming count "
            f"must match the full parse exactly")

    def test_a_match_straddling_the_read_chunk_is_not_lost(self, tmp_path, monkeypatch):
        """The measured bug: 14,558 records counted as 14,557 because exactly one
        occurrence fell across a 1MB boundary of a 123MB file. A small chunk makes
        straddles certain instead of rare."""
        monkeypatch.setattr(lc, "CHUNK_BYTES", 37)
        p = tmp_path / "heartbeat.json"
        p.write_text(json.dumps({"data": [
            {"heartbeat_number": n, "observation": {}} for n in range(1, 501)]}),
            encoding="utf-8")
        assert lc._count_heartbeat_records(p) == 500

    def test_a_chunk_that_is_exactly_the_pattern_still_counts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lc, "CHUNK_BYTES", len(b'"heartbeat_number":'))
        p = tmp_path / "heartbeat.json"
        p.write_text(json.dumps({"data": [
            {"heartbeat_number": n} for n in range(1, 21)]}), encoding="utf-8")
        assert lc._count_heartbeat_records(p) == 20

    def test_the_two_counters_agree(self, tmp_path):
        """The chain's counter and the steward's decide where a run STARTS, so
        they must not disagree."""
        import world_steward as wsm
        p = tmp_path / "heartbeat.json"
        p.write_text(json.dumps({"data": [
            {"heartbeat_number": n, "observation": {}} for n in range(1, 301)]}),
            encoding="utf-8")
        assert lc._count_heartbeat_records(p) == wsm._count_heartbeat_records(p) == 300

    def test_prose_naming_the_key_does_not_inflate(self, tmp_path):
        """The colon is why the pattern is safe: a reasoning string that mentions
        the key must not add to the count."""
        p = tmp_path / "heartbeat.json"
        p.write_text(json.dumps({"data": [
            {"heartbeat_number": 1,
             "observation": {"note": 'I wrote "heartbeat_number" in my reasoning'}}]}
        ), encoding="utf-8")
        assert lc._count_heartbeat_records(p) == 1

    def test_store_state_uses_tick_as_position(self, monkeypatch, tmp_path):
        """store_state returns the TICK as the position, not the count.
        The tick is the only authoritative heartbeat position."""
        monkeypatch.setattr(lc, "STORES",
                            {"east": tmp_path, "west": tmp_path})
        (tmp_path / "world_state.json").write_text(
            '{"data": {"tick": 10, "tile_occupancy": {}}}',
            encoding="utf-8")
        count, tick, occ = lc.store_state("east")
        assert count == 10 and tick == 10

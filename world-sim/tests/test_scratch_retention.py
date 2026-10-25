"""Tests for automatic scratch evidence retention (TDD).

Guarantees:
- Keep the newest 50 completed heartbeat evidence files per civilization.
- Prune only older scratch evidence.
- Never delete an in-flight heartbeat file.
- Never touch canonical ledgers, provenance, memories, fog, or world state.
- Run retention after successful heartbeat persistence, not during execution.
- Log deleted counts and recovered bytes.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.world.scratch_retention import (
    prune_scratch_evidence,
    RetentionStats,
    RetentionSafetyError,
)
from backend.world.canonical_heartbeat_runner import _apply_retention


def _create_fake_hb_files(
    scratch_dir: Path, pair: str, hb_range: range, completed: bool = True
) -> list[Path]:
    created = []
    for hb in hb_range:
        ev_p = scratch_dir / f"lockstep_{pair}_hb{hb}_evidence.json"
        ev_p.write_text(f'{{"pair": "{pair}", "hb": {hb}, "data": "x" * 100}}', encoding="utf-8")
        st_p = scratch_dir / f"lockstep_{pair}_hb{hb}_status.json"
        status = "evidence-exported" if completed else "running"
        st_p.write_text(json.dumps({"status": status, "expected_heartbeat": hb}), encoding="utf-8")
        log_p = scratch_dir / f"lockstep_{pair}_hb{hb}_run.log"
        log_p.write_text(f"log for hb {hb}\n", encoding="utf-8")
        created.append(ev_p)
    return created


def test_prune_keeps_newest_50_evidence_files(tmp_path: Path):
    scratch_dir = tmp_path / ".scratch" / "lockstep"
    scratch_dir.mkdir(parents=True)

    # Create 75 completed heartbeats for East (HB 100 to 174)
    _create_fake_hb_files(scratch_dir, "east", range(100, 175), completed=True)

    stats = prune_scratch_evidence(scratch_dir, pair="east", keep_count=50)

    assert isinstance(stats, RetentionStats)
    assert stats.deleted_count == 25
    assert stats.kept_count == 50
    assert stats.recovered_bytes > 0

    # Oldest 25 evidence files (HB 100 to 124) must be pruned
    for hb in range(100, 125):
        assert not (scratch_dir / f"lockstep_east_hb{hb}_evidence.json").exists()

    # Newest 50 evidence files (HB 125 to 174) must be preserved
    for hb in range(125, 175):
        assert (scratch_dir / f"lockstep_east_hb{hb}_evidence.json").exists()


def test_prune_never_deletes_in_flight_heartbeat(tmp_path: Path):
    scratch_dir = tmp_path / ".scratch" / "lockstep"
    scratch_dir.mkdir(parents=True)

    # 50 completed heartbeats (HB 1 to 50)
    _create_fake_hb_files(scratch_dir, "east", range(1, 51), completed=True)
    # 1 in-flight heartbeat (HB 51, status="running")
    _create_fake_hb_files(scratch_dir, "east", range(51, 52), completed=False)

    # Prune with keep_count=30
    stats = prune_scratch_evidence(scratch_dir, pair="east", keep_count=30)

    # The in-flight heartbeat file (HB 51) must NEVER be touched
    assert (scratch_dir / "lockstep_east_hb51_evidence.json").exists()
    assert (scratch_dir / "lockstep_east_hb51_status.json").exists()

    # The newest 30 completed (HB 21 to 50) must be preserved
    for hb in range(21, 51):
        assert (scratch_dir / f"lockstep_east_hb{hb}_evidence.json").exists()

    # The older 20 completed (HB 1 to 20) are pruned
    assert stats.deleted_count == 20
    for hb in range(1, 21):
        assert not (scratch_dir / f"lockstep_east_hb{hb}_evidence.json").exists()


def test_prune_independent_per_civilization(tmp_path: Path):
    scratch_dir = tmp_path / ".scratch" / "lockstep"
    scratch_dir.mkdir(parents=True)

    _create_fake_hb_files(scratch_dir, "east", range(1, 61), completed=True)  # 60 files
    _create_fake_hb_files(scratch_dir, "west", range(1, 71), completed=True)  # 70 files

    # Prune East only
    east_stats = prune_scratch_evidence(scratch_dir, pair="east", keep_count=50)
    assert east_stats.deleted_count == 10
    assert east_stats.kept_count == 50

    # West must have zero files deleted
    west_evidence_before = list(scratch_dir.glob("lockstep_west_hb*_evidence.json"))
    assert len(west_evidence_before) == 70

    # Now prune West only
    west_stats = prune_scratch_evidence(scratch_dir, pair="west", keep_count=50)
    assert west_stats.deleted_count == 20
    assert west_stats.kept_count == 50

    # East count remains 50
    assert len(list(scratch_dir.glob("lockstep_east_hb*_evidence.json"))) == 50


def test_prune_preserves_non_evidence_and_meta_files(tmp_path: Path):
    scratch_dir = tmp_path / ".scratch" / "lockstep"
    scratch_dir.mkdir(parents=True)

    _create_fake_hb_files(scratch_dir, "east", range(1, 60), completed=True)

    viewer_data = scratch_dir / "viewer_data.js"
    viewer_data.write_text("window.VIEWER_DATA = {};", encoding="utf-8")
    lock_file = scratch_dir / "chain_east.lock"
    lock_file.write_text("1234\n", encoding="utf-8")

    prune_scratch_evidence(scratch_dir, pair="east", keep_count=50)

    assert viewer_data.exists()
    assert lock_file.exists()


def test_prune_safety_boundary_refuses_canonical_dirs(tmp_path: Path):
    canonical_dir = tmp_path / ".runtime" / "first-pair"
    canonical_dir.mkdir(parents=True)

    with pytest.raises(RetentionSafetyError):
        prune_scratch_evidence(canonical_dir, pair="east", keep_count=50)

    data_dir = tmp_path / "world-sim" / "data"
    data_dir.mkdir(parents=True)
    with pytest.raises(RetentionSafetyError):
        prune_scratch_evidence(data_dir, pair="east", keep_count=50)


def test_prune_fewer_than_keep_count(tmp_path: Path):
    scratch_dir = tmp_path / ".scratch" / "lockstep"
    scratch_dir.mkdir(parents=True)

    _create_fake_hb_files(scratch_dir, "east", range(1, 21), completed=True)  # 20 files

    stats = prune_scratch_evidence(scratch_dir, pair="east", keep_count=50)
    assert stats.deleted_count == 0
    assert stats.kept_count == 20
    assert stats.recovered_bytes == 0


def test_apply_retention_integration(tmp_path: Path, capsys):
    scratch_dir = tmp_path / ".scratch" / "lockstep"
    scratch_dir.mkdir(parents=True)

    _create_fake_hb_files(scratch_dir, "east", range(1, 65), completed=True)  # 64 files

    # Call the hook wired into runner_main
    _apply_retention(scratch_dir, "east")

    out = capsys.readouterr().out
    assert "[retention] east: pruned 14 older evidence files" in out
    remaining = list(scratch_dir.glob("lockstep_east_hb*_evidence.json"))
    assert len(remaining) == 50

"""Canonical ABSENT first-pair state commitment - focused tests.

These prove the absent-state ``state_commitment`` is real, deterministic,
hex64 (so it satisfies the existing birth-candidate rollback-anchor contract),
fail-closed when the canonical persistence root contains ANY file (including an
unknown/unrecognized file), never callable against a caller-controlled root,
repeatable, and write-free.

Epoch-independence note: the canonical ``.runtime/first-pair`` root now
legitimately holds authoritative state (``goals.json`` + ``provenance.jsonl``),
so the public ABSENT API must fail closed in the live repo. These tests
therefore drive ABSENT-determinism through the module's pure/injected scan
seam ``_scan_present_files`` (already used by the fail-closed tests below) or
against isolated ``tmp_path`` directories, and keep the public-API assertions
adaptive to whatever the canonical root actually contains. The live canonical
surface is never written, replaced, or deleted.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

import backend.world.local_first_pair_absent_state as absent_state

HEX64 = re.compile(r"^[0-9a-f]{64}$")

# In-workspace isolated scratch dir (writable under this sandbox), mirroring
# the sibling test suites. Never the canonical .runtime/first-pair.
_SCRATCH = Path(__file__).resolve().parent.parent / ".absent-state-scratch"


@pytest.fixture()
def scratch_dir():
    import shutil

    shutil.rmtree(_SCRATCH, ignore_errors=True)
    _SCRATCH.mkdir(parents=True, exist_ok=True)
    yield _SCRATCH
    shutil.rmtree(_SCRATCH, ignore_errors=True)


def _expected_material():
    return {
        "genesis": "first_pair",
        "schema_version": "first_absent_state.1",
        "domain_separator": "GENESIS_FIRST_PAIR_ABSENT_STATE_V1",
        "authoritative_state": "absent",
        "record_file_names": sorted(absent_state._AUTHORITATIVE_RECORD_FILES),
        "record_files_present": [],
    }


def _expected_commitment() -> str:
    mat = json.dumps(_expected_material(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(mat.encode("utf-8")).hexdigest()


def _simulate_absent(monkeypatch):
    """Drive the public API's scan through the injected seam as if ABSENT.

    Matches the injected-scan pattern already used by the fail-closed tests
    below; no reliance on the live canonical root being empty.
    """
    monkeypatch.setattr(absent_state, "_scan_present_files", lambda root: [])


def test_absent_state_commitment_is_deterministic_hex64(monkeypatch):
    _simulate_absent(monkeypatch)
    first = absent_state.first_pair_absent_state_commitment()
    second = absent_state.first_pair_absent_state_commitment()
    assert first == second
    assert HEX64.fullmatch(first) is not None


def test_absent_state_commitment_matches_expected_canonical_material(monkeypatch):
    _simulate_absent(monkeypatch)
    assert absent_state.first_pair_absent_state_commitment() == _expected_commitment()


def test_repeated_absence_yields_identical_commitment(monkeypatch):
    _simulate_absent(monkeypatch)
    seen = {absent_state.first_pair_absent_state_commitment() for _ in range(3)}
    assert len(seen) == 1


def test_fail_closed_when_authoritative_record_present(monkeypatch):
    # An authoritative record (known state) present -> fail closed.
    monkeypatch.setattr(
        absent_state, "_scan_present_files", lambda root: ["world_state.json"]
    )
    with pytest.raises(ValueError) as excinfo:
        absent_state.first_pair_absent_state_commitment()
    assert "world_state.json" in str(excinfo.value)

    verdict = absent_state.assert_first_pair_persistence_empty()
    assert verdict["ok"] is False
    assert verdict["authoritative_empty"] is False
    assert "world_state.json" in verdict["present_files"]


def test_fail_closed_when_unknown_file_present(monkeypatch):
    # An UNKNOWN/unrecognized file present -> still fail closed (fail-open is
    # the defect this test guards against). Not silently ignored.
    monkeypatch.setattr(
        absent_state, "_scan_present_files", lambda root: ["unexpected_state.bin"]
    )
    with pytest.raises(ValueError):
        absent_state.first_pair_absent_state_commitment()

    verdict = absent_state.assert_first_pair_persistence_empty()
    assert verdict["ok"] is False
    assert "unexpected_state.bin" in verdict["present_files"]
    assert "unexpected_state.bin" in verdict["present_filenames_all"]


def test_commitment_function_cannot_be_redirected():
    # Public API accepts no root argument: a caller-controlled root cannot
    # redirect authority.
    with pytest.raises(TypeError):
        absent_state.first_pair_absent_state_commitment(root=Path("."))
    with pytest.raises(TypeError):
        absent_state.assert_first_pair_persistence_empty(root=Path("."))


def test_detection_core_reports_all_present_files(scratch_dir):
    # The detection core scans the ENTIRE directory, not just the known set,
    # so absence is only reported when the root contains no files at all.
    # Exercised against an isolated scratch dir, independent of the live root.
    # A non-existent or empty directory -> absent.
    assert absent_state._scan_present_files(scratch_dir / "missing") == []
    empty_dir = scratch_dir / "empty"
    empty_dir.mkdir()
    assert absent_state._scan_present_files(empty_dir) == []
    # A populated directory reports recognized AND unknown entries.
    populated = scratch_dir / "populated"
    populated.mkdir()
    (populated / "world_state.json").write_text("{}", encoding="utf-8")
    (populated / "goals.json").write_text("{}", encoding="utf-8")
    (populated / "unexpected_state.bin").write_text("x", encoding="utf-8")
    assert absent_state._scan_present_files(populated) == [
        "goals.json",
        "unexpected_state.bin",
        "world_state.json",
    ]


def test_public_commitment_is_write_free():
    # The public canonical API fails closed when the canonical root has
    # entries (post-state epoch), or returns ABSENT when it is empty (pre-state
    # epoch). Either way, calling it must not create a file as a side effect.
    root = absent_state._CANONICAL_PERSISTENCE_ROOT
    present_before = set(absent_state._scan_present_files(root))
    verdict_before = absent_state.assert_first_pair_persistence_empty()
    assert verdict_before["ok"] == (not present_before)

    try:
        absent_state.first_pair_absent_state_commitment()
    except ValueError:
        # Non-empty canonical root -> fail closed, as the contract requires.
        pass

    present_after = set(absent_state._scan_present_files(root))
    verdict_after = absent_state.assert_first_pair_persistence_empty()
    # No file was created or removed by computing the commitment.
    assert present_after == present_before
    assert verdict_after["ok"] == (not present_before)
    assert set(verdict_after["present_files"]) == present_before


def test_commitment_satisfies_birth_candidate_state_commitment_contract(monkeypatch):
    # The existing birth-candidate rollback anchor requires state_commitment
    # to be exactly 64 lowercase hex (`_is_hex64` in 10IC). Prove ours qualifies.
    _simulate_absent(monkeypatch)
    c = absent_state.first_pair_absent_state_commitment()
    assert type(c) is str
    assert len(c) == 64
    assert all(ch in "0123456789abcdef" for ch in c)


def test_hash_material_contains_no_machine_path():
    # The committed material must not contain an absolute/host path (contract
    # Section 3). Drive-prefixed or absolute path must not appear.
    material = absent_state._absent_material()
    text = json.dumps(material, sort_keys=True)
    assert "C:\\" not in text
    assert "S:\\" not in text
    for value in material.values():
        if isinstance(value, str):
            assert not Path(value).is_absolute()
    # record_file_names are bare filenames, not paths.
    for name in material["record_file_names"]:
        assert "/" not in name and "\\" not in name
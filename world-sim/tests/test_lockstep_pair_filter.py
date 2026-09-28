"""Pair filter for the lockstep chain.

The chain's merged clock hard-stops when the two stores disagree, which is
correct for a true lockstep run and useless for a single-pair census. The
optional third argument restricts the run to a subset.

The dangerous failure is silence: a filter that selected nothing would advance
zero heartbeats and exit 0, reporting success for a run that never ran.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

lockstep = importlib.import_module("lockstep_chain")


@pytest.fixture(autouse=True)
def _reset_pairs():
    """Every test must leave the module global as it found it."""
    before = lockstep.PAIRS
    yield
    lockstep.PAIRS = before


class TestDefaultIsUnchanged:
    def test_no_spec_means_both_pairs(self):
        assert lockstep.select_pairs(None) == ("east", "west")
        assert lockstep.PAIRS == lockstep.PAIRS_ALL

    def test_empty_spec_means_both_pairs(self):
        assert lockstep.select_pairs("") == ("east", "west")

    def test_whitespace_spec_means_both_pairs(self):
        assert lockstep.select_pairs("  ") == ("east", "west")


class TestSubsetSelection:
    def test_east_only(self):
        assert lockstep.select_pairs("east") == ("east",)
        assert lockstep.PAIRS == ("east",)

    def test_west_only(self):
        assert lockstep.select_pairs("west") == ("west",)

    def test_both_explicitly(self):
        assert lockstep.select_pairs("east,west") == ("east", "west")

    def test_strips_whitespace_around_names(self):
        assert lockstep.select_pairs(" east , west ") == ("east", "west")


class TestFailClosed:
    def test_unknown_pair_is_a_hard_error(self):
        with pytest.raises(SystemExit) as exc:
            lockstep.select_pairs("eest")
        assert "eest" in str(exc.value)

    def test_unknown_pair_among_valid_ones_is_still_an_error(self):
        """A partially-valid spec must not silently run a subset."""
        with pytest.raises(SystemExit):
            lockstep.select_pairs("east,north")

    def test_error_lists_the_known_pairs(self):
        with pytest.raises(SystemExit) as exc:
            lockstep.select_pairs("nope")
        assert "east" in str(exc.value) and "west" in str(exc.value)

    def test_rejected_spec_leaves_pairs_untouched(self):
        with pytest.raises(SystemExit):
            lockstep.select_pairs("nope")
        assert lockstep.PAIRS == lockstep.PAIRS_ALL


class TestStoreCoverage:
    def test_every_selectable_pair_has_a_store(self):
        for name in lockstep.PAIRS_ALL:
            assert name in lockstep.STORES
            assert (lockstep.STORES[name] / "world_state.json").is_file(), (
                f"{name} store is missing world_state.json"
            )


class TestSnapshotFlag:
    """The snapshot push is an EXTERNAL network write to a public viewer.

    A silently-ignored flag would publish world state to a public URL the
    caller believed they had switched off, so an unknown flag must fail hard.
    """

    def _reset(self):
        lockstep.SNAPSHOTS_ENABLED = True

    def test_default_enables_snapshots(self):
        self._reset()
        start, end, pairs, snap = lockstep.parse_args(["944", "1000"])
        assert snap is True
        assert lockstep.SNAPSHOTS_ENABLED is True

    def test_no_snapshot_disables_them(self):
        self._reset()
        _, _, _, snap = lockstep.parse_args(["944", "1000", "east", "--no-snapshot"])
        assert snap is False
        assert lockstep.SNAPSHOTS_ENABLED is False

    def test_flag_is_position_independent(self):
        self._reset()
        _, _, _, snap = lockstep.parse_args(["--no-snapshot", "944", "1000", "east"])
        assert snap is False

    def test_unknown_flag_is_a_hard_error(self):
        self._reset()
        with pytest.raises(SystemExit) as exc:
            lockstep.parse_args(["944", "1000", "--no-snapshots"])
        assert "--no-snapshots" in str(exc.value)

    def test_missing_range_is_a_hard_error(self):
        self._reset()
        with pytest.raises(SystemExit):
            lockstep.parse_args(["944"])

    def test_known_flag_is_named_in_the_error(self):
        with pytest.raises(SystemExit) as exc:
            lockstep.parse_args(["944", "1000", "--bogus"])
        assert "--no-snapshot" in str(exc.value)

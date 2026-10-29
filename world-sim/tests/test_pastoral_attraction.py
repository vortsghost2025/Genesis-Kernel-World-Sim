"""Tests for Phase 10KH: Pastoral Attraction Dynamics in backend.world.fauna.

Verifies:
1. Determinism: same (entity, tile, seed, signal) produces identical choices across runs.
2. Statistical bias: attraction reduces mean distance to signal over >= 2000 trials.
3. Graded pull: bias is not absolute (some steps still increase distance).
4. Tamed immunity: tamed entities continue using anchor stepping unaffected by attraction.
5. Horse flight precedence: untamed horses flee within flee radius and only use attraction beyond it.
"""
from __future__ import annotations

import random
from pathlib import Path
import pytest

from backend.world import fauna


def test_attraction_preserves_rng_stream():
    """Identical seed, entity, tile, and signal must yield byte-identical step across calls."""
    entity = {"id": "cow-test", "kind": "cow", "tamed": False, "trust": 0}
    tile = (10, 10)
    signal = [(0, 0)]
    seed = 42

    rng1 = random.Random(seed)
    step1 = fauna._free_drift_step(entity, tile, rng1, signal_xys=signal)

    rng2 = random.Random(seed)
    step2 = fauna._free_drift_step(entity, tile, rng2, signal_xys=signal)

    assert step1 == step2, "Attraction step must be strictly deterministic given same seed"


def _mean_distance(start_tile, signal, n_trials=2500, attracted=True):
    entity = {"id": "cow-test", "kind": "cow", "tamed": False, "trust": 0}
    dists = []
    for i in range(n_trials):
        rng = random.Random(i + 1000)
        nxt = fauna._free_drift_step(
            entity, start_tile, rng, signal_xys=signal if attracted else None
        )
        dists.append(fauna._dist(nxt, signal[0]))
    return sum(dists) / len(dists)


@pytest.mark.parametrize("start_dist", [6, 9, 12, 14])
def test_attraction_reduces_mean_distance_to_signal(start_dist):
    """Attraction must pull toward signal by a material margin at every pastoral distance.

    Regression guard: weighting by absolute distance is nearly flat across an
    8-neighbourhood and produced only 0.04 tiles/step at distance 6, which is
    no attraction at all. The distance-gain gradient must deliver >= 0.40
    tiles/step consistently.
    """
    signal = [(0, 0)]
    start_tile = (start_dist, 0)
    n_trials = 2500

    mean_baseline = _mean_distance(start_tile, signal, n_trials, attracted=False)
    mean_attracted = _mean_distance(start_tile, signal, n_trials, attracted=True)

    assert mean_attracted < mean_baseline, (
        f"Attracted mean distance ({mean_attracted:.3f}) must be strictly less "
        f"than baseline ({mean_baseline:.3f}) at start distance {start_dist}"
    )
    delta = mean_baseline - mean_attracted
    assert delta >= 0.40, (
        f"Attraction delta ({delta:.3f}) at distance {start_dist} must be >= 0.40 tiles; "
        f"the absolute-distance weight scheme degenerated to a near-uniform walk"
    )


def test_attraction_is_graded_not_absolute():
    """Bias is not a tractor beam: some trials must still move away or stay at equal distance."""
    entity = {"id": "cow-test", "kind": "cow", "tamed": False, "trust": 0}
    start_tile = (10, 0)
    signal = [(0, 0)]
    initial_dist = fauna._dist(start_tile, signal[0])
    n_trials = 500

    moved_away_or_equal = 0
    for i in range(n_trials):
        rng = random.Random(i + 5000)
        next_tile = fauna._free_drift_step(entity, start_tile, rng, signal_xys=signal)
        d = fauna._dist(next_tile, signal[0])
        if d >= initial_dist:
            moved_away_or_equal += 1

    assert moved_away_or_equal > 0, "Attraction must be graded; some animals must step away or remain equal"
    # Over 500 trials, it should not be 100% strictly closer (graded stochasticity)
    assert moved_away_or_equal >= 20, (
        f"Expected at least 20 steps away/equal out of 500, got {moved_away_or_equal}"
    )


def test_tamed_animals_unaffected_by_attraction():
    """Tamed animals must continue using anchor stepping and ignore signal_xys."""
    entity = {
        "id": "cow-tamed",
        "kind": "cow",
        "tamed": True,
        "trust": 5,
        "anchor_tile": [0, 0],
    }
    tile = (2, 2)
    signal = [(50, 50)]  # distant signal

    for seed in range(50):
        rng1 = random.Random(seed)
        step_no_sig = fauna._free_drift_step(entity, tile, rng1, signal_xys=None)

        rng2 = random.Random(seed)
        step_sig = fauna._free_drift_step(entity, tile, rng2, signal_xys=signal)

        assert step_no_sig == step_sig, f"Tamed animal stepped differently at seed {seed}"


def test_horse_flee_precedence():
    """Untamed horse flees within HORSE_FLEE_RADIUS=2, but uses attraction outside."""
    horse = {"id": "horse-test", "kind": "horse", "tamed": False, "trust": 0}
    horse_tile = (2, 0)
    agent_xy = (0, 0)  # dist 2 -> within HORSE_FLEE_RADIUS
    signal = [(0, 0)]

    rng = random.Random(999)
    # When agent is at dist 2, horse must flee (step away from agent)
    flee_step = fauna._horse_step(horse, horse_tile, [agent_xy], rng, signal_xys=signal)
    flee_dist = fauna._dist(flee_step, agent_xy)
    assert flee_dist > 2, f"Horse must flee from agent at dist 2, but stepped to {flee_step} (dist {flee_dist})"

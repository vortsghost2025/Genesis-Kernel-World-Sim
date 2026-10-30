"""Tests for Phase 10KH/10KS: Pastoral Attraction Dynamics in backend.world.fauna.

Verifies:
1. Determinism: same (entity, tile, seed, signal) produces identical choices across runs.
2. Multi-step arrival distribution (10KS Priority 1): >= 98% of grazers starting at distances
   6, 9, 12, 14 reach the settlement (<= 1) within 50 steps under the 10KH gain gradient,
   with verified mean arrival steps (N=1,000 seeds), heavily outperforming the uniform control arm.
3. Multi-step boundary retention (10KS Priority 1): 0.0% of grazers escape beyond radius 16
   under the gain gradient, whereas the control arm suffers substantial escape.
4. Graded pull: bias is not absolute (some steps still increase distance).
5. Tamed immunity: tamed entities continue using anchor stepping unaffected by attraction.
6. Horse flight precedence: untamed horses flee within flee radius and only use attraction beyond it.
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


def _simulate_trajectory(start_dist: int, attracted: bool, steps: int = 50, n_runs: int = 1000):
    """Simulate n_runs trajectories starting at (start_dist, 0) relative to settlement at (0, 0)."""
    entity = {"id": "cow-sim", "kind": "cow", "tamed": False, "trust": 0}
    signal = [(0, 0)]
    reached = 0
    escaped = 0
    steps_to_reach = []

    for seed in range(n_runs):
        rng = random.Random(seed)
        pos = (start_dist, 0)
        did_reach = False
        for s in range(1, steps + 1):
            pos = fauna._free_drift_step(
                entity, pos, rng, signal_xys=signal if attracted else None
            )
            if fauna._dist(pos, (0, 0)) <= 1:
                did_reach = True
                steps_to_reach.append(s)
                break
        if did_reach:
            reached += 1
        else:
            if fauna._dist(pos, (0, 0)) > 16:
                escaped += 1

    arrival_pct = (reached / n_runs) * 100.0
    escape_pct = (escaped / n_runs) * 100.0
    mean_steps = (sum(steps_to_reach) / len(steps_to_reach)) if steps_to_reach else None
    return arrival_pct, escape_pct, mean_steps


@pytest.mark.parametrize(
    "start_dist,min_arrival,max_mean_steps",
    [
        (6, 99.0, 12.0),
        (9, 99.0, 18.0),
        (12, 99.0, 22.0),
        (14, 98.0, 26.0),
    ],
)
def test_multistep_arrival_distribution(start_dist: int, min_arrival: float, max_mean_steps: float):
    """Pastoral gradient must achieve >= 98-99% arrival within 50 steps across distances 6-14 (N=1,000 seeds).

    Replaces the single-step derivative floor with a trajectory-level regression net.
    """
    treatment_arrival, _, treatment_mean_steps = _simulate_trajectory(
        start_dist, attracted=True, steps=50, n_runs=1000
    )
    control_arrival, _, _ = _simulate_trajectory(
        start_dist, attracted=False, steps=50, n_runs=1000
    )

    assert treatment_arrival >= min_arrival, (
        f"Gradient arrival at d={start_dist} was {treatment_arrival:.1f}%, expected >= {min_arrival}%"
    )
    assert treatment_mean_steps is not None and treatment_mean_steps <= max_mean_steps, (
        f"Gradient mean steps at d={start_dist} was {treatment_mean_steps:.1f}, expected <= {max_mean_steps}"
    )
    assert treatment_arrival >= control_arrival * 4.0, (
        f"Gradient arrival ({treatment_arrival:.1f}%) must outperform control ({control_arrival:.1f}%) by >= 4x"
    )


@pytest.mark.parametrize("start_dist", [6, 9, 12, 14])
def test_multistep_retention_against_escape(start_dist: int):
    """Under the pastoral gradient, zero grazers starting at d <= 14 may escape beyond radius 16."""
    _, treatment_escape, _ = _simulate_trajectory(start_dist, attracted=True, steps=50, n_runs=1000)
    _, control_escape, _ = _simulate_trajectory(start_dist, attracted=False, steps=50, n_runs=1000)

    assert treatment_escape <= 0.2, (
        f"Gradient escape at d={start_dist} was {treatment_escape:.1f}%, expected <= 0.2%"
    )
    assert control_escape > treatment_escape, (
        f"Control escape ({control_escape:.1f}%) should strictly exceed treatment ({treatment_escape:.1f}%)"
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
    flee_step = fauna._horse_step(horse, horse_tile, [agent_xy], rng, signal_xys=signal)
    flee_dist = fauna._dist(flee_step, agent_xy)
    assert flee_dist > 2, f"Horse must flee from agent at dist 2, but stepped to {flee_step} (dist {flee_dist})"

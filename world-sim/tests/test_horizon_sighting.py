"""Tests for Phase 10KH: Distant Horizon Sighting & Prompt Framing.

Verifies:
1. Sighting horizon bounds: dist <= 6 -> nearby only; 7 <= dist <= 15 -> distant only; dist >= 16 -> neither.
2. Snake exclusion: snakes never appear in distant sighting.
3. Prompt line formatting: distant sightings are purely informational with no interaction verbs.
4. Sorting & deduplication: distant animals sorted by distance, deduplicated by id.
5. Operator factual message discipline: operator statement contains no banned directive phrases.
"""
from __future__ import annotations

import types
import pytest
from pathlib import Path

from backend.world import first_pair_runtime
from backend.world import first_pair_cognition_model


def _mock_runtime_with_fauna(agent_ref: str, agent_xy: tuple[int, int], fauna_entities: list[dict]):
    """Create a minimal duck-typed runtime instance to test _fauna_visible."""
    rt = object.__new__(first_pair_runtime.FirstPairRuntime)
    world_state = types.SimpleNamespace()
    world_state.tile_occupancy = {agent_ref: f"cont_a_gen_{agent_xy[0]}_{agent_xy[1]}"}
    world_state.fauna = fauna_entities
    rt._world_state = world_state
    rt._tile_xy = lambda tid: tuple(map(int, tid.replace("cont_a_gen_", "").split("_"))) if tid.startswith("cont_a_gen_") else None
    rt._entity_xy = lambda t: tuple(t) if isinstance(t, (list, tuple)) else None
    return rt


def test_horizon_sighting_bounds():
    """Verify bounds: dist <= 6 in nearby; 7 <= dist <= 15 in distant; dist >= 16 omitted."""
    agent_ref = "east_adam"
    agent_xy = (0, 0)
    entities = [
        {"id": "cow-near", "kind": "cow", "tile": [5, 0], "trust": 0, "tamed": False},    # dist 5 -> nearby
        {"id": "cow-edge", "kind": "cow", "tile": [6, 0], "trust": 0, "tamed": False},    # dist 6 -> nearby
        {"id": "cow-dist-min", "kind": "cow", "tile": [7, 0], "trust": 0, "tamed": False}, # dist 7 -> distant
        {"id": "cow-dist-mid", "kind": "cow", "tile": [12, 0], "trust": 0, "tamed": False},# dist 12 -> distant
        {"id": "cow-dist-max", "kind": "cow", "tile": [15, 0], "trust": 0, "tamed": False},# dist 15 -> distant
        {"id": "cow-far", "kind": "cow", "tile": [16, 0], "trust": 0, "tamed": False},    # dist 16 -> neither
        {"id": "cow-vfar", "kind": "cow", "tile": [30, 0], "trust": 0, "tamed": False},   # dist 30 -> neither
    ]

    rt = _mock_runtime_with_fauna(agent_ref, agent_xy, entities)
    vis = rt._fauna_visible(agent_ref)

    assert "nearby" in vis, "Observation must contain nearby"
    assert "distant" in vis, "Observation must contain distant"

    nearby_ids = {e["id"] for e in vis["nearby"]}
    distant_ids = {e["id"] for e in vis["distant"]}

    assert nearby_ids == {"cow-near", "cow-edge"}, f"Unexpected nearby: {nearby_ids}"
    assert distant_ids == {"cow-dist-min", "cow-dist-mid", "cow-dist-max"}, f"Unexpected distant: {distant_ids}"
    assert "cow-far" not in nearby_ids and "cow-far" not in distant_ids
    assert "cow-vfar" not in nearby_ids and "cow-vfar" not in distant_ids


def test_horizon_excludes_snakes():
    """Snakes at distant horizon (dist 7-15) must NEVER be included in distant list."""
    agent_ref = "east_adam"
    agent_xy = (0, 0)
    entities = [
        {"id": "snake-near", "kind": "snake", "tile": [4, 0]},   # dist 4 -> nearby
        {"id": "snake-dist", "kind": "snake", "tile": [10, 0]},  # dist 10 -> excluded from distant
    ]

    rt = _mock_runtime_with_fauna(agent_ref, agent_xy, entities)
    vis = rt._fauna_visible(agent_ref)

    nearby_ids = {e["id"] for e in vis["nearby"]}
    distant_ids = {e["id"] for e in vis["distant"]}

    assert "snake-near" in nearby_ids, "Nearby snake should remain in nearby"
    assert "snake-dist" not in distant_ids, "Distant snake must NOT be in distant sighting list"
    assert len(distant_ids) == 0, f"Distant list must be empty, got {distant_ids}"


def test_prompt_horizon_line_has_no_interaction_verbs():
    """Distant animal prompt line must be purely observational, omitting offer_food / milk_animal."""
    ctx = types.SimpleNamespace()
    ctx.observation = {
        "fauna": {
            "nearby": [],
            "distant": [
                {"kind": "cow", "id": "cow-123", "distance": 12, "trust": 0, "tamed": False},
                {"kind": "horse", "id": "horse-456", "distance": 9, "trust": 0, "tamed": False},
            ],
        },
        "self_body": {"state": "healthy", "hunger": 10, "warmth": 90, "vitality": 100},
        "environment": {"weather": "clear", "temperature": 18, "season": "spring", "time_of_day": "day"},
    }
    ctx.goals = []
    ctx.inventory = {}
    ctx.carried_weight = 0
    ctx.max_capacity = 20
    ctx.current_tile = "cont_a_gen_0_0"
    ctx.agent_ref = "east_adam"
    ctx.pair_id = "east"

    # Minimal duck-typed model to format prompt lines
    lines = first_pair_cognition_model._format_fauna_lines(ctx.observation)
    full_text = " ".join(lines)

    assert "cow-123" in full_text
    assert "horse-456" in full_text
    # Forbidden interaction verbs on distant lines:
    assert "offer_food" not in full_text, "Distant line must NOT suggest offer_food"
    assert "milk_animal" not in full_text, "Distant line must NOT suggest milk_animal"
    assert "too far to interact" in full_text.lower() or "horizon" in full_text.lower()


def test_operator_message_is_factual_only():
    """Verify that the proposed West unblocking message contains no banned directive phrases."""
    proposed_message = (
        "The world is an active physical environment, not an inert record. "
        "Crafting, tools, shelters, compounds, domestic animals, and cultivation "
        "are functional and respond to action. You are not required to stand by."
    )
    banned_phrases = [
        "build a",
        "go to",
        "you should",
        "move to",
        "try building",
        "head to",
        "i want you to",
        "your task is",
    ]
    lower = proposed_message.lower()
    for phrase in banned_phrases:
        assert phrase not in lower, f"Operator message contains banned directive phrase '{phrase}'"

"""Tests for Phase 10KH/10KS: Distant Horizon Sighting, Directionality & Prompt Framing.

Verifies:
1. Sighting horizon bounds: dist <= 6 -> nearby only; 7 <= dist <= 15 -> distant only; dist >= 16 -> neither.
2. Snake exclusion: snakes never appear in distant sighting.
3. Prompt line formatting (10KS Priority 2): distant sightings include directional bearing and actionable
   navigational affordance ("Moving in that direction can bring it within pastoral range"), while
   explicitly excluding interaction verbs (offer_food, milk_animal) and the demotivating "too far" copy.
4. Sorting & deduplication: distant animals sorted by distance, deduplicated by id.
5. Cardinal bearing (10KS Priority 2): FirstPairRuntime._cardinal_bearing computes 8-way compass direction.
6. Operator factual message discipline: operator statement contains no banned directive phrases.
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


def test_cardinal_bearing_eight_octants():
    """Verify 8-way compass bearing calculation across standard coordinate grid."""
    center = (0, 0)
    octants = [
        ((0, -10), "north"),
        ((10, -10), "northeast"),
        ((10, 0), "east"),
        ((10, 10), "southeast"),
        ((0, 10), "south"),
        ((-10, 10), "southwest"),
        ((-10, 0), "west"),
        ((-10, -10), "northwest"),
        # Near-axis off angles
        ((10, -2), "east"),
        ((10, -8), "northeast"),
        ((2, -10), "north"),
        ((-2, -10), "north"),
    ]
    for target, expected in octants:
        bearing = first_pair_runtime.FirstPairRuntime._cardinal_bearing(center, target)
        assert bearing == expected, f"Bearing from {center} to {target} was '{bearing}', expected '{expected}'"

    assert first_pair_runtime.FirstPairRuntime._cardinal_bearing(center, center) == ""


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


def test_horizon_sighting_includes_directional_bearing():
    """Distant sightings must carry an accurate directional bearing field."""
    agent_ref = "east_adam"
    agent_xy = (10, 10)
    entities = [
        {"id": "cow-ne", "kind": "cow", "tile": [18, 2], "trust": 0, "tamed": False}, # dx=+8, dy=-8 -> dist 8 northeast
        {"id": "horse-w", "kind": "horse", "tile": [0, 10], "trust": 0, "tamed": False}, # dx=-10, dy=0 -> dist 10 west
        {"id": "cow-s", "kind": "cow", "tile": [10, 22], "trust": 0, "tamed": False}, # dx=0, dy=+12 -> dist 12 south
    ]

    rt = _mock_runtime_with_fauna(agent_ref, agent_xy, entities)
    vis = rt._fauna_visible(agent_ref)

    distant_map = {e["id"]: e for e in vis["distant"]}
    assert distant_map["cow-ne"]["bearing"] == "northeast"
    assert distant_map["horse-w"]["bearing"] == "west"
    assert distant_map["cow-s"]["bearing"] == "south"


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


def test_prompt_horizon_line_renders_actionable_navigation_and_no_verbs():
    """Distant animal prompt line must render bearing and directional affordance, omitting interaction verbs."""
    obs = {
        "fauna": {
            "nearby": [],
            "distant": [
                {"kind": "cow", "id": "cow-123", "distance": 12, "bearing": "northeast", "trust": 0, "tamed": False},
                {"kind": "horse", "id": "horse-456", "distance": 9, "bearing": "west", "trust": 0, "tamed": False},
            ],
        }
    }

    lines = first_pair_cognition_model._format_fauna_lines(obs)
    full_text = " ".join(lines)

    assert "cow-123" in full_text
    assert "horse-456" in full_text
    assert "to the northeast" in full_text
    assert "to the west" in full_text
    assert "moving in that direction can bring it within pastoral range" in full_text.lower()
    assert "too far to interact" not in full_text.lower(), "Inhibitory copy must be removed"
    # Forbidden interaction verbs on distant lines:
    assert "offer_food" not in full_text, "Distant line must NOT suggest offer_food"
    assert "milk_animal" not in full_text, "Distant line must NOT suggest milk_animal"


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

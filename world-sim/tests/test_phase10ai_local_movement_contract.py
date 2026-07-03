"""Phase 10AI — Local Movement Contract.

Proves an agent can move locally inside the hidden planet substrate
without exposing hidden map data, and that the movement can be
represented as a world event.

Contract claims:
  1. Valid local move changes tile_id/region_id/coordinates.
  2. Invalid destination is rejected clearly.
  3. Non-local/far move is rejected clearly.
  4. Blocked travel is rejected.
  5. Move result does not include full true_map.
  6. Move result can become a world-event candidate (action_type="move_local").
  7. Candidate has explicit tick and territory_ref.
  8. Verifier accepts a valid move candidate.
  9. Ledger records only the move event, not hidden substrate.
 10. After move, build_local_observation sees the new local slice.
 11. Hidden regions/resources/landmarks outside the new visible slice
     do not leak into export.
 12. Sanitized public output stays safe.
 13. Movement across regions works (cross-region local move).
 14. Same-tick duplicate move is rejected by verifier.
"""

from __future__ import annotations

import json
import sys

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import (
    build_local_observation,
    create_active_position,
    create_empty_known_map,
    validate_true_map,
)
from backend.world.local_movement import (
    DIRECTIONS,
    resolve_local_move,
)
from backend.world.world_event_candidate_mapper import candidate_from_move_result
from backend.world.world_event_ledger import (
    append_event,
    read_events,
    validate_event,
)
from backend.world.world_event_exporter import export_events
from backend.world.world_event_sanitizer import sanitize_public_text
from backend.world.world_event_verifier import verify_candidate_event

# ---------------------------------------------------------------------------
# Shared fixture: a hidden true_map with adjacent tiles
# ---------------------------------------------------------------------------

CONTINENT_ID = "cont_ai"
REGION_NORTH_ID = "reg_north"
REGION_EAST_ID = "reg_east"
REGION_SOUTH_ID = "reg_south"
REGION_HIDDEN_ID = "reg_hidden"


def _make_true_map() -> dict:
    """A hidden true_map with adjacent tiles for local movement testing.

    Layout (coordinates):
        (0,-1) tile_north_1     (reg_north)
        (0,0)  tile_start       (reg_north)
        (0,1)  tile_blocked     (reg_north, blocks_travel=True)
        (1,0)  tile_east_1      (reg_east)
        (5,5)  tile_far         (reg_south, non-local)
        (-5,5) tile_hidden      (reg_hidden, completely hidden region)
    """
    return {
        "schema_version": "7B.1",
        "world_id": "test_world_10ai",
        "seed": "10ai_seed",
        "continents": [
            {"continent_id": CONTINENT_ID, "name": "Test Continent"},
        ],
        "regions": [
            {"region_id": REGION_NORTH_ID, "continent_id": CONTINENT_ID,
             "name": "North Vale"},
            {"region_id": REGION_EAST_ID, "continent_id": CONTINENT_ID,
             "name": "Eastern Ridge"},
            {"region_id": REGION_SOUTH_ID, "continent_id": CONTINENT_ID,
             "name": "Southern Plains"},
            {"region_id": REGION_HIDDEN_ID, "continent_id": CONTINENT_ID,
             "name": "Hidden Hollow"},
        ],
        "tiles": [
            {
                "tile_id": "tile_start", "continent_id": CONTINENT_ID,
                "region_id": REGION_NORTH_ID,
                "coordinates": {"x": 0, "y": 0},
                "terrain": "grassland", "biome": "temperate",
                "elevation": 10, "water": None,
                "resources": ["herbs"], "hazards": [],
                "landmark_ids": ["lm_start_shrine"], "blocks_travel": False,
            },
            {
                "tile_id": "tile_north_1", "continent_id": CONTINENT_ID,
                "region_id": REGION_NORTH_ID,
                "coordinates": {"x": 0, "y": -1},
                "terrain": "forest", "biome": "boreal",
                "elevation": 15, "water": None,
                "resources": ["wood", "berries"], "hazards": [],
                "landmark_ids": [], "blocks_travel": False,
            },
            {
                "tile_id": "tile_blocked", "continent_id": CONTINENT_ID,
                "region_id": REGION_NORTH_ID,
                "coordinates": {"x": 0, "y": 1},
                "terrain": "mountain", "biome": "alpine",
                "elevation": 100, "water": None,
                "resources": ["stone"], "hazards": ["avalanche"],
                "landmark_ids": [], "blocks_travel": True,
            },
            {
                "tile_id": "tile_east_1", "continent_id": CONTINENT_ID,
                "region_id": REGION_EAST_ID,
                "coordinates": {"x": 1, "y": 0},
                "terrain": "desert", "biome": "arid",
                "elevation": 5, "water": None,
                "resources": ["sand"], "hazards": ["heat"],
                "landmark_ids": [], "blocks_travel": False,
            },
            {
                "tile_id": "tile_far", "continent_id": CONTINENT_ID,
                "region_id": REGION_SOUTH_ID,
                "coordinates": {"x": 5, "y": 5},
                "terrain": "plain", "biome": "savanna",
                "elevation": 3, "water": None,
                "resources": ["grain"], "hazards": [],
                "landmark_ids": [], "blocks_travel": False,
            },
            {
                "tile_id": "tile_hidden", "continent_id": CONTINENT_ID,
                "region_id": REGION_HIDDEN_ID,
                "coordinates": {"x": -5, "y": 5},
                "terrain": "cave", "biome": "subterranean",
                "elevation": -10, "water": None,
                "resources": ["crystals", "obsidian"], "hazards": ["darkness"],
                "landmark_ids": ["lm_hidden_cavern"], "blocks_travel": True,
            },
        ],
        "landmarks": [
            {
                "landmark_id": "lm_start_shrine", "continent_id": CONTINENT_ID,
                "tile_id": "tile_start", "kind": "shrine",
                "hidden_name": "Shrine of Beginnings",
                "description": "A simple stone shrine",
            },
            {
                "landmark_id": "lm_hidden_cavern", "continent_id": CONTINENT_ID,
                "tile_id": "tile_hidden", "kind": "cavern",
                "hidden_name": "Hidden Cavern",
                "description": "A deep underground cavern",
            },
        ],
        "resources": [
            {"resource_id": "res_herbs", "tile_id": "tile_start",
             "kind": "herbs", "renewable": True},
            {"resource_id": "res_wood", "tile_id": "tile_north_1",
             "kind": "wood", "renewable": True},
            {"resource_id": "res_berries", "tile_id": "tile_north_1",
             "kind": "berries", "renewable": True},
            {"resource_id": "res_stone", "tile_id": "tile_blocked",
             "kind": "stone", "renewable": False},
            {"resource_id": "res_sand", "tile_id": "tile_east_1",
             "kind": "sand", "renewable": True},
            {"resource_id": "res_grain", "tile_id": "tile_far",
             "kind": "grain", "renewable": True},
            {"resource_id": "res_crystals", "tile_id": "tile_hidden",
             "kind": "crystals", "renewable": False},
            {"resource_id": "res_obsidian", "tile_id": "tile_hidden",
             "kind": "obsidian", "renewable": False},
        ],
        "hazards": [
            {"hazard_id": "haz_avalanche", "tile_id": "tile_blocked",
             "kind": "avalanche", "severity": 3},
            {"hazard_id": "haz_heat", "tile_id": "tile_east_1",
             "kind": "heat", "severity": 2},
            {"hazard_id": "haz_dark", "tile_id": "tile_hidden",
             "kind": "darkness", "severity": 4},
        ],
        "mysteries": [],
        "travel_edges": [],
    }


def _hidden_region_names() -> list[str]:
    return ["Hidden Hollow"]


def _hidden_resource_kinds() -> list[str]:
    return ["crystals", "obsidian"]


def _hidden_landmark_names() -> list[str]:
    return ["Hidden Cavern"]


# ═══════════════════════════════════════════════════════════════════════════
# Movement resolution tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMovementResolution:
    """Claims 1–5: movement resolution is correct and safe."""

    def _start_position(self) -> dict:
        return create_active_position(
            agent_id="explorer_ai",
            continent_id=CONTINENT_ID,
            region_id=REGION_NORTH_ID,
            tile_id="tile_start",
            coordinates={"x": 0, "y": 0},
        )

    def test_valid_north_move_changes_position(self):
        """Claim 1: valid local move changes tile/region/coordinates."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "north", true_map, tick=1)
        assert result["ok"], f"North move failed: {result['error']}"
        assert result["tile_id"] == "tile_north_1"
        assert result["territory_ref"] == REGION_NORTH_ID
        assert result["new_position"]["tile_id"] == "tile_north_1"
        assert result["new_position"]["coordinates"] == {"x": 0, "y": -1}

    def test_valid_east_move_changes_region(self):
        """Moving east crosses into a different region."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "east", true_map, tick=1)
        assert result["ok"], f"East move failed: {result['error']}"
        assert result["tile_id"] == "tile_east_1"
        assert result["territory_ref"] == REGION_EAST_ID

    def test_invalid_destination_rejected(self):
        """Claim 2: direction with no tile at destination is rejected."""
        true_map = _make_true_map()
        pos = self._start_position()
        # Moving west from (0,0) finds no tile at (-1,0)
        result = resolve_local_move(pos, "west", true_map, tick=1)
        assert not result["ok"]
        assert "no tile" in result["error"].lower()

    def test_non_local_move_rejected(self):
        """Claim 3: far destination (beyond 1 step, Manhattan > 1) is rejected."""
        true_map = _make_true_map()
        pos = self._start_position()
        # tile_far is at (5,5) — Manhattan distance 10 from (0,0), not local
        result = resolve_local_move(
            pos, "north", true_map, destination_tile_id="tile_far", tick=1
        )
        assert not result["ok"]
        assert "too far" in result["error"].lower()
        assert "manhattan distance" in result["error"].lower()

    def test_blocked_travel_rejected(self):
        """Claim 4: tile with blocks_travel=True is rejected."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "south", true_map, tick=1)
        assert not result["ok"]
        assert "blocked" in result["error"].lower()

    def test_already_at_destination_rejected(self):
        """Moving to the same tile is rejected via destination_tile_id."""
        true_map = _make_true_map()
        pos = self._start_position()
        # Requesting tile_start while already at tile_start
        result = resolve_local_move(
            pos, "north", true_map, destination_tile_id="tile_start", tick=1
        )
        assert not result["ok"]
        assert "already at destination" in result["error"].lower()

    def test_result_does_not_contain_full_true_map(self):
        """Claim 5: move result dict does not include the true_map."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "north", true_map, tick=1)
        assert result["ok"]
        result_str = json.dumps(result)
        assert "true_map" not in result_str
        # Hidden region/resource names absent
        for name in _hidden_region_names():
            assert name not in result_str
        for kind in _hidden_resource_kinds():
            assert kind not in result_str

    def test_result_includes_before_after_refs(self):
        """Successful move includes tile-based before/after refs."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "north", true_map, tick=1)
        assert result["ok"]
        assert result["before_ref"] == "tile:tile_start"
        assert result["after_ref"] == "tile:tile_north_1"

    def test_result_includes_new_position(self):
        """Successful move provides a complete new position dict."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "north", true_map, tick=1)
        assert result["ok"]
        new_pos = result["new_position"]
        assert new_pos["tile_id"] == "tile_north_1"
        assert new_pos["coordinates"] == {"x": 0, "y": -1}
        assert new_pos["last_moved_tick"] == 1
        # Original position not mutated
        assert pos["tile_id"] == "tile_start"

    def test_invalid_direction_raises_value_error(self):
        """Unrecognised direction raises ValueError."""
        true_map = _make_true_map()
        pos = self._start_position()
        with pytest.raises(ValueError, match="unrecognised direction"):
            resolve_local_move(pos, "sideways", true_map, tick=1)

    def test_missing_position_fields_raises_value_error(self):
        """Position missing required fields raises ValueError."""
        true_map = _make_true_map()
        with pytest.raises(ValueError, match="required fields"):
            resolve_local_move({"tile_id": "tile_start"}, "north", true_map, tick=1)

    # ── destination_tile_id path ──────────────────────────────────────────

    def test_destination_tile_id_valid_local_move(self):
        """destination_tile_id performs a valid local move when adjacent."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(
            pos, "north", true_map, destination_tile_id="tile_north_1", tick=1
        )
        assert result["ok"], f"dest_tile_id move failed: {result['error']}"
        assert result["tile_id"] == "tile_north_1"

    def test_destination_tile_id_nonexistent_rejected(self):
        """destination_tile_id with unknown tile ID is rejected."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(
            pos, "north", true_map, destination_tile_id="tile_gone", tick=1
        )
        assert not result["ok"]
        assert "no tile with id" in result["error"].lower()

    # ── Coordinate validation ─────────────────────────────────────────────

    def test_coordinates_y_must_be_numeric(self):
        """coordinates.y missing or non-numeric raises ValueError."""
        true_map = _make_true_map()
        pos = self._start_position()
        bad_pos = dict(pos)
        bad_pos["coordinates"] = {"x": 0, "y": None}
        with pytest.raises(ValueError, match="coordinates.*y"):
            resolve_local_move(bad_pos, "north", true_map, tick=1)

    def test_coordinates_missing_both_raises(self):
        """coordinates dict missing both x and y raises."""
        true_map = _make_true_map()
        pos = self._start_position()
        bad_pos = dict(pos)
        bad_pos["coordinates"] = {}
        with pytest.raises(ValueError, match="coordinates.*x"):
            resolve_local_move(bad_pos, "north", true_map, tick=1)

    # ── Tick validation ───────────────────────────────────────────────────

    def test_tick_negative_raises_value_error(self):
        """Negative tick raises ValueError."""
        true_map = _make_true_map()
        pos = self._start_position()
        with pytest.raises(ValueError, match="tick must be"):
            resolve_local_move(pos, "north", true_map, tick=-1)

    def test_tick_string_raises_value_error(self):
        """Non-integer tick raises ValueError."""
        true_map = _make_true_map()
        pos = self._start_position()
        with pytest.raises(ValueError, match="tick must be"):
            resolve_local_move(pos, "north", true_map, tick="one")

    def test_tick_zero_accepted(self):
        """tick=0 is a valid non-negative tick."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "north", true_map, tick=0)
        assert result["ok"]
        assert result["new_position"]["last_moved_tick"] == 0


class TestAllDirections:
    """All eight cardinal/intercardinal directions are supported."""

    def _start_position(self) -> dict:
        return create_active_position(
            agent_id="explorer", continent_id=CONTINENT_ID,
            region_id=REGION_NORTH_ID, tile_id="tile_start",
            coordinates={"x": 0, "y": 0},
        )

    def test_all_directions_recognised(self):
        """Every direction in DIRECTIONS is accepted without error."""
        true_map = _make_true_map()
        pos = self._start_position()
        for direction in DIRECTIONS:
            # Most will fail "no tile" but should not raise ValueError
            try:
                resolve_local_move(pos, direction, true_map, tick=1)
            except ValueError:
                pytest.fail(f"Direction {direction!r} raised ValueError")


# ═══════════════════════════════════════════════════════════════════════════
# Candidate event mapping tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMoveCandidateMapping:
    """Claims 6–7: move result maps to a valid world-event candidate."""

    def _start_position(self) -> dict:
        return create_active_position(
            agent_id="explorer_ai", continent_id=CONTINENT_ID,
            region_id=REGION_NORTH_ID, tile_id="tile_start",
            coordinates={"x": 0, "y": 0},
        )

    def test_successful_move_produces_candidate(self):
        """Claim 6: successful move result becomes a candidate event."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "north", true_map, tick=1)
        assert result["ok"]
        candidate = candidate_from_move_result(
            "explorer_ai", "Moved north", result, tick=1
        )
        assert candidate is not None
        assert candidate["action_type"] == "move_local"
        # Validate event schema
        val = validate_event(candidate)
        assert val["ok"], f"Move candidate failed validation: {val['errors']}"

    def test_failed_move_returns_none(self):
        """Failed move result produces None candidate."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "west", true_map, tick=1)
        assert not result["ok"]
        candidate = candidate_from_move_result(
            "explorer_ai", "Moved west", result, tick=1
        )
        assert candidate is None

    def test_candidate_has_tick_and_territory_ref(self):
        """Claim 7: candidate has explicit tick and territory_ref."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "north", true_map, tick=5)
        candidate = candidate_from_move_result(
            "explorer_ai", "Moved north", result, tick=5
        )
        assert candidate["tick"] == 5
        assert candidate["territory_ref"] == REGION_NORTH_ID

    def test_candidate_claim_scope_is_observed(self):
        """Move candidate has explicit observed scope."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "north", true_map, tick=1)
        candidate = candidate_from_move_result(
            "explorer_ai", "Moved north", result, tick=1
        )
        assert candidate["claim_scope"] == "observed"

    def test_candidate_has_before_after_refs(self):
        """Move candidate has tile-based before/after refs (for mutation validation)."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "north", true_map, tick=1)
        candidate = candidate_from_move_result(
            "explorer_ai", "Moved north", result, tick=1
        )
        assert candidate["before_ref"] == "tile:tile_start"
        assert candidate["after_ref"] == "tile:tile_north_1"

    def test_candidate_evidence_is_agent_action(self):
        """Move candidate evidence uses agent_action category."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "north", true_map, tick=1)
        candidate = candidate_from_move_result(
            "explorer_ai", "Moved north", result, tick=1
        )
        categories = {
            ev["category"] for ev in candidate.get("evidence_refs", [])
            if isinstance(ev, dict)
        }
        assert "agent_action" in categories

    def test_candidate_does_not_leak_true_map(self):
        """Candidate event dict does not contain true_map or hidden names."""
        true_map = _make_true_map()
        pos = self._start_position()
        result = resolve_local_move(pos, "north", true_map, tick=1)
        candidate = candidate_from_move_result(
            "explorer_ai", "Moved north", result, tick=1
        )
        candidate_json = json.dumps(candidate)
        assert "true_map" not in candidate_json
        assert "tile_hidden" not in candidate_json
        for name in _hidden_region_names():
            assert name not in candidate_json
        for kind in _hidden_resource_kinds():
            assert kind not in candidate_json


# ═══════════════════════════════════════════════════════════════════════════
# Verifier and ledger integration tests
# ═══════════════════════════════════════════════════════════════════════════


class TestVerifierIntegration:
    """Claim 8: verifier accepts a valid move candidate."""

    def _start_position(self) -> dict:
        return create_active_position(
            agent_id="explorer_ai", continent_id=CONTINENT_ID,
            region_id=REGION_NORTH_ID, tile_id="tile_start",
            coordinates={"x": 0, "y": 0},
        )

    def _move_result(self, direction: str = "north", tick: int = 1) -> dict:
        true_map = _make_true_map()
        pos = self._start_position()
        return resolve_local_move(pos, direction, true_map, tick=tick)

    def _move_candidate(self, direction: str = "north", tick: int = 1) -> dict:
        result = self._move_result(direction, tick=tick)
        return candidate_from_move_result(
            "explorer_ai", f"Moved {direction}", result, tick=tick
        )

    def test_verifier_accepts_valid_move(self):
        """Claim 8: verifier accepts a valid move candidate."""
        candidate = self._move_candidate("north", tick=1)
        result = verify_candidate_event(candidate, [])
        assert result["accepted"], (
            f"Verifier rejected move: {result['errors']}"
        )

    def test_verifier_accepts_cross_region_move(self):
        """Moving to a different region also passes verifier."""
        candidate = self._move_candidate("east", tick=1)
        result = verify_candidate_event(candidate, [])
        assert result["accepted"], (
            f"Verifier rejected cross-region move: {result['errors']}"
        )

    def test_duplicate_move_rejected(self):
        """Claim 14: same tick+actor+territory duplicate move rejected."""
        cand1 = self._move_candidate("north", tick=1)
        cand2 = self._move_candidate("north", tick=1)
        result1 = verify_candidate_event(cand1, [])
        assert result1["accepted"]
        result2 = verify_candidate_event(cand2, [cand1])
        assert not result2["accepted"], (
            "Duplicate move should be rejected"
        )
        assert any("duplicate" in e.lower() for e in result2["errors"])

    def test_different_tick_moves_allowed(self):
        """Same actor moving in different ticks are distinct."""
        cand1 = self._move_candidate("north", tick=1)
        # After moving north, the agent is at tile_north_1 at tick 1
        # For cand2 at tick 2, we need a new position.
        # But resolve_local_move with pos at tile_start can't move
        # south from tile_north_1. Let's just test the duplicate
        # detection: same actor, action_type, and territory at different ticks.
        # Actually, cand1 already moved to tile_north_1 (reg_north).
        # Cand2 at tick=2 from tile_start north would be same territory.
        result2 = self._move_result("north", tick=2)
        cand2 = candidate_from_move_result(
            "explorer_ai", "Moved north", result2, tick=2
        )
        result2v = verify_candidate_event(cand2, [cand1])
        assert result2v["accepted"], (
            f"Different-tick move rejected: {result2v['errors']}"
        )


class TestLedgerIntegration:
    """Claim 9: ledger records only the move event, not hidden substrate."""

    def test_move_appends_to_ledger(self, tmp_path):
        """Valid move event appends to the ledger."""
        true_map = _make_true_map()
        pos = create_active_position(
            "explorer_ai", CONTINENT_ID, REGION_NORTH_ID,
            "tile_start", {"x": 0, "y": 0},
        )
        result = resolve_local_move(pos, "north", true_map, tick=1)
        candidate = candidate_from_move_result(
            "explorer_ai", "Moved north", result, tick=1
        )
        ledger = tmp_path / "ledger.jsonl"
        ap_result = append_event(ledger, candidate)
        assert ap_result["ok"], f"Append failed: {ap_result['errors']}"

        events = read_events(ledger)
        assert len(events) == 1
        assert events[0]["action_type"] == "move_local"

    def test_ledger_does_not_contain_hidden_substrate(self, tmp_path):
        """Claim 9: ledger has no hidden data."""
        true_map = _make_true_map()
        pos = create_active_position(
            "explorer_ai", CONTINENT_ID, REGION_NORTH_ID,
            "tile_start", {"x": 0, "y": 0},
        )
        result = resolve_local_move(pos, "north", true_map, tick=1)
        candidate = candidate_from_move_result(
            "explorer_ai", "Moved north", result, tick=1
        )
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, candidate)

        ledger_text = ledger.read_text(encoding="utf-8")
        assert "true_map" not in ledger_text
        assert "tile_hidden" not in ledger_text
        for name in _hidden_region_names():
            assert name not in ledger_text
        for kind in _hidden_resource_kinds():
            assert kind not in ledger_text

    def test_ledger_holds_move_and_observation(self, tmp_path):
        """Move event + observation event can coexist in ledger."""
        true_map = _make_true_map()

        # Move north
        pos = create_active_position(
            "explorer_ai", CONTINENT_ID, REGION_NORTH_ID,
            "tile_start", {"x": 0, "y": 0},
        )
        move_result = resolve_local_move(pos, "north", true_map, tick=1)
        move_candidate = candidate_from_move_result(
            "explorer_ai", "Moved north", move_result, tick=1
        )

        # Observe from new position
        new_pos = move_result["new_position"]
        known_map = create_empty_known_map("explorer_ai")
        observation = build_local_observation(true_map, new_pos, known_map, {"radius": 0})
        from backend.world.slice_to_event_bridge import observation_slice_to_candidate
        observe_candidate = observation_slice_to_candidate(
            observation, tick=2
        )

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, move_candidate)
        append_event(ledger, observe_candidate)

        events = read_events(ledger)
        assert len(events) == 2
        action_types = [e["action_type"] for e in events]
        assert action_types == ["move_local", "observe"]


# ═══════════════════════════════════════════════════════════════════════════
# Post-move observation tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPostMoveObservation:
    """Claim 10: after move, observation sees the new local slice."""

    def test_observation_after_move_shows_new_tile(self):
        """Claim 10: building observation from new position sees new tile."""
        true_map = _make_true_map()
        pos = create_active_position(
            "explorer_ai", CONTINENT_ID, REGION_NORTH_ID,
            "tile_start", {"x": 0, "y": 0},
        )
        result = resolve_local_move(pos, "north", true_map, tick=1)
        new_pos = result["new_position"]

        known_map = create_empty_known_map("explorer_ai")
        observation = build_local_observation(true_map, new_pos, known_map, {"radius": 0})
        visible_ids = observation.get("visible_tile_ids", [])
        assert "tile_north_1" in visible_ids
        assert "tile_start" not in visible_ids  # radius=0 at new pos

    def test_post_move_observation_does_not_leak_hidden(self):
        """Observation from new position still excludes hidden data."""
        true_map = _make_true_map()
        pos = create_active_position(
            "explorer_ai", CONTINENT_ID, REGION_NORTH_ID,
            "tile_start", {"x": 0, "y": 0},
        )
        result = resolve_local_move(pos, "north", true_map, tick=1)
        new_pos = result["new_position"]

        known_map = create_empty_known_map("explorer_ai")
        observation = build_local_observation(true_map, new_pos, known_map, {"radius": 0})
        obs_json = json.dumps(observation)
        for name in _hidden_region_names():
            assert name not in obs_json
        for kind in _hidden_resource_kinds():
            assert kind not in obs_json

    def test_move_then_observe_full_pipeline(self, tmp_path):
        """Move → observe → verify → ledger → export → sanitize is safe."""
        true_map = _make_true_map()
        pos = create_active_position(
            "explorer_ai", CONTINENT_ID, REGION_NORTH_ID,
            "tile_start", {"x": 0, "y": 0},
        )

        # Move
        move_result = resolve_local_move(pos, "north", true_map, tick=1)
        move_candidate = candidate_from_move_result(
            "explorer_ai", "Moved north", move_result, tick=1
        )

        # Observe from new position
        new_pos = move_result["new_position"]
        known_map = create_empty_known_map("explorer_ai")
        observation = build_local_observation(true_map, new_pos, known_map, {"radius": 0})
        from backend.world.slice_to_event_bridge import observation_slice_to_candidate
        observe_candidate = observation_slice_to_candidate(
            observation, actor_id="explorer_ai", tick=2
        )

        # Verify both
        v1 = verify_candidate_event(move_candidate, [])
        assert v1["accepted"]
        v2 = verify_candidate_event(observe_candidate, [move_candidate])
        assert v2["accepted"]

        # Append both
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, move_candidate)
        append_event(ledger, observe_candidate)

        # Export and sanitize
        events = read_events(ledger)
        for fmt in ("json", "jsonl", "csv"):
            export_str = export_events(events, fmt=fmt)
            sanitized = sanitize_public_text(export_str)
            # Hidden data absent
            for name in _hidden_region_names():
                assert name not in sanitized, f"{name} leaked in {fmt}"
            for kind in _hidden_resource_kinds():
                assert kind not in sanitized, f"{kind} leaked in {fmt}"
            for lm in _hidden_landmark_names():
                assert lm not in sanitized, f"{lm} leaked in {fmt}"
            # World data survives
            assert "tile_north_1" in sanitized, f"tile_north_1 missing from {fmt}"
            assert "move_local" in sanitized, f"move_local missing from {fmt}"
            assert "observe" in sanitized, f"observe missing from {fmt}"


# ═══════════════════════════════════════════════════════════════════════════
# Full pipeline — move → observe → export → sanitize
# ═══════════════════════════════════════════════════════════════════════════


class TestFullPipeline:
    """Claims 11–12: hidden data does not leak through full pipeline."""

    def test_full_pipeline_move_and_observe_no_leak(self, tmp_path):
        """Move + observe + export + sanitize keeps hidden data hidden."""
        true_map = _make_true_map()

        # Start at tile_start, move east to cross into reg_east
        pos = create_active_position(
            "explorer_ai", CONTINENT_ID, REGION_NORTH_ID,
            "tile_start", {"x": 0, "y": 0},
        )
        move_result = resolve_local_move(pos, "east", true_map, tick=1)
        move_candidate = candidate_from_move_result(
            "explorer_ai", "Moved east", move_result, tick=1
        )

        # Observe from new position
        new_pos = move_result["new_position"]
        known_map = create_empty_known_map("explorer_ai")
        observation = build_local_observation(true_map, new_pos, known_map, {"radius": 0})
        from backend.world.slice_to_event_bridge import observation_slice_to_candidate
        observe_candidate = observation_slice_to_candidate(
            observation, actor_id="explorer_ai", tick=2
        )

        # Pipeline
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, move_candidate)
        append_event(ledger, observe_candidate)
        events = read_events(ledger)

        for fmt in ("json", "jsonl", "csv"):
            export_str = export_events(events, fmt=fmt)
            sanitized = sanitize_public_text(export_str)

            # Hidden region never leaks
            assert "Hidden Hollow" not in sanitized
            # Hidden tiles/landmarks never leak
            assert "tile_hidden" not in sanitized
            assert "Hidden Cavern" not in sanitized
            # Hidden resources never leak
            assert "crystals" not in sanitized
            assert "obsidian" not in sanitized

            # Observed data survives
            assert "tile_east_1" in sanitized
            assert "move_local" in sanitized
            assert "observe" in sanitized

    def test_move_to_new_region_preserves_old_observation(self, tmp_path):
        """Observation from previous region is still accessible after move."""
        true_map = _make_true_map()
        pos = create_active_position(
            "explorer_ai", CONTINENT_ID, REGION_NORTH_ID,
            "tile_start", {"x": 0, "y": 0},
        )

        # Observe at start
        known_map = create_empty_known_map("explorer_ai")
        obs1 = build_local_observation(true_map, pos, known_map, {"radius": 0})
        from backend.world.slice_to_event_bridge import observation_slice_to_candidate
        cand1 = observation_slice_to_candidate(obs1, actor_id="explorer_ai", tick=1)

        # Move east
        move_result = resolve_local_move(pos, "east", true_map, tick=2)
        move_cand = candidate_from_move_result(
            "explorer_ai", "Moved east", move_result, tick=2
        )

        # Observe at new position
        new_pos = move_result["new_position"]
        obs2 = build_local_observation(true_map, new_pos, known_map, {"radius": 0})
        cand2 = observation_slice_to_candidate(obs2, actor_id="explorer_ai", tick=3)

        # Pipeline
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, cand1)
        append_event(ledger, move_cand)
        append_event(ledger, cand2)

        events = read_events(ledger)
        assert len(events) == 3

        # Territory refs span both regions
        refs = {e["territory_ref"] for e in events}
        assert REGION_NORTH_ID in refs
        assert REGION_EAST_ID in refs
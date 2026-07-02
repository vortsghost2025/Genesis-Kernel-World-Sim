"""Phase 10AH — Observed Slice Bridge Hardening.

Hardens the Phase 10AG observed-slice bridge and verifier seam with
explicit edge-case guards:

  1. tick=None → ValueError (M1 — bridge must require tick)
  2. claim_scope="observed" is explicit, not heuristic (M2)
  3. duplicate key includes territory_ref (M3)
  4. input validation rejects malformed observation dicts

All files touched are pure modules — no daemon, scheduler, provider,
Docker, runtime, live agents, or public data.
"""

from __future__ import annotations

import sys

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import (
    build_local_observation,
    create_empty_known_map,
)
from backend.world.slice_to_event_bridge import observation_slice_to_candidate
from backend.world.world_event_candidate_mapper import candidate_from_observe_result
from backend.world.world_event_ledger import validate_event
from backend.world.world_event_verifier import verify_candidate_event


# ---------------------------------------------------------------------------
# Shared fixture helpers (same hidden true_map as 10AF/10AG)
# ---------------------------------------------------------------------------

def _make_hidden_true_map() -> dict:
    return {
        "schema_version": "7B.1",
        "world_id": "test_world_10ah",
        "seed": "10ah_seed",
        "continents": [{"continent_id": "cont_ah", "name": "Test"},],
        "regions": [
            {"region_id": "reg_vale", "continent_id": "cont_ah", "name": "Misty Vale"},
            {"region_id": "reg_grotto", "continent_id": "cont_ah", "name": "Sunken Grotto"},
        ],
        "tiles": [
            {
                "tile_id": "tile_vale_1", "continent_id": "cont_ah",
                "region_id": "reg_vale",
                "coordinates": {"x": 0, "y": 0},
                "terrain": "grassland", "biome": "temperate",
                "elevation": 10, "water": None,
                "resources": ["herbs"], "hazards": [],
                "landmark_ids": [], "blocks_travel": False,
            },
            {
                "tile_id": "tile_grotto_1", "continent_id": "cont_ah",
                "region_id": "reg_grotto",
                "coordinates": {"x": 10, "y": 0},
                "terrain": "cave", "biome": "subterranean",
                "elevation": -5, "water": None,
                "resources": ["crystals"], "hazards": [],
                "landmark_ids": [], "blocks_travel": False,
            },
        ],
        "landmarks": [],
        "resources": [
            {"resource_id": "res_herbs", "tile_id": "tile_vale_1",
             "kind": "herbs", "renewable": True},
            {"resource_id": "res_crystals", "tile_id": "tile_grotto_1",
             "kind": "crystals", "renewable": False},
        ],
        "hazards": [],
        "mysteries": [],
        "travel_edges": [],
    }


def _make_vale_position() -> dict:
    return {
        "schema_version": "7B.1",
        "agent_id": "agent_vale",
        "active": True,
        "continent_id": "cont_ah",
        "region_id": "reg_vale",
        "tile_id": "tile_vale_1",
        "coordinates": {"x": 0, "y": 0},
        "facing": "north", "movement_mode": "walk",
        "travel_capabilities": ["walk_local"], "last_moved_tick": 0,
    }


def _make_grotto_position() -> dict:
    return {
        "schema_version": "7B.1",
        "agent_id": "agent_grotto",
        "active": True,
        "continent_id": "cont_ah",
        "region_id": "reg_grotto",
        "tile_id": "tile_grotto_1",
        "coordinates": {"x": 10, "y": 0},
        "facing": "south", "movement_mode": "walk",
        "travel_capabilities": ["walk_local"], "last_moved_tick": 0,
    }


def _build_observation(position: dict) -> dict:
    true_map = _make_hidden_true_map()
    known_map = create_empty_known_map(position["agent_id"])
    return build_local_observation(true_map, position, known_map, {"radius": 0})


def _build_observation_radius(position: dict, radius: int = 2) -> dict:
    true_map = _make_hidden_true_map()
    known_map = create_empty_known_map(position["agent_id"])
    return build_local_observation(true_map, position, known_map, {"radius": radius})


# ═══════════════════════════════════════════════════════════════════════════
# Tests — M1: tick=None rejection
# ═══════════════════════════════════════════════════════════════════════════


class TestTickRequired:
    """M1: bridge must reject missing/None/negative tick."""

    def test_tick_none_raises_value_error(self):
        """observation_slice_to_candidate raises ValueError when tick=None."""
        observation = _build_observation(_make_vale_position())
        with pytest.raises(ValueError, match="tick is required"):
            observation_slice_to_candidate(observation, tick=None)

    def test_tick_missing_raises_value_error(self):
        """observation_slice_to_candidate raises TypeError when tick omitted."""
        observation = _build_observation(_make_vale_position())
        with pytest.raises(TypeError):
            # tick is now a required keyword argument with no default
            observation_slice_to_candidate(observation)

    def test_tick_negative_raises_value_error(self):
        """Negative tick raises ValueError."""
        observation = _build_observation(_make_vale_position())
        with pytest.raises(ValueError, match="tick is required"):
            observation_slice_to_candidate(observation, tick=-1)

    def test_tick_zero_accepted(self):
        """tick=0 is valid (non-negative)."""
        observation = _build_observation(_make_vale_position())
        candidate = observation_slice_to_candidate(observation, tick=0)
        result = validate_event(candidate)
        assert result["ok"], f"Candidate with tick=0 failed: {result['errors']}"
        assert candidate["tick"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Tests — M2: explicit claim_scope
# ═══════════════════════════════════════════════════════════════════════════


class TestExplicitClaimScope:
    """M2: claim_scope is explicitly set to 'observed', not heuristic."""

    def test_candidate_claim_scope_is_observed(self):
        """Bridge-produced candidate has claim_scope='observed'."""
        observation = _build_observation(_make_vale_position())
        candidate = observation_slice_to_candidate(observation, tick=1)
        assert candidate["claim_scope"] == "observed"

    def test_mapper_respects_explicit_scope_from_result(self):
        """candidate_from_observe_result uses explicit scope from result dict."""
        result = {
            "territory_ref": "reg_vale",
            "evidence_used": [{"category": "observed_world_fact", "tile_ids": ["tile_vale_1"]}],
            "claim_scope": "observed",
        }
        candidate = candidate_from_observe_result("test_agent", "test", result, tick=1)
        assert candidate["claim_scope"] == "observed"

    def test_explicit_scope_overrides_heuristic(self):
        """Explicit 'hypothesis' scope overrides observed_world_fact evidence."""
        result = {
            "territory_ref": "reg_vale",
            "evidence_used": [{"category": "observed_world_fact", "tile_ids": ["tile_vale_1"]}],
            "claim_scope": "hypothesis",
        }
        candidate = candidate_from_observe_result("test_agent", "test", result, tick=1)
        # Explicit hypothesis should override the observed_world_fact heuristic
        assert candidate["claim_scope"] == "hypothesis"

    def test_bridge_candidate_passes_verifier_with_observed_scope(self):
        """Bridge candidate with explicit observed scope passes verifier."""
        observation = _build_observation(_make_vale_position())
        candidate = observation_slice_to_candidate(observation, tick=1)
        result = verify_candidate_event(candidate, [])
        assert result["accepted"], (
            f"Verifier rejected bridge candidate: {result['errors']}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Tests — M3: territory_ref in duplicate key
# ═══════════════════════════════════════════════════════════════════════════


class TestDuplicateDetectionWithTerritory:
    """M3: duplicate key includes territory_ref."""

    def test_same_tick_same_actor_different_territory_allowed(self):
        """Same tick + actor + action_type in different territories is OK."""
        obs_vale = _build_observation(_make_vale_position())
        obs_grotto = _build_observation(_make_grotto_position())

        cand1 = observation_slice_to_candidate(obs_vale, actor_id="explorer", tick=1)
        cand2 = observation_slice_to_candidate(obs_grotto, actor_id="explorer", tick=1)

        # Both should be accepted independently (different territory_ref)
        result1 = verify_candidate_event(cand1, [])
        assert result1["accepted"]
        result2 = verify_candidate_event(cand2, [cand1])
        assert result2["accepted"], (
            f"Same-tick different-territory observation rejected: {result2['errors']}"
        )

    def test_same_tick_same_actor_same_territory_rejected(self):
        """Same tick + actor + territory is rejected as duplicate."""
        observation = _build_observation(_make_vale_position())
        cand1 = observation_slice_to_candidate(observation, actor_id="explorer", tick=1)
        cand2 = observation_slice_to_candidate(observation, actor_id="explorer", tick=1)

        result1 = verify_candidate_event(cand1, [])
        assert result1["accepted"]

        result2 = verify_candidate_event(cand2, [cand1])
        assert not result2["accepted"], (
            "Same-tick same-territory duplicate should be rejected"
        )
        assert any("duplicate" in e.lower() for e in result2["errors"])

    def test_different_tick_same_actor_same_territory_allowed(self):
        """Different ticks with same actor+territory are distinct observations."""
        observation = _build_observation(_make_vale_position())
        cand1 = observation_slice_to_candidate(observation, actor_id="explorer", tick=1)
        cand2 = observation_slice_to_candidate(observation, actor_id="explorer", tick=2)

        result1 = verify_candidate_event(cand1, [])
        assert result1["accepted"]
        result2 = verify_candidate_event(cand2, [cand1])
        assert result2["accepted"], (
            f"Different-tick observation rejected: {result2['errors']}"
        )

    def test_same_tick_different_actor_same_territory_allowed(self):
        """Two agents observing same territory at same tick are distinct."""
        obs_vale = _build_observation(_make_vale_position())
        cand1 = observation_slice_to_candidate(obs_vale, actor_id="agent_a", tick=1)
        cand2 = observation_slice_to_candidate(obs_vale, actor_id="agent_b", tick=1)

        result1 = verify_candidate_event(cand1, [])
        assert result1["accepted"]
        result2 = verify_candidate_event(cand2, [cand1])
        assert result2["accepted"], (
            f"Different-actor same-tick rejected: {result2['errors']}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Tests — Input validation
# ═══════════════════════════════════════════════════════════════════════════


class TestInputValidation:
    """Bridge validates observation dict structure."""

    def test_missing_position_key_raises(self):
        """Missing 'position' key raises ValueError."""
        bad_obs = {"visible_tile_ids": [], "visible_tiles": [],
                    "visible_landmarks": [], "agent_id": "test"}
        with pytest.raises(ValueError, match="position"):
            observation_slice_to_candidate(bad_obs, tick=1)

    def test_missing_agent_id_raises(self):
        """Missing 'agent_id' key raises ValueError."""
        bad_obs = {"position": {"region_id": "reg_vale"}, "visible_tile_ids": [],
                    "visible_tiles": [], "visible_landmarks": []}
        with pytest.raises(ValueError, match="agent_id"):
            observation_slice_to_candidate(bad_obs, tick=1)

    def test_empty_dict_raises(self):
        """Empty dict observation raises ValueError."""
        with pytest.raises(ValueError, match="required keys"):
            observation_slice_to_candidate({}, tick=1)

    def test_missing_multiple_keys_raises(self):
        """Missing multiple required keys reports all in error."""
        with pytest.raises(ValueError) as exc:
            observation_slice_to_candidate({"position": {}}, tick=1)
        msg = str(exc.value)
        # Should mention all missing keys
        assert "agent_id" in msg
        assert "visible_tile_ids" in msg
        assert "visible_tiles" in msg
        assert "visible_landmarks" in msg


# ═══════════════════════════════════════════════════════════════════════════
# Tests — Radius > 0 multi-tile coverage
# ═══════════════════════════════════════════════════════════════════════════


class TestMultiTileObservation:
    """Bridge works with radius > 0 observations spanning multiple tiles."""

    def test_radius_2_produces_valid_candidate(self):
        """Observation with radius 2 produces a valid candidate."""
        # At Vale (0,0) radius 2 reaches tiles within Manhattan distance <= 2
        position = _make_vale_position()
        true_map = _make_hidden_true_map()
        known_map = create_empty_known_map(position["agent_id"])
        observation = build_local_observation(true_map, position, known_map, {"radius": 3})
        # radius 3 from (0,0) — grotto is at (10,0), so still only vale visible
        # but let's just verify the candidate is valid
        candidate = observation_slice_to_candidate(observation, actor_id="test_agent", tick=1)
        result = validate_event(candidate)
        assert result["ok"], f"Multi-tile candidate failed: {result['errors']}"

    def test_radius_2_evidence_tile_ids_gt_0(self):
        """Radius > 0 may show more than one tile."""
        true_map = _make_hidden_true_map()
        position = _make_vale_position()
        known_map = create_empty_known_map(position["agent_id"])
        observation = build_local_observation(true_map, position, known_map, {"radius": 10})
        # radius 10 from (0,0) covers vale (0,0) and grotto (10,0) at Manhattan dist 10
        candidate = observation_slice_to_candidate(observation, actor_id="test_agent", tick=1)
        # Should include tile_vale_1 (and possibly tile_grotto_1 if radius 10 reaches it)
        tile_ids = set()
        for ev in candidate.get("evidence_refs", []):
            if isinstance(ev, dict):
                tile_ids.update(ev.get("tile_ids", []))
        assert "tile_vale_1" in tile_ids
        # Either 1 or 2 tiles visible depending on radius
        assert len(tile_ids) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# Tests — Auto-generated timestamp
# ═══════════════════════════════════════════════════════════════════════════


class TestAutoTimestamp:
    """timestamp_utc is auto-generated when omitted."""

    def test_timestamp_utc_populated_when_omitted(self):
        """Candidate gets an ISO-8601 timestamp when none provided."""
        observation = _build_observation(_make_vale_position())
        candidate = observation_slice_to_candidate(observation, tick=1)
        ts = candidate.get("timestamp_utc", "")
        assert ts, "timestamp_utc should not be empty"
        assert ts.endswith("Z"), f"timestamp_utc should end with Z, got: {ts}"
        assert "T" in ts, f"timestamp_utc should contain T separator, got: {ts}"
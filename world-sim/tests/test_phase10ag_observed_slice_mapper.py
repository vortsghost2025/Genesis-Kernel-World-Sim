"""Phase 10AG — Observed Slice → World Event Mapper.

Proves that a fog-of-war local observation (from the hidden planet substrate
in 10AF) can be converted into a valid world event candidate via the
slice_to_event_bridge, and that the resulting candidate flows correctly through
the full event pipeline (verifier → ledger → export → sanitizer) without
leaking hidden substrate.

Contract claims:
  1. Bridge converts observation to valid candidate — the output of
     ``observation_slice_to_candidate`` satisfies ``validate_event``.
  2. Bridge preserves territory — the candidate's ``territory_ref`` matches
     the observed position's region.
  3. Bridge builds correct evidence — the candidate carries
     ``observed_world_fact`` evidence with only the visible tile IDs.
  4. Hidden data does not leak into bridge output — tile IDs, landmark IDs,
     region names, and resource kinds from hidden areas are absent.
  5. Candidate passes the verifier — ``verify_candidate_event`` accepts the
     bridged candidate.
  6. Candidate flows into the ledger — ``append_event`` succeeds and the
     event is readable.
  7. Full pipeline produces safe public output — export + sanitizer preserves
     observed data while keeping hidden substrate hidden.
  8. Bridge works from multiple positions — agents at different locations
     on the hidden planet get correct, non-leaking candidates.
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
    create_empty_known_map,
    get_visible_tile_ids,
    validate_true_map,
)
from backend.world.slice_to_event_bridge import observation_slice_to_candidate
from backend.world.world_event_ledger import (
    append_event,
    read_events,
    validate_event,
)
from backend.world.world_event_exporter import export_events
from backend.world.world_event_sanitizer import sanitize_public_text
from backend.world.world_event_verifier import verify_candidate_event

# ---------------------------------------------------------------------------
# Shared fixture: the hidden true_map from 10AF
# ---------------------------------------------------------------------------

HIDDEN_CONTINENT_ID = "cont_af"
HIDDEN_TILE_IDS = ("tile_vale_1", "tile_grotto_1", "tile_spire_1")
HIDDEN_LANDMARK_IDS = ("lm_vale_shrine", "lm_grotto_pool", "lm_spire_peak")


def _make_hidden_true_map() -> dict:
    """Return the same synthetic hidden true_map used in 10AF."""
    return {
        "schema_version": "7B.1",
        "world_id": "test_world_10af",
        "seed": "10af_seed",
        "continents": [
            {"continent_id": HIDDEN_CONTINENT_ID, "name": "Sanctuary"},
        ],
        "regions": [
            {"region_id": "reg_vale", "continent_id": HIDDEN_CONTINENT_ID,
             "name": "Misty Vale"},
            {"region_id": "reg_grotto", "continent_id": HIDDEN_CONTINENT_ID,
             "name": "Sunken Grotto"},
            {"region_id": "reg_spire", "continent_id": HIDDEN_CONTINENT_ID,
             "name": "Obsidian Spire"},
        ],
        "tiles": [
            {
                "tile_id": "tile_vale_1", "continent_id": HIDDEN_CONTINENT_ID,
                "region_id": "reg_vale",
                "coordinates": {"x": 0, "y": 0},
                "terrain": "grassland", "biome": "temperate",
                "elevation": 10, "water": None,
                "resources": ["herbs"], "hazards": [],
                "landmark_ids": ["lm_vale_shrine"], "blocks_travel": False,
            },
            {
                "tile_id": "tile_grotto_1", "continent_id": HIDDEN_CONTINENT_ID,
                "region_id": "reg_grotto",
                "coordinates": {"x": 10, "y": 0},
                "terrain": "cave", "biome": "subterranean",
                "elevation": -5,
                "water": {"type": "pool", "fresh": True},
                "resources": ["crystals"], "hazards": ["darkness"],
                "landmark_ids": ["lm_grotto_pool"], "blocks_travel": False,
            },
            {
                "tile_id": "tile_spire_1", "continent_id": HIDDEN_CONTINENT_ID,
                "region_id": "reg_spire",
                "coordinates": {"x": -10, "y": 0},
                "terrain": "mountain", "biome": "alpine",
                "elevation": 100, "water": None,
                "resources": ["obsidian"], "hazards": ["thin_air"],
                "landmark_ids": ["lm_spire_peak"], "blocks_travel": False,
            },
        ],
        "landmarks": [
            {
                "landmark_id": "lm_vale_shrine", "continent_id": HIDDEN_CONTINENT_ID,
                "tile_id": "tile_vale_1", "kind": "shrine",
                "hidden_name": "Sanctuary of Whispers",
                "description": "A moss-covered stone shrine",
            },
            {
                "landmark_id": "lm_grotto_pool", "continent_id": HIDDEN_CONTINENT_ID,
                "tile_id": "tile_grotto_1", "kind": "water_source",
                "hidden_name": "Crystal Pool",
                "description": "A glowing underground pool",
            },
            {
                "landmark_id": "lm_spire_peak", "continent_id": HIDDEN_CONTINENT_ID,
                "tile_id": "tile_spire_1", "kind": "peak",
                "hidden_name": "Raven's Perch",
                "description": "A jagged obsidian spire",
            },
        ],
        "resources": [
            {"resource_id": "res_herbs", "tile_id": "tile_vale_1",
             "kind": "herbs", "renewable": True},
            {"resource_id": "res_crystals", "tile_id": "tile_grotto_1",
             "kind": "crystals", "renewable": False},
            {"resource_id": "res_obsidian", "tile_id": "tile_spire_1",
             "kind": "obsidian", "renewable": False},
        ],
        "hazards": [
            {"hazard_id": "haz_dark", "tile_id": "tile_grotto_1",
             "kind": "darkness", "severity": 2},
            {"hazard_id": "haz_air", "tile_id": "tile_spire_1",
             "kind": "thin_air", "severity": 3},
        ],
        "mysteries": [],
        "travel_edges": [],
    }


def _make_misty_vale_position() -> dict:
    """Agent standing at tile_vale_1 in Misty Vale."""
    return {
        "schema_version": "7B.1",
        "agent_id": "test_agent_ag",
        "active": True,
        "continent_id": HIDDEN_CONTINENT_ID,
        "region_id": "reg_vale",
        "tile_id": "tile_vale_1",
        "coordinates": {"x": 0, "y": 0},
        "facing": "north",
        "movement_mode": "walk",
        "travel_capabilities": ["walk_local"],
        "last_moved_tick": 0,
    }


def _make_grotto_position() -> dict:
    """Agent standing at tile_grotto_1 in Sunken Grotto."""
    return {
        "schema_version": "7B.1",
        "agent_id": "test_agent_grotto",
        "active": True,
        "continent_id": HIDDEN_CONTINENT_ID,
        "region_id": "reg_grotto",
        "tile_id": "tile_grotto_1",
        "coordinates": {"x": 10, "y": 0},
        "facing": "south",
        "movement_mode": "walk",
        "travel_capabilities": ["walk_local"],
        "last_moved_tick": 0,
    }


def _hidden_region_names() -> list[str]:
    return ["Sunken Grotto", "Obsidian Spire"]


def _hidden_landmark_hidden_names() -> list[str]:
    return ["Crystal Pool", "Raven's Perch"]


def _hidden_resource_kinds() -> list[str]:
    return ["crystals", "obsidian"]


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestBridgeConvertsObservation:
    """Contract claims 1–4: bridge produces a valid, non-leaking candidate."""

    def _build_observation(self, position: dict) -> dict:
        true_map = _make_hidden_true_map()
        known_map = create_empty_known_map(position["agent_id"])
        return build_local_observation(true_map, position, known_map, {"radius": 0})

    # ── 1. Valid candidate ────────────────────────────────────────────────

    def test_bridge_produces_valid_candidate(self):
        """Contract claim 1: bridge output passes validate_event."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation)
        result = validate_event(candidate)
        assert result["ok"], (
            f"Candidate failed validation: {result['errors']}"
        )

    def test_bridge_produces_valid_candidate_grotto(self):
        """Same as above but from a different region."""
        observation = self._build_observation(_make_grotto_position())
        candidate = observation_slice_to_candidate(observation)
        result = validate_event(candidate)
        assert result["ok"], (
            f"Grotto candidate failed validation: {result['errors']}"
        )

    # ── 2. Territory preservation ─────────────────────────────────────────

    def test_bridge_preserves_territory_vale(self):
        """Contract claim 2: candidate territory_ref matches observed region."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation)
        assert candidate["territory_ref"] == "reg_vale"

    def test_bridge_preserves_territory_grotto(self):
        observation = self._build_observation(_make_grotto_position())
        candidate = observation_slice_to_candidate(observation)
        assert candidate["territory_ref"] == "reg_grotto"

    # ── 3. Evidence construction ─────────────────────────────────────────

    def test_bridge_evidence_has_observed_world_fact(self):
        """Contract claim 3: evidence includes observed_world_fact category."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation)
        categories = {
            ev["category"]
            for ev in candidate.get("evidence_refs", [])
            if isinstance(ev, dict)
        }
        assert "observed_world_fact" in categories

    def test_bridge_evidence_tile_ids_match_observation(self):
        """Evidence tile_ids are exactly the visible tile IDs."""
        observation = self._build_observation(_make_misty_vale_position())
        visible_ids = set(observation.get("visible_tile_ids", []))
        candidate = observation_slice_to_candidate(observation)
        for ev in candidate.get("evidence_refs", []):
            if isinstance(ev, dict) and ev.get("category") == "observed_world_fact":
                evidence_ids = set(ev.get("tile_ids", []))
                assert evidence_ids == visible_ids, (
                    f"Evidence tile_ids {evidence_ids} don't match "
                    f"observation's visible_tile_ids {visible_ids}"
                )
                break
        else:
            pytest.fail("No observed_world_fact evidence found")

    def test_bridge_sets_observed_scope(self):
        """Candidate claim_scope is 'observed' when observation has data."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation)
        assert candidate["claim_scope"] == "observed"

    def test_bridge_actor_id_fallback(self):
        """When no actor_id is given, bridge uses agent_id from observation."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation)
        assert candidate["actor_id"] == "test_agent_ag"

    def test_bridge_actor_id_override(self):
        """Explicit actor_id overrides the observation's agent_id."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(
            observation, actor_id="custom_agent", tick=5
        )
        assert candidate["actor_id"] == "custom_agent"
        assert candidate["tick"] == 5

    def test_bridge_action_type_is_observe(self):
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation)
        assert candidate["action_type"] == "observe"

    # ── 4. Hidden data does not leak ──────────────────────────────────────

    def test_bridge_hidden_tile_ids_not_in_evidence(self):
        """Contract claim 4: hidden tile IDs are absent from evidence."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation)
        for ev in candidate.get("evidence_refs", []):
            if isinstance(ev, dict):
                for tid in ev.get("tile_ids", []):
                    assert tid in ("tile_vale_1",), (
                        f"Unexpected tile_id in evidence: {tid}"
                    )

    def test_bridge_hidden_landmark_ids_not_in_evidence(self):
        """Hidden landmark IDs are absent from evidence observation_detail."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation)
        # Check the observation_detail JSON for landmark IDs
        for ev in candidate.get("evidence_refs", []):
            if isinstance(ev, dict) and "observation_detail" in ev:
                detail = ev["observation_detail"]
                if "lm_grotto_pool" in detail or "lm_spire_peak" in detail:
                    pytest.fail(
                        f"Hidden landmark ID leaked into observation_detail: {detail}"
                    )

    def test_bridge_summary_contains_no_hidden_region_names(self):
        """The summary JSON mentions only the observed region, not hidden ones."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation)
        summary_text = candidate["summary"]
        for hidden in _hidden_region_names():
            assert hidden not in summary_text, (
                f"Hidden region name leaked into summary: {hidden}"
            )

    def test_bridge_summary_contains_no_hidden_resource_kinds(self):
        """Resources from hidden regions are absent from summary."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation)
        summary_text = candidate["summary"]
        for kind in _hidden_resource_kinds():
            assert kind not in summary_text, (
                f"Hidden resource kind leaked into summary: {kind}"
            )

    def test_bridge_summary_contains_observed_data(self):
        """The summary contains the observed region_id and tile count."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation)
        summary_text = candidate["summary"]
        assert "reg_vale" in summary_text
        assert "tile_vale_1" in summary_text
        assert "herbs" in summary_text


class TestCandidatePassesVerification:
    """Contract claim 5: verifier accepts the bridged candidate."""

    def test_verify_accepts_candidate(self):
        """verify_candidate_event returns accepted=True with no existing events."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation, tick=1)
        result = verify_candidate_event(candidate, [])
        assert result["accepted"], (
            f"Verifier rejected candidate: {result['errors']}"
        )

    def test_verify_accepts_multiple_observations(self):
        """Two bridge observations at different ticks pass verification."""
        obs1 = self._build_observation(_make_misty_vale_position())
        cand1 = observation_slice_to_candidate(obs1, actor_id="agent_a", tick=1)
        result1 = verify_candidate_event(cand1, [])
        assert result1["accepted"]

        obs2 = self._build_observation(_make_misty_vale_position())
        cand2 = observation_slice_to_candidate(obs2, actor_id="agent_b", tick=2)
        result2 = verify_candidate_event(cand2, [cand1])
        assert result2["accepted"], (
            f"Second candidate rejected: {result2['errors']}"
        )

    def _build_observation(self, position: dict) -> dict:
        true_map = _make_hidden_true_map()
        known_map = create_empty_known_map(position["agent_id"])
        return build_local_observation(true_map, position, known_map, {"radius": 0})


class TestCandidateFlowsIntoLedger:
    """Contract claim 6: candidate appends to ledger and is readable."""

    def _build_observation(self, position: dict) -> dict:
        true_map = _make_hidden_true_map()
        known_map = create_empty_known_map(position["agent_id"])
        return build_local_observation(true_map, position, known_map, {"radius": 0})

    def test_append_to_ledger(self, tmp_path):
        """append_event succeeds for a bridged candidate."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation, tick=1)

        ledger = tmp_path / "ledger.jsonl"
        result = append_event(ledger, candidate)
        assert result["ok"], (
            f"append_event failed: {result['errors']}"
        )

        events = read_events(ledger)
        assert len(events) == 1
        assert events[0]["event_id"] == candidate["event_id"]
        assert events[0]["territory_ref"] == "reg_vale"

    def test_append_two_observations_from_different_positions(self, tmp_path):
        """Two bridged observations from different positions both append."""
        obs_vale = self._build_observation(_make_misty_vale_position())
        cand_vale = observation_slice_to_candidate(
            obs_vale, actor_id="agent_vale", tick=1
        )

        obs_grotto = self._build_observation(_make_grotto_position())
        cand_grotto = observation_slice_to_candidate(
            obs_grotto, actor_id="agent_grotto", tick=2
        )

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, cand_vale)
        append_event(ledger, cand_grotto)

        events = read_events(ledger)
        assert len(events) == 2
        territory_refs = {e["territory_ref"] for e in events}
        assert territory_refs == {"reg_vale", "reg_grotto"}

    def test_ledger_does_not_contain_hidden_substrate(self, tmp_path):
        """The true_map structure is absent from the ledger file."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation, tick=1)

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, candidate)

        ledger_text = ledger.read_text(encoding="utf-8")
        assert "true_map" not in ledger_text
        for hidden in _hidden_landmark_hidden_names():
            assert hidden not in ledger_text, (
                f"Hidden landmark name leaked into ledger: {hidden}"
            )


class TestFullPipelineNoLeak:
    """Contract claims 7–8: full pipeline (bridge → → → sanitizer) is safe."""

    def _build_observation(self, position: dict) -> dict:
        true_map = _make_hidden_true_map()
        known_map = create_empty_known_map(position["agent_id"])
        return build_local_observation(true_map, position, known_map, {"radius": 0})

    @pytest.mark.parametrize("fmt", ["json", "jsonl", "csv"])
    def test_bridge_to_sanitized_export_no_hidden_leak(self, tmp_path, fmt):
        """Full pipeline produces public output with no hidden data."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation, tick=1)

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, candidate)
        events = read_events(ledger)
        export_str = export_events(events, fmt=fmt)
        sanitized = sanitize_public_text(export_str)

        # Hidden substrate absent
        for hidden in _hidden_region_names():
            assert hidden not in sanitized, (
                f"Hidden region leaked in {fmt}: {hidden}"
            )
        for hidden in _hidden_landmark_hidden_names():
            assert hidden not in sanitized, (
                f"Hidden landmark name leaked in {fmt}: {hidden}"
            )
        for kind in _hidden_resource_kinds():
            assert kind not in sanitized, (
                f"Hidden resource kind leaked in {fmt}: {kind}"
            )

        # Observed data survives
        assert "reg_vale" in sanitized, (
            f"Observed region_id missing from {fmt}"
        )
        assert "tile_vale_1" in sanitized, (
            f"Observed tile_id missing from {fmt}"
        )
        assert "herbs" in sanitized, (
            f"Observed resource kind missing from {fmt}"
        )

    @pytest.mark.parametrize("fmt", ["json", "jsonl", "csv"])
    def test_full_pipeline_multiple_positions(self, tmp_path, fmt):
        """Observations from both Vale and Grotto produce safe exports."""
        obs_vale = self._build_observation(_make_misty_vale_position())
        cand_vale = observation_slice_to_candidate(
            obs_vale, actor_id="agent_vale", tick=1
        )

        obs_grotto = self._build_observation(_make_grotto_position())
        cand_grotto = observation_slice_to_candidate(
            obs_grotto, actor_id="agent_grotto", tick=2
        )

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, cand_vale)
        append_event(ledger, cand_grotto)
        events = read_events(ledger)

        export_str = export_events(events, fmt=fmt)
        sanitized = sanitize_public_text(export_str)

        # Both observed regions appear
        assert "reg_vale" in sanitized
        assert "reg_grotto" in sanitized

        # The third region (spire) is never observed and never leaks
        assert "Obsidian Spire" not in sanitized
        assert "Raven's Perch" not in sanitized

    def test_pipeline_with_verifier_before_ledger(self, tmp_path):
        """Bridged candidate passes verifier, then appends to ledger."""
        observation = self._build_observation(_make_misty_vale_position())
        candidate = observation_slice_to_candidate(observation, tick=1)

        # Verify
        verify_result = verify_candidate_event(candidate, [])
        assert verify_result["accepted"], (
            f"Verifier rejected: {verify_result['errors']}"
        )

        # Append
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, candidate)
        events = read_events(ledger)
        assert len(events) == 1

        # Sanitized export
        export_str = export_events(events, fmt="json")
        sanitized = sanitize_public_text(export_str)
        assert "reg_vale" in sanitized
        assert "tile_vale_1" in sanitized

    def test_pipeline_detects_duplicate_tick(self, tmp_path):
        """Two observations at the same tick by the same actor fail verifier."""
        observation = self._build_observation(_make_misty_vale_position())
        cand1 = observation_slice_to_candidate(
            observation, actor_id="agent_a", tick=1
        )
        cand2 = observation_slice_to_candidate(
            observation, actor_id="agent_a", tick=1
        )

        # First one accepted
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, cand1)
        existing = read_events(ledger)

        # Second one rejected by verifier
        result = verify_candidate_event(cand2, existing)
        assert not result["accepted"], (
            "Duplicate tick+actor should be rejected"
        )
        assert any("duplicate" in e.lower() for e in result["errors"]), (
            f"No duplicate error in: {result['errors']}"
        )
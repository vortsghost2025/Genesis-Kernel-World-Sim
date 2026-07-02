"""Phase 10AF — Hidden Planet Substrate Contract.

Proves that a hidden world (true_map) can exist behind fog-of-war,
that an agent observes only a local slice, that the ledger records
only observed data, and that the full hidden substrate never leaks
into public export.

Contract claims:
  1. Planet has hidden truth — the true_map exists with regions/tiles/
     landmarks an agent has not yet seen.
  2. Agent can observe only local slice — fog-of-war limits visible
     tiles to those within range of the agent's position.
  3. Ledger records only observed slice — only the local observation
     is appended, not the full hidden substrate.
  4. Hidden substrate does not leak into public export — region
     names, landmark names, tile data from hidden areas are absent
     from exported output.
  5. Sanitized public output stays safe — even when the observed
     slice carries fake leak markers, the sanitizer redacts them.

This is a pure test — no daemon, runtime, live agents, canonical
data files, providers, or Docker.
"""

from __future__ import annotations

import copy
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
from backend.world.world_event_ledger import append_event, read_events, validate_event
from backend.world.world_event_exporter import export_events
from backend.world.world_event_sanitizer import (
    REDACTED_PATH,
    REDACTED_SECRET,
    REDACTED_RUNTIME,
    REDACTED_AGENT_TRACE,
    REDACTED_SKILL_REF,
    sanitize_public_text,
    sanitize_public_mapping,
)

# ---------------------------------------------------------------------------
# Synthetic hidden substrate (true_map) — the full hidden truth of a world.
# Three regions on one continent, each with its own tile, landmark,
# resources, and hazards.
# ---------------------------------------------------------------------------

HIDDEN_CONTINENT_ID = "cont_af"
HIDDEN_REGION_IDS = ("reg_vale", "reg_grotto", "reg_spire")
HIDDEN_TILE_IDS = ("tile_vale_1", "tile_grotto_1", "tile_spire_1")
HIDDEN_LANDMARK_IDS = ("lm_vale_shrine", "lm_grotto_pool", "lm_spire_peak")

# Synthetic fake leak markers — harmless placeholders that the sanitizer must
# redact if they appear in exported text.  No real paths, usernames, secrets,
# hostnames, or transcript language.
FAKE_LEAK_PATH = r"C:\Users\example\Documents\seed.txt"
FAKE_LEAK_SECRET = "TOKEN=dummy-placeholder"
FAKE_LEAK_IP = "127.0.0.1"
FAKE_LEAK_THOUGHT = "Thought: scanning terrain"
FAKE_LEAK_SKILL = "/agent-tools:skill"


def _make_hidden_true_map() -> dict:
    """Return a synthetic hidden true_map with three regions.

    All data is synthetic and harmless.
    """
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
    """Return an active agent position at tile_vale_1 in Misty Vale."""
    return {
        "schema_version": "7B.1",
        "agent_id": "test_agent_af",
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


def _make_observation_event(agent_id: str, observation: dict, tick: int = 1) -> dict:
    """Build a minimal world event from a local observation result.

    The summary holds a safe JSON payload describing what was seen.
    The evidence_refs carry the full observation detail so it appears
    in the exported output (and can be checked for leaks).
    """
    pos = observation.get("position", {})
    summary = json.dumps({
        "observed_region": pos.get("region_id"),
        "visible_tile_count": len(observation.get("visible_tiles", [])),
        "visible_landmark_count": len(observation.get("visible_landmarks", [])),
        "seen_resources": list(
            set(
                r
                for tile in observation.get("visible_tiles", [])
                for r in tile.get("resources", [])
            )
        ),
    })
    return {
        "event_id": f"evt_{agent_id}_{tick:04d}",
        "schema_version": "10K.1",
        "tick": tick,
        "actor_id": agent_id,
        "lens": "test",
        "territory_ref": pos.get("region_id", "unknown"),
        "action_type": "observe",
        "summary": summary,
        "evidence_refs": [
            {
                "category": "observed_world_fact",
                "tile_ids": list(observation.get("visible_tile_ids", [])),
                "observation_detail": json.dumps(observation, sort_keys=True),
            }
        ],
        "claim_scope": "observed",
        "before_ref": None,
        "after_ref": None,
        "affected_agents": [],
        "artifacts_created_or_changed": [],
        "relationship_delta": {},
        "consequence": {},
        "verification_status": "pending",
    }


def _hidden_region_names() -> list[str]:
    """Return the names of hidden regions that should NOT appear in
    public export when the agent is positioned at Misty Vale."""
    return ["Sunken Grotto", "Obsidian Spire"]


def _hidden_landmark_names() -> list[str]:
    """Return hidden landmark names an agent at Misty Vale should NOT see."""
    return ["Crystal Pool", "Raven's Perch"]


def _hidden_resource_kinds() -> list[str]:
    """Return resource kinds from hidden regions."""
    return ["crystals", "obsidian"]


def _make_observe_event_with_leaks(tick: int = 1) -> dict:
    """Build a minimal observe event whose summary contains every
    class of fake leak marker, simulating what could happen if an
    agent's observation text accidentally captured such content."""
    summary = (
        f"Observed at {FAKE_LEAK_PATH}; "
        f"config {FAKE_LEAK_SECRET}; "
        f"bound to {FAKE_LEAK_IP}; "
        f"{FAKE_LEAK_THOUGHT}; "
        f"used {FAKE_LEAK_SKILL}"
    )
    return {
        "event_id": f"evt_agent_leak_{tick:04d}",
        "schema_version": "10K.1",
        "tick": tick,
        "actor_id": "test_agent_leaky",
        "lens": "test",
        "territory_ref": "reg_vale",
        "action_type": "observe",
        "summary": summary,
        "evidence_refs": [
            {
                "category": "observed_world_fact",
                "tile_ids": ["tile_vale_1"],
                "detail": f"Path: {FAKE_LEAK_PATH}, key={FAKE_LEAK_SECRET}",
            }
        ],
        "claim_scope": "observed",
        "before_ref": None,
        "after_ref": None,
        "affected_agents": [],
        "artifacts_created_or_changed": [],
        "relationship_delta": {},
        "consequence": {},
        "verification_status": "pending",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestHiddenSubstrateExists:
    """Contract claim 1: planet has hidden truth."""

    def test_hidden_true_map_validates(self):
        """The synthetic true_map passes validate_true_map()."""
        true_map = _make_hidden_true_map()
        result = validate_true_map(true_map)
        assert result["ok"], f"true_map validation failed: {result['errors']}"

    def test_hidden_true_map_contains_all_regions(self):
        """All three regions are present in the hidden substrate."""
        true_map = _make_hidden_true_map()
        region_names = {r["name"] for r in true_map["regions"]}
        for name in ("Misty Vale", "Sunken Grotto", "Obsidian Spire"):
            assert name in region_names, f"Missing hidden region: {name}"

    def test_hidden_true_map_contains_all_tiles(self):
        """All three tiles are present in the hidden substrate."""
        true_map = _make_hidden_true_map()
        tile_ids = {t["tile_id"] for t in true_map["tiles"]}
        for tid in HIDDEN_TILE_IDS:
            assert tid in tile_ids, f"Missing hidden tile: {tid}"

    def test_hidden_true_map_contains_all_landmarks(self):
        """All three landmarks are present in the hidden substrate."""
        true_map = _make_hidden_true_map()
        landmark_ids = {lm["landmark_id"] for lm in true_map["landmarks"]}
        for lid in HIDDEN_LANDMARK_IDS:
            assert lid in landmark_ids, f"Missing hidden landmark: {lid}"

    def test_hidden_landmarks_have_hidden_names(self):
        """Hidden landmarks carry hidden_name that agents have not yet learned."""
        true_map = _make_hidden_true_map()
        hidden_names = {
            lm["hidden_name"]
            for lm in true_map["landmarks"]
            if "hidden_name" in lm
        }
        for name in ("Sanctuary of Whispers", "Crystal Pool", "Raven's Perch"):
            assert name in hidden_names, f"Missing hidden landmark name: {name}"

    def test_hidden_resources_exist(self):
        """Resources from all three regions exist in the substrate."""
        true_map = _make_hidden_true_map()
        kinds = {r["kind"] for r in true_map["resources"]}
        for kind in ("herbs", "crystals", "obsidian"):
            assert kind in kinds, f"Missing hidden resource: {kind}"


class TestFogOfWarLimitsObservation:
    """Contract claim 2: agent can observe only local slice."""

    def test_get_visible_tile_ids_radius_0(self):
        """At radius 0, only the agent's own tile is visible."""
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        visible = get_visible_tile_ids(true_map, position, radius=0)
        assert visible == ["tile_vale_1"], (
            f"Expected only tile_vale_1, got {visible}"
        )

    def test_hidden_tiles_not_visible_at_radius_1(self):
        """Grotto and Spire tiles are NOT visible from Misty Vale at radius 1.

        Coordinates: Vale (0,0), Grotto (10,0), Spire (-10,0).
        Manhattan distance to Grotto = 10, to Spire = 10.
        At radius 1, only tiles within distance <= 1 are visible.
        """
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        visible = get_visible_tile_ids(true_map, position, radius=1)
        # tile_vale_1 is at (0,0) — distance 0, always visible
        assert "tile_vale_1" in visible
        assert "tile_grotto_1" not in visible, (
            "Grotto tile leaked through fog-of-war"
        )
        assert "tile_spire_1" not in visible, (
            "Spire tile leaked through fog-of-war"
        )

    def test_build_local_observation_excludes_hidden_landmarks(self):
        """Landmarks in hidden regions are absent from local observation."""
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        known_map = create_empty_known_map("test_agent_af")
        observation = build_local_observation(true_map, position, known_map, {"radius": 0})

        visible_landmark_ids = {lm["true_landmark_id"] for lm in observation["visible_landmarks"]}
        # Vale shrine should be visible, the other two hidden
        assert "lm_vale_shrine" in visible_landmark_ids
        assert "lm_grotto_pool" not in visible_landmark_ids
        assert "lm_spire_peak" not in visible_landmark_ids

    def test_observation_contains_only_local_tile_data(self):
        """Observation tiles are restricted to visible ones only."""
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        known_map = create_empty_known_map("test_agent_af")
        observation = build_local_observation(true_map, position, known_map, {"radius": 0})

        observed_tile_ids = {t["tile_id"] for t in observation["visible_tiles"]}
        assert "tile_vale_1" in observed_tile_ids
        assert "tile_grotto_1" not in observed_tile_ids
        assert "tile_spire_1" not in observed_tile_ids


class TestLedgerRecordsOnlyObservedSlice:
    """Contract claim 3: ledger records only observed slice."""

    def test_observation_event_appends_to_ledger(self, tmp_path):
        """A local-observation event is appended successfully."""
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        known_map = create_empty_known_map("test_agent_af")
        observation = build_local_observation(true_map, position, known_map, {"radius": 0})
        event = _make_observation_event("test_agent_af", observation)

        ledger = tmp_path / "ledger.jsonl"
        result = append_event(ledger, event)
        assert result["ok"], f"append failed: {result['errors']}"

        events = read_events(ledger)
        assert len(events) == 1
        assert events[0]["event_id"] == "evt_test_agent_af_0001"

    def test_ledger_event_mentions_only_local_region(self, tmp_path):
        """The event summary mentions only the observed region, not hidden ones."""
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        known_map = create_empty_known_map("test_agent_af")
        observation = build_local_observation(true_map, position, known_map, {"radius": 0})
        event = _make_observation_event("test_agent_af", observation)

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)

        events = read_events(ledger)
        summary_text = events[0]["summary"]
        # The observed region SHOULD appear
        assert "reg_vale" in summary_text
        # Hidden regions should NOT appear
        for hidden_name in _hidden_region_names():
            assert hidden_name not in summary_text, (
                f"Hidden region name leaked into ledger: {hidden_name}"
            )

    def test_ledger_evidence_refs_contain_only_observed_tile_ids(self, tmp_path):
        """Evidence tile_ids are only the visible ones, not hidden tiles."""
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        known_map = create_empty_known_map("test_agent_af")
        observation = build_local_observation(true_map, position, known_map, {"radius": 0})
        event = _make_observation_event("test_agent_af", observation)

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)

        events = read_events(ledger)
        for evidence in events[0].get("evidence_refs", []):
            tile_ids = evidence.get("tile_ids", [])
            for tid in tile_ids:
                assert tid in HIDDEN_TILE_IDS, f"Unexpected tile_id: {tid}"
            # No hidden tiles should leak in
            assert "tile_grotto_1" not in tile_ids
            assert "tile_spire_1" not in tile_ids

    def test_ledger_does_not_contain_hidden_substrate(self, tmp_path):
        """The full hidden true_map is not stored in the ledger.

        Only the observation event is in the ledger — the entire
        true_map is never serialized.
        """
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        known_map = create_empty_known_map("test_agent_af")
        observation = build_local_observation(true_map, position, known_map, {"radius": 0})
        event = _make_observation_event("test_agent_af", observation)

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)

        ledger_text = ledger.read_text(encoding="utf-8")
        # The full true_map data should NOT appear in the ledger
        assert "true_map" not in ledger_text
        assert "Sanctuary of Whispers" not in ledger_text
        # Top-level field names that happen to match true_map keys are OK in the
        # event schema (e.g., "schema_version") — the assertion is that the
        # hidden true_map structure as a whole is absent.
        assert '"world_id"' not in ledger_text or "test_world_10af" not in ledger_text


class TestExportDoesNotLeakHiddenSubstrate:
    """Contract claim 4: hidden substrate does not leak into public export."""

    def _export_test_events(self, tmp_path, fmt: str) -> str:
        """Helper: build a local observation, append to ledger, export in fmt."""
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        known_map = create_empty_known_map("test_agent_af")
        observation = build_local_observation(true_map, position, known_map, {"radius": 0})
        event = _make_observation_event("test_agent_af", observation)

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)
        events = read_events(ledger)
        return export_events(events, fmt=fmt)

    def test_json_export_contains_no_hidden_region_names(self, tmp_path):
        output = self._export_test_events(tmp_path, "json")
        for hidden in _hidden_region_names():
            assert hidden not in output, (
                f"Hidden region name leaked into JSON export: {hidden}"
            )

    def test_json_export_contains_no_hidden_landmark_names(self, tmp_path):
        output = self._export_test_events(tmp_path, "json")
        for hidden in _hidden_landmark_names():
            assert hidden not in output, (
                f"Hidden landmark name leaked into JSON export: {hidden}"
            )

    def test_json_export_contains_no_hidden_resource_kinds(self, tmp_path):
        output = self._export_test_events(tmp_path, "json")
        for kind in _hidden_resource_kinds():
            assert kind not in output, (
                f"Hidden resource kind leaked into JSON export: {kind}"
            )

    def test_jsonl_export_contains_no_hidden_region_names(self, tmp_path):
        output = self._export_test_events(tmp_path, "jsonl")
        for hidden in _hidden_region_names():
            assert hidden not in output, (
                f"Hidden region name leaked into JSONL export: {hidden}"
            )

    def test_csv_export_contains_no_hidden_region_names(self, tmp_path):
        output = self._export_test_events(tmp_path, "csv")
        for hidden in _hidden_region_names():
            assert hidden not in output, (
                f"Hidden region name leaked into CSV export: {hidden}"
            )

    def test_observed_region_id_does_appear_in_export(self, tmp_path):
        """The region_id of the observed region appears in export (proof the
        observed slice made it through, not a leak of hidden data)."""
        output = self._export_test_events(tmp_path, "json")
        assert "reg_vale" in output, "Observed region_id missing from export"
        assert "tile_vale_1" in output, "Observed tile_id missing from export"

    def test_export_does_not_contain_true_map_itself(self, tmp_path):
        """The complete true_map structure is absent from every export format."""
        for fmt in ("json", "jsonl", "csv"):
            output = self._export_test_events(tmp_path, fmt)
            assert "true_map" not in output, (
                f"Full true_map leaked into {fmt} export"
            )
            assert "Raven's Perch" not in output, (
                f"Hidden landmark name leaked into {fmt} export"
            )


class TestSanitizedPublicOutputStaysSafe:
    """Contract claim 5: sanitized public output stays safe.

    Even when the observed event data carries fake leak markers
    (paths, secrets, IPs, trace markers, skill refs), the sanitizer
    redacts them all before the output becomes public-facing.
    """

    @pytest.mark.parametrize("fmt", ["json", "jsonl", "csv"])
    def test_sanitized_export_redacts_paths(self, tmp_path, fmt):
        event = _make_observe_event_with_leaks()
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)
        events = read_events(ledger)
        export_str = export_events(events, fmt=fmt)
        sanitized = sanitize_public_text(export_str)
        assert FAKE_LEAK_PATH not in sanitized
        assert REDACTED_PATH in sanitized

    @pytest.mark.parametrize("fmt", ["json", "jsonl", "csv"])
    def test_sanitized_export_redacts_secrets(self, tmp_path, fmt):
        event = _make_observe_event_with_leaks()
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)
        events = read_events(ledger)
        export_str = export_events(events, fmt=fmt)
        sanitized = sanitize_public_text(export_str)
        assert FAKE_LEAK_SECRET not in sanitized
        assert REDACTED_SECRET in sanitized

    @pytest.mark.parametrize("fmt", ["json", "jsonl", "csv"])
    def test_sanitized_export_redacts_runtime_markers(self, tmp_path, fmt):
        event = _make_observe_event_with_leaks()
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)
        events = read_events(ledger)
        export_str = export_events(events, fmt=fmt)
        sanitized = sanitize_public_text(export_str)
        assert FAKE_LEAK_IP not in sanitized
        assert REDACTED_RUNTIME in sanitized

    @pytest.mark.parametrize("fmt", ["json", "jsonl", "csv"])
    def test_sanitized_export_redacts_agent_trace_markers(self, tmp_path, fmt):
        event = _make_observe_event_with_leaks()
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)
        events = read_events(ledger)
        export_str = export_events(events, fmt=fmt)
        sanitized = sanitize_public_text(export_str)
        assert FAKE_LEAK_THOUGHT not in sanitized
        assert REDACTED_AGENT_TRACE in sanitized

    @pytest.mark.parametrize("fmt", ["json", "jsonl", "csv"])
    def test_sanitized_export_redacts_skill_refs(self, tmp_path, fmt):
        event = _make_observe_event_with_leaks()
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)
        events = read_events(ledger)
        export_str = export_events(events, fmt=fmt)
        sanitized = sanitize_public_text(export_str)
        assert FAKE_LEAK_SKILL not in sanitized
        assert REDACTED_SKILL_REF in sanitized

    def test_sanitized_export_via_mapping(self, tmp_path):
        """sanitize_public_mapping also works on the exported dict structure."""
        event = _make_observe_event_with_leaks()
        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)
        events = read_events(ledger)
        sanitized_events = sanitize_public_mapping(events)
        export_str = export_events(sanitized_events, fmt="json")
        assert FAKE_LEAK_PATH not in export_str
        assert FAKE_LEAK_SECRET not in export_str
        assert FAKE_LEAK_IP not in export_str
        assert FAKE_LEAK_SKILL not in export_str

    def test_hidden_substrate_data_survives_sanitizer(self, tmp_path):
        """World language (region IDs, tile kinds) is preserved by the
        sanitizer — only the fake leak markers are redacted."""
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        known_map = create_empty_known_map("test_agent_af")
        observation = build_local_observation(true_map, position, known_map, {"radius": 0})
        event = _make_observation_event("test_agent_af", observation)

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)
        events = read_events(ledger)
        export_str = export_events(events, fmt="json")
        sanitized = sanitize_public_text(export_str)

        # Observed data survives (region_id, tile_id, resource kind)
        assert "reg_vale" in sanitized
        assert "tile_vale_1" in sanitized
        assert "herbs" in sanitized
        # Hidden data still absent
        assert "Sunken Grotto" not in sanitized
        assert "Obsidian Spire" not in sanitized

    def test_sanitized_event_still_validates(self, tmp_path):
        """A sanitized event dict still passes validate_event."""
        event = _make_observe_event_with_leaks()
        sanitized_event = sanitize_public_mapping(event)
        result = validate_event(sanitized_event)
        assert result["ok"], (
            f"Sanitized event failed validation: {result['errors']}"
        )


class TestFullPipelineProof:
    """End-to-end: hidden true_map → fog-of-war → observe → ledger →
    export → sanitize.  The complete pipeline proves the contract."""

    def test_full_pipeline_no_hidden_leak(self, tmp_path):
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        known_map = create_empty_known_map("test_agent_af")
        observation = build_local_observation(true_map, position, known_map, {"radius": 0})
        event = _make_observation_event("test_agent_af", observation)

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, event)
        events = read_events(ledger)

        for fmt in ("json", "jsonl", "csv"):
            export_str = export_events(events, fmt=fmt)
            sanitized = sanitize_public_text(export_str)

            # Hidden substrate did not leak
            for hidden in _hidden_region_names():
                assert hidden not in sanitized, (
                    f"Hidden region leaked in {fmt}: {hidden}"
                )

            # Observed data survives (region_id, tile_id, resource kind)
            assert "reg_vale" in sanitized, (
                f"Observed region_id missing after sanitize in {fmt}"
            )
            assert "tile_vale_1" in sanitized, (
                f"Observed tile_id missing after sanitize in {fmt}"
            )
            assert "herbs" in sanitized, (
                f"Observed resource missing after sanitize in {fmt}"
            )

    def test_full_pipeline_with_leaks_still_safe(self, tmp_path):
        """Even with leaks in the observed data, the full pipeline
        produces clean public output."""
        # Plant a leaky event alongside a clean observation
        true_map = _make_hidden_true_map()
        position = _make_misty_vale_position()
        known_map = create_empty_known_map("test_agent_af")
        clean_observation = build_local_observation(
            true_map, position, known_map, {"radius": 0}
        )
        clean_event = _make_observation_event("test_agent_clean", clean_observation, tick=1)
        leaky_event = _make_observe_event_with_leaks(tick=2)

        ledger = tmp_path / "ledger.jsonl"
        append_event(ledger, clean_event)
        append_event(ledger, leaky_event)

        events = read_events(ledger)
        assert len(events) == 2

        for fmt in ("json", "jsonl", "csv"):
            export_str = export_events(events, fmt=fmt)
            sanitized = sanitize_public_text(export_str)

            # Hidden substrate absent
            for hidden in _hidden_region_names():
                assert hidden not in sanitized, (
                    f"Hidden region leaked in {fmt}: {hidden}"
                )
            # Leak markers absent
            assert FAKE_LEAK_PATH not in sanitized
            assert FAKE_LEAK_SECRET not in sanitized
            assert FAKE_LEAK_IP not in sanitized
            assert FAKE_LEAK_THOUGHT not in sanitized
            assert FAKE_LEAK_SKILL not in sanitized
            # Observed data preserved
            assert "Misty Vale" not in sanitized
            assert "reg_vale" in sanitized

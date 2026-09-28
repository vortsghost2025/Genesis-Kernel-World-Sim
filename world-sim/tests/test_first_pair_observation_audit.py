"""Observation persistence: the heartbeat record must retain what the agent saw.

`world-sim/docs/world_observation_transmission_spec.md` §7 recorded the gap:
`heartbeat.json` stores `"observation": {}`, so the record cannot answer "what
was this agent shown when it decided that?". Without it, no phase can measure
behaviour change after the fact.

This suite pins the fix at the persistence boundary. Pure: scratch stores
under tmp_path, no canonical store, no network, no provider.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.world.first_pair_runtime as rt_mod
from backend.world.first_pair_persistence import (
    HeartbeatRecord,
    load_heartbeat_history,
)

WORLD_SIM = Path(__file__).resolve().parents[1]


class TestHeartbeatRecordShape:
    def test_observation_is_required_and_round_trips(self):
        rec = HeartbeatRecord(
            heartbeat_number=1,
            agent_id="both",
            position="",
            observation={},
            action_taken=None,
        )
        assert rec.observation == {}
        envelope = rec.to_envelope()
        assert envelope["data"]["observation"] == {}

    def test_observation_serializes_when_populated(self):
        rec = HeartbeatRecord(
            heartbeat_number=2,
            agent_id="both",
            position="",
            observation={"tile_id": "t1", "visible_tiles": ["t1", "t2"]},
            action_taken=None,
        )
        payload = json.loads(json.dumps(rec.to_envelope()))["data"]
        assert payload["observation"]["tile_id"] == "t1"
        assert payload["observation"]["visible_tiles"] == ["t1", "t2"]


class TestObservationIsAuditable:
    """The record must be reconstructable into what the agent was shown."""

    def _record(self, obs: dict) -> HeartbeatRecord:
        return HeartbeatRecord(
            heartbeat_number=1,
            agent_id="both",
            position="",
            observation=obs,
            action_taken=None,
        )

    def test_visible_tiles_recoverable_from_record(self):
        obs = {
            "tile_id": "t1",
            "visible_tiles": ["t1", "t2", "t3"],
            "objects_here": [],
            "visible_tile_details": [
                {"tile_id": "t1", "terrain": "hill", "resources": ["stone"]}
            ],
        }
        payload = json.loads(json.dumps(self._record(obs).to_envelope()))["data"]
        stored = payload["observation"]
        assert stored["visible_tiles"] == ["t1", "t2", "t3"]
        assert stored["visible_tile_details"][0]["terrain"] == "hill"

    def test_water_in_record_is_recoverable(self):
        obs = {
            "tile_id": "origin",
            "visible_tiles": ["origin"],
            "objects_here": [],
            "visible_tile_details": [
                {
                    "tile_id": "origin",
                    "terrain": "grassland",
                    "water": {"type": "river", "drinkable": True},
                    "hazards": [],
                    "resources": ["fiber_plants", "fresh_water"],
                }
            ],
        }
        payload = json.loads(json.dumps(self._record(obs).to_envelope()))["data"]
        detail = payload["observation"]["visible_tile_details"][0]
        assert detail["water"]["drinkable"] is True
        assert "fresh_water" in detail["resources"]

    def test_empty_observation_is_distinguishable_from_absent(self):
        """A heartbeat that stored nothing must be auditable as such."""
        payload = json.loads(json.dumps(self._record({}).to_envelope()))["data"]
        assert "observation" in payload
        assert payload["observation"] == {}

    def test_record_survives_round_trip_through_store(self, tmp_path):
        """Persisted record must reload with the observation intact."""
        from backend.world.first_pair_persistence import (
            FirstPairPersistenceStore,
            append_heartbeat,
        )
        store = FirstPairPersistenceStore(tmp_path)
        obs = {
            "tile_id": "t1",
            "visible_tiles": ["t1"],
            "objects_here": [],
            "visible_tile_details": [
                {"tile_id": "t1", "terrain": "hill", "water": {}, "hazards": []}
            ],
        }
        append_heartbeat(store, self._record(obs))
        history = load_heartbeat_history(store)
        assert len(history) == 1
        assert history[0].observation["tile_id"] == "t1"
        assert history[0].observation["visible_tile_details"][0]["terrain"] == "hill"


class TestRuntimeAuditProjection:
    """The runtime must build the per-agent audit map it promises."""

    def test_projects_per_agent_visible_tiles(self):
        rt = object.__new__(rt_mod.FirstPairRuntime)
        out = rt._audit_observations({
            "east_adam": {
                "tile_id": "a1", "visible_tiles": ["a1", "a2"],
                "objects_here": [], "visible_tile_details": [],
                "physics": {"version": "epistemic.1.1"},
            },
            "east_eve": {
                "tile_id": "e1", "visible_tiles": ["e1"],
                "objects_here": [], "visible_tile_details": [],
            },
        })
        assert set(out) == {"east_adam", "east_eve"}
        assert out["east_adam"]["visible_tiles"] == ["a1", "a2"]
        assert out["east_eve"]["visible_tiles"] == ["e1"]

    def test_two_agents_on_different_tiles_stay_separate(self):
        """A merged map would misrepresent what each agent saw."""
        rt = object.__new__(rt_mod.FirstPairRuntime)
        out = rt._audit_observations({
            "east_adam": {"tile_id": "a1", "visible_tiles": ["a1"]},
            "east_eve": {"tile_id": "e1", "visible_tiles": ["e1", "e2"]},
        })
        assert out["east_adam"]["visible_tiles"] == ["a1"]
        assert out["east_eve"]["visible_tiles"] == ["e1", "e2"]

    def test_empty_observations_yield_empty_audit(self):
        rt = object.__new__(rt_mod.FirstPairRuntime)
        assert rt._audit_observations({}) == {}
        assert rt._audit_observations(None) == {}

    def test_fog_error_is_retained_as_the_audit_signal(self):
        rt = object.__new__(rt_mod.FirstPairRuntime)
        out = rt._audit_observations({
            "east_adam": {
                "tile_id": "a1", "visible_tiles": ["a1"],
                "fog_error": "geography observation unavailable",
            },
        })
        assert out["east_adam"]["fog_error"] == (
            "geography observation unavailable"
        )

    def test_conditions_retained_when_present(self):
        rt = object.__new__(rt_mod.FirstPairRuntime)
        out = rt._audit_observations({
            "east_adam": {
                "tile_id": "a1", "visible_tiles": ["a1"],
                "conditions": {"visibility": "storm"},
            },
        })
        assert out["east_adam"]["conditions"]["visibility"] == "storm"

    def test_drops_non_observation_keys(self):
        """Only observation content is retained, not unrelated context."""
        rt = object.__new__(rt_mod.FirstPairRuntime)
        out = rt._audit_observations({
            "east_adam": {
                "tile_id": "a1", "visible_tiles": ["a1"],
                "private_memories": ["secret"],
                "operator_messages": [{"text": "hi"}],
            },
        })
        assert "private_memories" not in out["east_adam"]
        assert "operator_messages" not in out["east_adam"]

    def test_never_stores_implementation_internals(self):
        rt = object.__new__(rt_mod.FirstPairRuntime)
        out = rt._audit_observations({
            "east_adam": {"tile_id": "a1", "visible_tiles": ["a1"]},
        })
        text = json.dumps(out)
        assert "true_map" not in text
        assert "known_map" not in text


class TestNoSecretLeakIntoRecord:
    @staticmethod
    def _record(obs: dict) -> HeartbeatRecord:
        return HeartbeatRecord(
            heartbeat_number=1,
            agent_id="both",
            position="",
            observation=obs,
            action_taken=None,
        )

    def test_record_never_carries_implementation_names(self):
        obs = {
            "tile_id": "t1",
            "visible_tiles": ["t1"],
            "objects_here": [],
            "visible_tile_details": [],
        }
        text = json.dumps(self._record(obs).to_envelope())
        assert "true_map" not in text
        assert "known_map" not in text
        assert "true_landmark_id" not in text

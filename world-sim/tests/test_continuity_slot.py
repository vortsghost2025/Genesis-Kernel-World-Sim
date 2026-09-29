"""Continuity slot — "what am I in the middle of?"

`docs/continuity_slot_spec.md`. Folds recurrence signal, session state,
want-tracking, and joint plans into one piggyback-metadata record: no new
verb, no economy change, aging automatic, stale lines dropped with notice.

Design constraints the tests pin down:

  * OPTIONAL output field. Required would break every existing model output
    (missing_field errors). Absent metadata leaves everything untouched.
  * CONTEXT NEVER VETOES ACTION. Malformed metadata is an error note; the
    proposed action still executes.
  * AGES, not dates. Every line carries its heartbeat; staleness is computed
    against an explicit current heartbeat — no wall clock, no hidden state.
  * READ-ONLY recurrence. The shared-theme line is computed by the runtime;
    agent metadata cannot set it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_model import (  # noqa: E402
    validate_model_output,
)
from backend.world.first_pair_persistence import (  # noqa: E402
    detect_recurrence,
    load_continuity,
    prune_continuity,
    render_continuity,
    save_continuity,
    update_continuity,
)


def _out(raw):
    return validate_model_output(raw, "genesis-agent-aaa")


def _valid_output(**overrides):
    base = {
        "observation_summary": "saw hills",
        "self_model_update": None,
        "goal_updates": [],
        "proposed_action": {"action_type": "no_action"},
        "memory_candidates": [],
        "questions_for_humans": [],
        "uncertainty": "none",
        "decision_summary": "rest",
        "confidence": 0.5,
    }
    base.update(overrides)
    return base


def _meta(**overrides):
    base = {"continuing": "mapping the west hills"}
    base.update(overrides)
    return base


class TestOutputParsing:
    def test_absent_metadata_leaves_output_untouched(self):
        out = _out(_valid_output())
        assert out.is_valid, out.validation_errors
        assert out.continuity_update is None

    def test_well_formed_metadata_parses(self):
        out = _out(_valid_output(
            continuity_update=_meta(paused="waiting on Eve",
                                    open_questions=["why one water tile?"]),
        ))
        assert out.is_valid, out.validation_errors
        assert out.continuity_update["continuing"] == "mapping the west hills"
        assert out.continuity_update["open_questions"] == ["why one water tile?"]

    def test_unknown_top_fields_still_rejected(self):
        raw = _valid_output()
        raw["smuggled"] = 1
        out = _out(raw)
        assert not out.is_valid
        assert any("smuggled" in e for e in out.validation_errors)

    def test_malformed_metadata_does_not_veto_action(self):
        """Context must never veto action: error noted, action survives —
        end to end, through the validity gate, not just the parser."""
        raw = _valid_output(
            continuity_update={"continuing": 42},
            proposed_action={"action_type": "move", "target_tile": "t1",
                             "reason": "survey"},
        )
        out = _out(raw)
        assert any("continuity" in e for e in out.validation_errors)
        assert out.is_valid, ("malformed context metadata must not "
                              "invalidate the turn")
        assert out.proposed_action is not None
        assert out.proposed_action.get("action_type") == "move"
        assert out.continuity_update is None, ("bad metadata is dropped, "
                                               "not persisted")

    def test_oversized_metadata_rejected(self):
        raw = _valid_output(continuity_update={"continuing": "x" * 5000})
        out = _out(raw)
        assert any("continuity" in e for e in out.validation_errors)

    def test_too_many_open_questions_rejected(self):
        raw = _valid_output(
            continuity_update={"open_questions": ["a", "b", "c", "d"]})
        out = _out(raw)
        assert any("continuity" in e for e in out.validation_errors)

    def test_wrong_shaped_fields_rejected(self):
        raw = _valid_output(continuity_update={"completed": ["not", "a", "str"]})
        out = _out(raw)
        assert any("continuity" in e for e in out.validation_errors)


class TestStore:
    def test_update_writes_slots_with_heartbeat(self):
        rec = update_continuity({}, _meta(), heartbeat=100)
        assert rec["continuing"] == {"text": "mapping the west hills",
                                     "since_hb": 100}

    def test_absent_fields_leave_slots_untouched(self):
        rec = update_continuity({}, _meta(), heartbeat=100)
        rec2 = update_continuity(rec, {"paused": "rain"}, heartbeat=101)
        assert rec2["continuing"]["since_hb"] == 100
        assert rec2["paused"] == {"text": "rain", "since_hb": 101}

    def test_empty_string_clears_a_slot(self):
        rec = update_continuity({}, _meta(), heartbeat=100)
        rec2 = update_continuity(rec, {"continuing": ""}, heartbeat=101)
        assert rec2["continuing"] is None

    def test_open_questions_cap_three_oldest_dropped(self):
        rec = update_continuity(
            {}, {"open_questions": ["q1", "q2", "q3"]}, heartbeat=100)
        rec2 = update_continuity(rec, {"open_questions": ["q4"]}, heartbeat=101)
        texts = [q["text"] for q in rec2["open_questions"]]
        assert texts == ["q2", "q3", "q4"], texts

    def test_round_trip_through_store(self, tmp_path):
        from backend.world.first_pair_persistence import (
            FirstPairPersistenceStore,
        )

        store = FirstPairPersistenceStore(tmp_path / "store")
        save_continuity(store, "east_adam",
                        update_continuity({}, _meta(), heartbeat=100))
        loaded = load_continuity(store, "east_adam")
        assert loaded["continuing"]["text"] == "mapping the west hills"

    def test_unknown_agent_loads_empty(self, tmp_path):
        from backend.world.first_pair_persistence import (
            FirstPairPersistenceStore,
        )

        store = FirstPairPersistenceStore(tmp_path / "store")
        assert load_continuity(store, "east_adam") == {}


class TestAging:
    def test_stale_lines_drop_with_notice_not_silence(self):
        rec = update_continuity({}, _meta(), heartbeat=100)
        kept, notices = prune_continuity(rec, current_hb=301)
        assert kept.get("continuing") is None
        assert any("mapping the west hills" in n for n in notices)

    def test_fresh_lines_survive_without_notice(self):
        rec = update_continuity({}, _meta(), heartbeat=100)
        kept, notices = prune_continuity(rec, current_hb=150)
        assert kept["continuing"]["text"] == "mapping the west hills"
        assert notices == []

    def test_boundary_is_not_stale(self):
        rec = update_continuity({}, _meta(), heartbeat=100)
        kept, _ = prune_continuity(rec, current_hb=300)
        assert kept["continuing"] is not None


class TestRendering:
    def test_record_renders_with_ages(self):
        rec = update_continuity({}, _meta(open_questions=["why one water?"]),
                                heartbeat=100)
        text = render_continuity(rec, current_hb=140)
        assert "mapping the west hills" in text
        assert "40 heartbeats ago" in text
        assert "why one water?" in text

    def test_empty_record_renders_neutral(self):
        text = render_continuity({}, current_hb=140)
        assert "Traceback" not in text
        assert text.strip(), "must not be an empty block"


class TestRecurrence:
    def test_shared_repeated_theme_detected(self):
        a = ["surveying the clay hills again"] * 4 + ["resting"]
        b = ["clay hills need mapping"] * 4 + ["moving"]
        found = detect_recurrence(a, b, threshold=5)
        assert any("clay" in t and "hill" in t for t in found), found

    def test_one_sided_repetition_is_not_shared(self):
        a = ["clay hills clay hills"] * 6
        b = ["resting quietly here"]
        assert detect_recurrence(a, b, threshold=5) == []

    def test_below_threshold_is_silent(self):
        a = ["clay hills"] * 2
        b = ["clay hills"] * 2
        assert detect_recurrence(a, b, threshold=5) == []

    def test_common_words_are_not_themes(self):
        a = ["the world is wide and the sky is blue"] * 6
        b = ["the world is wide and the sky is blue"] * 6
        found = detect_recurrence(a, b, threshold=5)
        assert "the" not in found and "and" not in found


class TestPromptRendering:
    def test_section_renders_at_top_of_observations(self):
        from backend.world.first_pair_cognition_model import build_system_prompt
        from backend.world.first_pair_cognition_interface import AgentContext

        ctx = AgentContext(
            agent_id="a", canonical_name="A", canonical_ref="east_adam",
            other_agent_id="b", other_agent_name="B", other_agent_ref="east_eve",
            heartbeat_number=140, position="t1",
            observation={"tile_id": "t1"}, memory=[], goals=[],
            unanswered_questions=[], world_public_objects={},
            habitat_allowed_tiles=["t1"], habitat_movement_allowed=True,
            previous_action=None, timestamp_utc="2026-09-28T00:00:00+00:00",
            continuity_section="--- CURRENT CONTEXT ---\n- continuing: hills",
        )
        prompt = build_system_prompt(ctx)
        assert "--- CURRENT CONTEXT ---" in prompt
        assert prompt.index("CURRENT CONTEXT") < prompt.index("Your observation")

    def test_absent_section_renders_nothing_broken(self):
        from backend.world.first_pair_cognition_model import build_system_prompt
        from backend.world.first_pair_cognition_interface import AgentContext

        ctx = AgentContext(
            agent_id="a", canonical_name="A", canonical_ref="east_adam",
            other_agent_id="b", other_agent_name="B", other_agent_ref="east_eve",
            heartbeat_number=140, position="t1",
            observation={"tile_id": "t1"}, memory=[], goals=[],
            unanswered_questions=[], world_public_objects={},
            habitat_allowed_tiles=["t1"], habitat_movement_allowed=True,
            previous_action=None, timestamp_utc="2026-09-28T00:00:00+00:00",
        )
        assert "Traceback" not in build_system_prompt(ctx)


class TestRuntimeWiring:
    def _applied(self, tmp_path, agent_ref="east_adam", meta=None, hb=100):
        from backend.world.first_pair_cognition_interface import (
            CognitionOutput,
        )
        from backend.world.first_pair_persistence import (
            FirstPairPersistenceStore,
        )
        from backend.world.first_pair_runtime import FirstPairRuntime

        store = FirstPairPersistenceStore(tmp_path / "store")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt._load_or_initialize()
        out = CognitionOutput(
            action={"action_type": "no_action"},
            memory_write=[],
            goal_updates=[],
            questions_raised=[],
            internal_reasoning="test",
            confidence=0.5,
            continuity_update=meta,
        )
        rt._apply_cognition_output(agent_ref, out, hb)
        return store

    def test_apply_persists_metadata(self, tmp_path):
        store = self._applied(tmp_path,
                              meta={"continuing": "mapping west"})
        assert load_continuity(store, "east_adam")["continuing"] == {
            "text": "mapping west", "since_hb": 100}

    def test_apply_without_metadata_changes_nothing(self, tmp_path):
        store = self._applied(tmp_path, meta=None)
        assert load_continuity(store, "east_adam") == {}

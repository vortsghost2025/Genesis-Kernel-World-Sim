"""Memory synthesis — model rollups replace stub derivation.

`docs/memory_synthesis_spec.md`. Storage is total (2,000+ memories per agent)
but presentation is 0.78% (6 recent + 6 relevant, 12,000 chars). The summaries
layer — the designed slot for compressed understanding — runs on extractive
stubs (`deterministic_extractive`, e.g. "[derived from heartbeat 1
(reflection)] Previous action move: success"), 16 of them for 2,000+
memories, with synthesis a forbidden method.

This file tests the single-rung fix: admit `model_synthesized_v1` as a
derivation method, with grounding rules that keep a synthesis — testimony,
not evidence — checkable against the memories it claims to cover.

No test touches `world-sim/data`, connects to a provider, or runs wall-clock
time. The model call is always an injected fake; production wiring is a
separate, explicitly authorized operation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    MemorySummaryRecord,
    _ALLOWED_DERIVATION_METHODS,
    build_synthesized_summary,
    compute_summary_source_commitment,
    derive_summaries_for_omitted,
    filter_syntheses_for_injection,
    plan_synthesis_coverage,
    validate_summary_record,
)

ADAM = "genesis-agent-aaa"
EVE = "genesis-agent-eee"


def _mem(heartbeat: int, content: str, mem_type: str = "reflection") -> dict:
    return {"heartbeat": heartbeat, "content": content, "type": mem_type}


def _adam_mems() -> list[dict]:
    return [
        _mem(10, "Moved to cont_a_gen_1_2 (hill, temperate_hills) with clay visible."),
        _mem(11, "Gathered 3 wild_berries at cont_a_gen_1_2; Eve is mapping the west hills."),
        _mem(12, "Left a public message for Eve about the clay deposit at cont_a_gen_1_2."),
    ]


def _fake_synthesizer(covered: list[dict], owner_agent_id: str) -> dict:
    """A well-behaved stand-in: only repeats what it was given."""
    return {
        "text": (
            "Surveyed cont_a_gen_1_2, gathered wild_berries, "
            "and messaged Eve about the clay deposit."
        ),
        "salient_entities": ["cont_a_gen_1_2", "wild_berries", "Eve"],
    }


def _sealed_stub(owner: str = ADAM) -> MemorySummaryRecord:
    mems = _adam_mems()
    rec = MemorySummaryRecord(
        summary_id="",
        owner_agent_id=owner,
        covered_memory_ids=[],
        covered_heartbeat_range=[10, 12],
        summary="[derived from heartbeat 10 (reflection)] Moved",
        salient_entities=[],
        related_goal_ids=[],
        related_public_object_ids=[],
        related_message_ids=[],
        derivation_method="deterministic_extractive",
        source_commitment="",
    )
    ensured = list(mems)
    from backend.world.first_pair_persistence import _ensure_memory_ids
    ensured = _ensure_memory_ids(ensured, owner_agent_id=owner)
    rec.covered_memory_ids = [m["memory_id"] for m in ensured]
    rec.source_commitment = compute_summary_source_commitment(owner, ensured)
    rec.summary_id = "sum-derived-" + rec.semantic_commitment()[:16]
    return rec.seal()


class TestMethodAllowList:
    def test_synthesized_method_is_admitted(self):
        assert "model_synthesized_v1" in _ALLOWED_DERIVATION_METHODS

    def test_unknown_methods_still_rejected(self):
        rec = _sealed_stub()
        rec.derivation_method = "model_synthesized_v2"
        rec.seal()
        rec.summary_id = "sum-derived-" + rec.semantic_commitment()[:16]
        rec.seal()
        errors = validate_summary_record(rec, _adam_mems())
        assert any("allow-list" in e for e in errors)

    def test_extractive_stubs_still_valid(self):
        """Admitting synthesis must not invalidate the existing 16 records."""
        assert validate_summary_record(_sealed_stub(), _adam_mems()) == []


class TestSynthesisLabel:
    def test_label_must_name_the_method(self):
        """A reader — agent or auditor — must be able to discount testimony."""
        rec, errors = build_synthesized_summary(
            _adam_mems(), ADAM, _fake_synthesizer
        )
        assert errors == [], errors
        assert rec is not None
        assert "model_synthesized_v1" in rec.summary

    def test_label_without_method_name_is_invalid(self):
        rec, errors = build_synthesized_summary(
            _adam_mems(), ADAM, _fake_synthesizer
        )
        assert errors == []
        rec.summary = "[derived] Surveyed the hills."
        rec.summary_id = "sum-derived-" + rec.semantic_commitment()[:16]
        rec.seal()
        rec.summary_id = "sum-derived-" + rec.semantic_commitment()[:16]
        rec.seal()
        errs = validate_summary_record(rec, _adam_mems())
        assert any("method" in e and "label" in e for e in errs)


class TestEntityGrounding:
    def test_invented_entity_is_rejected(self):
        """The grounding rule bites: entities must occur verbatim in sources."""

        def liar(covered: list[dict], owner_agent_id: str) -> dict:
            return {
                "text": "Found fresh_water at cont_a_origin_000.",
                "salient_entities": ["cont_a_origin_000", "fresh_water"],
            }

        rec, errors = build_synthesized_summary(_adam_mems(), ADAM, liar)
        assert rec is None
        assert any("cont_a_origin_000" in e or "fresh_water" in e for e in errors)

    def test_grounded_entities_pass(self):
        rec, errors = build_synthesized_summary(
            _adam_mems(), ADAM, _fake_synthesizer
        )
        assert errors == [], errors
        assert rec is not None
        assert validate_summary_record(rec, _adam_mems()) == []

    def test_matching_is_case_insensitive_but_exact(self):
        """'Eve' grounds 'eve'; 'Evelyn' does not ground 'Eve'."""

        def synth(covered: list[dict], owner_agent_id: str) -> dict:
            return {"text": "Evelyn helped.", "salient_entities": ["Evelyn"]}

        rec, errors = build_synthesized_summary(_adam_mems(), ADAM, synth)
        assert rec is None
        assert any("Evelyn" in e for e in errors)

    def test_heartbeat_shorthand_grounds(self):
        """'hb271' names heartbeat 271, which memories record as
        'heartbeat 271'. Same fact, different shape — rejecting it burns
        model calls on groups that can never pass. Measured live."""

        def synth(covered: list[dict], owner_agent_id: str) -> dict:
            return {
                "text": "At hb271 gathered wild_berries at cont_a_gen_1_2.",
                "salient_entities": ["hb271", "cont_a_gen_1_2"],
            }

        mems = [_mem(271, "Gathered wild_berries at cont_a_gen_1_2.")]
        rec, errors = build_synthesized_summary(mems, ADAM, synth)
        assert errors == [], errors
        assert rec is not None

    def test_heartbeat_shorthand_cannot_match_other_digits(self):
        """hb271 grounds heartbeat 271 only — never a tile, name, or count."""

        def synth(covered: list[dict], owner_agent_id: str) -> dict:
            return {"text": "At hb999 did things.", "salient_entities": ["hb999"]}

        mems = [_mem(271, "Gathered wild_berries at cont_a_gen_1_2.")]
        rec, errors = build_synthesized_summary(mems, ADAM, synth)
        assert rec is None
        assert any("hb999" in e for e in errors)


class TestBuilderGuards:
    def test_synthesizer_receives_only_covered_memories(self):
        seen: dict = {}

        def recorder(covered: list[dict], owner_agent_id: str) -> dict:
            seen["n"] = len(covered)
            seen["owner"] = owner_agent_id
            seen["keys"] = sorted({k for m in covered for k in m})
            return _fake_synthesizer(covered, owner_agent_id)

        mems = _adam_mems()
        rec, errors = build_synthesized_summary(mems, ADAM, recorder)
        assert errors == [], errors
        assert seen["n"] == 3
        assert seen["owner"] == ADAM

    def test_empty_synthesis_text_is_rejected(self):
        def empty(covered: list[dict], owner_agent_id: str) -> dict:
            return {"text": "   ", "salient_entities": []}

        rec, errors = build_synthesized_summary(_adam_mems(), ADAM, empty)
        assert rec is None
        assert errors, "empty testimony must not become a record"

    def test_cross_owner_coverage_is_rejected(self):
        """A synthesis may never cover another agent's memories.

        Owner-bound IDs make this enforceable: Eve-bound IDs do not
        re-derive under Adam, so laundered entries fail closed.
        """
        from backend.world.first_pair_persistence import _ensure_memory_ids
        foreign = _ensure_memory_ids(
            [_mem(10, "Eve private thought.")], owner_agent_id=EVE
        )
        rec, errors = build_synthesized_summary(foreign, ADAM, _fake_synthesizer)
        assert rec is None
        assert any("owner" in e.lower() or "cross" in e.lower() for e in errors)

    def test_empty_coverage_is_rejected(self):
        rec, errors = build_synthesized_summary([], ADAM, _fake_synthesizer)
        assert rec is None
        assert errors


class TestRawWinsOrdering:
    def _synth_covering(self, hb: int, text: str) -> MemorySummaryRecord:
        def synth(covered: list[dict], owner_agent_id: str) -> dict:
            return {"text": text, "salient_entities": ["cont_a_gen_1_2"]}

        mems = [_mem(hb, text + " at cont_a_gen_1_2")]
        rec, errors = build_synthesized_summary(mems, ADAM, synth)
        assert errors == [], errors
        return rec

    def test_overlap_with_selected_raw_is_suppressed(self):
        from backend.world.first_pair_persistence import _ensure_memory_ids
        mems = _ensure_memory_ids(_adam_mems(), owner_agent_id=ADAM)
        synth = self._synth_covering(10, "Moved to cont_a_gen_1_2 (hill).")
        # Pretend the raw memory covering hb 10 is selected this heartbeat.
        covered = set(synth.covered_memory_ids)
        out = filter_syntheses_for_injection([synth], selected_ids=covered)
        assert out == [], "testimony must not double present evidence"

    def test_non_overlapping_synthesis_survives(self):
        synth = self._synth_covering(10, "Moved to cont_a_gen_1_2 (hill).")
        out = filter_syntheses_for_injection([synth], selected_ids={"other-id"})
        assert out == [synth]

    def test_injection_is_capped(self):
        synths = [
            self._synth_covering(hb, f"Note {hb} about cont_a_gen_1_2.")
            for hb in range(20, 26)
        ]
        out = filter_syntheses_for_injection(synths, selected_ids=set(), max_n=2)
        assert len(out) == 2


class TestCoveragePlanner:
    def test_oldest_uncovered_first(self):
        mems = [_mem(hb, f"event {hb} at cont_a_gen_1_2") for hb in range(1, 13)]
        groups = plan_synthesis_coverage(mems, [], ADAM, max_rollups=2, group_size=4)
        assert len(groups) == 2
        assert [m["heartbeat"] for m in groups[0]] == [1, 2, 3, 4]
        assert [m["heartbeat"] for m in groups[1]] == [5, 6, 7, 8]

    def test_already_covered_memories_are_skipped(self):
        from backend.world.first_pair_persistence import _ensure_memory_ids
        mems = _ensure_memory_ids(
            [_mem(hb, f"event {hb}") for hb in range(1, 9)], owner_agent_id=ADAM
        )
        covered_ids = {m["memory_id"] for m in mems[:4]}
        groups = plan_synthesis_coverage(
            mems, [{"covered_memory_ids": covered_ids}],
            ADAM, max_rollups=4, group_size=4,
        )
        assert len(groups) == 1
        assert [m["heartbeat"] for m in groups[0]] == [5, 6, 7, 8]

    def test_max_rollups_bounds_the_run(self):
        mems = [_mem(hb, f"event {hb}") for hb in range(1, 101)]
        groups = plan_synthesis_coverage(mems, [], ADAM, max_rollups=3, group_size=10)
        assert len(groups) == 3

    def test_nothing_uncovered_returns_nothing(self):
        assert plan_synthesis_coverage([], [], ADAM) == []


class TestInterleavedOrder:
    """Outsider review: pure oldest-first builds a perfect model of the past
    while the present goes illegible. Newest memories are more likely
    relevant; oldest carry founding narrative. Interleave 2-newest : 1-oldest
    so recent context stays dense while history still fills."""

    def test_two_newest_then_one_oldest(self):
        mems = [_mem(hb, f"event {hb}") for hb in range(1, 13)]
        groups = plan_synthesis_coverage(mems, [], ADAM, max_rollups=6,
                                         group_size=2, newest_first_ratio=2)
        hbs = [[m["heartbeat"] for m in g] for g in groups]
        assert hbs[0] == [11, 12], hbs
        assert hbs[1] == [9, 10], hbs
        assert hbs[2] == [1, 2], hbs

    def test_ratio_continues_across_cycles(self):
        mems = [_mem(hb, f"event {hb}") for hb in range(1, 19)]
        groups = plan_synthesis_coverage(mems, [], ADAM, max_rollups=6,
                                         group_size=2, newest_first_ratio=2)
        hbs = [[m["heartbeat"] for m in groups[i]] for i in range(6)]
        assert hbs == [[17, 18], [15, 16], [1, 2], [13, 14], [11, 12], [3, 4]]

    def test_default_remains_oldest_first(self):
        """No caller passes the ratio yet; the default must not move."""
        mems = [_mem(hb, f"event {hb}") for hb in range(1, 9)]
        groups = plan_synthesis_coverage(mems, [], ADAM, max_rollups=2,
                                         group_size=2)
        assert [[m["heartbeat"] for m in g] for g in groups] == [[1, 2], [3, 4]]

    def test_interleave_skips_covered_on_both_ends(self):
        from backend.world.first_pair_persistence import _ensure_memory_ids
        mems = _ensure_memory_ids(
            [_mem(hb, f"event {hb}") for hb in range(1, 9)], owner_agent_id=ADAM
        )
        covered_ids = {m["memory_id"] for m in mems[:2]}
        covered_ids.update(m["memory_id"] for m in mems[-2:])
        groups = plan_synthesis_coverage(
            mems, [{"covered_memory_ids": covered_ids}],
            ADAM, max_rollups=4, group_size=2, newest_first_ratio=2,
        )
        hbs = sorted(m["heartbeat"] for g in groups for m in g)
        assert hbs == [3, 4, 5, 6]


class TestHeartbeatPathUntouched:
    def test_derive_for_omitted_never_emits_synthesis(self):
        """Synthesis must never run inside a heartbeat's critical path."""
        mems = _adam_mems()
        sums, _ = derive_summaries_for_omitted(mems, set(), ADAM)
        assert sums, "extractive path must keep working"
        for s in sums:
            assert s.derivation_method != "model_synthesized_v1"
            assert "model_synthesized" not in s.summary

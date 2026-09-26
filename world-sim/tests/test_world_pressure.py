"""World pressure: RETIRED. These tests pin the removal so it cannot return.

The hunger/capacity pressure model shipped in 05f314f/be5ce8a and was
removed in this phase. It failed for a measured reason, recorded in
docs/epistemic_pressure_spec.md:

  * famished build-gate rejections: 0 in 70 heartbeats
  * 5 of 5 built objects stated their purpose as inventory relief
    ("to reduce goods overcapacity") - it made agents accountants
  * east_adam's home tile yields 1 wild_berry/heartbeat and consumption
    removed 1/heartbeat, pinning his food at 0 for 100+ ticks. He
    reported it as a bug at HB797. The East pair's 0% build rate was not
    apathy; it was two agents correctly refusing to act on a rigged
    board, misread as "the world asks nothing of them."

So the tests below are mostly NEGATIVE: they assert the retired
mechanics are gone, and that the deadlock the agents reported is
actually resolved. The positive behaviours that survive the retirement
(build, placement authority, the ask sink, the rule-change notice, the
operator channel, request reconciliation, echo suppression, outcome
persistence) are pinned here too, because "removal" must not quietly
take anything else with it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.world.first_pair_cognition_model import build_system_prompt
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    append_agent_question_proposal,
    append_operator_message,
    load_agent_question_proposals,
    load_heartbeat_history,
    load_inventory,
    load_operator_messages,
    save_world_state,
)
from backend.world.first_pair_runtime import FirstPairRuntime
from backend.world.world_pressure import GATHER_YIELD, PHYSICS_VERSION
from scripts.export_viewer_snapshot import build_pair_snapshot
from scripts.operator_inbox import render as render_inbox, scan_pair


ADAM_ID = "genesis-agent-4327298502de9566131e81212dd3b383666b6f18bc887d8508ab3a059e73f34e"


def _fresh_store(tmp_path: Path) -> FirstPairPersistenceStore:
    return FirstPairPersistenceStore(tmp_path / ".runtime" / "first-pair")


def _runtime(store) -> FirstPairRuntime:
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt.run()
    return rt


def _build_action(**overrides) -> dict:
    base = {
        "action_type": "build",
        "object_id": "wall-001",
        "object_type": "wall",
        "description": "A low dry-stone wall marking my corner of the world.",
        "tile_id": "tile-alpha",
        "materials": {"stone": 3},
    }
    base.update(overrides)
    return base


def _allow_tile(rt, tile="tile-alpha"):
    rt._world_state.tile_occupancy["east_adam"] = tile
    rt._habitat.setdefault("allowed_tile_ids", []).append(tile)


# ---------------------------------------------------------------------------
# The retirement itself
# ---------------------------------------------------------------------------


class TestRetiredMechanicsAreGone:
    def test_world_pressure_exports_no_metabolism(self):
        import backend.world.world_pressure as wp
        for name in ("FOOD_CAP", "GOODS_CAP", "FOOD_PER_HEARTBEAT",
                     "FOOD_KINDS", "GATHER_REJECT_FOOD", "GATHER_REJECT_GOODS",
                     "BUILD_REJECT_FAMISHED", "split_ledgers",
                     "consume_choice", "gather_allowance",
                     "provisions_view", "carrying_view"):
            assert not hasattr(wp, name), f"{name} still exported - retirement undone"

    def test_yield_is_one_again(self):
        assert GATHER_YIELD == 1

    def test_version_moved_to_the_new_era(self):
        assert PHYSICS_VERSION == "epistemic.1"

    def test_runtime_has_no_pressure_step(self):
        rt = FirstPairRuntime(heartbeat_limit=1, store=_fresh_store(Path(".")))
        assert not hasattr(rt, "_pressure_step")
        assert not hasattr(rt, "_pressure_state")

    def test_no_provisions_or_carrying_in_the_observation(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", 4)
        ctx = rt._build_context("east_adam", 2)
        assert "provisions" not in ctx.observation
        assert "carrying" not in ctx.observation
        assert ctx.physics["version"] == PHYSICS_VERSION

    def test_prompt_has_no_body_section(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        prompt = build_system_prompt(rt._build_context("east_adam", 2))
        assert "YOUR BODY" not in prompt
        assert "famished" not in prompt.lower()
        assert "THE WORLD'S TERMS" in prompt

    def test_exporter_ships_no_pressure_block(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", 2)
        snap = build_pair_snapshot(
            "east", store.root, {"tiles": [], "continents": []})
        assert "pressure" not in snap
        assert snap["inventories"]["east_adam"] == {"stone": 2}

    def test_watcher_no_longer_reports_starving(self, tmp_path):
        import importlib
        import scripts.agent_watch as aw
        importlib.reload(aw)
        assert not hasattr(aw, "scan_starving")
        for fn in ("scan_asks", "scan_stuck", "scan_first_build", "scan_dead"):
            assert hasattr(aw, fn), f"{fn} must survive the retirement"


# ---------------------------------------------------------------------------
# The deadlock the agents reported, fixed
# ---------------------------------------------------------------------------


class TestDeadlockResolved:
    """The regression that motivated the retirement. Written first."""

    def test_one_berry_tile_accumulates_instead_of_cancelling(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=4, store=store)
        rt.run()  # initialize
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        for hb in range(2, 6):
            rt._current_tile_resources = {
                "tile-alpha": [{"kind": "wild_berries", "amount": 1}]}
            rt._execute_action(
                "east_adam",
                {"action_type": "gather", "resource_kind": "wild_berries"},
                heartbeat_number=hb)
        # nothing removes it any more: 4 gathers on a 1-berry tile = 4 held
        assert load_inventory(store)["east_adam"]["wild_berries"] == 4

    def test_heartbeats_do_not_consume_food(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=3, store=store)
        add_to_inventory(store, "east_adam", "wild_berries", 5)
        rt.run()
        assert load_inventory(store)["east_adam"]["wild_berries"] == 5

    def test_goods_accumulate_without_a_cap(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        rt._current_tile_resources = {
            "tile-alpha": [{"kind": "stone", "amount": 99}]}
        for _ in range(3):
            rt._execute_action(
                "east_adam",
                {"action_type": "gather", "resource_kind": "stone"},
                heartbeat_number=2)
        assert load_inventory(store)["east_adam"]["stone"] == 3

    def test_no_hands_full_rejection_is_possible(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        rt._current_tile_resources = {
            "tile-alpha": [{"kind": "stone", "amount": 999}]}
        for _ in range(5):
            outcome = rt._execute_action(
                "east_adam",
                {"action_type": "gather", "resource_kind": "stone"},
                heartbeat_number=2)
            assert outcome.get("status") == "success"
            assert "hands full" not in str(outcome)

    def test_build_works_with_no_food_held(self, tmp_path):
        """The famished gate is gone: no food, no block."""
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", 5)
        _allow_tile(rt)
        outcome = rt._execute_action(
            "east_adam", _build_action(), heartbeat_number=2)
        assert outcome.get("status") == "success", outcome


# ---------------------------------------------------------------------------
# Surviving behaviour: the build layer must be untouched
# ---------------------------------------------------------------------------


class TestBuildLayerSurvives:
    def test_build_spends_and_creates(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", 5)
        _allow_tile(rt)
        outcome = rt._execute_action(
            "east_adam", _build_action(), heartbeat_number=2)
        assert outcome.get("status") == "success"
        assert outcome.get("materials_spent") == {"stone": 3}
        assert load_inventory(store)["east_adam"]["stone"] == 2
        obj = rt._world_state.public_objects.get("wall-001")
        assert obj is not None and obj.get("materials") == {"stone": 3}

    def test_build_on_own_tile_ignores_a_stale_whitelist(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._habitat["allowed_tile_ids"] = ["some-other-tile"]
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        add_to_inventory(store, "east_adam", "stone", 5)
        outcome = rt._execute_action(
            "east_adam", _build_action(), heartbeat_number=2)
        assert outcome.get("status") == "success", outcome

    def test_build_on_other_tile_still_refused(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        add_to_inventory(store, "east_adam", "stone", 9)
        outcome = rt._execute_action(
            "east_adam", _build_action(tile_id="tile-elsewhere"),
            heartbeat_number=2)
        assert outcome.get("status") == "rejected"
        assert load_inventory(store)["east_adam"]["stone"] == 9

    def test_insufficient_materials_rejects_no_partial(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", 2)
        _allow_tile(rt)
        outcome = rt._execute_action(
            "east_adam", _build_action(materials={"stone": 3}), heartbeat_number=2)
        assert outcome.get("status") == "rejected"
        assert load_inventory(store)["east_adam"]["stone"] == 2
        assert "wall-001" not in rt._world_state.public_objects

    def test_gather_still_rejects_a_barren_tile_truthfully(self, tmp_path):
        """The world still says no when there is nothing. That is not a cap."""
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        rt._current_tile_resources = {"tile-alpha": []}
        outcome = rt._execute_action(
            "east_adam",
            {"action_type": "gather", "resource_kind": "wild_berries"},
            heartbeat_number=2)
        assert outcome.get("status") == "rejected"
        assert "No wild_berries available" in outcome.get("reason", "")


# ---------------------------------------------------------------------------
# Surviving behaviour: loop integrity
# ---------------------------------------------------------------------------


class TestPhysicsNoticeSurvives:
    def test_version_and_new_flag_present(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt._load_or_initialize()
        ctx = rt._build_context("east_adam", 1)
        assert ctx.physics["version"] == PHYSICS_VERSION
        assert ctx.physics["new_to_agent"] is True

    def test_notice_fires_once_then_clears(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        first = build_system_prompt(rt._build_context("east_adam", 2))
        second = build_system_prompt(rt._build_context("east_adam", 3))
        assert "THE WORLD'S TERMS" in first and "THE WORLD'S TERMS" in second
        assert "terms have changed" not in second


class TestOperatorChannelSurvives:
    def _say(self, store, text, addressed_to="all", author="Sean"):
        return append_operator_message(store, {
            "message_id": "op-1", "author": author, "addressed_to": addressed_to,
            "text": text, "created_at_utc": "2026-09-26T00:00:00+00:00"})

    def test_broadcast_reaches_both_agents(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._say(store, "I am watching.")
        assert len(rt._build_context("east_adam", 2).operator_messages) == 1
        assert len(rt._build_context("east_eve", 2).operator_messages) == 1

    def test_addressed_message_not_shown_to_others(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._say(store, "Only for you.", addressed_to="east_eve")
        assert rt._build_context("east_adam", 2).operator_messages == []
        assert len(rt._build_context("east_eve", 2).operator_messages) == 1

    def test_prompt_carries_the_operator_message(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._say(store, "The stone is yours.")
        prompt = build_system_prompt(rt._build_context("east_adam", 2))
        assert "MESSAGES FROM THE OPERATOR" in prompt
        assert "The stone is yours." in prompt

    def test_exporter_ships_operator_messages(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._say(store, "visible to the show")
        snap = build_pair_snapshot(
            "east", store.root, {"tiles": [], "continents": []})
        assert snap["operator_messages"][-1]["text"] == "visible to the show"


class TestAskSinkSurvives:
    def _ask(self, qid="q-1"):
        return {
            "action_type": "ask_human", "question_id": qid,
            "question": "Why is build refused?", "reason_for_asking": "Blocked",
            "urgency": "high"}

    def test_ask_persisted_and_noncanonical(self, tmp_path):
        from backend.world.first_pair_persistence import load_questions
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        outcome = rt._execute_action("east_adam", self._ask(), heartbeat_number=2)
        assert outcome.get("status") == "proposed"
        records = load_agent_question_proposals(store)
        assert records[-1]["status"] == "unheard"
        assert load_questions(store) == []

    def test_inbox_shows_unheard_asks(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._execute_action("east_adam", self._ask(), heartbeat_number=2)
        report = scan_pair("east", store.root)
        assert report["unheard_asks"]
        assert "UNHEARD ASKS" in render_inbox([report])


class TestReconciliationSurvives:
    def _grant(self, store, capability_id="gather"):
        from backend.world.first_pair_persistence import (
            CapabilityGrantRecord, append_capability_grant)
        append_capability_grant(store, CapabilityGrantRecord(
            grant_id="g-" + capability_id, capability_id=capability_id,
            scope="pair", reason="operator grant", status="granted"))

    def test_granted_requests_are_retired(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._grant(store, "gather")
        rt._world_state.capability_requests = [
            {"capability_id": "gather", "requesting_agent_id": "x", "status": "pending"},
            {"capability_id": "sail", "requesting_agent_id": "x", "status": "pending"},
        ]
        assert rt._reconcile_capability_requests() == 1
        statuses = {r["capability_id"]: r["status"]
                    for r in rt._world_state.capability_requests}
        assert statuses == {"gather": "granted", "sail": "pending"}


class TestEchoSuppressionSurvives:
    def test_identical_thought_recorded_once(self):
        from backend.world.first_pair_runtime import _reflection_is_echo
        mem = [{"type": "reflection", "content": "goods 51/20, food 13/20"}]
        assert _reflection_is_echo(mem, "goods 51/20, food 14/20") is True
        assert _reflection_is_echo(mem, "something else entirely") is False


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------


class TestCompliance:
    def test_heartbeat_records_still_carry_outcomes(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        history = load_heartbeat_history(store)
        assert history[-1].action_outcomes

    def test_history_grows_append_only(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=3, store=store)
        rt.run()
        assert [h.heartbeat_number for h in load_heartbeat_history(store)] == [1, 2, 3]

    def test_retirement_does_not_rewrite_the_true_map(self, tmp_path):
        p = Path("data/world/true_map.json")
        if not p.is_file():
            pytest.skip("true map not present")
        before = p.stat().st_mtime_ns
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        assert p.stat().st_mtime_ns == before

"""World pressure — provision, two-ledger carrying capacity, famished build gate.

TDD suite for docs/world_pressure_spec.md (v2). Covers the pure physics
module (ledger split, most-held food consumption choice, the per-ledger
gather allowance with frozen rejection strings), runtime wiring (per-
heartbeat consumption, gather allowance, famished build gate, fail-closed
behavior, observation keys), placement authority (the HB701-743 live-arc
regression: build must work on the agent's own tile even when the static
policy whitelist is stale), the noncanonical ask sink (agent_questions.json
— an agent that is stuck must be audible to the operator), prompt
projection, heartbeat outcome persistence (census contract), and exporter.
"""

from __future__ import annotations

import json
import re
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
from backend.world.world_pressure import (
    BUILD_REJECT_FAMISHED,
    FOOD_CAP,
    FOOD_KINDS,
    FOOD_PER_HEARTBEAT,
    GATHER_YIELD,
    GOODS_CAP,
    GATHER_REJECT_FOOD,
    GATHER_REJECT_GOODS,
    PHYSICS_VERSION,
    carrying_view,
    consume_choice,
    gather_allowance,
    provisions_view,
    split_ledgers,
)
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


def _pressure(rt, ref="east_adam", hb=2):
    """Refresh the tick-pressure state the way the run loop does."""
    return rt._pressure_step(ref, hb)


# ---------------------------------------------------------------------------
# Pure physics: ledger split
# ---------------------------------------------------------------------------


class TestSplitLedgers:
    def test_classification(self):
        led = split_ledgers({"wild_berries": 5, "stone": 3, "fish": 2})
        assert led == {"food": 7, "goods": 3}

    def test_all_food_kinds_classified(self):
        for kind in FOOD_KINDS:
            assert split_ledgers({kind: 1}) == {"food": 1, "goods": 0}

    def test_fiber_and_water_are_goods(self):
        led = split_ledgers({"fiber_plants": 4, "fresh_water": 2})
        assert led == {"food": 0, "goods": 6}

    def test_empty(self):
        assert split_ledgers({}) == {"food": 0, "goods": 0}

    def test_malformed_tolerated(self):
        led = split_ledgers({"wild_berries": "x", "stone": True, "clay": -1,
                             "fish": 3, None: 5})
        assert led == {"food": 3, "goods": 0}
        assert split_ledgers(None) == {"food": 0, "goods": 0}
        assert split_ledgers(["wild_berries"]) == {"food": 0, "goods": 0}

    def test_zero_amounts_count_as_zero(self):
        assert split_ledgers({"wild_berries": 0, "stone": 0}) == {"food": 0, "goods": 0}


# ---------------------------------------------------------------------------
# Pure physics: consumption choice (most-held food kind, deterministic ties)
# ---------------------------------------------------------------------------


class TestConsumeChoice:
    def test_most_held_food_kind(self):
        assert consume_choice({"wild_berries": 2, "fish": 5, "stone": 9}) == "fish"

    def test_tie_break_deterministic(self):
        h = {"mushrooms": 3, "wild_berries": 3}
        assert consume_choice(h) == sorted(["mushrooms", "wild_berries"])[0]
        assert consume_choice(h) == consume_choice(dict(reversed(list(h.items()))))

    def test_no_food_returns_none(self):
        assert consume_choice({"stone": 4}) is None
        assert consume_choice({}) is None

    def test_zero_food_kind_ignored(self):
        assert consume_choice({"wild_berries": 0, "stone": 2}) is None
        assert consume_choice({"wild_berries": 0, "fish": 1}) == "fish"


# ---------------------------------------------------------------------------
# Pure physics: the per-ledger gather allowance
# ---------------------------------------------------------------------------


class TestGatherAllowance:
    def test_take_is_yield_when_room_and_tile_allow(self):
        take, reason = gather_allowance("wild_berries", {"wild_berries": 0}, 0, 0, 5)
        assert take == GATHER_YIELD
        assert reason is None

    def test_partial_take_tops_off_nearly_full_ledger(self):
        # 18/20 with yield 3: only 2 fit
        take, reason = gather_allowance("wild_berries", {"wild_berries": 18}, 18, 0, 5)
        assert (take, reason) == (2, None)

    def test_tile_limits_take(self):
        take, reason = gather_allowance("wild_berries", {"wild_berries": 0}, 0, 0, 1)
        assert (take, reason) == (1, None)

    def test_at_cap_food_rejected_frozen_string(self):
        take, reason = gather_allowance("wild_berries", {"wild_berries": 20}, 20, 0, 5)
        assert take == 0
        assert reason == GATHER_REJECT_FOOD

    def test_food_refill_after_eating(self):
        # started 20, ate 1 -> 19: one unit of room
        take, reason = gather_allowance("wild_berries", {"wild_berries": 19}, 20, 0, 5)
        assert (take, reason) == (1, None)

    def test_goods_fill_to_cap_then_reject(self):
        assert gather_allowance("stone", {"stone": 19}, 0, 19, 5) == (1, None)
        take, reason = gather_allowance("stone", {"stone": 20}, 0, 20, 5)
        assert take == 0 and reason == GATHER_REJECT_GOODS

    def test_over_cap_goods_take_nothing(self):
        # the live-arc shape: West Eve with 51 fiber
        take, reason = gather_allowance("fiber_plants", {"fiber_plants": 51}, 0, 51, 5)
        assert take == 0
        assert reason == GATHER_REJECT_GOODS

    def test_over_cap_food_may_replace_only_what_was_eaten(self):
        # started 45 (over cap), ate 1 -> 44; room is exactly 1
        take, reason = gather_allowance("wild_berries", {"wild_berries": 44}, 45, 0, 5)
        assert (take, reason) == (1, None)

    def test_over_cap_food_never_grows(self):
        # did not eat this tick: no room at all
        take, reason = gather_allowance("wild_berries", {"wild_berries": 45}, 45, 0, 5)
        assert take == 0
        assert reason == GATHER_REJECT_FOOD

    def test_frozen_reason_strings(self):
        assert GATHER_REJECT_GOODS == "hands full"
        assert GATHER_REJECT_FOOD == "food store full"

    def test_zero_food_over_cap_goods_may_gather_food(self):
        # trap check: famished agent with 65 goods can still forage
        take, reason = gather_allowance("wild_berries", {"stone": 65}, 0, 65, 5)
        assert take == GATHER_YIELD
        assert reason is None

    def test_unknown_kind_is_goods(self):
        take, reason = gather_allowance("mythril", {"mythril": 20}, 0, 20, 5)
        assert take == 0 and reason == GATHER_REJECT_GOODS

    def test_empty_kind_is_not_a_cap_question(self):
        assert gather_allowance("", {}, 0, 0, 5) == (0, None)

    def test_food_is_bankable(self):
        """Yield must exceed consumption or food can never exceed 1."""
        assert GATHER_YIELD > FOOD_PER_HEARTBEAT
        food = 0
        for _ in range(10):
            take, reason = gather_allowance("wild_berries", {"wild_berries": food}, food, 0, 9)
            assert reason is None
            food = max(0, food - FOOD_PER_HEARTBEAT) + take
        # the steady ceiling is cap minus the per-tick burn (eat precedes
        # gather); the HB701-743 failure pinned this at 1, forever
        assert food >= FOOD_CAP - FOOD_PER_HEARTBEAT
        assert food > 5


# ---------------------------------------------------------------------------
# Runtime wiring: per-heartbeat consumption
# ---------------------------------------------------------------------------


class TestPressureStep:
    def test_consumption_persists_via_store(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        add_to_inventory(store, "east_adam", "wild_berries", 3)
        rt.run()
        # heartbeat 1: adam ate 1 berry during his pressure step
        assert load_inventory(store)["east_adam"]["wild_berries"] == 2

    def test_consumption_picks_most_held_food(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        add_to_inventory(store, "east_adam", "wild_berries", 1)
        add_to_inventory(store, "east_adam", "fish", 4)
        rt.run()
        inv = load_inventory(store)["east_adam"]
        assert inv["fish"] == 3
        assert inv["wild_berries"] == 1

    def test_no_food_makes_famished_and_writes_nothing(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        # no food anywhere: no inventory file created, adam famished this tick
        assert not (store.root / "inventory.json").exists()
        assert rt._pressure_tick["east_adam"]["famished"] is True
        assert rt._pressure_tick["east_adam"]["food_start"] == 0

    def test_holding_food_not_famished(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        add_to_inventory(store, "east_adam", "wild_berries", 2)
        rt.run()
        assert rt._pressure_tick["east_adam"]["famished"] is False
        assert rt._pressure_tick["east_adam"]["consumed_kind"] == "wild_berries"

    def test_consume_step_fail_closed(self, tmp_path, monkeypatch):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "wild_berries", 2)

        def boom(*a, **k):
            raise OSError("disk exploded")

        monkeypatch.setattr(
            "backend.world.first_pair_runtime.add_to_inventory", boom)
        rt._pressure_tick = {}
        rt._pressure_step("east_adam")
        # holdings unchanged, agent not marked famished (it holds food)
        assert load_inventory(store)["east_adam"]["wild_berries"] == 2
        assert rt._pressure_tick["east_adam"]["famished"] is False
        assert rt._pressure_tick["east_adam"]["consumed_kind"] == ""

    def test_both_agents_consume_each_heartbeat(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        add_to_inventory(store, "east_adam", "wild_berries", 5)
        add_to_inventory(store, "east_eve", "fish", 5)
        rt.run()
        assert load_inventory(store)["east_adam"]["wild_berries"] == 4
        assert load_inventory(store)["east_eve"]["fish"] == 4

    def test_food_recovers_over_ticks_from_zero(self, tmp_path):
        """The HB701-743 pin (food 0/1 forever) must not recur."""
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=6, store=store)
        rt.run()  # famished start
        store2 = _fresh_store(tmp_path / "b")
        rt2 = FirstPairRuntime(heartbeat_limit=6, store=store2)
        rt2.run()
        # simulate: agent gathers food every tick from 0 via the executor
        rt2._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        rt2._current_tile_resources = {
            "tile-alpha": [{"kind": "wild_berries", "amount": 99}]}
        for hb in range(7, 13):
            rt2._pressure_step("east_adam", hb)
            rt2._execute_action(
                "east_adam",
                {"action_type": "gather", "resource_kind": "wild_berries"},
                heartbeat_number=hb)
        assert load_inventory(store2)["east_adam"]["wild_berries"] > 1


# ---------------------------------------------------------------------------
# Runtime wiring: gather allowance and famished build gate
# ---------------------------------------------------------------------------


class TestGatherRuntime:
    def _seed_tile(self, rt, kind, amount=99):
        rt._current_tile_resources = {"tile-alpha": [{"kind": kind, "amount": amount}]}
        _allow_tile(rt)

    def test_goods_cap_rejects_with_frozen_string(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", GOODS_CAP)
        add_to_inventory(store, "east_adam", "wild_berries", 1)
        _pressure(rt)  # eats the berry; goods start = 20
        self._seed_tile(rt, "stone")
        outcome = rt._execute_action(
            "east_adam",
            {"action_type": "gather", "resource_kind": "stone"},
            heartbeat_number=2)
        assert outcome == {"status": "rejected", "reason": GATHER_REJECT_GOODS}
        assert load_inventory(store)["east_adam"]["stone"] == GOODS_CAP

    def test_over_cap_goods_never_grow(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", 65)
        add_to_inventory(store, "east_adam", "wild_berries", 2)
        _pressure(rt)  # goods_start = 65 (over cap)
        self._seed_tile(rt, "stone")
        outcome = rt._execute_action(
            "east_adam",
            {"action_type": "gather", "resource_kind": "stone"},
            heartbeat_number=2)
        assert outcome.get("status") == "rejected"
        assert load_inventory(store)["east_adam"]["stone"] == 65

    def test_over_cap_goods_zero_food_may_still_forage(self, tmp_path):
        """The famished-and-frozen trap must not exist."""
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", 65)
        _pressure(rt)  # no food -> famished, starts 0/65
        assert rt._pressure_tick["east_adam"]["famished"] is True
        self._seed_tile(rt, "wild_berries", 5)
        outcome = rt._execute_action(
            "east_adam",
            {"action_type": "gather", "resource_kind": "wild_berries"},
            heartbeat_number=2)
        assert outcome.get("status") == "success"
        assert load_inventory(store)["east_adam"]["wild_berries"] == GATHER_YIELD

    def test_over_cap_food_holds_steady_via_net_zero(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "wild_berries", 45)
        _pressure(rt)  # food_start=45, now 44
        self._seed_tile(rt, "wild_berries", 5)
        outcome = rt._execute_action(
            "east_adam",
            {"action_type": "gather", "resource_kind": "wild_berries"},
            heartbeat_number=2)
        assert outcome.get("status") == "success"
        assert outcome.get("amount_gathered") == 1  # replaced the meal, no more
        assert load_inventory(store)["east_adam"]["wild_berries"] == 45
        # a second gather in the same tick would grow the over-cap ledger
        outcome2 = rt._execute_action(
            "east_adam",
            {"action_type": "gather", "resource_kind": "wild_berries"},
            heartbeat_number=2)
        assert outcome2 == {"status": "rejected", "reason": GATHER_REJECT_FOOD}

    def test_gather_missing_kind_rejection_unaffected(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        outcome = rt._execute_action(
            "east_adam", {"action_type": "gather"}, heartbeat_number=2)
        assert outcome == {"status": "rejected", "reason": "Missing resource_kind"}

    def test_tile_depletion_visible(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._seed_tile(rt, "stone", amount=5)
        outcome = rt._execute_action(
            "east_adam",
            {"action_type": "gather", "resource_kind": "stone"},
            heartbeat_number=2)
        assert outcome.get("amount_gathered") == GATHER_YIELD
        assert outcome.get("remaining_on_tile") == 5 - GATHER_YIELD


class TestFamishedBuildGate:
    def test_famished_blocks_build(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", 5)
        _pressure(rt)  # no food -> famished
        _allow_tile(rt)
        outcome = rt._execute_action(
            "east_adam", _build_action(), heartbeat_number=2)
        assert outcome == {"status": "rejected", "reason": BUILD_REJECT_FAMISHED}
        assert load_inventory(store)["east_adam"]["stone"] == 5
        assert "wall-001" not in rt._world_state.public_objects

    def test_not_famished_build_unaffected(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", 5)
        add_to_inventory(store, "east_adam", "wild_berries", 2)
        _pressure(rt)  # eats; not famished
        _allow_tile(rt)
        outcome = rt._execute_action(
            "east_adam", _build_action(), heartbeat_number=2)
        assert outcome.get("status") == "success"
        assert load_inventory(store)["east_adam"]["stone"] == 2

    def test_frozen_famished_reason(self):
        assert BUILD_REJECT_FAMISHED == "famished: you cannot build on an empty stomach"

    def test_build_materials_leave_ledgers(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", 6)
        add_to_inventory(store, "east_adam", "wild_berries", 2)
        _pressure(rt)  # eats 1 berry -> food ledger 1
        _allow_tile(rt)
        outcome = rt._execute_action(
            "east_adam", _build_action(materials={"stone": 5}), heartbeat_number=2)
        assert outcome.get("status") == "success"
        led = split_ledgers(load_inventory(store)["east_adam"])
        assert led == {"food": 1, "goods": 1}


# ---------------------------------------------------------------------------
# Placement authority (HB701-743 live-arc regression)
# ---------------------------------------------------------------------------


class TestPlacementAuthority:
    """Build on your own tile is always permitted.

    The old code validated placement against the static runtime-policy
    whitelist, which is never updated as fog exploration grows. A live
    agent that had walked to a discovered tile was refused construction
    on the tile she stood on (26 refused attempts in 43 ticks).
    """

    def test_build_on_own_tile_succeeds_when_policy_is_stale(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        # stale whitelist that excludes the agent's current tile (a live
        # store's runtime_policy.topology after fog exploration grows)
        rt._habitat["allowed_tile_ids"] = ["some-other-tile"]
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        add_to_inventory(store, "east_adam", "stone", 5)
        add_to_inventory(store, "east_adam", "wild_berries", 2)
        _pressure(rt)
        outcome = rt._execute_action(
            "east_adam", _build_action(), heartbeat_number=2)
        assert outcome.get("status") == "success", outcome
        assert rt._world_state.public_objects.get("wall-001") is not None

    def test_build_on_other_tile_still_refused(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        add_to_inventory(store, "east_adam", "stone", 9)
        add_to_inventory(store, "east_adam", "wild_berries", 2)
        _pressure(rt)
        outcome = rt._execute_action(
            "east_adam", _build_action(tile_id="tile-elsewhere"), heartbeat_number=2)
        assert outcome.get("status") == "rejected"
        assert "not" in outcome.get("reason", "") or "Cannot" in outcome.get("reason", "")
        assert load_inventory(store)["east_adam"]["stone"] == 9

    def test_create_public_object_on_own_tile_succeeds_when_policy_is_stale(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._habitat["allowed_tile_ids"] = ["some-other-tile"]
        rt._world_state.tile_occupancy["east_adam"] = "tile-alpha"
        outcome = rt._execute_action("east_adam", {
            "action_type": "create_public_object",
            "object_id": "mark-001",
            "object_type": "mark",
            "description": "A stone I set down here.",
            "tile_id": "tile-alpha",
        }, heartbeat_number=2)
        assert outcome.get("status") == "success", outcome


# ---------------------------------------------------------------------------
# Noncanonical ask sink: a stuck agent must be audible (HB701-743)
# ---------------------------------------------------------------------------


class TestAskSink:
    def _ask(self, qid="q-1", question="Why is build refused?", urgency="high"):
        return {
            "action_type": "ask_human",
            "question_id": qid,
            "question": question,
            "reason_for_asking": "Blocked repeatedly",
            "urgency": urgency,
        }

    def test_ask_persisted_to_noncanonical_sink(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        outcome = rt._execute_action("east_adam", self._ask(), heartbeat_number=2)
        assert outcome.get("status") == "proposed"
        assert outcome.get("sink") == "agent_questions.json"
        records = load_agent_question_proposals(store)
        assert len(records) == 1
        assert records[0]["question_id"] == "q-1"
        assert records[0]["status"] == "unheard"
        assert records[0]["heartbeat"] == 2
        # canonical questions.json is untouched
        from backend.world.first_pair_persistence import load_questions
        assert load_questions(store) == []

    def test_duplicate_ask_rejected_across_processes(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._execute_action("east_adam", self._ask(), heartbeat_number=2)
        # a fresh runtime == a fresh heartbeat process
        rt2 = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt2._load_or_initialize()
        outcome = rt2._execute_action("east_adam", self._ask(), heartbeat_number=3)
        assert outcome.get("status") == "rejected"
        assert "Duplicate" in outcome.get("reason", "")

    def test_sink_failure_never_breaks_the_ask(self, tmp_path, monkeypatch):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)

        def boom(*a, **k):
            raise OSError("sink exploded")

        monkeypatch.setattr(
            "backend.world.first_pair_runtime.append_agent_question_proposal", boom)
        outcome = rt._execute_action("east_adam", self._ask(), heartbeat_number=2)
        assert outcome.get("status") == "proposed"
        assert outcome.get("sink") == "memory-only"

    def test_inbox_shows_unheard_asks(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._execute_action(
            "east_adam",
            self._ask(question="Build refused on my own tile 20 times"),
            heartbeat_number=2)
        report = scan_pair("east", store.root)
        assert report["unheard_asks"]
        assert report["unheard_asks"][0]["heartbeat"] == 2
        text = render_inbox([report])
        assert "UNHEARD ASKS" in text
        assert "Build refused on my own tile" in text

    def test_append_helper_is_append_only(self, tmp_path):
        store = _fresh_store(tmp_path)
        append_agent_question_proposal(store, {"question_id": "a"})
        append_agent_question_proposal(store, {"question_id": "b"})
        assert [r["question_id"] for r in load_agent_question_proposals(store)] == ["a", "b"]


# ---------------------------------------------------------------------------
# Context + prompt projection
# ---------------------------------------------------------------------------


class TestContextAndPrompt:
    def test_observation_carries_pressure_keys(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "wild_berries", 3)
        add_to_inventory(store, "east_adam", "stone", 2)
        _pressure(rt)  # eats 1 berry
        ctx = rt._build_context("east_adam", 2)
        assert ctx.observation["provisions"] == {"food_units": 2, "famished": False}
        assert ctx.observation["carrying"] == {
            "food_used": 2, "food_cap": FOOD_CAP,
            "goods_used": 2, "goods_cap": GOODS_CAP,
        }
        assert ctx.provisions == {"food_units": 2, "famished": False}
        assert ctx.carrying["goods_used"] == 2

    def test_prompt_shows_body_section(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "wild_berries", 3)
        add_to_inventory(store, "east_adam", "stone", 2)
        _pressure(rt)
        ctx = rt._build_context("east_adam", 2)
        prompt = build_system_prompt(ctx)
        assert "YOUR BODY" in prompt
        assert "food 2/20" in prompt
        assert "goods 2/20" in prompt
        assert "famished" not in prompt.split("YOUR BODY")[1].split("---")[0].lower()

    def test_prompt_famished_line_only_when_famished(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "stone", 2)
        _pressure(rt)  # famished
        ctx = rt._build_context("east_adam", 2)
        prompt = build_system_prompt(ctx)
        assert "famished" in prompt.lower()
        assert "cannot build" in prompt.lower()

    def test_pressure_sections_carry_no_map_data(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        add_to_inventory(store, "east_adam", "wild_berries", 2)
        _pressure(rt)
        ctx = rt._build_context("east_adam", 2)
        prompt = build_system_prompt(ctx)
        body = prompt.split("YOUR BODY")[1] if "YOUR BODY" in prompt else ""
        for leak in ("cont_a_", "cont_b_", "mst_", "cont_a_east_000"):
            assert leak not in body

    def test_views_are_plain(self):
        assert provisions_view({"wild_berries": 0}, True) == {
            "food_units": 0, "famished": True}
        assert carrying_view({"wild_berries": 3, "stone": 2}) == {
            "food_used": 3, "food_cap": FOOD_CAP,
            "goods_used": 2, "goods_cap": GOODS_CAP}


# ---------------------------------------------------------------------------
# Loop integrity: rule-change notice, operator channel, request
# reconciliation, reflection-echo suppression
# ---------------------------------------------------------------------------


class TestPhysicsNotice:
    """An agent must be able to notice the world's terms changed."""

    def test_observation_carries_version_and_new_flag(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        ctx = rt._build_context("east_adam", 2)
        assert ctx.physics["version"] == PHYSICS_VERSION
        # _runtime already ran one heartbeat, so the first notice has
        # already fired for this agent: the flag is now False
        assert ctx.physics["new_to_agent"] is False
        assert ctx.observation["physics"]["version"] == PHYSICS_VERSION

    def test_first_ever_exposure_is_flagged(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt._load_or_initialize()
        ctx = rt._build_context("east_adam", 1)
        assert ctx.physics["new_to_agent"] is True

    def test_notice_fires_once_then_clears(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._build_context("east_adam", 2)  # records the version
        ctx = rt._build_context("east_adam", 3)
        assert ctx.physics["new_to_agent"] is False

    def test_prompt_states_terms_and_the_change_once(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt._load_or_initialize()
        prompt = build_system_prompt(rt._build_context("east_adam", 1))
        assert "THE WORLD'S TERMS" in prompt
        assert PHYSICS_VERSION in prompt
        assert "terms have changed" in prompt
        # second heartbeat: the change line is gone
        prompt2 = build_system_prompt(rt._build_context("east_adam", 2))
        assert "THE WORLD'S TERMS" in prompt2
        assert "terms have changed" not in prompt2

    def test_change_notice_fires_again_after_a_version_bump(self, tmp_path, monkeypatch):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._build_context("east_adam", 2)
        monkeypatch.setattr(
            "backend.world.first_pair_runtime.PHYSICS_VERSION", "pressure.99")
        ctx = rt._build_context("east_adam", 3)
        assert ctx.physics["version"] == "pressure.99"
        assert ctx.physics["new_to_agent"] is True

    def test_each_agent_tracked_separately(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt._load_or_initialize()
        rt._build_context("east_adam", 1)  # adam sees it first
        ctx = rt._build_context("east_eve", 1)  # eve has not yet
        assert ctx.physics["new_to_agent"] is True


class TestOperatorChannel:
    def _say(self, store, text, addressed_to="all", author="Sean"):
        return append_operator_message(store, {
            "message_id": "op-1",
            "author": author,
            "addressed_to": addressed_to,
            "text": text,
            "created_at_utc": "2026-09-26T00:00:00+00:00",
        })

    def test_message_reaches_the_addressed_agent(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._say(store, "The stone at the spring is yours.")
        ctx = rt._build_context("east_adam", 2)
        assert len(ctx.operator_messages) == 1
        prompt = build_system_prompt(ctx)
        assert "MESSAGES FROM THE OPERATOR" in prompt
        assert "The stone at the spring is yours." in prompt
        assert "Sean" in prompt
        assert "Nothing obliges you" in prompt

    def test_addressed_message_not_shown_to_others(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._say(store, "Only for you.", addressed_to="east_eve")
        assert rt._build_context("east_adam", 2).operator_messages == []
        assert len(rt._build_context("east_eve", 2).operator_messages) == 1

    def test_broadcast_reaches_both(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._say(store, "I am watching.")
        assert len(rt._build_context("east_adam", 2).operator_messages) == 1
        assert len(rt._build_context("east_eve", 2).operator_messages) == 1

    def test_operator_log_is_append_only(self, tmp_path):
        store = _fresh_store(tmp_path)
        self._say(store, "first")
        self._say(store, "second")
        assert [m["text"] for m in load_operator_messages(store)] == ["first", "second"]

    def test_script_writes_and_reads(self, tmp_path, monkeypatch):
        import scripts.operator_say as opsay
        monkeypatch.setitem(opsay.PAIRS, "east", tmp_path / "store")
        (tmp_path / "store").mkdir()
        message = opsay.say("east", "hello from the operator", author="Sean")
        assert message["message_id"].startswith("op-")
        messages = load_operator_messages(
            FirstPairPersistenceStore(tmp_path / "store"))
        assert messages[-1]["text"] == "hello from the operator"
        assert "hello from the operator" in opsay.history("east")

    def test_exporter_ships_operator_messages(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._say(store, "visible to the show")
        snap = build_pair_snapshot(
            "east", store.root, {"tiles": [], "continents": []})
        assert snap["operator_messages"][-1]["text"] == "visible to the show"


class TestRequestReconciliation:
    def _grant(self, store, capability_id="gather"):
        from backend.world.first_pair_persistence import (
            CapabilityGrantRecord, append_capability_grant)
        append_capability_grant(store, CapabilityGrantRecord(
            grant_id="g-" + capability_id, capability_id=capability_id,
            scope="pair", reason="operator grant", status="granted"))

    def test_pending_requests_for_granted_capability_retired(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._grant(store, "gather")
        rt._world_state.capability_requests = [
            {"capability_id": "gather", "requesting_agent_id": "x", "status": "pending"},
            {"capability_id": "sail", "requesting_agent_id": "x", "status": "pending"},
        ]
        retired = rt._reconcile_capability_requests()
        assert retired == 1
        statuses = {r["capability_id"]: r["status"] for r in rt._world_state.capability_requests}
        assert statuses == {"gather": "granted", "sail": "pending"}

    def test_reconcile_runs_in_the_loop(self, tmp_path):
        store = _fresh_store(tmp_path)
        self._grant(store, "gather")
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()  # first heartbeat: initializes and persists world state
        # put the stale requests on disk, where a fresh process sees them
        ws = json.loads((store.root / "world_state.json").read_text(encoding="utf-8"))["data"]
        ws["capability_requests"] = [
            {"capability_id": "gather", "requesting_agent_id": "x", "status": "pending"},
            {"capability_id": "sail", "requesting_agent_id": "x", "status": "pending"},
        ]
        save_world_state(store, type(rt._world_state)(**ws))
        # a fresh runtime = a fresh heartbeat process; the reconcile must
        # retire the granted request before the tick is persisted
        rt2 = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt2.run()
        saved = json.loads((store.root / "world_state.json").read_text(encoding="utf-8"))["data"]
        statuses = {r["capability_id"]: r["status"] for r in saved["capability_requests"]}
        assert statuses == {"gather": "granted", "sail": "pending"}

    def test_inbox_lists_only_pending_requests(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        self._grant(store, "gather")
        rt._world_state.capability_requests = [
            {"capability_id": "gather", "requesting_agent_id": "x", "status": "pending",
             "heartbeat": 1, "reason": "please"},
            {"capability_id": "sail", "requesting_agent_id": "x", "status": "pending",
             "heartbeat": 2, "reason": "a boat"},
        ]
        save_world_state(store, rt._world_state)
        assert scan_pair("east", store.root)["capability_request_total"] == 2
        rt._reconcile_capability_requests()
        save_world_state(store, rt._world_state)
        report = scan_pair("east", store.root)
        # the granted one is retired: it is no longer an outstanding ask
        assert report["capability_request_total"] == 1
        text = render_inbox([report])
        assert "'sail'" in text
        assert "'gather'" not in text


class TestReflectionEchoSuppression:
    def test_identical_thought_recorded_once(self, tmp_path):
        from backend.world.first_pair_runtime import _reflection_is_echo
        mem = []
        assert _reflection_is_echo(mem, "goods 51/20, food 13/20") is False
        mem.append({"type": "reflection", "content": "goods 51/20, food 13/20"})
        assert _reflection_is_echo(mem, "goods 51/20, food 14/20") is True

    def test_different_thought_recorded(self, tmp_path):
        from backend.world.first_pair_runtime import _reflection_is_echo
        mem = [{"type": "reflection", "content": "I gathered berries"}]
        assert _reflection_is_echo(mem, "the sky changed") is False

    def test_empty_reflection_never_echo(self, tmp_path):
        from backend.world.first_pair_runtime import _reflection_is_echo
        mem = [{"type": "reflection", "content": ""}]
        assert _reflection_is_echo(mem, "") is False

    def test_loop_does_not_grow_memory_with_one_belief(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=4, store=store)
        rt.run()
        mem = json.loads((store.root / "memory.json").read_text(encoding="utf-8"))["data"]
        for ref, entries in mem.items():
            reflections = [m for m in entries if m.get("type") == "reflection"]
            texts = [m.get("content", "") for m in reflections]
            # no two consecutive reflections may normalize to the same thought
            norm = [re.sub(r"\d+", "#", t.strip().lower()) for t in texts]
            for a, b in zip(norm, norm[1:]):
                assert a != b


# ---------------------------------------------------------------------------
# Persistence: heartbeat outcomes (census contract)
# ---------------------------------------------------------------------------


class TestOutcomePersistence:
    def test_heartbeat_records_carry_action_outcomes(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        add_to_inventory(store, "east_adam", "wild_berries", 3)
        rt.run()
        history = load_heartbeat_history(store)
        assert len(history) == 1
        outcomes = history[-1].action_outcomes
        assert isinstance(outcomes, dict)
        assert "east_adam" in outcomes and "east_eve" in outcomes
        assert outcomes["east_adam"].get("status") in (
            "success", "rejected", "blocked", "no_action", "unknown_action")

    def test_old_records_without_outcomes_still_load(self, tmp_path):
        store = _fresh_store(tmp_path)
        from backend.world.first_pair_persistence import (
            HeartbeatRecord, append_heartbeat)
        append_heartbeat(store, HeartbeatRecord(
            heartbeat_number=1, agent_id="both", position="",
            observation={}, action_taken=None))
        history = load_heartbeat_history(store)
        assert history[-1].action_outcomes == {}

    def test_heartbeat_history_grows_append_only(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=2, store=store)
        add_to_inventory(store, "east_adam", "wild_berries", 5)
        rt.run()
        history = load_heartbeat_history(store)
        assert [h.heartbeat_number for h in history] == [1, 2]
        # consumption happened across both ticks: net -2 food
        assert (load_inventory(store)["east_adam"]["wild_berries"]
                == 5 - 2 * FOOD_PER_HEARTBEAT)


# ---------------------------------------------------------------------------
# Exporter: pressure block
# ---------------------------------------------------------------------------


class TestExporterPressure:
    def test_pair_snapshot_has_pressure_block(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        add_to_inventory(store, "east_adam", "wild_berries", 3)
        add_to_inventory(store, "east_adam", "stone", 2)
        rt.run()
        snap = build_pair_snapshot(
            "east", store.root, {"tiles": [], "continents": []})
        assert snap is not None
        pressure = snap["pressure"]["east_adam"]
        assert pressure["carrying"] == {
            "food_used": 3 - FOOD_PER_HEARTBEAT, "food_cap": FOOD_CAP,
            "goods_used": 2, "goods_cap": GOODS_CAP}
        assert pressure["provisions"]["food_units"] == 3 - FOOD_PER_HEARTBEAT
        assert pressure["provisions"]["famished"] is False

    def test_pair_snapshot_pressure_famished_when_no_food(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        add_to_inventory(store, "east_adam", "stone", 2)
        rt.run()
        snap = build_pair_snapshot(
            "east", store.root, {"tiles": [], "continents": []})
        assert snap["pressure"]["east_adam"]["provisions"]["famished"] is True

    def test_heartbeat_feed_exposes_outcome_reason(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = FirstPairRuntime(heartbeat_limit=1, store=store)
        rt.run()
        snap = build_pair_snapshot(
            "east", store.root, {"tiles": [], "continents": []})
        hb = snap["heartbeats"][-1]
        for ref, slim in hb["actions"].items():
            assert "outcome_status" in slim
            assert "outcome_reason" in slim

    def test_pair_snapshot_ships_agent_asks(self, tmp_path):
        store = _fresh_store(tmp_path)
        rt = _runtime(store)
        rt._execute_action("east_adam", {
            "action_type": "ask_human",
            "question_id": "q-show",
            "question": "Why is build refused on my own tile?",
            "reason_for_asking": "Blocked 20 times",
            "urgency": "high",
        }, heartbeat_number=2)
        snap = build_pair_snapshot(
            "east", store.root, {"tiles": [], "continents": []})
        asks = snap["agent_asks"]
        assert len(asks) == 1
        assert asks[0]["question"] == "Why is build refused on my own tile?"
        assert asks[0]["agent"] == "east_adam"
        assert asks[0]["urgency"] == "high"

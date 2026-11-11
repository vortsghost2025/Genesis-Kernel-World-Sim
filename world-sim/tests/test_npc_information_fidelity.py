"""Tests for Phase 10OU: NPC information fidelity.

Specification: docs/phase_10os_npc_information_fidelity_spec.md
A) kinder rejection messages (holdings + tile resources + duplicate facts)
B) operator-answer pinning inside the 4-slot human-context cap
C) honest own-map resource roll-up (observed_resources + prompt line)

All strings here are asserted to carry no banned directive phrasing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import build_system_prompt
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    select_human_context,
)
from backend.world.first_pair_runtime import FirstPairRuntime

BANNED = ["build a", "go to", "you should", "move to", "try building", "head to"]


def _fresh_store(tmp_path: Path) -> FirstPairPersistenceStore:
    return FirstPairPersistenceStore(tmp_path / ".runtime" / "first-pair")


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(heartbeat_limit=1, store=_fresh_store(tmp_path))
    rt.run()
    return rt


# ---------------------------------------------------------------------------
# A. Kinder rejections
# ---------------------------------------------------------------------------

def test_insufficient_materials_names_holdings_summary(tmp_path):
    """245 blind Eve builds happened because the rejection named only the
    shortfall, not what she held. The new reason must carry holdings."""
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "wood", 124)
    add_to_inventory(rt._store, "east_adam", "stone", 5)
    rt._world_state.tile_occupancy["east_adam"] = "public-shared-center"
    res = rt._execute_build(
        "east_adam",
        {
            "object_id": "eve-hut-001",
            "object_type": "shelter",
            "description": "test shelter",
            "tile_id": "public-shared-center",
            "materials": {"timber": 2, "stone": 3},
        },
        1,
    )
    assert res["status"] == "rejected"
    reason = res["reason"]
    assert "Insufficient timber" in reason
    # 10PW: a staged build's first action costs only its foundation stage, so
    # the reason names that stage AND the whole project's requirement. An
    # agent reading "need 1" must not conclude one log raises a house.
    assert "need 1" in reason and "hold 0" in reason
    assert "foundation stage" in reason
    assert "2 for the whole shelter" in reason
    assert "holdings:" in reason
    assert "wood 124" in reason
    assert len(reason) <= 200, f"reason must stay legible: {reason!r}"
    for phrase in BANNED:
        assert phrase not in reason.lower()


def test_gather_rejection_names_tile_resources(tmp_path):
    """'No stone available on this tile' must say what the tile lists."""
    rt = _runtime(tmp_path)
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    rt._current_tile_resources["cont_a_gen_0_0"] = [
        {"kind": "clay", "amount": 3},
        {"kind": "wild_berries", "amount": 2},
    ]
    res = rt._execute_gather("east_adam", {"resource_kind": "stone"}, 1)
    assert res["status"] == "rejected"
    assert "No stone available on this tile" in res["reason"]
    assert "clay" in res["reason"] and "wild_berries" in res["reason"]
    for phrase in BANNED:
        assert phrase not in res["reason"].lower()


def test_gather_rejection_on_empty_tile_says_nothing_gatherable(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    rt._current_tile_resources["cont_a_gen_0_0"] = []
    res = rt._execute_gather("east_adam", {"resource_kind": "stone"}, 1)
    assert res["status"] == "rejected"
    assert "nothing gatherable" in res["reason"]
    for phrase in BANNED:
        assert phrase not in res["reason"].lower()


def test_duplicate_object_id_names_existing_type_and_tile(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.tile_occupancy["east_adam"] = "public-shared-center"
    rt._world_state.public_objects["hut-001"] = {
        "object_id": "hut-001",
        "object_type": "shelter",
        "tile_id": "public-shared-center",
    }
    res = rt._execute_build(
        "east_adam",
        {
            "object_id": "hut-001",
            "object_type": "shelter",
            "description": "test shelter",
            "tile_id": "public-shared-center",
            "materials": {"timber": 2},
        },
        1,
    )
    assert res["status"] == "rejected"
    assert "Duplicate object_id" in res["reason"]
    assert "shelter" in res["reason"] and "public-shared-center" in res["reason"]
    for phrase in BANNED:
        assert phrase not in res["reason"].lower()


# ---------------------------------------------------------------------------
# B. Operator-answer pinning
# ---------------------------------------------------------------------------

def _q(qid, status, hb, text="q", answer="a"):
    return {
        "question_id": qid,
        "status": status,
        "heartbeat": hb,
        "question": text,
        "answer": answer,
        "related_goal_id": None,
    }


def test_most_recent_answered_survives_four_pending_competitors():
    """The stone answer was lost because answered records compete with
    pending ones for 4 slots. The most recent answered must be pinned."""
    answered = [
        _q("old", "answered", 100, "old stone q", "old stone a"),
        _q("new", "answered", 200, "new stone q", "new stone a"),
    ]
    pending = [_q(f"p{i}", "pending", 300 + i, f"q{i}") for i in range(4)]
    selected, ans_ids, pend_ids, omitted = select_human_context(
        answered_questions=answered,
        unresolved_questions=pending,
        active_goal_ids=set(),
    )
    assert len(selected) == 4
    assert "new" in ans_ids, "most recent answered record must be pinned in selection"
    assert omitted == 2  # 6 records, 4 slots
    # deterministic: same input, same output
    selected2, _, _, _ = select_human_context(
        answered_questions=answered,
        unresolved_questions=pending,
        active_goal_ids=set(),
    )
    assert [s["question_id"] for s in selected] == [s["question_id"] for s in selected2]


def test_pin_order_puts_pinned_first():
    answered = [_q("new", "answered", 200)]
    pending = [_q(f"p{i}", "pending", 300 + i) for i in range(3)]
    selected, _, _, _ = select_human_context(
        answered_questions=answered,
        unresolved_questions=pending,
        active_goal_ids=set(),
    )
    assert selected[0]["question_id"] == "new", "pinned answered must lead the selection"


def test_no_answered_records_keeps_old_scoring():
    pending = [_q(f"p{i}", "pending", 300 + i) for i in range(6)]
    selected, ans_ids, pend_ids, omitted = select_human_context(
        answered_questions=[],
        unresolved_questions=pending,
        active_goal_ids=set(),
    )
    assert len(selected) == 4
    assert ans_ids == []
    assert omitted == 2


# ---------------------------------------------------------------------------
# C. Resource roll-up
# ---------------------------------------------------------------------------

def test_rollup_uses_own_known_map_only_and_is_fact(tmp_path):
    """The prompt line must come from the agent's known map, never the
    true map, and must carry no directive."""
    from backend.world.first_pair_runtime import FirstPairRuntime as RT

    km = {
        "agent_id": "genesis-agent-x",
        "known_tiles": {
            "cont_b_gen_50_46": {"tile_id": "cont_b_gen_50_46", "observed_resources": ["clay", "stone", "wild_berries"]},
            "cont_b_gen_33_57": {"tile_id": "cont_b_gen_33_57", "observed_resources": []},
        },
        "known_landmarks": {},
    }
    # helper must exist and read only the known map
    assert hasattr(RT, "_observed_resource_rollup"), "rollup helper missing (10OU-C)"
    line = RT._observed_resource_rollup(km)
    assert "stone" in line and "cont_b_gen_50_46" in line
    assert "cont_b_gen_33_57" not in line, "tiles with no observed resources add noise"
    for phrase in BANNED:
        assert phrase not in line.lower()


def test_rollup_empty_when_no_resources_observed():
    from backend.world.first_pair_runtime import FirstPairRuntime as RT

    km = {"agent_id": "x", "known_tiles": {"t": {"tile_id": "t", "observed_resources": []}}, "known_landmarks": {}}
    assert RT._observed_resource_rollup(km) == ""


def _context_with_rollup(rollup: str) -> AgentContext:
    return AgentContext(
        agent_id="genesis-agent-x",
        canonical_name="Eve",
        canonical_ref="west_eve",
        heartbeat_number=1,
        position="cont_b_gen_33_57",
        observation={"tile_id": "cont_b_gen_33_57", "visible_tiles": [], "objects_here": []},
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=[],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-11-07T00:00:00Z",
        inventory={},
        observed_resource_rollup=rollup,
    )


def test_prompt_renders_rollup_line_and_omits_when_empty():
    prompt = build_system_prompt(_context_with_rollup("stone: cont_b_gen_50_46"))
    assert "Resources observed on visited tiles" in prompt
    assert "cont_b_gen_50_46" in prompt
    prompt_empty = build_system_prompt(_context_with_rollup(""))
    assert "Resources observed on visited tiles" not in prompt_empty


def test_adapter_merge_carries_resources_into_known_map():
    """Root cause: merge_observation hardcoded resources [] when rebuilding
    fog tiles. Now visible details must flow into observed_resources."""
    from backend.world.first_pair_fog_adapter import merge_observation

    km = {
        "schema_version": "known_map.1",
        "agent_id": "genesis-agent-x",
        "known_tiles": {},
        "known_landmarks": {},
        "named_places": {},
        "routes": [],
        "hypotheses": [],
        "myths": [],
        "contact_evidence": [],
        "last_observation_tick": 0,
    }
    obs = {
        "visible_tile_details": [
            {"tile_id": "cont_a_gen_0_0", "terrain": "forest", "biome": "temperate_forest",
             "landmarks": [], "resources": ["stone", "clay"], "hazards": []},
        ]
    }
    updated = merge_observation(km, obs, 7)
    entry = updated["known_tiles"]["cont_a_gen_0_0"]
    assert sorted(entry["observed_resources"]) == ["clay", "stone"]


def test_runtime_merge_helper_unions_visible_resources():
    """The runtime-side merge used before the observation is returned must
    union the same way, so the roll-up sees resources immediately."""
    from backend.world.first_pair_runtime import FirstPairRuntime as RT

    km = {"agent_id": "x", "known_tiles": {}}
    obs = {"visible_tile_details": [{"tile_id": "t1", "resources": ["stone"], "hazards": ["cold"]}]}
    updated, changed = RT._merge_visible_resources_into_known_map(km, obs, 3)
    assert changed is True
    assert updated["known_tiles"]["t1"]["observed_resources"] == ["stone"]
    assert updated["known_tiles"]["t1"]["observed_hazards"] == ["cold"]
    # union, not replace: a second merge with different resources adds
    updated2, changed2 = RT._merge_visible_resources_into_known_map(
        updated, {"visible_tile_details": [{"tile_id": "t1", "resources": ["clay"], "hazards": []}]}, 4
    )
    assert changed2 is True
    assert updated2["known_tiles"]["t1"]["observed_resources"] == ["clay", "stone"]

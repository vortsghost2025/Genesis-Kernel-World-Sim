"""Phase 10RU — the homestead pool stays, but it stops rewriting declarations
and it stops spending a partner who is not there.

A sibling lane added a "homestead pool" so a builder can draw structural
materials from the home rather than only from its own pack. That solves a real
deadlock (west_adam hoarded timber while west_eve tried to build), and the
CONTAINER half of it is kept. Two parts of it are changed here:

  1. it AUTO-FILLED the rung floor into the agent's declared materials whenever
     the model left timber out. That invents an intent the agent never
     expressed and hides an under-declaration, against 10QA's rule that a
     declared materials dict IS the whole cost. The refusal now names the pool
     instead, so the agent re-declares from it itself (the 10QL/10RF/10RH/10RN
     pattern);
  2. it pooled the partner's pack wherever the two agents happened to be, so one
     agent could spend the other's belongings from across the valley with no way
     to know. The partner's stock now counts only when they are standing on the
     build tile or beside it -- and the debit is clamped so it can never drive
     another agent's holdings negative.

The pool itself is now disclosed, so neither agent can be surprised by it.

No provider, no network: tempdir stores only.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_interface import AgentContext  # noqa: E402
from backend.world.first_pair_cognition_model import (  # noqa: E402
    _home_network_description,
    build_system_prompt,
)
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    add_to_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402

HERE = "cont_a_gen_0_0"
FAR = "cont_a_gen_9_9"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store, pair_id="east")
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = HERE
    rt._world_state.tile_occupancy["east_eve"] = HERE
    rt._vitals_for("east_adam")
    rt._vitals_for("east_eve")
    return rt


def _build(rt: FirstPairRuntime, otype: str, materials: dict):
    return rt._execute_action("east_adam", {
        "action_type": "build",
        "object_id": f"{otype}-1",
        "object_type": otype,
        "description": "test",
        "tile_id": HERE,
        "materials": materials,
    }, 200)


def _container(rt: FirstPairRuntime, contents: dict, tile: str = HERE) -> str:
    obj_id = f"cache-{tile}"
    rt._world_state.public_objects[obj_id] = {
        "object_id": obj_id, "object_type": "supply_cache", "tile_id": tile,
        "materials": {}, "contents": dict(contents),
    }
    return obj_id


# --- 1. the declaration is the agent's own ----------------------------------

def test_a_short_declaration_is_refused_and_the_refusal_names_the_pool(tmp_path):
    """The world must not invent the missing timber; it must say where it is."""
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "timber", 12)     # personal stock
    out = _build(rt, "cabin", {"stone": 4})                   # no timber declared
    assert out["status"] == "rejected", out
    reason = out["reason"]
    assert "you declared 0" in reason, reason
    assert "homestead pool holds" in reason, reason
    assert "12 timber" in reason, reason


def test_the_refusal_does_not_claim_the_pool_when_it_cannot_cover_it(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "timber", 1)
    reason = _build(rt, "cabin", {"stone": 4})["reason"]
    assert "homestead pool holds" not in reason, reason


def test_declaring_the_floor_succeeds_by_drawing_on_a_container(tmp_path):
    """The useful half: the home's stored materials fund the build.

    A staged build spends only its FIRST stage's share up front (10PW), so the
    container drops rather than emptying.
    """
    rt = _runtime(tmp_path)
    _container(rt, {"timber": 8, "stone": 8})
    out = _build(rt, "cabin", {"timber": 3, "stone": 4})
    assert out["status"] == "success", out
    stored = rt._world_state.public_objects[f"cache-{HERE}"]["contents"]
    assert stored.get("timber", 0) < 8, stored
    assert stored.get("stone", 0) < 8, stored
    assert rt._get_agent_inventory("east_adam").get("timber", 0) == 0, (
        "with nothing personal, the container must have paid")


# --- 2. the partner counts only when they are there -------------------------

def test_a_partner_at_the_build_site_can_fund_it(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_eve", "timber", 9)
    add_to_inventory(rt._store, "east_eve", "stone", 9)
    rt._world_state.tile_occupancy["east_eve"] = "cont_a_gen_1_0"   # adjacent
    out = _build(rt, "cabin", {"timber": 3, "stone": 4})
    assert out["status"] == "success", out
    assert rt._get_agent_inventory("east_eve").get("timber") < 9, (
        "the partner's stock should have paid the timber")
    assert rt._get_agent_inventory("east_eve").get("stone") < 9, (
        "and the stone")


def test_a_partner_across_the_valley_cannot(tmp_path):
    """The defect this gate removes: spending an absent partner's belongings."""
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_eve", "timber", 90)
    rt._world_state.tile_occupancy["east_eve"] = FAR
    out = _build(rt, "cabin", {"timber": 3, "stone": 4})
    assert out["status"] == "rejected", out
    assert rt._get_agent_inventory("east_eve").get("timber") == 90, (
        "an absent partner's stock must be untouched")


def test_pooling_never_drives_a_partner_negative(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_eve", "timber", 1)      # beside the build
    rt._world_state.tile_occupancy["east_eve"] = HERE
    _build(rt, "cabin", {"timber": 3, "stone": 4})
    held = rt._get_agent_inventory("east_eve").get("timber", 0)
    assert held >= 0, f"partner inventory went negative: {held}"


# --- 3. and it is disclosed -------------------------------------------------

def test_the_home_disclosure_names_the_pool():
    text = _home_network_description()
    assert "HOMESTEAD POOL" in text
    assert "container on the build tile" in text
    assert "beside it" in text


def test_the_pool_is_reachable_from_the_prompt():
    ctx = AgentContext(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position=HERE,
        observation={"self_body": {"downed": False, "vitality": 100.0,
                                   "thirst": 10.0, "hunger": 10.0,
                                   "warmth": 100.0, "wetness": 0.0}},
        memory=[], goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
    )
    assert "HOMESTEAD POOL" in build_system_prompt(ctx)

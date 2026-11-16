"""Phase 10RN — refusals name the ROUTE, and food gets a distance.

The third instance of one pattern, measured 2026-11-14 on the live east lane:

    hb 13719/13721/13722  east_adam: eat edible_roots
      -> "You hold no edible_roots to eat"
    hb 13719/13722        east_eve: drink at operator-provision-hb13608-...
      -> "operator-provision-hb13608-fresh_water-2 holds no fresh_water"

Both refusals were TRUE and both said nothing about the way forward: `nuts` sat
on a tile one tile away that Adam had already observed, and Eve was carrying 148
fresh_water of her own. Adam retried three times; Eve twice.

So food gets what water (10QM) and shelter (10RL) already had -- a distance --
and the two refusals now name the route:

  * `eat` with none of that kind: says what food the body DOES hold, and the
    nearest food it has observed with its distance (or says plainly that it has
    observed none);
  * `drink` aimed at an empty vessel: says how much fresh_water the body is
    carrying and that `source carried` works, or names the nearest drinkable
    tile if it holds none.

Edibility is `survival.EAT_SATISFACTION`'s own key set, so the fact cannot drift
from what eating accepts. No provider, no network: tempdir stores only.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_interface import AgentContext  # noqa: E402
from backend.world.first_pair_cognition_model import build_system_prompt  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    add_to_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402

HERE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store, pair_id="east")
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = HERE
    rt._vitals_for("east_adam")
    return rt


def _know(rt: FirstPairRuntime, tiles: dict[str, list[str]],
          agent: str = "east_adam") -> None:
    """A valid known map: tile id -> the resources observed there."""
    from backend.world.first_pair_fog_adapter import persist_known_map

    known = {"schema_version": "7B.1", "agent_id": agent,
             "contact_evidence": [], "hypotheses": [], "myths": [],
             "known_landmarks": {}, "named_places": {}, "routes": [],
             "last_observation_tick": 1,
             "known_tiles": {
                 t: {"tile_id": t, "observed_resources": res,
                     "first_observed_tick": 1, "last_observed_tick": 1,
                     "visit_count": 0, "confidence": 1.0,
                     "observed_terrain": "grassland",
                     "observed_biome": "temperate_valley",
                     "observed_hazards": [], "agent_given_name": None,
                     "notes": []}
                 for t, res in tiles.items()}}
    persist_known_map(rt._store.root, agent, known)


def _vessel(rt: FirstPairRuntime, contents) -> str:
    obj_id = "supply_cache-1"
    rt._world_state.public_objects[obj_id] = {
        "object_id": obj_id, "object_type": "supply_cache", "tile_id": HERE,
        "materials": {}, "contents": dict(contents),
    }
    return obj_id


def _act(rt: FirstPairRuntime, action: dict):
    return rt._execute_action("east_adam", action, 200)


# --- the food distance ------------------------------------------------------

def test_the_nearest_known_food_is_measured_from_their_own_memory(tmp_path):
    rt = _runtime(tmp_path)
    _know(rt, {"cont_a_gen_1_0": ["nuts"], "cont_a_gen_4_0": ["wild_berries"]})
    got = rt._nearest_known_food_for("east_adam")
    assert got["tile_id"] == "cont_a_gen_1_0"
    assert got["distance"] == 1
    assert got["kinds"] == ["nuts"]


def test_only_what_eating_accepts_counts_as_food(tmp_path):
    """Edibility is EAT_SATISFACTION's own key set, not an invented list."""
    rt = _runtime(tmp_path)
    _know(rt, {"cont_a_gen_1_0": ["stone", "clay", "wood"]})
    assert rt._nearest_known_food_for("east_adam") == {}


def test_an_unobserved_food_tile_is_not_offered(tmp_path):
    rt = _runtime(tmp_path)
    assert rt._nearest_known_food_for("east_adam") == {}
    _know(rt, {"cont_a_gen_2_0": ["mushrooms"]})
    assert rt._nearest_known_food_for("east_adam")["tile_id"] == "cont_a_gen_2_0"


def test_the_other_continent_is_not_one_tile_away(tmp_path):
    rt = _runtime(tmp_path)
    _know(rt, {"cont_b_gen_1_0": ["nuts"]})
    assert rt._nearest_known_food_for("east_adam") == {}


# --- the eat refusal names the route ---------------------------------------

def test_eating_what_you_do_not_hold_names_the_nearest_food_and_distance(tmp_path):
    """The exact live case: nuts one tile away, refusal said only 'you hold none'."""
    rt = _runtime(tmp_path)
    _know(rt, {"cont_a_gen_1_0": ["nuts"]})
    out = _act(rt, {"action_type": "eat", "resource_kind": "edible_roots"})
    assert out["status"] == "rejected"
    reason = out["reason"]
    assert "You hold no edible_roots to eat" in reason
    assert "nuts" in reason and "cont_a_gen_1_0" in reason, reason
    assert "1 tile east" in reason, reason


def test_the_eat_refusal_names_food_the_body_does_hold(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "wild_berries", 6)
    _know(rt, {"cont_a_gen_1_0": ["nuts"]})
    reason = _act(rt, {"action_type": "eat",
                       "resource_kind": "edible_roots"})["reason"]
    assert "You are carrying wild_berries x6" in reason, reason


def test_eating_what_you_do_not_hold_names_the_gather_route(tmp_path):
    """The 2026-11-15 gap: hours at hunger 100, told where food was, never told
    that `gather` is the action that takes it -- and that a downed body cannot."""
    rt = _runtime(tmp_path)
    _know(rt, {"cont_a_gen_1_0": ["nuts"]})
    reason = _act(rt, {"action_type": "eat",
                       "resource_kind": "edible_roots"})["reason"]
    assert "gather" in reason, reason
    assert "no tool and no grant" in reason, reason
    assert "collapsed body cannot gather" in reason, reason


def test_the_eat_refusal_says_so_when_no_food_has_ever_been_seen(tmp_path):
    rt = _runtime(tmp_path)
    reason = _act(rt, {"action_type": "eat",
                       "resource_kind": "edible_roots"})["reason"]
    assert "not observed any food" in reason, reason


def test_eating_food_you_hold_still_works(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "edible_roots", 2)
    assert _act(rt, {"action_type": "eat",
                     "resource_kind": "edible_roots"})["status"] == "success"


# --- the drink refusal names the carried water ------------------------------

def test_drinking_from_an_empty_vessel_names_your_own_water(tmp_path):
    """The exact live case: an empty object, while carrying 148 fresh_water."""
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "fresh_water", 148)
    obj_id = _vessel(rt, {})
    out = _act(rt, {"action_type": "drink", "source": "target",
                    "target_object_id": obj_id, "reason": "satisfy thirst"})
    assert out["status"] == "rejected"
    reason = out["reason"]
    assert "holds no fresh_water" in reason
    assert "fresh_water x148" in reason, reason
    assert "source carried" in reason, reason


def test_drinking_from_an_empty_vessel_with_none_carried_names_the_nearest_water(tmp_path):
    rt = _runtime(tmp_path)
    _know(rt, {"cont_a_gen_3_0": ["fresh_water"]})
    obj_id = _vessel(rt, {})
    reason = _act(rt, {"action_type": "drink", "source": "target",
                       "target_object_id": obj_id})["reason"]
    assert "You hold no water" in reason, reason
    assert "cont_a_gen_3_0" in reason and "3 tiles east" in reason, reason


def test_drinking_from_a_filled_vessel_still_works(tmp_path):
    rt = _runtime(tmp_path)
    obj_id = _vessel(rt, {"fresh_water": 4})
    assert _act(rt, {"action_type": "drink", "source": "target",
                     "target_object_id": obj_id})["status"] == "success"


# --- and the prompt carries the food distance -------------------------------

def _ctx(downed: bool, food: dict) -> AgentContext:
    return AgentContext(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position=HERE,
        observation={"self_body": {"downed": downed, "vitality": 5.0,
                                   "thirst": 10.0, "hunger": 70.0,
                                   "warmth": 25.0, "wetness": 72.0}},
        memory=[], goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
        nearest_known_food=food,
    )


def test_the_hungry_prompt_names_the_nearest_food_with_a_distance():
    prompt = build_system_prompt(_ctx(False, {
        "tile_id": "cont_a_gen_1_0", "distance": 1, "kinds": ["nuts"]}))
    assert "the nearest food you have observed is nuts on cont_a_gen_1_0, " \
           "1 tile east" in prompt


def test_the_collapsed_prompt_names_the_food_distance_too():
    prompt = build_system_prompt(_ctx(True, {
        "tile_id": "cont_a_gen_-44_5", "distance": 1, "kinds": ["nuts"]}))
    assert "the nearest food you have observed is" in prompt
    assert "collapsed body can crawl one tile per heartbeat" in prompt


def test_it_invents_no_food_when_none_has_been_observed():
    prompt = build_system_prompt(_ctx(False, {}))
    assert "the nearest food you have observed" not in prompt

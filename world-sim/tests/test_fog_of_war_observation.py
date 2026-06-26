import copy
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import (
    add_agent_place_name,
    build_local_observation,
    create_empty_known_map,
    get_visible_tile_ids,
    merge_observation_into_known_map,
    project_legacy_map_state,
)


FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "fog_of_war"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_observation_returns_local_tiles_only_and_hides_full_map():
    true_map = load_fixture("sample_true_map.json")
    position = load_fixture("sample_position_east_adam.json")
    known_map = create_empty_known_map("east_adam")

    visible = get_visible_tile_ids(true_map, position, radius=1)
    observation = build_local_observation(true_map, position, known_map, conditions={"radius": 1})

    assert visible == ["cont_a_origin_000", "cont_a_origin_001"]
    assert {tile["tile_id"] for tile in observation["visible_tiles"]} == set(visible)
    assert "cont_a_far_999" not in visible
    assert "cont_b_origin_000" not in visible
    assert "tiles" not in observation
    assert "continents" not in observation
    assert observation["agent_id"] == "east_adam"


def test_known_map_merge_adds_observed_tiles_only():
    true_map = load_fixture("sample_true_map.json")
    position = load_fixture("sample_position_east_adam.json")
    known_map = create_empty_known_map("east_adam")
    observation = build_local_observation(true_map, position, known_map, conditions={"radius": 1})

    updated = merge_observation_into_known_map(known_map, observation, tick=7)

    assert set(updated["known_tiles"]) == {"cont_a_origin_000", "cont_a_origin_001"}
    assert "cont_a_far_999" not in updated["known_tiles"]
    assert updated["last_observation_tick"] == 7
    assert updated["known_tiles"]["cont_a_origin_000"]["first_observed_tick"] == 7


def test_agent_naming_preserves_true_ids_and_allows_different_names():
    adam_map = create_empty_known_map("east_adam")
    eve_map = create_empty_known_map("east_eve")

    add_agent_place_name(adam_map, "lm_cont_a_river_001", "Silver Thread", 4, "bright at dawn")
    add_agent_place_name(eve_map, "lm_cont_a_river_001", "River of First Light", 5, "seen from afar")

    assert adam_map["named_places"]["lm_cont_a_river_001"]["agent_given_name"] == "Silver Thread"
    assert eve_map["named_places"]["lm_cont_a_river_001"]["agent_given_name"] == "River of First Light"
    assert "lm_cont_a_river_001" in adam_map["named_places"]
    assert "lm_cont_a_river_001" in eve_map["named_places"]


def test_legacy_projection_does_not_mutate_inputs():
    true_map = load_fixture("sample_true_map.json")
    known_map = create_empty_known_map("east_adam")
    before_true = copy.deepcopy(true_map)
    before_known = copy.deepcopy(known_map)

    projected = project_legacy_map_state(true_map, {"east_adam": known_map})

    assert projected["entities"]
    assert true_map == before_true
    assert known_map == before_known

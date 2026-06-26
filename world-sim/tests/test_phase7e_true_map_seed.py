import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import (
    build_local_observation,
    create_active_position,
    create_empty_known_map,
    get_visible_tile_ids,
    validate_true_map,
)


FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "fog_of_war"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_seed_validates():
    seed = load_fixture("phase7e_true_map_seed_v1.json")
    assert validate_true_map(seed)["ok"] is True


def test_adam_and_eve_start_continents_separate():
    adam = create_active_position(
        "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0},
    )
    eve = create_active_position(
        "east_eve", "cont_b", "cont_b_dawn_isle", "cont_b_origin_000", {"x": 50, "y": 50},
    )
    assert adam["continent_id"] != eve["continent_id"]
    assert adam["continent_id"] == "cont_a"
    assert eve["continent_id"] == "cont_b"


def test_adam_observation_does_not_leak_eve_continent():
    seed = load_fixture("phase7e_true_map_seed_v1.json")
    adam_pos = create_active_position(
        "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0},
    )
    visible = get_visible_tile_ids(seed, adam_pos, radius=1)
    for tile_id in visible:
        tile = next(t for t in seed["tiles"] if t["tile_id"] == tile_id)
        assert tile["continent_id"] == "cont_a", f"{tile_id} leaks cont_b"
    assert "cont_b_origin_000" not in visible


def test_eve_observation_does_not_leak_adam_continent():
    seed = load_fixture("phase7e_true_map_seed_v1.json")
    eve_pos = create_active_position(
        "east_eve", "cont_b", "cont_b_dawn_isle", "cont_b_origin_000", {"x": 50, "y": 50},
    )
    visible = get_visible_tile_ids(seed, eve_pos, radius=1)
    for tile_id in visible:
        tile = next(t for t in seed["tiles"] if t["tile_id"] == tile_id)
        assert tile["continent_id"] == "cont_b", f"{tile_id} leaks cont_a"
    assert "cont_a_origin_000" not in visible


def test_local_observation_does_not_expose_full_map_keys():
    seed = load_fixture("phase7e_true_map_seed_v1.json")
    adam_pos = create_active_position(
        "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0},
    )
    known = create_empty_known_map("east_adam")
    observation = build_local_observation(seed, adam_pos, known, conditions={"radius": 1})
    assert "tiles" not in observation
    assert "continents" not in observation
    assert "regions" not in observation
    assert "travel_edges" not in observation
    assert "mysteries" not in observation
    assert "visible_tile_ids" in observation
    assert "visible_tiles" in observation


def test_seed_contains_required_elements():
    seed = load_fixture("phase7e_true_map_seed_v1.json")
    hazards = set()
    for tile in seed["tiles"]:
        hazards.update(tile.get("hazards", []))
    assert len(hazards) >= 1, "at least one hazard required"
    assert seed["mysteries"], "at least one mystery required"
    assert seed["landmarks"], "at least one landmark required"
    tile_resources = set()
    for tile in seed["tiles"]:
        tile_resources.update(tile.get("resources", []))
    assert len(tile_resources) >= 1, "at least one resource required"
    assert seed["travel_edges"], "at least one travel edge required"


def test_travel_edges_connect_existing_tiles_and_do_not_cross_continents():
    seed = load_fixture("phase7e_true_map_seed_v1.json")
    tile_ids = {t["tile_id"] for t in seed["tiles"]}
    tile_continent = {t["tile_id"]: t["continent_id"] for t in seed["tiles"]}
    for edge in seed["travel_edges"]:
        assert edge["from_tile_id"] in tile_ids, f"edge from unknown tile: {edge['from_tile_id']}"
        assert edge["to_tile_id"] in tile_ids, f"edge to unknown tile: {edge['to_tile_id']}"
        assert tile_continent[edge["from_tile_id"]] == tile_continent[edge["to_tile_id"]], (
            f"edge crosses continents: {edge['from_tile_id']} -> {edge['to_tile_id']}"
        )


def test_no_agent_data_in_true_map():
    seed = load_fixture("phase7e_true_map_seed_v1.json")
    assert "agent_id" not in seed
    assert "contact_evidence" not in seed
    assert "known_tiles" not in seed
    assert "known_landmarks" not in seed
    assert "named_places" not in seed
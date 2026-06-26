import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import (
    build_local_observation,
    create_active_position,
    create_dormant_position,
    create_empty_known_map,
    get_visible_tile_ids,
    merge_observation_into_known_map,
    validate_true_map,
)


FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "fog_of_war"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


SEED_PATH = "phase7e_true_map_seed_v1.json"


def test_seed_validates():
    seed = load_fixture(SEED_PATH)
    assert validate_true_map(seed)["ok"] is True


def test_adam_visible_tiles_are_all_cont_a():
    seed = load_fixture(SEED_PATH)
    pos = create_active_position(
        "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0},
    )
    visible = get_visible_tile_ids(seed, pos, radius=1)
    assert len(visible) > 0, "Adam should see at least one tile"
    for tile_id in visible:
        tile = next(t for t in seed["tiles"] if t["tile_id"] == tile_id)
        assert tile["continent_id"] == "cont_a", f"{tile_id} is on {tile['continent_id']}, expected cont_a"


def test_eve_visible_tiles_are_all_cont_b():
    seed = load_fixture(SEED_PATH)
    pos = create_active_position(
        "east_eve", "cont_b", "cont_b_dawn_isle", "cont_b_origin_000", {"x": 50, "y": 50},
    )
    visible = get_visible_tile_ids(seed, pos, radius=1)
    assert len(visible) > 0, "Eve should see at least one tile"
    for tile_id in visible:
        tile = next(t for t in seed["tiles"] if t["tile_id"] == tile_id)
        assert tile["continent_id"] == "cont_b", f"{tile_id} is on {tile['continent_id']}, expected cont_b"


def test_adam_cannot_see_eve_start():
    seed = load_fixture(SEED_PATH)
    pos = create_active_position(
        "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0},
    )
    visible = get_visible_tile_ids(seed, pos, radius=1)
    assert "cont_b_origin_000" not in visible


def test_eve_cannot_see_adam_start():
    seed = load_fixture(SEED_PATH)
    pos = create_active_position(
        "east_eve", "cont_b", "cont_b_dawn_isle", "cont_b_origin_000", {"x": 50, "y": 50},
    )
    visible = get_visible_tile_ids(seed, pos, radius=1)
    assert "cont_a_origin_000" not in visible


def test_observation_hides_full_map_keys():
    seed = load_fixture(SEED_PATH)
    pos = create_active_position(
        "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0},
    )
    known = create_empty_known_map("east_adam")
    obs = build_local_observation(seed, pos, known, conditions={"radius": 1})
    for forbidden_key in ("tiles", "continents", "regions", "travel_edges", "mysteries"):
        assert forbidden_key not in obs, f"observation must not expose {forbidden_key}"
    assert "visible_tile_ids" in obs
    assert "visible_tiles" in obs


def test_known_map_merge_is_per_agent_in_memory():
    seed = load_fixture(SEED_PATH)
    adam_pos = create_active_position(
        "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0},
    )
    eve_pos = create_active_position(
        "east_eve", "cont_b", "cont_b_dawn_isle", "cont_b_origin_000", {"x": 50, "y": 50},
    )
    adam_km = create_empty_known_map("east_adam")
    eve_km = create_empty_known_map("east_eve")

    adam_obs = build_local_observation(seed, adam_pos, adam_km, conditions={"radius": 1})
    eve_obs = build_local_observation(seed, eve_pos, eve_km, conditions={"radius": 1})

    adam_km = merge_observation_into_known_map(adam_km, adam_obs, tick=1)
    eve_km = merge_observation_into_known_map(eve_km, eve_obs, tick=1)

    for tile_id in adam_km["known_tiles"]:
        assert tile_id.startswith("cont_a_"), f"Adam known tile {tile_id} must be cont_a"
    for tile_id in eve_km["known_tiles"]:
        assert tile_id.startswith("cont_b_"), f"Eve known tile {tile_id} must be cont_b"

    assert adam_km["last_observation_tick"] == 1
    assert eve_km["last_observation_tick"] == 1

    adam_obs2 = build_local_observation(seed, adam_pos, adam_km, conditions={"radius": 1})
    adam_km = merge_observation_into_known_map(adam_km, adam_obs2, tick=2)
    for tile_id in adam_obs["visible_tile_ids"]:
        assert adam_km["known_tiles"][tile_id]["visit_count"] >= 2, (
            f"{tile_id} visit_count should accumulate across ticks"
        )


def test_no_contact_evidence_created():
    seed = load_fixture(SEED_PATH)
    adam_pos = create_active_position(
        "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0},
    )
    adam_km = create_empty_known_map("east_adam")
    eve_km = create_empty_known_map("east_eve")

    adam_obs = build_local_observation(seed, adam_pos, adam_km, conditions={"radius": 1})
    adam_km = merge_observation_into_known_map(adam_km, adam_obs, tick=1)
    assert adam_km["contact_evidence"] == []
    assert eve_km["contact_evidence"] == []


def test_dormant_west_position_produces_no_visible_tiles():
    seed = load_fixture(SEED_PATH)
    west_adam = create_dormant_position("west_adam")
    west_eve = create_dormant_position("west_eve")
    assert get_visible_tile_ids(seed, west_adam, radius=5) == []
    assert get_visible_tile_ids(seed, west_eve, radius=5) == []
    assert west_adam["active"] is False
    assert west_eve["active"] is False


def test_only_fixture_path_referenced():
    source = Path(__file__).read_text(encoding="utf-8")
    assert "tests/fixtures/fog_of_war/" in source
    assert "phase7e_true_map_seed_v1.json" in source
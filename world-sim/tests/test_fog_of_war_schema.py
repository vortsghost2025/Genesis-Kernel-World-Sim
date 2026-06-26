import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import (
    create_active_position,
    create_dormant_position,
    create_empty_known_map,
    validate_known_map,
    validate_true_map,
    validate_world_position,
)


FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "fog_of_war"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_true_map_and_known_map_validate():
    true_map = load_fixture("sample_true_map.json")
    known_map = load_fixture("sample_known_map_east_adam.json")

    assert validate_true_map(true_map)["ok"] is True
    assert validate_known_map(known_map)["ok"] is True


def test_positions_validate_and_adam_eve_start_on_separate_continents():
    adam = load_fixture("sample_position_east_adam.json")
    eve = load_fixture("sample_position_east_eve.json")

    assert validate_world_position(adam)["ok"] is True
    assert validate_world_position(eve)["ok"] is True
    assert adam["continent_id"] != eve["continent_id"]
    assert adam["agent_id"] == "east_adam"
    assert eve["agent_id"] == "east_eve"


def test_factory_helpers_create_valid_active_and_dormant_positions():
    known = create_empty_known_map("east_adam")
    active = create_active_position(
        "east_adam",
        "cont_a",
        "cont_a_origin_valley",
        "cont_a_origin_000",
        {"x": 0, "y": 0},
    )
    west_adam = create_dormant_position("west_adam")
    west_eve = create_dormant_position("west_eve")

    assert validate_known_map(known)["ok"] is True
    assert validate_world_position(active)["ok"] is True
    assert validate_world_position(west_adam)["ok"] is True
    assert validate_world_position(west_eve)["ok"] is True
    assert west_adam["active"] is False
    assert west_eve["active"] is False


def test_schema_template_files_exist_for_future_data_generation():
    schema_dir = PROJECT_ROOT / "schemas" / "fog_of_war"
    expected = {
        "true_map.schema.json",
        "known_map.schema.json",
        "world_position.schema.json",
        "observation.schema.json",
    }
    assert expected == {path.name for path in schema_dir.glob("*.schema.json")}

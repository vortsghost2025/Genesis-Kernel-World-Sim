import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import (
    add_contact_evidence,
    add_hypothesis,
    contact_level,
    create_empty_known_map,
    validate_known_map,
)


def test_contact_remains_locked_at_levels_zero_through_two():
    known_map = create_empty_known_map("east_adam")
    assert contact_level(known_map)["level"] == 0
    assert contact_level(known_map)["unlocked"] is False

    add_contact_evidence(known_map, {"evidence_id": "ev1", "level": 1, "type": "smoke", "reveals_agent": False})
    assert contact_level(known_map)["level"] == 1
    assert contact_level(known_map)["unlocked"] is False

    add_contact_evidence(known_map, {"evidence_id": "ev2", "level": 2, "type": "footprints", "reveals_agent": False})
    assert contact_level(known_map)["level"] == 2
    assert contact_level(known_map)["unlocked"] is False


def test_contact_unlocks_at_level_four_or_level_three_with_investigation():
    level_three = create_empty_known_map("east_eve")
    add_contact_evidence(level_three, {"evidence_id": "ev3", "level": 3, "type": "carved_marker", "reveals_agent": False})
    assert contact_level(level_three)["unlocked"] is False
    assert contact_level(level_three, explicit_investigation=True)["unlocked"] is True

    level_four = create_empty_known_map("east_eve")
    add_contact_evidence(level_four, {"evidence_id": "ev4", "level": 4, "type": "direct_sighting", "reveals_agent": True})
    assert contact_level(level_four)["level"] == 4
    assert contact_level(level_four)["unlocked"] is True


def test_hypotheses_and_contact_evidence_validate_as_known_map_content():
    known_map = create_empty_known_map("east_adam")
    add_hypothesis(known_map, "The river may continue north.", "Water sound heard northward.", 0.35, 3)
    add_contact_evidence(known_map, {"evidence_id": "ev5", "level": 1, "type": "unknown_tracks", "reveals_agent": False})

    assert known_map["hypotheses"][0]["status"] == "unverified"
    assert validate_known_map(known_map)["ok"] is True

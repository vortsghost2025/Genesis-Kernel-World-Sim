import json
import tempfile
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import (
    build_canonical_observation,
    build_local_observation,
    create_active_position,
    create_empty_known_map,
    validate_true_map,
)


FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "fog_of_war"
SEED_PATH = FIXTURES / "phase7e_true_map_seed_v1.json"


def load_seed():
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def test_seed_validates():
    seed = load_seed()
    assert validate_true_map(seed)["ok"] is True


def test_adam_canonical_observation_sees_cont_a_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        root.mkdir(parents=True, exist_ok=True)

        (root / "world").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_eve").mkdir(parents=True, exist_ok=True)

        seed = load_seed()
        (root / "world" / "true_map.json").write_text(json.dumps(seed), encoding="utf-8")

        adam_pos = create_active_position(
            "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0}
        )
        (root / "agents" / "east_adam" / "world_position.json").write_text(
            json.dumps(adam_pos), encoding="utf-8"
        )
        adam_km = create_empty_known_map("east_adam")
        (root / "agents" / "east_adam" / "known_map.json").write_text(
            json.dumps(adam_km), encoding="utf-8"
        )

        eve_pos = create_active_position(
            "east_eve", "cont_b", "cont_b_dawn_isle", "cont_b_origin_000", {"x": 50, "y": 50}
        )
        (root / "agents" / "east_eve" / "world_position.json").write_text(
            json.dumps(eve_pos), encoding="utf-8"
        )
        eve_km = create_empty_known_map("east_eve")
        (root / "agents" / "east_eve" / "known_map.json").write_text(
            json.dumps(eve_km), encoding="utf-8"
        )

        obs = build_canonical_observation("east_adam", root, {"radius": 1})

        assert "visible_tile_ids" in obs
        assert len(obs["visible_tile_ids"]) > 0
        for tile_id in obs["visible_tile_ids"]:
            assert tile_id.startswith("cont_a_"), f"Adam sees {tile_id} which is not cont_a"


def test_eve_canonical_observation_sees_cont_b_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        root.mkdir(parents=True, exist_ok=True)

        (root / "world").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_eve").mkdir(parents=True, exist_ok=True)

        seed = load_seed()
        (root / "world" / "true_map.json").write_text(json.dumps(seed), encoding="utf-8")

        eve_pos = create_active_position(
            "east_eve", "cont_b", "cont_b_dawn_isle", "cont_b_origin_000", {"x": 50, "y": 50}
        )
        (root / "agents" / "east_eve" / "world_position.json").write_text(
            json.dumps(eve_pos), encoding="utf-8"
        )
        eve_km = create_empty_known_map("east_eve")
        (root / "agents" / "east_eve" / "known_map.json").write_text(
            json.dumps(eve_km), encoding="utf-8"
        )

        obs = build_canonical_observation("east_eve", root, {"radius": 1})

        assert "visible_tile_ids" in obs
        assert len(obs["visible_tile_ids"]) > 0
        for tile_id in obs["visible_tile_ids"]:
            assert tile_id.startswith("cont_b_"), f"Eve sees {tile_id} which is not cont_b"


def test_adam_cannot_see_eve_start():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "world").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam").mkdir(parents=True, exist_ok=True)

        seed = load_seed()
        (root / "world" / "true_map.json").write_text(json.dumps(seed), encoding="utf-8")

        adam_pos = create_active_position(
            "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0}
        )
        (root / "agents" / "east_adam" / "world_position.json").write_text(
            json.dumps(adam_pos), encoding="utf-8"
        )
        (root / "agents" / "east_adam" / "known_map.json").write_text(
            json.dumps(create_empty_known_map("east_adam")), encoding="utf-8"
        )

        obs = build_canonical_observation("east_adam", root, {"radius": 1})
        assert "cont_b_origin_000" not in obs["visible_tile_ids"]


def test_eve_cannot_see_adam_start():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "world").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_eve").mkdir(parents=True, exist_ok=True)

        seed = load_seed()
        (root / "world" / "true_map.json").write_text(json.dumps(seed), encoding="utf-8")

        eve_pos = create_active_position(
            "east_eve", "cont_b", "cont_b_dawn_isle", "cont_b_origin_000", {"x": 50, "y": 50}
        )
        (root / "world" / "true_map.json").write_text(json.dumps(seed), encoding="utf-8")
        (root / "agents" / "east_eve" / "world_position.json").write_text(
            json.dumps(eve_pos), encoding="utf-8"
        )
        (root / "agents" / "east_eve" / "known_map.json").write_text(
            json.dumps(create_empty_known_map("east_eve")), encoding="utf-8"
        )

        obs = build_canonical_observation("east_eve", root, {"radius": 1})
        assert "cont_a_origin_000" not in obs["visible_tile_ids"]


def test_observation_does_not_leak_full_true_map():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "world").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam").mkdir(parents=True, exist_ok=True)

        seed = load_seed()
        (root / "world" / "true_map.json").write_text(json.dumps(seed), encoding="utf-8")

        adam_pos = create_active_position(
            "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0}
        )
        (root / "agents" / "east_adam" / "world_position.json").write_text(
            json.dumps(adam_pos), encoding="utf-8"
        )
        (root / "agents" / "east_adam" / "known_map.json").write_text(
            json.dumps(create_empty_known_map("east_adam")), encoding="utf-8"
        )

        obs = build_canonical_observation("east_adam", root, {"radius": 1})

        for forbidden_key in ("tiles", "continents", "regions", "travel_edges", "mysteries"):
            assert forbidden_key not in obs, f"observation leaked {forbidden_key}"


def test_missing_true_map_fails_closed():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "agents" / "east_adam").mkdir(parents=True, exist_ok=True)

        adam_pos = create_active_position(
            "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0}
        )
        (root / "agents" / "east_adam" / "world_position.json").write_text(
            json.dumps(adam_pos), encoding="utf-8"
        )
        (root / "agents" / "east_adam" / "known_map.json").write_text(
            json.dumps(create_empty_known_map("east_adam")), encoding="utf-8"
        )

        try:
            build_canonical_observation("east_adam", root)
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError as e:
            assert "true_map" in str(e)


def test_missing_position_fails_closed():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "world").mkdir(parents=True, exist_ok=True)

        seed = load_seed()
        (root / "world" / "true_map.json").write_text(json.dumps(seed), encoding="utf-8")

        try:
            build_canonical_observation("east_adam", root)
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError as e:
            assert "position" in str(e)


def test_missing_known_map_fails_closed():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "world").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam").mkdir(parents=True, exist_ok=True)

        seed = load_seed()
        (root / "world" / "true_map.json").write_text(json.dumps(seed), encoding="utf-8")

        adam_pos = create_active_position(
            "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0}
        )
        (root / "agents" / "east_adam" / "world_position.json").write_text(
            json.dumps(adam_pos), encoding="utf-8"
        )

        try:
            build_canonical_observation("east_adam", root)
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError as e:
            assert "known_map" in str(e)


def test_known_map_bytes_unchanged_after_call():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "world").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam").mkdir(parents=True, exist_ok=True)

        seed = load_seed()
        (root / "world" / "true_map.json").write_text(json.dumps(seed), encoding="utf-8")

        adam_pos = create_active_position(
            "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0}
        )
        (root / "agents" / "east_adam" / "world_position.json").write_text(
            json.dumps(adam_pos), encoding="utf-8"
        )
        adam_km = create_empty_known_map("east_adam")
        (root / "agents" / "east_adam" / "known_map.json").write_text(
            json.dumps(adam_km), encoding="utf-8"
        )

        before_bytes = (root / "agents" / "east_adam" / "known_map.json").read_bytes()
        build_canonical_observation("east_adam", root, {"radius": 1})
        after_bytes = (root / "agents" / "east_adam" / "known_map.json").read_bytes()

        assert before_bytes == after_bytes


def test_no_west_files_created():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "world").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam").mkdir(parents=True, exist_ok=True)

        seed = load_seed()
        (root / "world" / "true_map.json").write_text(json.dumps(seed), encoding="utf-8")

        adam_pos = create_active_position(
            "east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0}
        )
        (root / "agents" / "east_adam" / "world_position.json").write_text(
            json.dumps(adam_pos), encoding="utf-8"
        )
        (root / "agents" / "east_adam" / "known_map.json").write_text(
            json.dumps(create_empty_known_map("east_adam")), encoding="utf-8"
        )

        build_canonical_observation("east_adam", root, {"radius": 1})

        assert not (root / "agents" / "west_adam").exists()
        assert not (root / "agents" / "west_eve").exists()
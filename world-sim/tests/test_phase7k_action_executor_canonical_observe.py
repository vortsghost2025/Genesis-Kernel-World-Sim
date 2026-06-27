import json
import tempfile
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.daemon.action_executor import execute_action
from backend.world.fog_of_war import (
    create_active_position,
    create_empty_known_map,
)


FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "fog_of_war"
SEED_PATH = FIXTURES / "phase7e_true_map_seed_v1.json"


def load_seed():
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def setup_canonical_files(root):
    """Create canonical fog-of-war structure in temp dir."""
    root = Path(root)
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
    (root / "agents" / "east_adam" / "known_map.json").write_text(
        json.dumps(create_empty_known_map("east_adam")), encoding="utf-8"
    )

    eve_pos = create_active_position(
        "east_eve", "cont_b", "cont_b_dawn_isle", "cont_b_origin_000", {"x": 50, "y": 50}
    )
    (root / "agents" / "east_eve" / "world_position.json").write_text(
        json.dumps(eve_pos), encoding="utf-8"
    )
    (root / "agents" / "east_eve" / "known_map.json").write_text(
        json.dumps(create_empty_known_map("east_eve")), encoding="utf-8"
    )


def test_canonical_observe_adam_sees_cont_a():
    with tempfile.TemporaryDirectory() as tmpdir:
        setup_canonical_files(tmpdir)
        result = execute_action(
            agent_id="east_adam",
            action_type="observe",
            action_text="observe",
            world_path=Path("/dev/null"),
            use_canonical_fog=True,
            canonical_data_root=Path(tmpdir),
        )
        assert result["ok"] is True
        assert result["world_changed"] is False
        assert result["output_path"] is None
        assert "observation" in result
        obs = result["observation"]
        assert all(t.startswith("cont_a_") for t in obs["visible_tile_ids"])
        assert "cont_b_origin_000" not in obs["visible_tile_ids"]


def test_canonical_observe_eve_sees_cont_b():
    with tempfile.TemporaryDirectory() as tmpdir:
        setup_canonical_files(tmpdir)
        result = execute_action(
            agent_id="east_eve",
            action_type="observe",
            action_text="observe",
            world_path=Path("/dev/null"),
            use_canonical_fog=True,
            canonical_data_root=Path(tmpdir),
        )
        assert result["ok"] is True
        assert result["world_changed"] is False
        assert result["output_path"] is None
        assert "observation" in result
        obs = result["observation"]
        assert all(t.startswith("cont_b_") for t in obs["visible_tile_ids"])
        assert "cont_a_origin_000" not in obs["visible_tile_ids"]


def test_canonical_observe_known_map_unchanged():
    with tempfile.TemporaryDirectory() as tmpdir:
        setup_canonical_files(tmpdir)
        before = (Path(tmpdir) / "agents" / "east_adam" / "known_map.json").read_bytes()
        execute_action(
            agent_id="east_adam",
            action_type="observe",
            action_text="observe",
            world_path=Path("/dev/null"),
            use_canonical_fog=True,
            canonical_data_root=Path(tmpdir),
        )
        after = (Path(tmpdir) / "agents" / "east_adam" / "known_map.json").read_bytes()
        assert before == after


def test_canonical_observe_missing_data_root_fails():
    result = execute_action(
        agent_id="east_adam",
        action_type="observe",
        action_text="observe",
        world_path=Path("/dev/null"),
        use_canonical_fog=True,
        canonical_data_root=None,
    )
    assert result["ok"] is False
    assert "canonical_data_root" in result["error"]


def test_canonical_observe_missing_true_map_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "world").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam" / "world_position.json").write_text(
            json.dumps(create_active_position("east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0})), encoding="utf-8"
        )
        (root / "agents" / "east_adam" / "known_map.json").write_text(
            json.dumps(create_empty_known_map("east_adam")), encoding="utf-8"
        )
        result = execute_action(
            agent_id="east_adam",
            action_type="observe",
            action_text="observe",
            world_path=Path("/dev/null"),
            use_canonical_fog=True,
            canonical_data_root=root,
        )
        assert result["ok"] is False
        assert "canonical_file_missing" in result["error"]


def test_canonical_observe_missing_world_position_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "world").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam" / "known_map.json").write_text(
            json.dumps(create_empty_known_map("east_adam")), encoding="utf-8"
        )
        result = execute_action(
            agent_id="east_adam",
            action_type="observe",
            action_text="observe",
            world_path=Path("/dev/null"),
            use_canonical_fog=True,
            canonical_data_root=root,
        )
        assert result["ok"] is False
        assert "canonical_file_missing" in result["error"]


def test_canonical_observe_missing_known_map_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "world").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam").mkdir(parents=True, exist_ok=True)
        (root / "agents" / "east_adam" / "world_position.json").write_text(
            json.dumps(create_active_position("east_adam", "cont_a", "cont_a_origin_valley", "cont_a_origin_000", {"x": 0, "y": 0})), encoding="utf-8"
        )
        result = execute_action(
            agent_id="east_adam",
            action_type="observe",
            action_text="observe",
            world_path=Path("/dev/null"),
            use_canonical_fog=True,
            canonical_data_root=root,
        )
        assert result["ok"] is False
        assert "canonical_file_missing" in result["error"]


def test_legacy_observe_unchanged_when_flag_false():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "legacy_world.json").write_text(json.dumps({"resources": {"food": 0.5}}), encoding="utf-8")
        result = execute_action(
            agent_id="east_adam",
            action_type="observe",
            action_text="observe",
            world_path=root / "legacy_world.json",
            use_canonical_fog=False,
        )
        assert result["ok"] is True
        assert result["world_changed"] is False


def test_no_west_files_created():
    with tempfile.TemporaryDirectory() as tmpdir:
        setup_canonical_files(tmpdir)
        execute_action(
            agent_id="east_adam",
            action_type="observe",
            action_text="observe",
            world_path=Path("/dev/null"),
            use_canonical_fog=True,
            canonical_data_root=Path(tmpdir),
        )
        assert not (Path(tmpdir) / "agents" / "west_adam").exists()
        assert not (Path(tmpdir) / "agents" / "west_eve").exists()
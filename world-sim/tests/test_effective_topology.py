"""Shared movement-topology compatibility contracts."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import FirstPairPersistenceStore  # noqa: E402
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402


def test_partial_legacy_topology_allowed_tiles_fails_closed(tmp_path):
    """A missing key means no allowed tiles, not an aborted heartbeat."""
    rt = FirstPairRuntime(
        heartbeat_limit=1,
        store=FirstPairPersistenceStore(tmp_path / "store"),
        pair_id="east",
    )
    rt._load_or_initialize()
    rt._fog_active = lambda: False
    rt._runtime_policy = SimpleNamespace(topology={"tiles": []})
    assert rt._get_effective_allowed_tiles() == []

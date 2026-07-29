"""Phase 10FM — Compatibility smoke suite.

Minimal import and basic-run smoke test. Does not duplicate the focused suite
in test_first_pair_runtime.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.world.first_pair_runtime import FirstPairRuntime, run_first_pair_demo


class TestCompatibilitySmoke:
    def test_imports(self) -> None:
        assert FirstPairRuntime is not None
        assert run_first_pair_demo is not None

    def test_run_one_heartbeat(self, tmp_path: Path) -> None:
        result = run_first_pair_demo(
            heartbeats=1,
            persistence_root=tmp_path / "smoke",
        )
        assert result["heartbeats_completed"] == 1

    def test_heartbeats_completed_equals_requested(self, tmp_path: Path) -> None:
        for n in (1, 2, 3):
            result = run_first_pair_demo(
                heartbeats=n,
                persistence_root=tmp_path / f"smoke-{n}",
            )
            assert result["heartbeats_completed"] == n, f"Failed at n={n}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

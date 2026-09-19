"""Detached single-heartbeat launcher entry point (10IY).

Spawns the runner as an OS-level detached process (survives editor/UI
crash), writes the initial not-started status, and exits immediately.
The launcher never waits for the heartbeat. Thin wrapper over
backend.world.canonical_heartbeat_runner.launcher_main. See
world-sim/docs/canonical_heartbeat_runbook.md for the operator protocol.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.world.canonical_heartbeat_runner import launcher_main

if __name__ == "__main__":
    raise SystemExit(launcher_main())

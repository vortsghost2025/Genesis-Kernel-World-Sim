"""Detached single-heartbeat runner entry point (10IY).

Thin wrapper over backend.world.canonical_heartbeat_runner.runner_main.
See world-sim/docs/canonical_heartbeat_runbook.md for the operator protocol.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.world.canonical_heartbeat_runner import runner_main

if __name__ == "__main__":
    raise SystemExit(runner_main())

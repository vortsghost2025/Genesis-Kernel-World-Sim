"""Run the FULL world-sim test suite locally, on Sean's Windows box.

CI runs a portable subset because ~30 suites need this workstation: gitignored
live data, the built viewer artifact, Windows process flags, and the
operator's Telegram credentials. This script runs everything those suites
need, so local coverage stays complete.

    python world-sim/scripts/run_full_suite.py

Exit code is non-zero when anything fails, so it can gate a local pre-commit
check the same way CI gates a push.

WHY THE DIRECTORY FORM AND NOT AN EXPLICIT FILE LIST

This script used to glob test_*.py and pass every path as an explicit
argument. pytest preserves the order it is given, and that order triggered a
latent order-dependence in the 10AN-10AR family: 16 failures that do not
occur when pytest collects `tests/` itself. Same file set, different order,
different verdict -- which is exactly how this session briefly concluded
there were 16 more broken suites than there are. Collection order is
pytest's job, not ours; hand it the directory and let it decide.

WHY THE BASETEMP LIVES OUTSIDE THE REPO

It used to be `<world-sim>/.scratch/pytest-full`, and that alone produced 16
spurious failures in the 10AN-10AR family. Those suites include a guard
(`test_tempdir_only_ledger_boundary_is_enforced`) asserting that ledgers are
written to a temp dir and never into the repository tree. Pointing pytest's
own temp dir into the repository trips the guard against pytest itself. The
temp dir therefore goes to the platform temp location, and the whole suite
reports its true verdict: 4 known-red browser tests pending the operator's
adjudication, and nothing else.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
TESTS = WORLD_SIM / "tests"

# The import-exit family. They call sys.exit(1) during module import, which
# pytest treats as an INTERNALERROR and aborts collection for the whole run
# regardless of --continue-on-collection-errors. They are legacy and dead;
# excluding them is the only way the rest can report a verdict. (Collected
# rather than hardcoded, so a new one is caught the day it appears.)
IMPORT_EXIT_PATTERN = re.compile(r"^\s*sys\.exit\(", re.MULTILINE)


def _import_exit_files() -> list[str]:
    dead = []
    for path in sorted(TESTS.glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            dead.append(path.name)
            continue
        if IMPORT_EXIT_PATTERN.search(text):
            dead.append(path.name)
    return dead


def main() -> int:
    skipped = _import_exit_files()
    print(f"FULL SUITE: pytest collects {TESTS.name}/ itself (stable order).")
    if skipped:
        print(f"Skipping {len(skipped)} import-exit legacy modules: "
              + ", ".join(skipped))

    basetemp = Path(tempfile.gettempdir()) / "genesis-full-suite"
    args = [
        sys.executable, "-m", "pytest", str(TESTS), "-q",
        "--continue-on-collection-errors",
        "--basetemp", str(basetemp),
    ]
    for name in skipped:
        args.append(f"--ignore={TESTS / name}")
    proc = subprocess.run(args, cwd=str(WORLD_SIM))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())

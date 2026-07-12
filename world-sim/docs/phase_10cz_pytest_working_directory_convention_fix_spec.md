# Phase 10CZ - Pytest Working-Directory Convention Fix

Tooling-only spec that **maps out** the pytest working-directory convention for Genesis pure tests. No test rewrites, no runtime, no daemon/scheduler/network, no world-sim/data writes. Gate-7 stays closed. Stop before commit (spec only; applying the config file is a later gated step).

This phase was reassigned from the original 10CY bundle: the old post-10CV audit draft had folded the cwd fix, the single-line phase-index rows note, and a deferred whitespace/.gitattributes note into "10CY". 10CY was instead used for the 10CX metadata sync (commit `b6a675b`), so the pytest cwd fix is now its own phase: 10CZ.

## Rules
- tooling-only (config + docs; no test-code changes)
- docs/spec first; applying world-sim/pytest.ini is a later gated step
- no test rewrites
- no runtime / daemon / scheduler / network
- no world-sim/data writes
- gate-7 stays closed (10CH / 10CR precedent)
- stop before commit

## Problem (verified, read-only)
- 76 test files under `world-sim/tests/` do `from backend... import` (e.g. `world-sim/tests/test_phase10cv_gate7_free_dry_run_adapter.py:11` -> `from backend.world.local_gate7_free_dry_run_adapter import ...`).
- `backend` is a package at `world-sim/backend/`. It resolves only when the pytest rootdir / cwd is `world-sim` (added to `sys.path[0]` by `python -m pytest`).
- CI `pure-tests.yml` forces `working-directory: world-sim` (line 14) and runs `python -m pytest tests/...` (line 26), so CI always collects and passes.
- From the **repo root**, the command `python -m pytest world-sim/tests/test_phase10cv_gate7_free_dry_run_adapter.py` fails with `ModuleNotFoundError: backend`, because the rootdir becomes the repo root and `backend` (under `world-sim/`) is not importable.
- No `world-sim/pytest.ini`, no `pyproject.toml` `[tool.pytest.ini_options]`, no `conftest.py`, no `setup.cfg`/`tox.ini`, and no `.gitattributes` (the `eol=lf` rule mentioned in the old draft was never applied).

The risk: the test suite only works under one hidden working-directory assumption (the CI one). A developer running tests from the repo root gets a misleading `ModuleNotFoundError` that is not a real test failure.

## Fix / convention (to be applied in a later gated step)
1. **Add `world-sim/pytest.ini`:**
   ```
   [pytest]
   pythonpath = .
   ```
   `pythonpath = .` tells pytest to add the pytest rootdir (`world-sim`) to `sys.path`, so `backend` resolves whether pytest is launched from the repo root or from `world-sim`. After this, both of these collect and pass:
   - `python -m pytest world-sim/tests/test_phase10cv_gate7_free_dry_run_adapter.py` (from repo root)
   - `python -m pytest tests/...` (from world-sim)
2. **Document the convention** in this spec + README: "Run Genesis pure tests from the repo root or from `world-sim`; `world-sim/pytest.ini` makes `backend` importable either way. Do not rely on CI's `working-directory` for local test runs."
3. **Keep CI `working-directory: world-sim`** as-is (it remains valid; the ini makes it non-mandatory rather than the only working path).

## Out of scope (deferred, cosmetic)
- `.gitattributes` with `* text=auto eol=lf` to prevent line-ending drift (recommended later; not required for the cwd fix).
- One-time trailing-whitespace / spelling strip across older files (cosmetic only).
- Any test-file rewrites or runtime/daemon/scheduler/network code.

## Scope boundaries
- **In:** `world-sim/pytest.ini` (config, applied later), this spec doc, `README.md`, `world-sim/docs/phase_index.md`.
- **Out:** test-file edits, runtime/daemon/scheduler/network, world-sim/data access, gate-7, `.gitattributes` (deferred).

## Verification (for the later apply step, not this phase)
- `python -m pytest world-sim/tests/test_phase10cv_gate7_free_dry_run_adapter.py` from repo root -> collects and passes (was `ModuleNotFoundError: backend`).
- `python -m pytest tests/...` from `world-sim` -> still passes.
- GitHub Actions `pure-tests` workflow remains green.

## Allowed files (this phase)
- this spec doc (`world-sim/docs/phase_10cz_pytest_working_directory_convention_fix_spec.md`)
- `README.md`
- `world-sim/docs/phase_index.md`

## Checks
- `git diff --check`
- `git diff --numstat`
- `git status -sb`
- CRLF check on touched files (LF only)

## Output
```
PHASE: 10CZ - Pytest Working-Directory Convention Fix
FILES CHANGED: world-sim/docs/phase_10cz_pytest_working_directory_convention_fix_spec.md (new), README.md, world-sim/docs/phase_index.md
EVIDENCE USED: pure-tests.yml (working-directory: world-sim @ line 14; python -m pytest tests/... @ line 26); 76 test files import backend (world-sim/tests/test_phase10cv_gate7_free_dry_run_adapter.py:11); no world-sim/pytest.ini / pyproject / conftest / setup.cfg / tox.ini; no .gitattributes; ModuleNotFoundError: backend when run from repo root
CHECKS: git diff --check (no whitespace errors); git diff --numstat; git status -sb; CRLF/LF-only verified on touched files
STATUS: docs-only spec complete; working tree modified; NOT committed (stop before commit per rules)
PROPOSED COMMIT: 10CZ: Pytest working-directory convention fix - add world-sim/pytest.ini (pythonpath = .) so backend imports resolve from repo root or world-sim; map the convention; no test rewrites, runtime, daemon/scheduler/network, or world-sim/data writes; gate-7 stays closed.
RISK NOTES:
- The cwd fix (world-sim/pytest.ini) is DEFINED here but NOT applied in this phase; applying it is a later gated step. Until then, local test runs from the repo root still raise ModuleNotFoundError: backend (CI is unaffected because it pins working-directory: world-sim).
- 76 test files depend on backend resolving; any future move of the backend package must update pytest.ini / pythonpath accordingly.
- .gitattributes eol=lf and the one-time whitespace strip are deferred/cosmetic and intentionally out of scope here.
- Gate-7 remains closed; 10CZ does not reopen or touch it.
```

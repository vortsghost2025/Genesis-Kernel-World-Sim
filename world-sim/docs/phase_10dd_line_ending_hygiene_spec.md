# Phase 10DD - Line-Ending Hygiene Spec (.gitattributes)

Docs/spec-only phase that **maps out** the line-ending hygiene for Genesis. Defines the exact `.gitattributes` content and the scope; applying the file is a later gated step (10DE). No mass rewrites, no runtime, no daemon/scheduler/network, no world-sim/data writes. Gate-7 stays closed. Stop before commit (spec only).

This phase closes a deferred item from 10CZ: the original post-10CV audit draft had folded a `.gitattributes` (`* text=auto eol=lf`) rule into the "10CY" bundle. 10CY became the 10CX metadata sync and 10CZ/10DB handled the pytest cwd fix, so the line-ending rule is now its own phase: 10DD (spec) -> 10DE (apply).

## Rules
- docs/spec first; applying `.gitattributes` is a later gated step
- no mass file rewrites (esp. the deferred one-time whitespace strip)
- no test/backend rewrites
- no runtime / daemon / scheduler / network
- no world-sim/data writes
- gate-7 stays closed (10CH / 10CR precedent)
- stop before commit

## Problem (verified, read-only)
- No `.gitattributes` exists at repo root (confirmed `Test-Path .gitattributes` = False).
- **0** tracked files contain CRLF (all are already LF). So this is a *preventive* control, not a corrective one - there is no existing line-ending drift to fix.
- Trailing whitespace DOES exist in some tracked text files (e.g. `world-sim/frontend/map-v2.html` CSS rules carry trailing spaces). A one-time trailing-whitespace strip was explicitly deferred in 10CZ as "optional and deferred; it would touch many older files and is not required for any runtime phase."

The risk: without an explicit `eol=lf` rule, a future edit made on a Windows checkout (or a tool that emits CRLF) can silently introduce line-ending drift that makes diffs noisy and re-breaks cross-platform test runs.

## Fix / convention (to be applied in 10DE)
1. **Add `.gitattributes` at repo root:**
   ```
   * text=auto eol=lf
   ```
   `text=auto eol=lf` tells Git to normalize every text file to LF on commit, so CRLF cannot reappear regardless of the editor/OS that writes it.
2. **Keep it minimal.** Do not enumerate every extension. Optionally add binary guards later (`*.png binary`, `*.jpg binary`) only if a real binary-corruption case appears - out of scope here.
3. **Do NOT run a mass renormalize or whitespace strip in this phase.** Because 0 files currently have CRLF, no `git add --renormalize` is needed. The deferred one-time trailing-whitespace strip (touching many older files) stays out of scope and is tracked as a separate optional item.

## Out of scope (deferred)
- One-time trailing-whitespace strip across older files (cosmetic only; would touch many files; tracked separately as optional).
- Enumerating per-extension binary rules (only if a real case appears).
- Any test/backend/runtime/daemon/scheduler/network change.

## Scope boundaries
- **In:** `.gitattributes` (applied in 10DE), this spec doc, `README.md`, `world-sim/docs/phase_index.md`.
- **Out:** mass file edits, test/backend rewrites, runtime/daemon/scheduler/network, world-sim/data access, gate-7.

## Verification (for the 10DE apply step, not this phase)
- After creating `.gitattributes`, `git status -sb` is clean (no renormalize churn, since 0 files have CRLF).
- A deliberately introduced CRLF line, when staged/committed, is normalized to LF (verify with `git diff --word-diff` or a hexdump of the committed blob).
- CI pure-tests unaffected.

## Allowed files (this phase)
- this spec doc (`world-sim/docs/phase_10dd_line_ending_hygiene_spec.md`)
- `README.md`
- `world-sim/docs/phase_index.md`

## Checks
- `git diff --check`
- `git diff --numstat`
- `git status -sb`
- CRLF check on touched files (LF only)

## Output
```
PHASE: 10DD - Line-Ending Hygiene Spec (.gitattributes)
FILES CHANGED: world-sim/docs/phase_10dd_line_ending_hygiene_spec.md (new), README.md, world-sim/docs/phase_index.md
EVIDENCE USED: no .gitattributes at repo root; 0 tracked files contain CRLF (all LF - rule is preventive); trailing whitespace present in some tracked text files (e.g. world-sim/frontend/map-v2.html CSS) - mass strip deferred from 10CZ; 10CZ/10DB pytest cwd fix already shipped (eedb32c)
CHECKS: git diff --check (no whitespace errors); git diff --numstat; git status -sb; CRLF/LF-only verified on touched files
STATUS: docs-only spec complete; working tree modified; NOT committed (stop before commit per rules)
PROPOSED COMMIT: 10DD: line-ending hygiene spec - define .gitattributes (* text=auto eol=lf) to prevent CRLF drift; 0 files currently have CRLF so the rule is preventive; defer mass whitespace strip; no implementation, runtime, daemon/scheduler/network, or world-sim/data writes; gate-7 stays closed.
RISK NOTES:
  - .gitattributes is DEFINED here but NOT applied in this phase; applying it is 10DE (later gated step).
  - 0 files currently have CRLF, so no renormalize churn is expected on apply - if some appear later, a targeted renormalize is safe.
  - The one-time trailing-whitespace strip is intentionally deferred (would touch many older files); tracked as a separate optional item, not folded here.
  - Gate-7 remains closed; 10DD does not touch it.
```

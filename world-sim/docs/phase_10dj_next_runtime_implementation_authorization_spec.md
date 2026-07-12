# Phase 10DJ - Next Runtime Implementation Authorization Spec

Docs-only authorization spec. Cheap/free model OK. Does not implement code, does not touch backend/tests/runtime/world-sim/data, daemon/scheduler/network/provider/launcher/container/Docker, PatchRaccoon, or agent configs. Gate-7 stays closed. Stop before commit.

This phase is the single final docs-only gate after the cleanup lane (10CX -> 10DI). It does NOT open runtime; it names the exact next implementation target and its limits, and makes explicit that any implementation phase after this requires the GPT-5.6 Sol/Luna model switch.

## Rules
- docs-only authorization spec
- cheap/free model OK
- no implementation
- no backend/tests/runtime/world-sim/data changes
- no daemon/scheduler/network/provider/launcher/container/Docker
- no PatchRaccoon / agent-config changes
- gate-7 stays closed (10CH / 10CR precedent)
- stop before commit

## Authorization result (verified, read-only, against baseline `812dcd1 Phase 10DI: sync 10DH metadata`)

1. Cleanup lane is complete through 10DI. (10CX compact/restore boundary; 10CZ/10DB pytest cwd; 10DD/10DF LF hygiene; 10DH readiness audit 9/9 PASS; all metadata synced.)
2. Compact/restore sync boundary is locked. (10CX `2ef6d7e`; defines pre-compact snapshot, >=93% fidelity, quarantine on <93%, last-known-good reload.)
3. Pytest cwd fix is locked. (10DB `eedb32c`; `world-sim/pytest.ini` `[pytest] pythonpath = .`; 29/29 from both repo root and world-sim.)
4. LF hygiene is locked. (10DF `c40336a`; repo-root `.gitattributes` = `* text=auto eol=lf`; 0 renormalize churn.)
5. Gate-7 remains closed. (Every 10C*/10D* phase_index row ends "gate-7 stays closed"; 10CH/10CR/10CT confirm gate-7 NOT authorized for any use.)
6. Runtime/daemon/scheduler/network remain unauthorized. (10CH gates 6 (world-sim/data) and 7 (daemon/scheduler/network) remain blocked; 10CL/10CP/10CT are spec-only and hard-code all gate flags False.)
7. Any implementation phase after this requires GPT-5.6 Sol/Luna. (10CL/10CN/10CR rows require "operator approval and the GPT-5.6 Luna/Sol model switch" before any later live/runtime/write adapter phase.)
8. The next implementation must be minimal, single-surface, and separately committed. (One concern, one phase, one commit + metadata sync, per the 10CX..10DI discipline.)
9. No broad runtime wiring. (10CF conclusion: next possible non-doc phase must be a pure dry-run adapter spec/harness, not live runtime. 10CH: no code path can flip runtime/daemon/scheduler/network flags to True.)
10. No daemon/scheduler/network. (Gate-7 explicitly NOT authorized; 10CT satisfied gate-7 by absence only.)
11. No world-sim/data expansion unless explicitly authorized. (10CN gates gate-6; only candidate future write is the inert append-only 10CP ledger path, itself requiring the GPT-5.6 switch.)
12. No provider/model/container/Docker changes. (Denylist across 10CL/10CN/10CR; model switch is a separate operator action, not a repo edit here.)

## Recommended next implementation candidate (defined ONLY as a future candidate, not implemented here)

**10DL - Minimal Authorized Runtime Adapter Integration Harness**

- Pure, in-process, caller-driven harness that consumes already-built 10CJ dry-run decisions only (never raw 10BT, never 10CP writer directly beyond the 10CT allowlist).
- Emits an inert 10CJ-shaped decision: `executed` False, `runtime_allowed`/`daemon_allowed`/`scheduler_allowed`/`network_allowed`/`world_sim_data_accessed` all False, `planned_action` only `none` or `log_only`.
- Single permitted side effect: the already-authorized append-only 10CP inert ledger entry at the explicitly authorized path, with no new world-sim/data access.
- No daemon, scheduler, network, provider, launcher, container, Docker; no movement, map lookup, route execution, event emission, NPC behavior, co-presence, awareness, relationship, interaction, timing, or coordination.
- Gate-7 stays closed; this candidate satisfies gate-7 by absence, which does NOT authorize gate-7 for any other use.
- Requires operator approval AND the GPT-5.6 Sol/Luna model switch before any implementation phase; 10DL is named here only so the next serious step is unambiguous.

This spec does NOT implement 10DL. It authorizes only that 10DL is the named next candidate, bounded exactly as above, and that no broader runtime work may begin without the model switch.

## Scope boundaries
- **In:** this authorization spec, `README.md`, `world-sim/docs/phase_index.md`.
- **Out:** backend/tests/runtime/world-sim/data, daemon/scheduler/network/provider/launcher/container/Docker, PatchRaccoon/agent configs, gate-7, any 10DL implementation.

## Allowed files
- `world-sim/docs/phase_10dj_next_runtime_implementation_authorization_spec.md`
- `README.md`
- `world-sim/docs/phase_index.md`

## Checks
- `git diff --check`
- `git diff --numstat`
- `git status -sb`
- CRLF check on touched files (LF only)

## Output
```
PHASE: 10DJ - Next Runtime Implementation Authorization Spec
FILES CHANGED: world-sim/docs/phase_10dj_next_runtime_implementation_authorization_spec.md (new), README.md, world-sim/docs/phase_index.md
AUTHORIZATION RESULT:
  [1] cleanup lane complete through 10DI .............. PASS
  [2] compact/restore boundary locked ................ PASS (10CX, 2ef6d7e)
  [3] pytest cwd fix locked ....................... PASS (10DB, eedb32c, pytest.ini)
  [4] LF hygiene locked ........................... PASS (10DF, c40336a, .gitattributes)
  [5] gate-7 closed ............................. PASS
  [6] runtime/daemon/scheduler/network blocked . PASS (10CH gates 6/7)
  [7] future impl needs GPT-5.6 Sol/Luna ....... PASS (10CL/10CN/10CR)
  [8] next impl minimal/single-surface/separate . PASS (discipline 10CX..10DI)
  [9] no broad runtime wiring .................... PASS (10CF/10CH)
  [10] no daemon/scheduler/network ................ PASS (gate-7)
  [11] no world-sim/data expansion ............... PASS (10CN gate-6)
  [12] no provider/model/container/Docker ......... PASS (denylist)
  NEXT CANDIDATE: 10DL - Minimal Authorized Runtime Adapter Integration Harness (named only; not implemented here)
CHECKS: git diff --check clean; git diff --numstat; git status -sb; CRLF/LF-only verified on touched files
STATUS: docs-only authorization complete; working tree modified; NOT committed (stop before commit per rules)
PROPOSED COMMIT: 10DJ: next runtime implementation authorization spec - confirm cleanup lane locked through 10DI, name 10DL as the single minimal authorized next candidate (inert 10CJ-consumer harness, gate-7 by absence, GPT-5.6 Sol/Luna required); no implementation, runtime, daemon/scheduler/network, or world-sim/data writes.
RISK NOTES:
  - 10DJ authorizes ONLY that 10DL is the named next candidate; it does NOT implement 10DL or open runtime.
  - Any 10DL implementation requires operator approval AND the GPT-5.6 Sol/Luna model switch (out of scope for this cheap/free phase).
  - Gate-7 remains closed; 10DJ does not reopen or touch it.
  - The one-time trailing-whitespace strip stays deferred (would touch many older files).
```

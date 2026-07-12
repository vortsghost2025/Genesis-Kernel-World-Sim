# Phase 10DP - Next Runtime Expansion Candidate Spec

Docs-only expansion-candidate spec. Cheap/free model OK. Does not implement code, does not touch backend/tests/runtime/world-sim/data, daemon/scheduler/network/provider/launcher/container/Docker, PatchRaccoon, or agent configs. Gate-7 stays closed. Stop before commit.

This phase is the single docs-only gate after the 10DL implementation lane (10DJ -> 10DL -> 10DM -> 10DN -> 10DO). It does NOT open runtime; it names the exact next implementation target and its limits, and makes explicit that any implementation phase after this requires the GPT-5.6 Sol/Luna model switch.

## Rules
- docs-only expansion-candidate spec
- cheap/free model OK
- no implementation
- no backend/tests/runtime/world-sim/data changes
- no daemon/scheduler/network/provider/launcher/container/Docker
- no PatchRaccoon / agent-config changes
- gate-7 stays closed (10CH / 10CR precedent)
- stop before commit

## Authorization result (verified, read-only, against baseline `c781d5f Phase 10DO: sync 10DN metadata`)

1. 10DL implementation lane is complete. (10DL `32b13eb` implemented; 10DM `c054e9f` synced; 10DN `f594257` audited 12/12 PASS; 10DO `c781d5f` synced.)
2. Compact/restore sync boundary is locked. (10CX `2ef6d7e`; pre-compact snapshot, >=93% fidelity, quarantine on <93%, last-known-good reload.)
3. Pytest cwd fix is locked. (10DB `eedb32c`; `world-sim/pytest.ini` `[pytest] pythonpath = .`; 29/29 from both repo root and world-sim.)
4. LF hygiene is locked. (10DF `c40336a`; repo-root `.gitattributes` = `* text=auto eol=lf`; 0 renormalize churn.)
5. 10DL is exactly the 10DJ-authorized candidate. (pure in-process, 10CJ-only consumer, 10CV-only delegation, exact 10CJ-shaped inert output, no 10CP import/call, no file I/O, no equality_signal_value read/emit; all runtime/daemon/scheduler/network/world-data flags False; gate-7 closed — per 10DN audit.)
6. Gate-7 remains closed. (Every 10C*/10D* phase_index row ends "gate-7 stays closed"; 10CH/10CR/10CT confirm gate-7 NOT authorized for any use.)
7. Runtime/daemon/scheduler/network remain unauthorized. (10CH gates 6 (world-sim/data) and 7 (daemon/scheduler/network) remain blocked; 10CL/10CP/10CT/10CV hard-code all gate flags False.)
8. The gate-6 inert write path is pre-authorized but not yet exercised end-to-end. (10CN `c3ad522` defined the only candidate write location `world-sim/data/runtime_adapter_ledger/runtime_adapter_decisions.ndjson` as an allowlist target; 10CP `69967a9` implemented the inert ledger writer; no orchestrator yet calls 10CP with a real 10CJ/10DL result.)
9. Any implementation phase after this requires GPT-5.6 Sol/Luna. (10CL/10CN/10CR rows require "operator approval and the GPT-5.6 Luna/Sol model switch" before any later live/runtime/write adapter phase.)
10. The next implementation must be minimal, single-surface, and separately committed. (One concern, one phase, one commit + metadata sync, per the 10CX..10DO discipline.)
11. No broad runtime wiring. (10CF conclusion: next non-doc phase must be a pure dry-run/integration seam, not live runtime. 10CH: no code path can flip runtime/daemon/scheduler/network flags to True.)
12. No provider/model/container/Docker changes. (Denylist across 10CL/10CN/10CR; model switch is a separate operator action, not a repo edit here.)

## Recommended next implementation candidate (defined ONLY as a future candidate, not implemented here)

**10DR - Minimal Inert Ledger Write Orchestrator**

- Pure, in-process, caller-driven orchestrator that consumes an already-built 10BT decision and runs it through the existing inert chain only: 10BT -> 10CJ (dry-run consumer adapter) -> 10CV (gate-7-free dry-run adapter) / 10DL (integration validation) -> 10CP (inert ledger writer).
- The single permitted side effect is the already-authorized append-only 10CP inert ledger entry at the explicitly authorized path `world-sim/data/runtime_adapter_ledger/runtime_adapter_decisions.ndjson`, with no new world-sim/data access and no parent/directory creation.
- Emits an inert outcome: `executed` False, `runtime_allowed`/`daemon_allowed`/`scheduler_allowed`/`network_allowed`/`world_sim_data_accessed` all False, `planned_action` only `none` or `log_only`, and writes only when the 10CJ/10DL result is `ok=True`, `planned_action=="log_only"`, all five gate flags False, and a known inert signal type — i.e., the exact 10CN/10CP acceptance envelope.
- Never reads or emits `equality_signal_value`; never imports/calls raw 10BT, 10CJ, or 10CV internals beyond their public functions; treats 10CP as the only writer and never wraps or extends it.
- No daemon, scheduler, network, provider, launcher, container, Docker; no movement, map lookup, route execution, event emission, NPC behavior, co-presence, awareness, relationship, interaction, timing, or coordination.
- Gate-7 stays closed; this candidate satisfies gate-7 by absence, which does NOT authorize gate-7 for any other use.
- Requires operator approval AND the GPT-5.6 Sol/Luna model switch before any implementation phase; 10DR is named here only so the next serious step is unambiguous.

This spec does NOT implement 10DR. It authorizes only that 10DR is the named next candidate, bounded exactly as above, and that no broader runtime work may begin without the model switch.

## Scope boundaries
- **In:** this expansion-candidate spec, `README.md`, `world-sim/docs/phase_index.md`.
- **Out:** backend/tests/runtime/world-sim/data, daemon/scheduler/network/provider/launcher/container/Docker, PatchRaccoon/agent configs, gate-7, any 10DR implementation.

## Allowed files
- `world-sim/docs/phase_10dp_next_runtime_expansion_candidate_spec.md`
- `README.md`
- `world-sim/docs/phase_index.md`

## Checks
- `git diff --check`
- `git diff --numstat`
- `git status -sb`
- CRLF check on touched files (LF only)

## Output
```
PHASE: 10DP - Next Runtime Expansion Candidate Spec
FILES CHANGED: world-sim/docs/phase_10dp_next_runtime_expansion_candidate_spec.md (new), README.md, world-sim/docs/phase_index.md
AUTHORIZATION RESULT:
  [1] 10DL lane complete .................... PASS (32b13eb, c054e9f, f594257, c781d5f)
  [2] compact/restore boundary locked ........ PASS (10CX, 2ef6d7e)
  [3] pytest cwd fix locked .................. PASS (10DB, eedb32c, pytest.ini)
  [4] LF hygiene locked ...................... PASS (10DF, c40336a, .gitattributes)
  [5] 10DL = exactly 10DJ-authorized ...... PASS (10DN 12/12)
  [6] gate-7 closed ........................ PASS
  [7] runtime/daemon/scheduler/network blocked PASS (10CH gates 6/7)
  [8] gate-6 inert write path pre-authorized
      but not yet exercised e2e ............. PASS (10CN c3ad522, 10CP 69967a9)
  [9] future impl needs GPT-5.6 Sol/Luna ... PASS (10CL/10CN/10CR)
  [10] next impl minimal/single-surface/separate PASS (discipline 10CX..10DO)
  [11] no broad runtime wiring ............... PASS (10CF/10CH)
  [12] no provider/model/container/Docker .... PASS (denylist)
  NEXT CANDIDATE: 10DR - Minimal Inert Ledger Write Orchestrator (named only; not implemented here)
CHECKS: git diff --check clean; git diff --numstat; git status -sb; CRLF/LF-only verified on touched files
STATUS: docs-only candidate spec complete; working tree modified; NOT committed (stop before commit per rules)
PROPOSED COMMIT: 10DP: next runtime expansion candidate spec - confirm 10DL lane complete (10DJ/10DL/10DM/10DN/10DO), name 10DR as the single minimal authorized next candidate (inert ledger write orchestrator chaining 10BT->10CJ->10CV/10DL->10CP at the authorized gate-6 path, gate-7 by absence, GPT-5.6 Sol/Luna required); no implementation, runtime, daemon/scheduler/network, or world-sim/data writes.
RISK NOTES:
  - 10DP authorizes ONLY that 10DR is the named next candidate; it does NOT implement 10DR or open runtime.
  - Any 10DR implementation requires operator approval AND the GPT-5.6 Sol/Luna model switch (out of scope for this cheap/free phase).
  - Gate-7 remains closed; 10DP does not reopen or touch it.
  - The one-time trailing-whitespace strip stays deferred (would touch many older files).
```

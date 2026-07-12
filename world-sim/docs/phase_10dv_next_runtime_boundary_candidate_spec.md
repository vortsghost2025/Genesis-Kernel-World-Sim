# Phase 10DV — Next Runtime Boundary Candidate Spec

Docs-only specification naming the single next authorized runtime-boundary
candidate. This phase performs no implementation, touches no backend/tests
runtime code or `world-sim/data`, and stops before commit.

- Repo: `S:\Genesis Kernel World Sim`
- Baseline: `aad0787` Phase 10DU: sync 10DT metadata
- Mode: docs-only spec (cheap/free model OK)
- Out of scope: backend, tests, runtime, `world-sim/data`, daemon, scheduler,
  network, provider, launcher, container, Docker, PatchRaccoon, agent configs

## Context

Phase 10DR (`7447b88`) established the authorized gate-6 inert append path:
a pure in-process, caller-driven orchestrator that consumes an already-built
`10BT` decision, passes it through public `10CJ` and `10DL` (which internally
delegates to `10CV`), and calls `10CP` only after exact-shape / provenance /
known-signal / log-only / all-False-gate validation with two explicit ledger
paths. `10CP` remains the only writer and exact-path authority checker
(`world-sim/data/runtime_adapter_ledger/runtime_adapter_decisions.ndjson`,
authorized via `10CN` `c3ad522`, implemented via `10CP` `69967a9`).

Phase 10DT (`5ba1e51`) audited the committed 10DR and confirmed 14/14
boundary checks PASS; the historical boolean-type-drift risk (`ok=1` accepted
as `True`) was resolved (not deferred) by strict bool identity in 10DR
`_matches_expected` and independently in 10CP, covered by
`test_dependency_boolean_type_drift_fails_closed`.

Before any broader runtime expansion, the safest next move is to *verify* the
records that 10DR/10CP now write — not to add new write or execution
behavior. This closes the loop on the inert audit ledger without opening gate-7.

## Candidate Named

**10DX — Minimal Inert Ledger Read-Back Verifier**

This is the single authorized next candidate. No other candidate is named by
this phase.

10DX is specified to be:

- **pure read-only** — performs no mutation of any kind.
- **in-process / caller-driven** — runs only when a caller supplies a ledger
  path; it never starts work on its own.
- **consumes a caller-supplied ledger path only** — it reads the ledger the
  caller points at and nothing else.
- **has no default production ledger path** — if no path is supplied, it does
  not invent one; it reports the missing path and stops.
- **does not scan `world-sim/data`** — it never enumerates, globs, or walks
  directories; it reads only the single explicit path given.
- **does not write, append, overwrite, truncate, delete, rename, or repair** —
  strictly read-only; no ledger maintenance or recovery is in scope.
- **does not call the `10CP` writer** — `10CP` remains the only writer; 10DX
  never imports or invokes it.
- **verifies only existing inert `10CP`/`10DR` ledger records** — it checks
  records already written by the authorized pipeline, not arbitrary input.
- **checks record shape, allowed fields, `record_hash`, schema version,
  recognized inert signal type, and append-only line format** — each line must
  parse as a JSON object with the expected `10CP`/inert fields; unknown or
  forbidden fields are reported; the `record_hash` must be internally
  consistent with the record; the schema version must be an accepted inert
  version; the recognized signal type must be one of the six known inert types
  (`snapshot_id_equality`, `snapshot_hash_equality`,
  `current_tile_id_equality`, `route_intent_id_equality`,
  `known_tile_ids_set_equality`, `route_destination_tile_id_equality`); and the
  file must be valid newline-delimited JSON with no partial or interleaved
  lines.
- **never reads/emits `equality_signal_value`** — 10DX may confirm a record
  references a known signal *type* but must never read, store, log, export, or
  promote the signal's *value*; the value field is out of scope by design.
- **never promotes ledger contents into runtime/world state** — verification
  results are returned to the caller as a status object only; no world, ledger,
  or external state is updated.
- **never creates movement / map / route / event / NPC behavior** — 10DX is
  observability only; it produces no simulation side effects.
- **keeps all `runtime`/`daemon`/`scheduler`/`network`/`world-data`/`gate-7`
  flags `False`** — its status envelope hard-codes these to `False`, matching
  the 10DR contract.
- **gate-7 remains closed by absence** — 10DX enables no execution,
  provider, launcher, container, or Docker behavior.

## Authorization Result

- 10DV **only names 10DX**. It is a spec phase; no implementation is
  performed here.
- 10DX implementation is **not** authorized by this phase. A future
  implementation requires:
  - a dedicated implementation spec (e.g. 10DX itself, or a follow-up),
  - **GPT-5.6 Sol/Luna** authorization (per `10CL`/`10CN`/`10CR`), and
  - explicit operator approval before commit.
- 10DW will be the metadata-sync phase for 10DV (spec=N, sync=N+1).
- No code, backend, tests, runtime, or `world-sim/data` changes occur in
  this phase.

## Audit / Spec Confirmation

1. 10DR (`7447b88`) + 10DS (`d53e1e5`) closed — confirmed by baseline
   `aad0787` history.
2. 10DT (`5ba1e51`) + 10DU (`aad0787`) closed — confirmed.
3. 10DR audit 14/14 PASS — confirmed by 10DT (`5ba1e51`).
4. Boolean drift resolved, not deferred — confirmed by 10DT (`5ba1e51`);
   strict bool identity in 10DR `_matches_expected` and independently in 10CP.
5. 10CP remains the only writer — preserved: 10DX is read-only and does not
   call `10CP`.
6. Next work should be read-back verification before any broader runtime
   expansion — this is exactly what 10DX provides; no further expansion is
   named here.
7. No batch orchestrator yet — 10DX verifies a single caller-supplied ledger;
   no multi-decision batch candidate is named.
8. No local-sim bridge yet — no 10AI–10AN bridge to the inert ledger is named.
9. No gate-7 work yet — gate-7 remains closed by absence throughout.
10. No production `world-sim/data` access in this docs phase — only
    `world-sim/docs/` and root `README.md` / `world-sim/docs/phase_index.md`
    are touched.

## Checks

- `git diff --check` — clean (docs-only additions).
- `git diff --numstat` — three authorized file changes:
  `world-sim/docs/phase_10dv_next_runtime_boundary_candidate_spec.md` (new),
  `README.md` (+1 line), `world-sim/docs/phase_index.md` (+1 row).
- `git status -sb` — only the three authorized files modified/added; no backend,
  tests, runtime, or data changes.
- CRLF — 0 on all touched files (LF only).

## Status

Docs-only spec complete. Working tree modified (three authorized files); not
committed per instruction. Awaiting user go-ahead to commit/push 10DV, then
10DW metadata sync.

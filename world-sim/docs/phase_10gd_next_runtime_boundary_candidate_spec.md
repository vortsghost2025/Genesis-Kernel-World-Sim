# Phase 10GD — Next Runtime Boundary Candidate Spec

Docs-only specification naming the single next authorized runtime-boundary
candidate. This phase performs no implementation, touches no backend/tests
runtime code or `world-sim/data`, and stops before commit.

- Repo: `S:\Genesis Kernel World Sim`
- Baseline: `eb4b0e8 docs: record 10GC metadata hash`
- Mode: docs-only spec (cheap/free OK; no GPT-5.6 required)
- Out of scope: backend, tests, runtime, `world-sim/data`, daemon, scheduler,
  network, provider, launcher, container, Docker, PatchRaccoon, agent configs

## Context

The inert-ledger observability proof-chain is **closed** (at 10FN,
`afbc8d0`). A governance/provenance branch was opened at 10FR and is now fully
closed through 10FW, and a governance approval-authorization branch was opened
at 10FX and is now fully closed through 10GC:

- `10FX` (`6d06cc9`) — next-candidate spec naming **10FZ**
- `10FY` (`f8e1743`) — sync 10FX metadata
- `10FZ` (`86add55`) — Minimal Inert Model Routing Approval Authorization
  Reporter (implementation; 337 targeted tests, 238 optional 10FT regression,
  184 optional 10FN regression)
- `10GA` (`faefa01`) — sync 10FZ metadata (`bd059d9` hash correction)
- `10GB` (`9f95e1f`) — post-10FZ runtime boundary audit (14/14 checks PASS)
- `10GC` (`b579790`) — sync 10GB metadata (`eb4b0e8` hash correction)

`10FZ.1` is now the safe terminal artifact of the approval-authorization branch:
the exact 35-field authorization report output of
`create_minimal_inert_model_routing_approval_authorization_report` /
`export_minimal_inert_model_routing_approval_authorization_report`. It answers
"given a verified provenance report and an operator approval artifact, is this
routing authorized for execution, under what approval authority, for what
action, and with what boundaries?" — but it is observability only and performs
no execution.

**The approval-authorization branch does not yet answer the status-report
question:** "given a 10FZ.1 authorization report that a caller already produced,
what is its compact status summary — authorized/not_authorized or invalid —
without re-deriving or re-attesting the underlying approval decision?" Adding
another recursive approval verifier would only deepen a closed branch. The
right next move is a *new* trust surface: **authorization report status
reporting** layered over the already-safe 10FZ.1 output. This is a status
reporter, **not** a routing executor, **not** an approval re-authorizer, and
**not** a recursive approval/verification verifier.

## Candidate Named

**10GF — Minimal Inert Model Routing Authorization Report Status Reporter**

This is the single authorized next candidate. No other candidate is named by
this phase.

10GF is specified to be:

- **pure read-only status reporting** — performs no mutation of any kind; it
  never touches a ledger file or any runtime component for writing or reading,
  and never alters a supplied authorization report. It is a *reporter over an
  authorization report*, not an executor or re-authorizer.
- **in-process / caller-driven** — runs only when a caller supplies one 10FZ.1
  authorization report dict already produced by 10FZ; it never starts work on
  its own.
- **consumes one caller-supplied dict only** — exactly one 10FZ.1 authorization
  report dict (the safe 35-field output of 10FZ). It confirms the supplied
  report is internally consistent with its contract; it does not execute
  routing, invoke models, call providers, or re-implement any
  ledger/reporter/verifier logic.
- **has no default production ledger path and no default config path** — if the
  required report is missing, it does not invent or open one; it reports the
  missing input and stops.
- **does not read a ledger file or any filesystem path** — it consumes only the
  caller-supplied dict; it never opens, scans, globs, walks, lists, or inspects
  any filesystem path (no `open(`, `os`, `pathlib`, `Path.*`).
- **does not call any provider, model, agent-launch, or backend module** — no
  runtime execution, no provider API, no model inference, no agent launching, no
  config mutation. It performs its own independent validation of the supplied
  envelope; it does not delegate to any runtime component and imports only
  `__future__`/`hashlib`/`json`/`typing`.
- **does not re-read or re-verify the ledger** — it is a status reporter over a
  10FZ.1 authorization report, not a ledger verifier. It does not recompute
  10FN, 10FT, or any proof-chain content hash.
- **recomputes only the 10FZ report `decision_id` from safe material** — the
  10FZ own `decision_id` is recomputed and compared to detect tampering of the
  supplied report; any source provenance/approval/policy decision IDs present in
  the report are treated as opaque syntax-checked identifiers (not recomputed),
  because 10GD forbids 10GF from reproducing source governance fields.
- **does not write, append, overwrite, truncate, delete, rename, or repair** —
  strictly read-only over the supplied report; no maintenance or recovery is in
  scope.
- **does not scan `world-sim/data`** — it never enumerates, globs, or walks
  directories; it consumes only the caller-supplied dict.
- **never reads/emits secrets, tokens, raw config, or equality values** — 10GF
  surfaces only safe status metadata already present in the supplied report
  (schema version, decision ID, status, ok) in sanitized form; no secret,
  token, raw credential, config value, path, or equality value is stored,
  logged, exported, or promoted.
- **never promotes results into runtime/world state** — the status result is
  returned to the caller as a safe dict only; no world, ledger, routing, or
  external state is updated or executed. 10GF *reports* authorization status; it
  does not *grant*, *execute*, or *re-authorize* approval.
- **never creates movement / map / route execution / event / NPC behavior** —
  10GF is observability/status reporting only; it produces no simulation or
  execution side effects.
- **keeps all `runtime`/`daemon`/`scheduler`/`network`/`world-data`/`gate-7`
  flags `False`** — its output hard-codes these to `False`.
- **gate-7 remains closed by absence** — 10GF enables no execution, provider,
  launcher, container, or Docker behavior.

The status result is a compact safe report: `ok=True` with a generic
`authorized_status` (or `not_authorized_status`) status when the supplied 10FZ.1
authorization report satisfies its envelope and is internally consistent
(authorized or not_authorized, with all gate flags False and the exact
forbidden-boundary list intact); otherwise a sanitized `invalid_report`/`ok=False`
status with only a generic error (no raw source errors, secrets, config, paths,
or equality values emitted). It must never emit raw source errors, secrets,
tokens, raw config, the ledger path, records, or equality values.

## Authorization Result

- 10GD **only names 10GF**. It is a spec phase; no implementation is performed
  here.
- 10GF implementation is **not** authorized by this phase. A future
  implementation requires:
  - a dedicated implementation spec (e.g. 10GF itself, or a follow-up),
  - **GPT-5.6 Sol/Luna** authorization (per `10CL`/`10CN`/`10CR`), and
  - explicit operator approval before commit.
- 10GF is a status reporter layered over the already-safe 10FZ.1 authorization
  report output; it does **not** open runtime execution and does **not** require
  or imply any provider/model call.
- 10GE will be the metadata-sync phase for 10GD (spec=N, sync=N+1).
- No code, backend, tests, runtime, or `world-sim/data` changes occur in this
  phase.

## Audit / Spec Confirmation

1. Inert-ledger observability proof-chain closed at 10FN (`afbc8d0`); each of
   the eight surfaces audited (14/14) and metadata-synced; gate-7 closed; `10CP`
   sole writer.
2. Provenance branch closed through 10FW and approval-authorization branch
   closed through 10GC: `10FX` (`6d06cc9`) → `10FY` (`f8e1743`) → `10FZ`
   (`86add55`) → `10GA` (`faefa01`, hash `bd059d9`) → `10GB` (`9f95e1f`) →
   `10GC` (`b579790`, hash `eb4b0e8`); `10FZ.1` is the current safe terminal
   approval-authorization artifact; `10GB` audit confirmed 14/14 boundary checks
   PASS.
3. Branch transition confirmed: approval authorization reporting (10FZ) →
   authorization report status reporting (10GF). `10GF` is a status reporter over
   the caller-supplied 10FZ.1 authorization report, **not** a routing executor,
   **not** an approval re-authorizer, and **not** a recursive
   approval/verification verifier.
4. No new bool ingestion; `10GF` (if implemented later) reuses strict built-in
   type checks; no ledger/file/provider/model/config/agent access.
5. `10CP` remains the only writer — preserved: `10GF` does not call `10CP`.
6. No batch orchestrator, no local-sim bridge, no gate-7 work named here.
7. No production `world-sim/data` access in this docs phase — only
   `world-sim/docs/` and root `README.md` / `world-sim/docs/phase_index.md`
   are touched.

## Checks

- `git diff --check` — clean (docs-only additions).
- `git diff --numstat` — three authorized file changes:
  `world-sim/docs/phase_10gd_next_runtime_boundary_candidate_spec.md` (new),
  `README.md` (+1 line), `world-sim/docs/phase_index.md` (+1 row).
- `git status -sb` — only the three authorized files modified/added; no backend,
  tests, runtime, or data changes.
- CRLF — 0 on all touched files (LF only).

## Status

Docs-only spec complete. Working tree modified (three authorized files); not
committed per instruction. Awaiting user go-ahead to commit/push 10GD, then 10GE
metadata sync if the N/N+1 convention is applied.

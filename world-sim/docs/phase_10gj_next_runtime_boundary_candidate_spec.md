# Phase 10GJ — Next Runtime Boundary Candidate Spec

Docs-only specification naming the single next authorized runtime-boundary
candidate. This phase performs no implementation, touches no backend/tests
runtime code or `world-sim/data`, and stops before commit.

- Repo: `S:\Genesis Kernel World Sim`
- Baseline: `d6d2b26 docs: record 10GI metadata hash`
- Mode: docs-only spec (cheap/free OK; no GPT-5.6 required)
- Out of scope: backend, tests, runtime, `world-sim/data`, daemon, scheduler,
  network, provider, launcher, container, Docker, PatchRaccoon, agent configs

## Context

The inert-ledger observability proof-chain is **closed** (at 10FN,
`afbc8d0`). A governance/provenance branch was opened at 10FR and is now fully
closed through 10FW, a governance approval-authorization branch was opened at
10FX and is now fully closed through 10GC, and a governance authorization-report
**status-report** branch was opened at 10GD and is now fully closed through
10GI:

- `10GD` (`af76125`) — next-candidate spec naming **10GF**
- `10GE` (`650a86b`) — sync 10GD metadata (`a569dee` hash correction)
- `10GF` (`b93f71e`) — Minimal Inert Model Routing Authorization Report Status
  Reporter (implementation; 298 targeted tests, 337 optional 10FZ regression, 238
  optional 10FT regression, 184 optional 10FN regression)
- `10GG` (`6ee3735`) — sync 10GF metadata (`293a080` hash correction)
- `10GH` (`14276f3`) — post-10GF runtime boundary audit (14/14 checks PASS)
- `10GI` (`d49c6d8`) — sync 10GH metadata (`d6d2b26` hash correction)

`10GF.1` is now the safe terminal artifact of the status-report branch: the
exact 30-field authorization report status report output of
`create_minimal_inert_model_routing_authorization_report_status_report` /
`export_minimal_inert_model_routing_authorization_report_status_report`. It
answers "given a 10FZ.1 authorization report that a caller already produced,
what is its compact status summary — authorized_status / not_authorized_status
or invalid — without re-deriving or re-attesting the underlying approval
decision?" — but it is observability only and performs no execution.

**The status-report branch does not yet answer the verification question:**
"given a 10GF.1 status report that a caller already produced, is it internally
consistent and untampered — and what is its verification status — without
re-deriving or re-attesting the underlying 10FZ authorization decision?" Adding
another recursive authorization reporter would only deepen a closed branch. The
right next move is a *new* trust surface: **authorization report status
verification** layered over the already-safe 10GF.1 output. This is a verifier,
**not** a routing executor, **not** an approval re-authorizer, and **not** a
recursive authorization/verification verifier that re-derives source approval.

## Candidate Named

**10GL — Minimal Inert Model Routing Authorization Report Status Verification
Verifier Status Reporter**

This is the single authorized next candidate. No other candidate is named by
this phase. (Candidate identity is proposed here; operator confirmation at
commit is expected, per the session's review-contingent pattern.)

10GL is specified to be:

- **pure read-only verification** — performs no mutation of any kind; it never
  touches a ledger file or any runtime component for writing or reading, and
  never alters a supplied status report. It is a *verifier over a status
  report*, not an executor or re-authorizer.
- **in-process / caller-driven** — runs only when a caller supplies one 10GF.1
  status report dict already produced by 10GF; it never starts work on its own.
- **consumes one caller-supplied dict only** — exactly one 10GF.1 status report
  dict (the safe 30-field output of 10GF). It confirms the supplied report is
  internally consistent with its contract; it does not execute routing, invoke
  models, call providers, or re-implement any ledger/reporter logic.
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
- **does not re-read or re-verify the ledger** — it is a verifier over a 10GF.1
  status report, not a ledger verifier. It does not recompute 10FN, 10FT, 10FZ,
  or any proof-chain content hash.
- **recomputes only the 10GF report `decision_id` from safe material** — the
  10GF own `decision_id` is recomputed and compared to detect tampering of the
  supplied report; any source authorization/provenance/policy/approval decision
  IDs present in the report are treated as opaque syntax-checked identifiers
  (not recomputed), because 10GJ forbids 10GL from reproducing source
  governance fields.
- **does not write, append, overwrite, truncate, delete, rename, or repair** —
  strictly read-only over the supplied report; no maintenance or recovery is in
  scope.
- **does not scan `world-sim/data`** — it never enumerates, globs, or walks
  directories; it consumes only the caller-supplied dict.
- **never reads/emits secrets, tokens, raw config, or equality values** — 10GL
  surfaces only safe status metadata already present in the supplied report
  (schema version, decision ID, status, ok) in sanitized form; no secret, token,
  raw credential, config value, path, or equality value is stored, logged,
  exported, or promoted.
- **never promotes results into runtime/world state** — the verification result
  is returned to the caller as a safe dict only; no world, ledger, routing, or
  external state is updated or executed. 10GL *verifies* authorization report
  status; it does not *grant*, *execute*, or *re-authorize* approval.
- **never creates movement / map / route execution / event / NPC behavior** —
  10GL is observability/verification only; it produces no simulation or
  execution side effects.
- **keeps all `runtime`/`daemon`/`scheduler`/`network`/`world-data`/`gate-7`
  flags `False`** — its output hard-codes these to `False`.
- **gate-7 remains closed by absence** — 10GL enables no execution, provider,
  launcher, container, or Docker behavior.

The verification result is a compact safe report: `ok=True` with a generic
`verified_status` (or other positive verification status) when the supplied
10GF.1 status report satisfies its envelope and its recomputed 10GF decision ID
matches (authorized_status / not_authorized_status, with all gate flags False
and the exact claim boundary intact); otherwise a sanitized `invalid_report`/
`ok=False` status with only a generic error (no raw source errors, secrets,
config, paths, or equality values emitted). It must never emit raw source
errors, secrets, tokens, raw config, the ledger path, records, or equality
values.

## Authorization Result

- 10GJ **only names 10GL**. It is a spec phase; no implementation is performed
  here.
- 10GL implementation is **not** authorized by this phase. A future
  implementation requires:
  - a dedicated implementation spec (e.g. 10GL itself, or a follow-up),
  - **GPT-5.6 Sol/Luna** authorization (per `10CL`/`10CN`/`10CR`), and
  - explicit operator approval before commit.
- 10GL is a verifier layered over the already-safe 10GF.1 status report output;
  it does **not** open runtime execution and does **not** require or imply any
  provider/model call.
- 10GK will be the metadata-sync phase for 10GJ (spec=N, sync=N+1).
- No code, backend, tests, runtime, or `world-sim/data` changes occur in this
  phase.

## Audit / Spec Confirmation

1. Inert-ledger observability proof-chain closed at 10FN (`afbc8d0`); each of
   the eight surfaces audited (14/14) and metadata-synced; gate-7 closed; `10CP`
   sole writer.
2. Provenance branch closed through 10FW and approval-authorization branch
   closed through 10GC; status-report branch now closed through 10GI:
   `10GD` (`af76125`) → `10GE` (`650a86b`, hash `a569dee`) → `10GF` (`b93f71e`)
   → `10GG` (`6ee3735`, hash `293a080`) → `10GH` (`14276f3`, 14/14 boundary
   checks PASS) → `10GI` (`d49c6d8`, hash `d6d2b26`); `10GF.1` is the current
   safe terminal status-report artifact; `10GH` audit confirmed 14/14 boundary
   checks PASS.
3. Branch transition confirmed: authorization report status reporting (10GF) →
   authorization report status verification (10GL). `10GL` is a verifier over the
   caller-supplied 10GF.1 status report, **not** a routing executor, **not** an
   approval re-authorizer, and **not** a recursive
   authorization/verification verifier re-deriving source approval.
4. No new bool ingestion; `10GL` (if implemented later) reuses strict built-in
   type checks; no ledger/file/provider/model/config/agent access.
5. `10CP` remains the only writer — preserved: `10GL` does not call `10CP`.
6. No batch orchestrator, no local-sim bridge, no gate-7 work named here.
7. No production `world-sim/data` access in this docs phase — only
   `world-sim/docs/` and root `README.md` / `world-sim/docs/phase_index.md`
   are touched.

## Checks

- `git diff --check` — clean (docs-only additions).
- `git diff --numstat` — three authorized file changes:
  `world-sim/docs/phase_10gj_next_runtime_boundary_candidate_spec.md` (new),
  `README.md` (+1 line), `world-sim/docs/phase_index.md` (+1 row).
- `git status -sb` — only the three authorized files modified/added; no backend,
  tests, runtime, or data changes.
- CRLF — 0 on all touched files (LF only).

## Status

Docs-only spec complete. Working tree modified (three authorized files); not
committed per instruction. Awaiting user go-ahead to commit/push 10GJ, then 10GK
metadata sync if the N/N+1 convention is applied.

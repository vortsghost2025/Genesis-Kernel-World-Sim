# Phase 10GP — Next Runtime Boundary Candidate Spec

Docs-only specification naming the single next authorized runtime-boundary
candidate. This phase performs no implementation, touches no backend/tests
runtime code or `world-sim/data`, and stops before commit.

- Repo: `S:\Genesis Kernel World Sim`
- Baseline: `0cd661f docs: record 10GO metadata hash`
- Mode: docs-only spec (cheap/free OK; no GPT-5.6 required)
- Out of scope: backend, tests, runtime, `world-sim/data`, daemon, scheduler,
  network, provider, launcher, container, Docker, PatchRaccoon, agent configs

## Context

The inert-ledger observability proof-chain is **closed** (at 10FN,
`afbc8d0`). The provenance branch is closed through 10FW, the
approval-authorization branch is closed through 10GC, the authorization-report
status-report branch is closed through 10GI, and the authorization-report
status-verification branch is now fully closed through 10GO:

- `10GJ` (`c025c0e`) — next-candidate spec naming **10GL**
- `10GK` (`5b91e64`) — sync 10GJ metadata (`08f7766` hash correction)
- `10GL` (`8bb21c4`) — Minimal Inert Model Routing Authorization Report
  Status Verification Verifier Status Reporter (implementation; 307 targeted
  tests, 298 optional 10GF regression, 337 optional 10FZ regression, 238
  optional 10FT regression, 184 optional 10FN regression)
- `10GM` (`279683b`) — sync 10GL metadata (`f7838bd` hash correction)
- `10GN` (`dd11f1c`) — post-10GL runtime boundary audit (14/14 checks PASS)
- `10GO` (`caba931`) — sync 10GN metadata (`0cd661f` hash correction)

`10GL.1` is now the safe terminal artifact of the status-verification branch:
the exact 34-field verification report output of
`create_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_report`
/
`export_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_report`.
It answers "given a 10GF.1 status report that a caller already produced, is it
internally consistent and untampered — and what is its verification status —
without re-deriving or re-attesting the underlying 10FZ authorization decision?"
— but it is observability only and performs no execution.

**The status-verification branch does not yet answer the
verification-of-verification question:** "given a 10GL.1 verification report
that a caller already produced, is *that verification report* internally
consistent and untampered — and what is its meta-verification status — without
re-deriving or re-attesting the underlying 10GF status report or the 10FZ
authorization decision?" Adding another recursive authorization reporter would
only deepen a closed branch. The right next move is a *new* trust surface:
**authorization report status verification verifier status verification** layered
over the already-safe 10GL.1 output. This is a meta-verifier, **not** a routing
executor, **not** an approval re-authorizer, **not** a recursive
authorization/verification verifier that re-derives source approval, and **not**
a recursive verifier that re-derives the 10GF status report. It verifies exactly
one 10GL.1 verification report by recomputing only the 10GL decision ID from the
safe 34-field 10GL.1 material; it treats all source status-report and source
authorization/provenance/policy/approval decision IDs as opaque syntax-checked
identifiers.

## Candidate Named

**10GR — Minimal Inert Model Routing Authorization Report Status Verification
Verifier Status Verification Verifier Status Reporter**

This is the single authorized next candidate. No other candidate is named by
this phase. (Candidate identity is proposed here; operator confirmation at
commit is expected, per the session's review-contingent pattern.)

10GR is specified to be:

- **pure read-only meta-verification** — performs no mutation of any kind; it
  never touches a ledger file or any runtime component for writing or reading,
  and never alters a supplied verification report. It is a *verifier over a
  verification report*, not an executor or re-authorizer.
- **in-process / caller-driven** — runs only when a caller supplies one 10GL.1
  verification report dict already produced by 10GL; it never starts work on its
  own.
- **consumes one caller-supplied dict only** — exactly one 10GL.1 verification
  report dict (the safe 34-field output of 10GL). It confirms the supplied
  verification report is internally consistent with its contract; it does not
  execute routing, invoke models, call providers, or re-implement any
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
- **does not re-read or re-verify the ledger** — it is a meta-verifier over a
  10GL.1 verification report, not a ledger verifier. It does not recompute 10FN,
  10FT, 10FZ, 10GF, or any proof-chain content hash.
- **recomputes only the 10GL verification `decision_id` from safe material** —
  the 10GL own `decision_id` is recomputed and compared to detect tampering of
  the supplied verification report; any source status-report, source
  authorization, provenance, policy, approval, lane, provider, and model
  decision IDs present in the verification report are treated as opaque
  syntax-checked identifiers (not recomputed), because 10GP forbids 10GR from
  reproducing source governance or source status-report fields beyond
  structural syntax validation.
- **does not write, append, overwrite, truncate, delete, rename, or repair** —
  strictly read-only over the supplied verification report; no maintenance or
  recovery is in scope.
- **does not scan `world-sim/data`** — it never enumerates, globs, or walks
  directories; it consumes only the caller-supplied dict.
- **never reads/emits secrets, tokens, raw config, or equality values** — 10GR
  surfaces only safe verification metadata already present in the supplied
  verification report (schema version, decision ID, verification status, ok) in
  sanitized form; no secret, token, raw credential, config value, path, or
  equality value is stored, logged, exported, or promoted.
- **never promotes results into runtime/world state** — the meta-verification
  result is returned to the caller as a safe dict only; no world, ledger,
  routing, or external state is updated or executed. 10GR *verifies*
  authorization report status verification; it does not *grant*, *execute*, or
  *re-authorize* approval, and does not *re-verify* the 10GF status report
  beyond structural syntax checks on the supplied 10GL.1 output.
- **never creates movement / map / route execution / event / NPC behavior** —
  10GR is observability/verification only; it produces no simulation or
  execution side effects.
- **keeps all `runtime`/`daemon`/`scheduler`/`network`/`world-data`/`gate-7`
  flags `False`** — its output hard-codes these to `False`.
- **gate-7 remains closed by absence** — 10GR enables no execution, provider,
  launcher, container, or Docker behavior.

The meta-verification result is a compact safe report: `ok=True` with a generic
`verified_verification_status` when the supplied 10GL.1 verification report
satisfies its envelope and its recomputed 10GL decision ID matches
(`verified_authorized_verification_status` /
`verified_not_authorized_verification_status` corresponding to the source
verification status, with all gate flags False and the exact claim boundary
intact); otherwise a sanitized `invalid_verification_report`/`ok=False` status
with only a generic error (no raw source errors, secrets, config, paths, or
equality values emitted). It must never emit raw source errors, secrets,
tokens, raw config, the ledger path, records, or equality values.

## Authorization Result

- 10GP **only names 10GR**. It is a spec phase; no implementation is performed
  here.
- 10GR implementation is **not** authorized by this phase. A future
  implementation requires:
  - a dedicated implementation spec (e.g. 10GR itself, or a follow-up),
  - **GPT-5.6 Sol/Luna** authorization (per `10CL`/`10CN`/`10CR`), and
  - explicit operator approval before commit.
- 10GR is a meta-verifier layered over the already-safe 10GL.1 verification
  report output; it does **not** open runtime execution and does **not** require
  or imply any provider/model call.
- 10GQ will be the metadata-sync phase for 10GP (spec=N, sync=N+1).
- No code, backend, tests, runtime, or `world-sim/data` changes occur in this
  phase.

## Audit / Spec Confirmation

1. Inert-ledger observability proof-chain closed at 10FN (`afbc8d0`); each of
   the eight surfaces audited (14/14) and metadata-synced; gate-7 closed;
   `10CP` sole writer.
2. Provenance branch closed through 10FW, approval-authorization branch closed
   through 10GC, status-report branch closed through 10GI, and
   status-verification branch now closed through 10GO:
   `10GJ` (`c025c0e`) → `10GK` (`5b91e64`, hash `08f7766`) → `10GL`
   (`8bb21c4`) → `10GM` (`279683b`, hash `f7838bd`) → `10GN` (`dd11f1c`,
   14/14 boundary checks PASS) → `10GO` (`caba931`, hash `0cd661f`); `10GL.1`
   is the current safe terminal verification artifact; `10GN` audit confirmed
   14/14 boundary checks PASS.
3. Branch transition confirmed: authorization report status verification (10GL)
   → authorization report status verification verifier status verification
   (10GR). `10GR` is a meta-verifier over the caller-supplied 10GL.1
   verification report, **not** a routing executor, **not** an approval
   re-authorizer, **not** a recursive authorization/verification verifier
   re-deriving source approval, and **not** a recursive verifier re-deriving
   the 10GF status report — it recomputes only the 10GL decision ID from safe
   10GL.1 material, treating all deeper source IDs as opaque.
4. No new bool ingestion; `10GR` (if implemented later) reuses strict built-in
   type checks; no ledger/file/provider/model/config/agent access.
5. `10CP` remains the only writer — preserved: `10GR` does not call `10CP`.
6. No batch orchestrator, no local-sim bridge, no gate-7 work named here.
7. No production `world-sim/data` access in this docs phase — only
   `world-sim/docs/` and root `README.md` / `world-sim/docs/phase_index.md`
   are touched.

## Checks

- `git diff --check` — clean (docs-only additions).
- `git diff --numstat` — three authorized file changes:
  `world-sim/docs/phase_10gp_next_runtime_boundary_candidate_spec.md` (new),
  `README.md` (+1 line), `world-sim/docs/phase_index.md` (+1 row).
- `git status -sb` — only the three authorized files modified/added; no backend,
  tests, runtime, or data changes.
- CRLF — 0 on all touched files (LF only).

## Status

Docs-only spec complete. Working tree modified (three authorized files); not
committed per instruction. Awaiting user go-ahead to commit/push 10GP, then 10GQ
metadata sync if the N/N+1 convention is applied.

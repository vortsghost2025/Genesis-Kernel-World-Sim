# Phase 10FR — Next Runtime Boundary Candidate Spec

Docs-only specification naming the single next authorized runtime-boundary
candidate. This phase performs no implementation, touches no backend/tests
runtime code or `world-sim/data`, and stops before commit.

- Repo: `S:\Genesis Kernel World Sim`
- Baseline: `c716a98 docs: record 10FQ metadata hash`
- Mode: docs-only spec (GLM/free OK; no GPT-5.6 required)
- Out of scope: backend, tests, runtime, `world-sim/data`, daemon, scheduler,
  network, provider, launcher, container, Docker, PatchRaccoon, agent configs

## Context

The inert-ledger observability proof-chain is now **closed**. It spans eight
independent, inert, caller-driven surfaces sharing the same trust boundary
(no ledger file access, no `10CP` writer call, no runtime promotion):

- read-back (`10DX`, `f03f83d`)
- summary (`10ED`, `9671485`)
- status bundle (`10EJ`, `469c374`)
- status digest (`10EP`, `69bf981`)
- status digest verification (`10EV`, `f228d7e`)
- status digest verification reporting (`10FB`, `0818c49`)
- status digest verification report verification (`10FH`, `6446c31`)
- status reporter over 10FH (`10FN`, `afbc8d0`)

Each was audited (`10DZ`, `10EF`, `10EL`, `10ER`, `10EX`, `10FD`, `10FJ`,
`10FP`) and metadata-synced (`10DY`, `10EG`, `10EM`, `10ES`, `10EY`, `10FE`,
`10FK`, `10FO`, `10FQ`). Every audit confirmed 14/14 boundary checks PASS;
gate-7 remains closed; `10CP` remains the only writer. The `10FN.1` status
report (the exact 19-field output of
`create_minimal_inert_ledger_status_digest_verification_verifier_status_report`
/
`export_minimal_inert_ledger_status_digest_verification_verifier_status_report`)
is the current safe terminal artifact of this observability chain. `10FN`
already reports the verified 10FH.1 verification report as a canonical status
artifact — it is observability only, not another recursive verifier over the
chain.

**The proof-chain branch ends at 10FN.** Continuing to add more ledger
verifiers/reporters would only deepen a closed branch. The right next move is a
*new* trust surface: **model/routing provenance governance**. This answers a
different question than ledger integrity — not "is the ledger consistent?" but
"which model lane was authorized to produce which artifact class, under what
authority, with what pinned model/provider identity, and what boundaries were
forbidden?" It is a provenance reporter over a caller-supplied routing policy
artifact, **not** a ledger verifier and **not** another recursive verifier.

## Candidate Named

**10FT — Minimal Inert Model Routing Provenance Reporter**

This is the single authorized next candidate. No other candidate is named by
this phase.

10FT is specified to be:

- **pure read-only provenance reporting** — performs no mutation of any kind;
  it never touches a ledger file for writing or reading, and never alters a
  supplied routing/provenance policy artifact. It is a *reporter over a routing
  policy artifact*, not a verifier.
- **in-process / caller-driven** — runs only when a caller supplies a
  routing/provenance policy artifact (a dict already produced by an authorized
  routing/governance caller); it never starts work on its own.
- **consumes caller-supplied routing/provenance policy artifact dict only** —
  exactly one caller-supplied dict conforming to the defined 10FT envelope; it
  confirms the supplied artifact is internally consistent with the 10FT contract
  (authorized lane, artifact class, authority, pinned model/provider identity,
  forbidden boundaries); it does not execute routing, invoke models, or call
  providers, and does not re-implement any ledger/reporter/verifier logic.
- **has no default production ledger path and no default config path** — if a
  required artifact is missing, it does not invent or open one; it reports the
  missing input and stops.
- **does not read a ledger file or any filesystem path** — it consumes only the
  caller-supplied dict; it never opens, scans, globs, walks, lists, or inspects
  any filesystem path (no `open(`, `os`, `pathlib`, `Path.*`).
- **does not call any provider, model, agent-launch, or backend module** — no
  runtime execution, no provider API, no model inference, no agent launching,
  no config mutation. It performs its own independent validation of the supplied
  routing/provenance policy artifact envelope; it does not delegate to any
  runtime component and imports only `__future__`/`hashlib`/`json`/`typing`.
- **does not re-read or re-verify the ledger** — it is a provenance reporter
  over a routing policy artifact, not a ledger verifier.
- **recomputes only the 10FT `decision_id` from safe material** — the 10FT own
  `decision_id` is recomputed and compared to detect tampering of the artifact;
  any source lane/authority decision IDs present in the artifact are treated as
  opaque syntax-checked identifiers (not recomputed), because 10FR forbids 10FT
  from reproducing source governance fields.
- **does not write, append, overwrite, truncate, delete, rename, or repair** —
  strictly read-only over the supplied artifact; no maintenance or recovery is
  in scope.
- **does not scan `world-sim/data`** — it never enumerates, globs, or walks
  directories; it consumes only the caller-supplied dict.
- **never reads/emits secrets, tokens, raw config, or equality values** — 10FT
  surfaces only safe provenance metadata already present in the supplied
  artifact (authorized lane, artifact class, authority, pinned model/provider
  identity, forbidden boundaries) in sanitized form; no secret, token, raw
  credential, config value, path, or equality value is stored, logged, exported,
  or promoted.
- **never promotes results into runtime/world state** — the provenance result is
  returned to the caller as a safe dict only; no world, ledger, routing, or
  external state is updated or executed. 10FT *reports* routing provenance; it
  does not *execute* routing.
- **never creates movement / map / route execution / event / NPC behavior** —
  10FT is observability/governance reporting only; it produces no simulation or
  execution side effects.
- **keeps all `runtime`/`daemon`/`scheduler`/`network`/`world-data`/`gate-7`
  flags `False`** — its output hard-codes these to `False`.
- **gate-7 remains closed by absence** — 10FT enables no execution, provider,
  launcher, container, or Docker behavior.

The provenance result is a safe report: `ok=True` with a generic `verified`
status when the supplied artifact satisfies the 10FT envelope and its recomputed
`decision_id` matches; otherwise a sanitized `invalid_report`/`ok=False` status
with only a generic error (no raw source errors, secrets, config, paths, or
equality values emitted). It must never emit raw source errors, secrets, tokens,
raw config, the ledger path, records, or equality values.

## Authorization Result

- 10FR **only names 10FT**. It is a spec phase; no implementation is performed
  here.
- 10FT implementation is **not** authorized by this phase. A future
  implementation requires:
  - a dedicated implementation spec (e.g. 10FT itself, or a follow-up),
  - **GPT-5.6 Sol/Luna** authorization (per `10CL`/`10CN`/`10CR`), and
  - explicit operator approval before commit.
- 10FS will be the metadata-sync phase for 10FR (spec=N, sync=N+1).
- No code, backend, tests, runtime, or `world-sim/data` changes occur in this
  phase.

## Audit / Spec Confirmation

1. Inert-ledger observability proof-chain closed: `10DX` (`f03f83d`) → `10ED`
   (`9671485`) → `10EJ` (`469c374`) → `10EP` (`69bf981`) → `10EV` (`f228d7e`)
   → `10FB` (`0818c49`) → `10FH` (`6446c31`) → `10FN` (`afbc8d0`); each audited
   (14/14) and metadata-synced; gate-7 closed; `10CP` sole writer.
2. `10FN.1` status report is the current safe terminal observability artifact;
   `10FN` is observability only, not another recursive verifier over the chain.
3. Branch transition confirmed: proof-chain closure (at 10FN) → model/routing
   provenance governance. `10FT` is a provenance reporter over a
   caller-supplied routing policy artifact, **not** a ledger verifier and **not**
   another recursive verifier.
4. No new bool ingestion; `10FT` (if implemented later) reuses strict built-in
   type checks; no ledger/file/provider/model/config/agent access.
5. `10CP` remains the only writer — preserved: `10FT` does not call `10CP`.
6. No batch orchestrator, no local-sim bridge, no gate-7 work named here.
7. No production `world-sim/data` access in this docs phase — only
   `world-sim/docs/` and root `README.md` / `world-sim/docs/phase_index.md`
   are touched.

## Checks

- `git diff --check` — clean (docs-only additions).
- `git diff --numstat` — three authorized file changes:
  `world-sim/docs/phase_10fr_next_runtime_boundary_candidate_spec.md` (new),
  `README.md` (+1 line), `world-sim/docs/phase_index.md` (+1 row).
- `git status -sb` — only the three authorized files modified/added; no backend,
  tests, runtime, or data changes.
- CRLF — 0 on all touched files (LF only).

## Status

Docs-only spec complete. Working tree modified (three authorized files); not
committed per instruction. Awaiting user go-ahead to commit/push 10FR, then 10FS
metadata sync if the N/N+1 convention is applied.

# Phase 10FX — Next Runtime Boundary Candidate Spec

Docs-only specification naming the single next authorized runtime-boundary
candidate. This phase performs no implementation, touches no backend/tests
runtime code or `world-sim/data`, and stops before commit.

- Repo: `S:\Genesis Kernel World Sim`
- Baseline: `1ac030a docs: record 10FW metadata hash`
- Mode: docs-only spec (GLM/free OK; no GPT-5.6 required)
- Out of scope: backend, tests, runtime, `world-sim/data`, daemon, scheduler,
  network, provider, launcher, container, Docker, PatchRaccoon, agent configs

## Context

The inert-ledger observability proof-chain is **closed** (at 10FN,
`afbc8d0`). A new governance/provenance branch was opened at 10FR and is now
fully closed through 10FW:

- `10FR` (`6d9aaa9`) — next-candidate spec naming **10FT**
- `10FS` (`43032c2`) — sync 10FR metadata
- `10FT` (`d352d01`) — Minimal Inert Model Routing Provenance Reporter
  (implementation; 238 targeted tests, 184 optional 10FN regression)
- `10FU` (`1731522`) — sync 10FT metadata (`88a739b` hash correction)
- `10FV` (`106d05a`) — post-10FT runtime boundary audit (14/14 checks PASS)
- `10FW` (`58a9537`) — sync 10FV metadata (`1ac030a` hash correction)

`10FT.1` is now the safe terminal artifact of the provenance branch: the exact
28-field verified_provenance output of
`create_minimal_inert_model_routing_provenance_report` /
`export_minimal_inert_model_routing_provenance_report`. It answers "which model
lane was authorized to produce which artifact class, under what authority, with
what pinned model/provider identity, and what boundaries were forbidden?" — but
it is observability only and performs no execution.

**The provenance branch does not yet answer the authorization question:**
"given a verified provenance report, has an operator explicitly approved this
routing for execution, under what approval authority, for what action, and with
what boundaries?" Adding another recursive provenance verifier would only deepen
a closed branch. The right next move is a *new* trust surface: **operator
approval / execution-authorization governance** layered over the already-safe
10FT.1 provenance output. This is a governance reporter, **not** a routing
executor and **not** a recursive provenance verifier.

## Candidate Named

**10FZ — Minimal Inert Model Routing Approval Authorization Reporter**

This is the single authorized next candidate. No other candidate is named by
this phase.

10FZ is specified to be:

- **pure read-only approval-authorization reporting** — performs no mutation of
  any kind; it never touches a ledger file or any runtime component for writing
  or reading, and never alters a supplied provenance report or approval
  artifact. It is a *reporter over a provenance report plus an approval
  artifact*, not an executor.
- **in-process / caller-driven** — runs only when a caller supplies both (a) a
  10FT.1 verified_provenance report dict already produced by 10FT, and (b) an
  operator approval/authorization artifact dict already produced by an
  authorized governance caller; it never starts work on its own.
- **consumes two caller-supplied dicts only** — exactly one 10FT.1 provenance
  report dict (the safe 28-field output of 10FT) and exactly one
  caller-supplied operator approval/authorization artifact dict conforming to a
  defined 10FZ approval envelope. It confirms each supplied artifact is
  internally consistent with its contract; it does not execute routing, invoke
  models, call providers, or re-implement any ledger/reporter/verifier logic.
- **has no default production ledger path and no default config path** — if a
  required artifact is missing, it does not invent or open one; it reports the
  missing input and stops.
- **does not read a ledger file or any filesystem path** — it consumes only the
  two caller-supplied dicts; it never opens, scans, globs, walks, lists, or
  inspects any filesystem path (no `open(`, `os`, `pathlib`, `Path.*`).
- **does not call any provider, model, agent-launch, or backend module** — no
  runtime execution, no provider API, no model inference, no agent launching,
  no config mutation. It performs its own independent validation of both
  supplied envelopes; it does not delegate to any runtime component and imports
  only `__future__`/`hashlib`/`json`/`typing`.
- **does not re-read or re-verify the ledger** — it is an approval-authorization
  reporter over a provenance report and an approval artifact, not a ledger
  verifier. It does not recompute 10FN or any proof-chain content hash.
- **recomputes only the 10FZ `decision_id` from safe material** — the 10FZ own
  `decision_id` is recomputed and compared to detect tampering of the
  authorization artifact; any 10FT `provenance_report_decision_id` or source
  approval/authority decision IDs present in the artifacts are treated as opaque
  syntax-checked identifiers (not recomputed), because 10FX forbids 10FZ from
  reproducing source governance fields.
- **does not write, append, overwrite, truncate, delete, rename, or repair** —
  strictly read-only over the supplied artifacts; no maintenance or recovery is
  in scope.
- **does not scan `world-sim/data`** — it never enumerates, globs, or walks
  directories; it consumes only the two caller-supplied dicts.
- **never reads/emits secrets, tokens, raw config, or equality values** — 10FZ
  surfaces only safe authorization metadata already present in the supplied
  artifacts (provenance identity, approval authority, approved action, approved
  artifact class, forbidden boundaries) in sanitized form; no secret, token,
  raw credential, config value, path, or equality value is stored, logged,
  exported, or promoted.
- **never promotes results into runtime/world state** — the authorization result
  is returned to the caller as a safe dict only; no world, ledger, routing, or
  external state is updated or executed. 10FZ *reports* approval
  authorization; it does not *grant* or *execute* approval.
- **never creates movement / map / route execution / event / NPC behavior** —
  10FZ is observability/governance reporting only; it produces no simulation or
  execution side effects.
- **keeps all `runtime`/`daemon`/`scheduler`/`network`/`world-data`/`gate-7`
  flags `False`** — its output hard-codes these to `False`.
- **gate-7 remains closed by absence** — 10FZ enables no execution, provider,
  launcher, container, or Docker behavior.

The authorization result is a safe report: `ok=True` with a generic
`authorized` (or `not_authorized`) status when the supplied 10FT.1 provenance
report and the supplied operator approval artifact each satisfy their envelopes
and the approval is consistent with the provenance (matching artifact class,
lane, and authority, and no forbidden boundary crossed); otherwise a sanitized
`invalid_report`/`ok=False` status with only a generic error (no raw source
errors, secrets, config, paths, or equality values emitted). It must never emit
raw source errors, secrets, tokens, raw config, the ledger path, records, or
equality values.

## Authorization Result

- 10FX **only names 10FZ**. It is a spec phase; no implementation is performed
  here.
- 10FZ implementation is **not** authorized by this phase. A future
  implementation requires:
  - a dedicated implementation spec (e.g. 10FZ itself, or a follow-up),
  - **GPT-5.6 Sol/Luna** authorization (per `10CL`/`10CN`/`10CR`), and
  - explicit operator approval before commit.
- 10FZ is a governance reporter layered over the already-safe 10FT.1 provenance
  output; it does **not** open runtime execution and does **not** require or
  imply any provider/model call.
- 10FY will be the metadata-sync phase for 10FX (spec=N, sync=N+1).
- No code, backend, tests, runtime, or `world-sim/data` changes occur in this
  phase.

## Audit / Spec Confirmation

1. Inert-ledger observability proof-chain closed at 10FN (`afbc8d0`); each of
   the eight surfaces audited (14/14) and metadata-synced; gate-7 closed; `10CP`
   sole writer.
2. Provenance branch closed through 10FW: `10FR` (`6d9aaa9`) → `10FS`
   (`43032c2`) → `10FT` (`d352d01`) → `10FU` (`1731522`, hash `88a739b`) →
   `10FV` (`106d05a`) → `10FW` (`58a9537`, hash `1ac030a`); `10FT.1` is the
   current safe terminal provenance artifact; `10FV` audit confirmed 14/14
   boundary checks PASS.
3. Branch transition confirmed: provenance reporting (10FT) → approval
   authorization governance (10FZ). `10FZ` is an approval-authorization reporter
   over the caller-supplied 10FT.1 provenance report plus a caller-supplied
   operator approval artifact, **not** a routing executor and **not** a
   recursive provenance verifier.
4. No new bool ingestion; `10FZ` (if implemented later) reuses strict built-in
   type checks; no ledger/file/provider/model/config/agent access.
5. `10CP` remains the only writer — preserved: `10FZ` does not call `10CP`.
6. No batch orchestrator, no local-sim bridge, no gate-7 work named here.
7. No production `world-sim/data` access in this docs phase — only
   `world-sim/docs/` and root `README.md` / `world-sim/docs/phase_index.md`
   are touched.

## Checks

- `git diff --check` — clean (docs-only additions).
- `git diff --numstat` — three authorized file changes:
  `world-sim/docs/phase_10fx_next_runtime_boundary_candidate_spec.md` (new),
  `README.md` (+1 line), `world-sim/docs/phase_index.md` (+1 row).
- `git status -sb` — only the three authorized files modified/added; no backend,
  tests, runtime, or data changes.
- CRLF — 0 on all touched files (LF only).

## Status

Docs-only spec complete. Working tree modified (three authorized files); not
committed per instruction. Awaiting user go-ahead to commit/push 10FX, then 10FY
metadata sync if the N/N+1 convention is applied.

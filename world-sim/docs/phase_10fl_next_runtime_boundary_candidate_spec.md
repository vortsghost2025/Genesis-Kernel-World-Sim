# Phase 10FL — Next Runtime Boundary Candidate Spec

Docs-only specification naming the single next authorized runtime-boundary
candidate. This phase performs no implementation, touches no backend/tests
runtime code or `world-sim/data`, and stops before commit.

- Repo: `S:\Genesis Kernel World Sim`
- Baseline: `f3219aa docs: record 10FK metadata hash`
- Mode: docs-only spec (GLM/free OK; no GPT-5.6 required)
- Out of scope: backend, tests, runtime, `world-sim/data`, daemon, scheduler,
  network, provider, launcher, container, Docker, PatchRaccoon, agent configs

## Context

Phase 10DX (`f03f83d`) closed the read-back loop: a pure read-only,
in-process, caller-driven verifier over one explicit existing 10CP NDJSON file
(`local_minimal_inert_ledger_readback_verifier.py`). It performs no write, no
scan, no backend/10CP call, and keeps every runtime/daemon/scheduler/network/
world-data/gate-7 flag `False`. Phase 10DZ (`f0fa3f9`) audited the committed
10DX and confirmed 14/14 boundary checks PASS.

Phase 10ED (`9671485`) closed the summary loop; 10EJ (`469c374`) the bundle
loop; 10EP (`69bf981`) the digest loop; 10EV (`f228d7e`) the digest-verification
loop; 10FB (`0818c49`) the digest-verification-reporting loop; 10FH (`6446c31`)
the digest-verification-report verification loop. Each was audited (10EF, 10EL,
10ER, 10EX, 10FD, 10FJ) and each synced with a metadata phase (10EG, 10EM,
10ES, 10EY, 10FE, 10FK). All six predecessor audits confirmed 14/14 boundary
checks PASS; gate-7 remains closed; 10CP remains the only writer.

The read-back (`10DX`), summary (`10ED`), status bundle (`10EJ`), status digest
(`10EP`), status digest verification (`10EV`), status digest verification
reporting (`10FB`), and status digest verification report verification (`10FH`)
surfaces now exist as seven independent, inert, caller-driven
reporters/verifiers sharing the same inert-ledger trust boundary: no ledger file
access, no 10CP writer call, no runtime promotion. The 10FH.1 verification report
(the exact 44-field output of
`verify_minimal_inert_ledger_status_digest_verification_report` /
`export_minimal_inert_ledger_status_digest_verification_verifier_report`) is the
current safe terminal artifact of this observability chain. 10FH already
performs the integrity verification of a supplied 10FB.1 digest report — it is
not another re-verifier over the whole source chain.

The next safest move is a **status reporter over the already-safe 10FH
output**: it turns a verified 10FH.1 verification report into a canonical,
sanitized status artifact that an external monitor/dashboard can consume,
without re-verifying the chain, re-reading the ledger, or adding any file/backend
access. This keeps the loop inert (observability only) and leaves gate-7 closed.
It does not re-run 10DX/10ED/10EJ/10EP/10EV/10FB/10FH logic, and does not promote
the report into any runtime/world state. It is a reporter, not another recursive
verifier.

## Candidate Named

**10FN — Minimal Inert Ledger Status Digest Verification Verifier Status Reporter**

This is the single authorized next candidate. No other candidate is named by
this phase.

10FN is specified to be:

- **pure read-only status reporting** — performs no mutation of any kind; it
  never touches a ledger file for writing or reading, and never alters a supplied
  10FH verification report. It is a *reporter over 10FH*, not a second verifier.
- **in-process / caller-driven** — runs only when a caller supplies a 10FH.1
  verification report (a dict already returned by
  `verify_minimal_inert_ledger_status_digest_verification_report` or
  `export_minimal_inert_ledger_status_digest_verification_verifier_report`); it
  never starts work on its own.
- **consumes caller-supplied 10FH.1 verification report dict only** — exactly one
  caller-supplied dict conforming to the exact 44-field 10FH.1 envelope; it
  confirms the structured report that
  `verify_minimal_inert_ledger_status_digest_verification_report` already returns
  is internally consistent with the 10FH.1 contract; it does not re-implement
  verification, reporting, digest, bundle, summary, or read-back logic, and does
  not re-read the ledger.
- **has no default production ledger path** — if a required report is missing, it
  does not invent or open one; it reports the missing input and stops.
- **does not read a ledger file** — it consumes only the caller-supplied 10FH
  dict; it never opens, opens-in-read, scans, globs, walks, lists, or inspects
  any filesystem path.
- **does not call the `10DX` verifier, the `10ED` reporter, the `10EJ` bundle
  reporter, the `10EP` digest reporter, the `10EV` digest verifier, the `10FB`
  verification reporter, the `10FH` verification verifier, or the `10CP` writer** —
  `10CP` remains the only writer, `10DX` the only verifier, `10ED` the only
  summary reporter, `10EJ` the only status bundle reporter, `10EP` the only digest
  reporter, `10EV` the only digest verifier, `10FB` the only verification reporter,
  and `10FH` the only verification verifier; 10FN never imports or invokes any of
  them. 10FN performs its own independent validation of the exact 44-field 10FH.1
  envelope rather than delegating to 10FH.
- **does not re-read or re-verify the ledger** — it trusts the caller-supplied
  10FH verification report; no second read or re-verification path is added.
- **recomputes only the 10FH `verifier_decision_id` from safe 10FH material** —
  the 10FH own `verifier_decision_id` is recomputed and compared to detect
  tampering of the verification report artifact; the source `10FB-`, `10EV-`,
  `10EP-`, and `10EJ-` decision IDs are treated as opaque syntax-checked
  identifiers (not recomputed), because 10FL forbids 10FN from re-verifying the
  ledger or producing source fields.
- **does not write, append, overwrite, truncate, delete, rename, or repair** —
  strictly read-only over the supplied report; no ledger or report maintenance
  or recovery is in scope.
- **does not scan `world-sim/data`** — it never enumerates, globs, or walks
  directories; it consumes only the caller-supplied 10FH dict.
- **never reads/emits `equality_signal_value`** — 10FN may surface counts or
  known signal *types* already present in the 10FH envelope, but must never read,
  store, log, export, or promote any signal *value*; the value field is out of
  scope by design.
- **never promotes results into runtime/world state** — the status result is
  returned to the caller as a safe dict only; no world, ledger, or external state
  is updated.
- **never creates movement / map / route / event / NPC behavior** — 10FN is
  observability only; it produces no simulation side effects.
- **keeps all `runtime`/`daemon`/`scheduler`/`network`/`world-data`/`gate-7`
  flags `False`** — its output hard-codes these to `False`, matching the 10DX,
  10ED, 10EJ, 10EP, 10EV, 10FB, and 10FH contracts.
- **gate-7 remains closed by absence** — 10FN enables no execution, provider,
  launcher, container, or Docker behavior.

The status result is a safe report: `ok=True` with a generic `verified` status
when the supplied report satisfies the exact 44-field 10FH.1 envelope and its
recomputed `verifier_decision_id` matches; otherwise a sanitized
`invalid_report`/`ok=False` status with only a generic error (no raw source
errors, raw record hashes, the ledger path, records, or equality values
emitted). It must never emit raw source errors, raw record hashes, the ledger
path, records, or equality values; it must never re-emit 10FH internal digest
text.

## Authorization Result

- 10FL **only names 10FN**. It is a spec phase; no implementation is performed
  here.
- 10FN implementation is **not** authorized by this phase. A future
  implementation requires:
  - a dedicated implementation spec (e.g. 10FN itself, or a follow-up),
  - **GPT-5.6 Sol/Luna** authorization (per `10CL`/`10CN`/`10CR`), and
  - explicit operator approval before commit.
- 10FM will be the metadata-sync phase for 10FL (spec=N, sync=N+1).
- No code, backend, tests, runtime, or `world-sim/data` changes occur in this
  phase.

## Audit / Spec Confirmation

1. 10DX (`f03f83d`) + 10DY (`72ca46e`) closed — confirmed by history.
2. 10DZ (`f0fa3f9`) + 10DA (`c971a7b`) closed — confirmed (10DZ audit 14/14).
3. 10ED (`9671485`) + 10EE (`d9089bd`) closed — confirmed (incl. `9cda969`).
4. 10EF (`d1a37e3`) + 10EG (`227e52b`) closed — confirmed (10EF audit 14/14).
5. 10EJ (`469c374`) + 10EK (`78240ea`) closed — confirmed (incl. `d882751`).
6. 10EL (`bc082ae`) + 10EM (`96a8157`) closed — confirmed (10EL audit 14/14).
7. 10EP (`69bf981`) + 10EQ (`b3a7800`) closed — confirmed (incl. `59d82bc`).
8. 10ER (`5727d4b`) + 10ES (`10b3305`) closed — confirmed (10ER audit 14/14).
9. 10EV (`f228d7e`) + 10EW (`7c6f2ab`) closed — confirmed (incl. `9ae3199`).
10. 10EX (`90304e2`) + 10EY (`272900d`) closed — confirmed (10EX audit 14/14).
11. 10EZ (`dc1999f`) + 10FA (`77978f1`) closed — confirmed (incl. `4a93706`).
12. 10FB (`0818c49`) + 10FC (`e74993d`) closed — confirmed (incl. `c741d39`).
13. 10FD (`7642a5b`) + 10FE (`0c08465`) closed — confirmed (10FD audit 14/14).
14. 10FF (`c8913ca`) + 10FG (`6a496f2`) closed — confirmed (incl. `7be0f36`).
15. 10FH (`6446c31`) + 10FI (`996e2c5`) closed — confirmed (incl. `29a9e48`).
16. 10FJ (`f08192a`) + 10FK (`275096c`) closed — confirmed (10FJ audit 14/14;
    incl. `f3219aa` 10FK hash correction).
17. Boolean drift resolved, not deferred — 10DR/10CP strict bool identity and
    `test_dependency_boolean_type_drift_fails_closed` remain in place;
    10ED/10EJ/10EP/10EV/10FB/10FH add no new bool ingestion; 10FN (if
    implemented later) would add no new bool ingestion and would reuse strict
    built-in type checks.
18. 10CP remains the only writer — preserved: 10ED, 10EJ, 10EP, 10EV, 10FB, 10FH,
    and 10FN are read-only and do not call `10CP`.
19. Next work should be a read-only status reporter over the safe 10FH output
    (not another recursive verifier) before any broader runtime expansion — this
    is exactly what 10FN provides; no further expansion is named here.
20. No batch orchestrator yet — 10FN reports a single caller-supplied 10FH
    verification report; no multi-ledger batch candidate is named.
21. No local-sim bridge yet — no 10AI–10AN bridge to the inert ledger is named.
22. No gate-7 work yet — gate-7 remains closed by absence throughout.
23. No production `world-sim/data` access in this docs phase — only
    `world-sim/docs/` and root `README.md` / `world-sim/docs/phase_index.md`
    are touched.

## Checks

- `git diff --check` — clean (docs-only additions).
- `git diff --numstat` — three authorized file changes:
  `world-sim/docs/phase_10fl_next_runtime_boundary_candidate_spec.md` (new),
  `README.md` (+1 line), `world-sim/docs/phase_index.md` (+1 row).
- `git status -sb` — only the three authorized files modified/added; no backend,
  tests, runtime, or data changes.
- CRLF — 0 on all touched files (LF only).

## Status

Docs-only spec complete. Working tree modified (three authorized files); not
committed per instruction. Awaiting user go-ahead to commit/push 10FL, then 10FM
metadata sync if the N/N+1 convention is applied.

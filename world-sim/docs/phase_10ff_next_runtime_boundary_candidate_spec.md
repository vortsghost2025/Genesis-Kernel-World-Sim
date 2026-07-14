# Phase 10FF — Next Runtime Boundary Candidate Spec

Docs-only specification naming the single next authorized runtime-boundary
candidate. This phase performs no implementation, touches no backend/tests
runtime code or `world-sim/data`, and stops before commit.

- Repo: `S:\Genesis Kernel World Sim`
- Baseline: `b2c5505 docs: record 10FE metadata hash`
- Mode: docs-only spec (kilo OK)
- Out of scope: backend, tests, runtime, `world-sim/data`, daemon, scheduler,
  network, provider, launcher, container, Docker, PatchRaccoon, agent configs

## Context

Phase 10DX (`f03f83d`) closed the read-back loop: a pure read-only,
in-process, caller-driven verifier over one explicit existing 10CP NDJSON file
(`local_minimal_inert_ledger_readback_verifier.py`). It performs no write, no
scan, no backend/10CP call, and keeps every runtime/daemon/scheduler/network/
world-data/gate-7 flag `False`. Phase 10DZ (`f0fa3f9`) audited the committed
10DX and confirmed 14/14 boundary checks PASS.

Phase 10ED (`9671485`) closed the summary loop: a pure read-only,
in-process, caller-driven reporter over one caller-supplied exact 10DX result
dict (`local_minimal_inert_ledger_summary_reporter.py`). Phase 10EF
(`d1a37e3`) audited the committed 10ED and confirmed 14/14 boundary checks
PASS.

Phase 10EJ (`469c374`) closed the bundle loop: a pure read-only,
in-process, caller-driven reporter over one caller-supplied exact 10DX result
dict plus one caller-supplied exact 10ED report dict
(`local_minimal_inert_ledger_status_bundle_reporter.py`). Phase 10EL
(`bc082ae`) audited the committed 10EJ and confirmed 14/14 boundary checks PASS.

Phase 10EP (`69bf981`) closed the digest loop: a pure read-only,
in-process, caller-driven reporter over one caller-supplied exact 10EJ status
bundle dict (`local_minimal_inert_ledger_status_digest_reporter.py`). It
validates the exact 31-field 10EJ envelope, treats the 10EJ decision ID as an
opaque syntax-checked identifier (not recomputed), returns one safe 31-field
10EP.1 digest, and keeps every gate flag `False`. Phase 10ER (`5727d4b`) audited
the committed 10EP and confirmed 14/14 boundary checks PASS.

Phase 10EV (`f228d7e`) closed the digest-verification loop: a pure read-only,
in-process, caller-driven verifier over one caller-supplied exact 10EP digest
dict (`local_minimal_inert_ledger_status_digest_verifier.py`). It independently
validates the exact 31-field 10EP.1 envelope, recomputes only the 10EP decision
ID from safe 10EP material (treating the source 10EJ decision ID as opaque, not
recomputed), returns one safe 35-field 10EV.1 verification report with
`ok`/`verification_status` (`digest_intact` or `invalid_digest`), and keeps
every gate flag `False`. Phase 10EX (`90304e2`) audited the committed 10EV and
confirmed 14/14 boundary checks PASS (10EY `272900d` synced 10EX metadata).

Phase 10FB (`0818c49`) closed the digest-verification-reporting loop: a pure
read-only, in-process, caller-driven reporter over one caller-supplied exact
10EV verification report dict
(`local_minimal_inert_ledger_status_digest_verification_reporter.py`). It
independently validates the exact 35-field 10EV.1 envelope, recomputes only the
10EV decision ID from safe 10EV material (treating the source 10EP decision ID
as opaque, not recomputed), returns one safe 40-field 10FB.1 verification digest
report with `ok`/`verification_digest_status` (`verified_verification_digest`,
`non_verified_verification_digest`, or `invalid_10ev_source`), and keeps every
gate flag `False`. Phase 10FD (`7642a5b`) audited the committed 10FB and
confirmed 14/14 boundary checks PASS (10FE `0c08465` synced 10FD metadata).

The read-back (`10DX`), summary (`10ED`), status bundle (`10EJ`), status digest
(`10EP`), status digest verification (`10EV`), and status digest verification
reporting (`10FB`) surfaces now exist as six independent, inert, caller-driven
reporters/verifiers sharing the same inert-ledger trust boundary: no ledger file
access, no 10CP writer call, no runtime promotion. The verification digest
report (`10FB.1`) is the current safe terminal artifact of this observability
chain.

The next safest move is to *verify the integrity* of an already-produced 10FB
verification digest report — a tamper / round-trip check that confirms a
supplied report still satisfies the exact 10FB.1 envelope contract and its
recomputed decision ID — rather than produce new ledger data or add any new
ledger/file access. This keeps the loop inert (observability only) and leaves
gate-7 closed. It does not re-read the ledger, does not re-verify
10DX/10ED/10EJ/10EP/10EV sources, and does not promote the report into any
runtime/world state.

## Candidate Named

**10FH — Minimal Inert Ledger Status Digest Verification Verifier**

This is the single authorized next candidate. No other candidate is named by
this phase.

10FH is specified to be:

- **pure read-only integrity verification** — performs no mutation of any kind;
  it never touches a ledger file for writing or reading, and never alters a
  supplied verification digest report.
- **in-process / caller-driven** — runs only when a caller supplies a 10FB
  verification digest report (a dict already returned by
  `create_minimal_inert_ledger_status_digest_verification_report` or
  `export_minimal_inert_ledger_status_digest_verification_report`); it never
  starts work on its own.
- **consumes caller-supplied 10FB verification digest report dict only** — it
  confirms the structured report that
  `create_minimal_inert_ledger_status_digest_verification_report` already
  returns is internally consistent with the 10FB.1 contract; it does not
  re-implement verification, reporting, digest, bundle, summary, or read-back
  logic, and does not re-read the ledger.
- **has no default production ledger path** — if a required report is missing,
  it does not invent or open one; it reports the missing input and stops.
- **does not read a ledger file** — it consumes only the caller-supplied 10FB
  dict; it never opens, opens-in-read, scans, globs, walks, lists, or inspects
  any filesystem path.
- **does not call the `10DX` verifier, the `10ED` reporter, the `10EJ` bundle
  reporter, the `10EP` digest reporter, the `10EV` digest verifier, the `10FB`
  verification reporter, or the `10CP` writer** — `10CP` remains the only
  writer, `10DX` the only verifier, `10ED` the only summary reporter, `10EJ` the
  only status bundle reporter, `10EP` the only digest reporter, `10EV` the only
  digest verifier, and `10FB` the only verification reporter; 10FH never imports
  or invokes any of them. 10FH performs its own independent validation of the
  exact 40-field 10FB.1 envelope (mirroring how 10FB independently validated the
  35-field 10EV envelope and 10EV independently validated the 31-field 10EP
  envelope) rather than delegating to 10FB.
- **does not re-read or re-verify the ledger** — it trusts the caller-supplied
  10FB verification digest report; no second read or re-verification path is
  added.
- **recomputes only the 10FB decision ID from safe verification fields** — the
  10FB own `verification_digest_decision_id` is recomputed and compared to
  detect tampering of the verification digest artifact; the source `10EV-`
  decision ID is treated as an opaque syntax-checked identifier (not recomputed),
  because 10FF forbids 10FH from re-verifying the ledger or producing source
  fields.
- **does not write, append, overwrite, truncate, delete, rename, or repair** —
  strictly read-only over the supplied report; no ledger or report maintenance
  or recovery is in scope.
- **does not scan `world-sim/data`** — it never enumerates, globs, or walks
  directories; it consumes only the caller-supplied 10FB dict.
- **never reads/emits `equality_signal_value`** — 10FH may surface counts or
  known signal *types* already present in the 10FB envelope, but must never
  read, store, log, export, or promote any signal *value*; the value field is
  out of scope by design.
- **never promotes results into runtime/world state** — the verification result
  is returned to the caller as a safe dict only; no world, ledger, or external
  state is updated.
- **never creates movement / map / route / event / NPC behavior** — 10FH is
  observability only; it produces no simulation side effects.
- **keeps all `runtime`/`daemon`/`scheduler`/`network`/`world-data`/`gate-7`
  flags `False`** — its output hard-codes these to `False`, matching the 10DX,
  10ED, 10EJ, 10EP, 10EV, and 10FB contracts.
- **gate-7 remains closed by absence** — 10FH enables no execution, provider,
  launcher, container, or Docker behavior.

The verification result is a safe report: `ok=True` with a generic
`verified`/`digest_intact` status when the supplied report satisfies the exact
10FB.1 envelope and its recomputed decision ID matches; otherwise a sanitized
`invalid_digest`/`ok=False` status with only a generic error (no raw source
errors, raw record hashes, the ledger path, records, or equality values
emitted). It must never emit raw source errors, raw record hashes, the ledger
path, records, or equality values.

## Authorization Result

- 10FF **only names 10FH**. It is a spec phase; no implementation is
  performed here.
- 10FH implementation is **not** authorized by this phase. A future
  implementation requires:
  - a dedicated implementation spec (e.g. 10FH itself, or a follow-up),
  - **GPT-5.6 Sol/Luna** authorization (per `10CL`/`10CN`/`10CR`), and
  - explicit operator approval before commit.
- 10FG will be the metadata-sync phase for 10FF (spec=N, sync=N+1).
- No code, backend, tests, runtime, or `world-sim/data` changes occur in
  this phase.

## Audit / Spec Confirmation

1. 10DX (`f03f83d`) + 10DY (`72ca46e`) closed — confirmed by history.
2. 10DZ (`f0fa3f9`) + 10DA (`c971a7b`) closed — confirmed.
3. 10DX audit 14/14 PASS — confirmed by 10DZ (`f0fa3f9`).
4. 10ED (`9671485`) + 10EE (`d9089bd`) closed — confirmed by history
   (includes `9cda969` 10EE hash correction).
5. 10EF (`d1a37e3`) + 10EG (`227e52b`) closed — confirmed by history
   (includes `f7f9ceb` 10EG hash correction).
6. 10EF audit 14/14 PASS — confirmed by 10EF (`d1a37e3`).
7. 10EJ (`469c374`) + 10EK (`78240ea`) closed — confirmed by history
   (includes `d882751` 10EK hash correction).
8. 10EL (`bc082ae`) + 10EM (`96a8157`) closed — confirmed by history
   (includes `447cb5a` 10EM hash correction).
9. 10EL audit 14/14 PASS — confirmed by 10EL (`bc082ae`).
10. 10EP (`69bf981`) + 10EQ (`b3a7800`) closed — confirmed by history
    (includes `59d82bc` 10EQ hash correction).
11. 10ER (`5727d4b`) + 10ES (`10b3305`) closed — confirmed by history
    (includes `0454902` 10ES hash correction).
12. 10ER audit 14/14 PASS — confirmed by 10ER (`5727d4b`).
13. 10EV (`f228d7e`) + 10EW (`7c6f2ab`) closed — confirmed by history
    (includes `9ae3199` 10EW hash correction).
14. 10EX (`90304e2`) + 10EY (`272900d`) closed — confirmed by history
    (includes `aec3919` 10EY hash correction).
15. 10EX audit 14/14 PASS — confirmed by 10EX (`90304e2`).
16. 10EZ (`dc1999f`) + 10FA (`77978f1`) closed — confirmed by history
    (includes `4a93706` 10FA hash correction).
17. 10FB (`0818c49`) + 10FC (`e74993d`) closed — confirmed by history
    (includes `c741d39` 10FC hash correction).
18. 10FD (`7642a5b`) + 10FE (`0c08465`) closed — confirmed by history
    (includes `b2c5505` 10FE hash correction).
19. 10FD audit 14/14 PASS — confirmed by 10FD (`7642a5b`); README/phase_index
    reflect the committed state after the 10FE sync.
20. Boolean drift resolved, not deferred — preserved: 10DR/10CP strict bool
    identity and `test_dependency_boolean_type_drift_fails_closed` remain in
    place; 10ED/10EJ/10EP/10EV/10FB add no new bool ingestion; 10FH (if
    implemented later) would add no new bool ingestion and would reuse strict
    built-in type checks.
21. 10CP remains the only writer — preserved: 10ED, 10EJ, 10EP, 10EV, 10FB, and
    10FH are read-only and do not call `10CP`.
22. Next work should be a read-only integrity verification of the 10FB-supplied
    verification digest report before any broader runtime expansion — this is
    exactly what 10FH provides; no further expansion is named here.
23. No batch orchestrator yet — 10FH verifies a single caller-supplied 10FB
    verification digest report; no multi-ledger batch candidate is named.
24. No local-sim bridge yet — no 10AI–10AN bridge to the inert ledger is named.
25. No gate-7 work yet — gate-7 remains closed by absence throughout.
26. No production `world-sim/data` access in this docs phase — only
    `world-sim/docs/` and root `README.md` / `world-sim/docs/phase_index.md`
    are touched.

## Checks

- `git diff --check` — clean (docs-only additions).
- `git diff --numstat` — three authorized file changes:
  `world-sim/docs/phase_10ff_next_runtime_boundary_candidate_spec.md` (new),
  `README.md` (+1 line), `world-sim/docs/phase_index.md` (+1 row).
- `git status -sb` — only the three authorized files modified/added; no backend,
  tests, runtime, or data changes.
- CRLF — 0 on all touched files (LF only).

## Status

Docs-only spec complete. Working tree modified (three authorized files); not
committed per instruction. Awaiting user go-ahead to commit/push 10FF, then 10FG
metadata sync.

# Phase 10EZ — Next Runtime Boundary Candidate Spec

Docs-only specification naming the single next authorized runtime-boundary
candidate. This phase performs no implementation, touches no backend/tests
runtime code or `world-sim/data`, and stops before commit.

- Repo: `S:\Genesis Kernel World Sim`
- Baseline: `aec3919` docs: record 10EY metadata hash
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

The read-back (`10DX`), summary (`10ED`), status bundle (`10EJ`), status digest
(`10EP`), and status digest verification (`10EV`) surfaces now exist as five
independent, inert, caller-driven reporters/verifiers sharing the same inert-
ledger trust boundary: no ledger file access, no 10CP writer call, no runtime
promotion. The verification report (`10EV`) is the current safe terminal
artifact of this observability chain.

The next safest move is to *record the integrity result* of an already-verified
10EV verification report — a stable, deterministic digest of the verification
outcome — rather than produce new ledger data or add any new ledger/file
access. This keeps the loop inert (observability only) and leaves gate-7
closed. It does not re-read the ledger, does not re-verify 10DX/10ED/10EJ/10EP
sources, and does not promote the verification into any runtime/world state.

## Candidate Named

**10FB — Minimal Inert Ledger Status Digest Verification Reporter**

This is the single authorized next candidate. No other candidate is named by
this phase.

10FB is specified to be:

- **pure read-only digest reporting** — performs no mutation of any kind; it
  never touches a ledger file for writing or reading, and never alters a
  supplied verification report.
- **in-process / caller-driven** — runs only when a caller supplies a 10EV
  verification report (a dict already returned by
  `verify_minimal_inert_ledger_status_digest_report` or
  `export_minimal_inert_ledger_status_digest_verification_report`); it never
  starts work on its own.
- **consumes caller-supplied 10EV verification report dict only** — it confirms
  the structured report that
  `verify_minimal_inert_ledger_status_digest_report` already returns is
  internally consistent with the 10EV.1 contract; it does not re-implement
  verification, bundle, summary, or read-back logic, and does not re-read the
  ledger.
- **has no default production ledger path** — if a required report is missing,
  it does not invent or open one; it reports the missing input and stops.
- **does not read a ledger file** — it consumes only the caller-supplied 10EV
  dict; it never opens, opens-in-read, scans, globs, walks, lists, or inspects
  any filesystem path.
- **does not call the `10DX` verifier, the `10ED` reporter, the `10EJ` bundle
  reporter, the `10EP` digest reporter, the `10EV` digest verifier, or the
  `10CP` writer** — `10CP` remains the only writer, `10DX` the only verifier,
  `10ED` the only summary reporter, `10EJ` the only status bundle reporter,
  `10EP` the only digest reporter, and `10EV` the only digest verifier; 10FB
  never imports or invokes any of them. 10FB performs its own independent
  validation of the exact 35-field 10EV.1 envelope (mirroring how 10EP
  independently validated the 31-field 10EJ envelope) rather than delegating to
  10EV.
- **does not re-read or re-verify the ledger** — it trusts the caller-supplied
  10EV verification report; no second read or re-verification path is added.
- **recomputes only the 10EV decision ID from safe verification fields** — the
  10EV own `verifier_decision_id` is recomputed and compared to detect tampering
  of the verification artifact; the source `10EP-` decision ID is treated as an
  opaque syntax-checked identifier (not recomputed), because 10EZ forbids 10FB
  from re-verifying the ledger or producing source fields.
- **does not write, append, overwrite, truncate, delete, rename, or repair** —
  strictly read-only over the supplied report; no ledger or report maintenance
  or recovery is in scope.
- **does not scan `world-sim/data`** — it never enumerates, globs, or walks
  directories; it consumes only the caller-supplied 10EV dict.
- **never reads/emits `equality_signal_value`** — 10FB may surface counts or
  known signal *types* already present in the 10EV envelope, but must never
  read, store, log, export, or promote any signal *value*; the value field is
  out of scope by design.
- **never promotes results into runtime/world state** — the digest result is
  returned to the caller as a safe dict only; no world, ledger, or external
  state is updated.
- **never creates movement / map / route / event / NPC behavior** — 10FB is
  observability only; it produces no simulation side effects.
- **keeps all `runtime`/`daemon`/`scheduler`/`network`/`world-data`/`gate-7`
  flags `False`** — its output hard-codes these to `False`, matching the 10DX,
  10ED, 10EJ, 10EP, and 10EV contracts.
- **gate-7 remains closed by absence** — 10FB enables no execution, provider,
  launcher, container, or Docker behavior.

The digest result is a safe report: a deterministic human-readable digest text
plus one exact safe 10FB.1 envelope. Valid input — an intact `digest_intact`
10EV verification report — produces a `verified`/`ok=True` status (or equivalent
intact status) summarizing the verification outcome; an invalid or tampered
input collapses to a sanitized `invalid_10ev_source`/`ok=False` status with only
a generic error (no raw source errors, raw record hashes, the ledger path,
records, or equality values emitted). It must never emit raw source errors, raw
record hashes, the ledger path, records, or equality values. The report is
emitted through a strict deterministic snapshot exporter (exact field set,
sorted JSON, canonical SHA-256 decision ID) mirroring the 10EP/10EV exporters.

## Authorization Result

- 10EZ **only names 10FB**. It is a spec phase; no implementation is
  performed here.
- 10FB implementation is **not** authorized by this phase. A future
  implementation requires:
  - a dedicated implementation spec (e.g. 10FB itself, or a follow-up),
  - **GPT-5.6 Sol/Luna** authorization (per `10CL`/`10CN`/`10CR`), and
  - explicit operator approval before commit.
- 10FA will be the metadata-sync phase for 10EZ (spec=N, sync=N+1).
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
15. 10EX audit 14/14 PASS — confirmed by 10EX (`90304e2`); README/phase_index
    reflect the committed state after the 10EY sync.
16. Boolean drift resolved, not deferred — preserved: 10DR/10CP strict bool
    identity and `test_dependency_boolean_type_drift_fails_closed` remain in
    place; 10ED/10EJ/10EP/10EV add no new bool ingestion; 10FB (if implemented
    later) would add no new bool ingestion and would reuse strict built-in type
    checks.
17. 10CP remains the only writer — preserved: 10ED, 10EJ, 10EP, 10EV, and 10FB
    are read-only and do not call `10CP`.
18. Next work should be a read-only digest of the 10EV-supplied verification
    report before any broader runtime expansion — this is exactly what 10FB
    provides; no further expansion is named here.
19. No batch orchestrator yet — 10FB digests a single caller-supplied 10EV
    verification report; no multi-ledger batch candidate is named.
20. No local-sim bridge yet — no 10AI–10AN bridge to the inert ledger is named.
21. No gate-7 work yet — gate-7 remains closed by absence throughout.
22. No production `world-sim/data` access in this docs phase — only
    `world-sim/docs/` and root `README.md` / `world-sim/docs/phase_index.md`
    are touched.

## Checks

- `git diff --check` — clean (docs-only additions).
- `git diff --numstat` — three authorized file changes:
  `world-sim/docs/phase_10ez_next_runtime_boundary_candidate_spec.md` (new),
  `README.md` (+1 line), `world-sim/docs/phase_index.md` (+1 row).
- `git status -sb` — only the three authorized files modified/added; no backend,
  tests, runtime, or data changes.
- CRLF — 0 on all touched files (LF only).

## Status

Docs-only spec complete. Working tree modified (three authorized files); not
committed per instruction. Awaiting user go-ahead to commit/push 10EZ, then 10FA
metadata sync.

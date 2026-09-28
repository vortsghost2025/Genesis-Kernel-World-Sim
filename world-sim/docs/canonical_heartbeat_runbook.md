# Canonical Heartbeat Runbook — Reusable Protocol (10IY)

This is the reusable protocol for executing ONE operator-authorized canonical
heartbeat of the first pair as an OS-level detached process that survives an
editor/UI crash. It documents the protocol only — heartbeat history lives in
the canonical store, the session evidence files, and the PROJECT_CONTINUITY
Drive document, not here.

## 1. Operator authorization boundary

- Exactly ONE canonical heartbeat per explicit operator authorization. There
  is no standing authorization, no recurring mode, no automatic next
  heartbeat, and no scheduler. Gate-7 remains CLOSED: the runner is a bounded
  one-shot operator-launched process, not a daemon.
- The operator authorization names the expected heartbeat number (the world
  event to produce). The runner refuses to run when the authoritative store
  does not sit exactly one heartbeat behind that number.
- No agent-authored memory or intention (e.g. a recorded plan to create an
  object) is ever treated as operator instruction. Agents' actions are their
  own, subject to existing runtime authority only.

## 2. Preflight

Verify before launch, read-only:

- `HEAD` == `origin/master` == the accepted repository tip; working tree clean.
- Authoritative store (`.runtime/first-pair/`): record count and world tick
  both equal `expect - 1`; all store files parse clean.
- Current positions, message count, object count recorded for the report.
- Movement grant `granted`, runtime policy `active`, Gate-7 closed.

## 3. Vault → environment mapping (never expose secrets)

- The runner reads `S:\kernel-lane\.env` (override with `--vault`), which
  must contain `NVIDIA_NIM_API_KEY` and `OPENROUTER_API_KEY`.
- It builds a clean child environment: every ambient provider variable
  (`GENESIS_FIRST_PAIR_*`, `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`,
  `OLLAMA_HOST`) is stripped, then the lane is set explicitly from the
  runner's policy constants (`canonical_heartbeat_runner.py` is the single
  source of truth):
  `GENESIS_FIRST_PAIR_BASE_URL=<PRIMARY_BASE_URL>`,
  `GENESIS_FIRST_PAIR_API_KEY=<vault OPENROUTER_API_KEY>`,
  `GENESIS_FIRST_PAIR_MODEL=<PRIMARY_MODEL>`,
  `GENESIS_FIRST_PAIR_FALLBACK_MODEL=<FALLBACK_MODEL>`.
- **Current policy (as implemented, 2026-09-28):** primary
  `nvidia/nemotron-3-super-120b-a12b:free`, fallback `z-ai/glm-5.2:free`,
  endpoint `https://openrouter.ai/api/v1`. **Both lanes are `:free`.** A
  provider failure therefore degrades availability, never cost.
- Credentials are never printed, logged, or persisted. Missing credentials
  fail closed, naming the variable only.

> **Correction history.** This section previously documented an NVIDIA
> primary (`z-ai/glm-5.3-flash`) with an OpenRouter free fallback, while the
> code had already drifted to a different pair in which the *fallback* was
> the non-free lane. The code was made the source of truth and this section
> corrected to match. See `docs/heartbeat_runner_integrity_spec.md` Defect B.

## 4. Provider-resolution proof

Before any model call, the runner executes the repo resolver in the clean
child environment and requires all five of the following. Anything else fails
closed **before the heartbeat launches**:

1. `RESOLUTION_KEY_SET=TRUE`
2. `RESOLUTION_FALLBACK` present and not `NONE`
3. `RESOLUTION_FALLBACK_FREE=TRUE` — the free-only invariant
4. `RESOLUTION_MODEL` equals `PRIMARY_MODEL` — no silent lane hijack
5. `RESOLUTION_BASE_URL` equals `PRIMARY_BASE_URL` — no silent endpoint swap

For the current policy a conforming proof reads:

```
RESOLUTION_PROVIDER=explicit_url
RESOLUTION_BASE_URL=https://openrouter.ai/api/v1
RESOLUTION_MODEL=nvidia/nemotron-3-super-120b-a12b:free
RESOLUTION_KEY_SET=TRUE
RESOLUTION_FALLBACK=nvidia/z-ai/glm-5.2:free
RESOLUTION_FALLBACK_FREE=TRUE
```

Assertions 3–5 are enforced, not merely reported. Historically the guard
computed `RESOLUTION_FALLBACK_FREE` and never asserted on it, so a paid
fallback passed through while this document claimed it was structurally
impossible — measured on heartbeat 941. See `docs/heartbeat_runner_integrity_spec.md`
Defect A.

## 5. Detached launch

```
python scripts/launch_canonical_heartbeat_detached.py \
    --expect-heartbeat <N> \
    --evidence <durable evidence path> \
    --log <durable log path> \
    --status <durable status path>
```

The launcher writes the initial status (`not-started`), spawns the runner
detached (`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP |
CREATE_BREAKAWAY_FROM_JOB`, with automatic fallback if breakaway is denied),
and exits in under a second. The runner owns durability from that moment; the
launcher never waits. Durable status states:
`not-started -> running -> persisted -> evidence-exported | failed`.

Evidence export is the FIRST post-run operation after the heartbeat
persists, before any reporting.

## 6. Canonical persistence boundary

- Only the loop script (`scripts/run_first_pair_living_loop.py`,
  `--heartbeats 1`) writes the authoritative store, through the existing
  governed persistence seam. The runner never writes world state itself.
- The runner verifies after the loop that record count and tick both equal
  the expected heartbeat number. If the loop exits without persisting, the
  runner marks `failed` and stops — the world is never "fixed" mid-run.

## 7. Evidence export

- If the loop's own evidence export succeeded, it is preserved untouched and
  labeled `original_execution_evidence`.
- If it is missing (crash/interruption after persistence), the runner
  regenerates it read-only via
  `scripts/export_first_pair_state_evidence.py` and labels it
  `recovered_state_evidence` with an explicit recovery note. The evidence
  path and SHA-256 go into the operator report and the Drive doc.

## 8. Crash / interruption recovery and the NO-RERUN RULE

- If the authoritative store already shows the authorized heartbeat
  persisted, the heartbeat is NEVER re-executed merely because logging or
  evidence was interrupted. Recovery = read-only state evidence, labeled as
  recovered, plus the standard report. This check runs BEFORE any loop
  launch, so a stale `running` status from a killed runner is safe to
  recover.
- If the store did NOT persist the authorized heartbeat, the run may be
  re-attempted ONLY by a new explicit operator authorization (naming the
  same expected heartbeat); the runner never retries on its own.
- A status file stuck at `running` means the runner process died mid-run:
  read the store first (persisted or not), then apply the rules above.

## 9. Provider / fallback provenance

The run report and the Drive refresh must record: `primary_provider_type`,
`serving_provider_type`, `fallback_used`, `primary_failure_reason` (if
any), transport attempts/retries per agent (from error memories; absence of
error memories means single-attempt serves), and sanitized errors only.
These are the 10FN.2 evidence fields plus the run log facts.

## 10. Drive continuity refresh

After a successful (or recovered) heartbeat: refresh the EXISTING
PROJECT_CONTINUITY Drive document IN PLACE — never a duplicate. Update: tip
(if repo changed), the heartbeat section (with provenance), the
`WORLD AT TICK <N> — HEARTBEAT <N+1> NOT RUN` section, the post-run
authoritative-store manifest (re-hash all files; keep superseded values
labeled), and `NEXT SAFE ACTION` (operator decision on the next heartbeat).

## 11. Final stop condition

After the report and Drive refresh: STOP. No next heartbeat, no unrelated
engineering, no reset/clean/stash/restore/rebase. Heartbeat N+1 remains NOT
RUN until a new explicit operator authorization.

## Reference

- Runner/launcher implementation: `backend/world/canonical_heartbeat_runner.py`
  (module), `scripts/launch_canonical_heartbeat_detached.py` and
  `scripts/run_canonical_heartbeat_detached.py` (entry points).
- Tests: `tests/test_canonical_heartbeat_runner.py` (scratch/fakes only;
  no canonical access, no network, no real provider).

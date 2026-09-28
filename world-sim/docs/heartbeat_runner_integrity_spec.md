# Heartbeat Runner Integrity Spec — Three Measured Defects

**Status:** SPEC (docs-only phase). No runtime code in this commit.
**Date:** 2026-09-28
**Triggered by:** canonical heartbeat 941, run 2026-09-28T01:38Z
**Supersedes nothing.** Amends `docs/canonical_heartbeat_runbook.md` §3, §4, §7.

---

## 0. Why this phase exists

Heartbeat 941 was the first canonical run since 2026-09-26T23:43Z. The
heartbeat itself **succeeded**: the store persisted tick 941, 941 heartbeat
records, both agents acted, and the run cost nothing. Three defects surfaced
around that success. None of them damaged the world. All three mean the
runbook's stated guarantees were not being enforced by the code that claims
to enforce them.

This is the epistemic-phase rule applied to our own infrastructure: **measure
the board before changing the rules.** Every finding below is a measured
observation from a real run, not a reading of the code in the abstract.

---

## 1. Defect A — the free-only guard is a printer, not a gate

### 1.1 What the code claims

`backend/world/canonical_heartbeat_runner.py:13-15` (module docstring):

> Provider policy is fixed: NVIDIA primary (z-ai/glm-5.3-flash) plus
> OpenRouter free fallback (z-ai/glm-5.2:free ONLY; the committed free-only
> guard rejects any paid fallback at resolution).

`docs/canonical_heartbeat_runbook.md:57-61`:

> Anything else — wrong primary, missing fallback, or a non-`:free` fallback
> model — fails closed before the heartbeat launches. The committed free-only
> guard makes a paid OpenRouter fallback structurally impossible at resolution.

### 1.2 What actually happened

Measured resolution proof output from heartbeat 941:

```
RESOLUTION_PROVIDER=explicit_url
RESOLUTION_BASE_URL=https://openrouter.ai/api/v1
RESOLUTION_MODEL=nvidia/nemotron-3-super-120b-a12b:free
RESOLUTION_KEY_SET=TRUE
RESOLUTION_FALLBACK=nvidia/z-ai/glm-5.3-flash
RESOLUTION_FALLBACK_FREE=FALSE
```

The runbook requires `RESOLUTION_FALLBACK_FREE=TRUE` and states a non-`:free`
fallback **fails closed before the heartbeat launches**. It did not. The
heartbeat launched, and the status path that would have carried the rejection
(`runner_main:299-304`, detail `"provider resolution proof rejected (no paid
fallback permitted)"`) was never reached.

### 1.3 Root cause

`resolution_proof()` (`:139-174`) **computes** `RESOLUTION_FALLBACK_FREE` at
`:153` and then never asserts on it. The complete set of assertions is:

| line | assertion |
|---|---|
| `:168` | `proc.returncode != 0` → reject |
| `:170` | `RESOLUTION_KEY_SET=TRUE` must be present |
| `:172` | `RESOLUTION_FALLBACK=` present and not `NONE` |

There is no assertion on `RESOLUTION_FALLBACK_FREE`, `RESOLUTION_PROVIDER`, or
`RESOLUTION_MODEL`. The guard is a diagnostic that prints its verdict and is
never read. This is a lattice deformation in the Paper B sense: Layer 2
operational code stopped constraining Layer 3 execution while the
constitutional statement (docstring + runbook) continued to assert the
constraint held.

### 1.4 What this phase does

Add the missing assertions to `resolution_proof()` so a non-free fallback and
an off-policy provider/model each fail closed with a named reason. Fail-closed
means: return `(False, reason)` before any loop launch. The proof subprocess
already runs with no network access, so the change is pure comparison logic
over its stdout.

Proposed assertions, in order:

1. `RESOLUTION_KEY_SET=TRUE` (existing, `:170`)
2. `RESOLUTION_PROVIDER` must equal the expected provider for the configured
   lane (new)
3. `RESOLUTION_MODEL` must equal `PRIMARY_MODEL` (new)
4. `RESOLUTION_FALLBACK` present and not `NONE` (existing, `:172`)
5. `RESOLUTION_FALLBACK_FREE=TRUE` (new)

Assertions 2 and 3 are the ones that would have caught this run. Assertion 5
is the one the docstring and runbook both name explicitly and the code never
had.

---

## 2. Defect B — the policy constants and the documented policy disagree

### 2.1 The two policies

| | primary | fallback |
|---|---|---|
| **Runbook §3/§4 + module docstring** | `z-ai/glm-5.3-flash` on NVIDIA | `openrouter/z-ai/glm-5.2:free` |
| **Code, `:44-45`** | `nvidia/nemotron-3-super-120b-a12b:free` | `z-ai/glm-5.3-flash` |

The code's fallback has no `:free` suffix. The code's primary does. So the
lane that is permitted to be paid is the one the runbook promises is free-only,
and the provider is OpenRouter-by-explicit-URL rather than the NVIDIA lane the
runbook names.

`build_clean_env` (`:128`) sets `GENESIS_FIRST_PAIR_BASE_URL` to
`https://openrouter.ai/api/v1`, which is why the resolver reports
`provider_type=explicit_url` instead of `nvidia`.

### 2.2 Why this shipped without detection

The drift is internally consistent: the primary model *is* free, so nothing
about heartbeat 941 was expensive. A guard that only watched cost would have
seen nothing wrong. The defect was only visible because the runbook stated a
provider and a fallback that the code did not implement.

This is the Paper F lesson (NFM-016) in a different costume: a blanket
"looks fine" that is not per-item proof. The cost check passed; the
conformance check was never performed.

### 2.3 What this phase does

Two options, operator's choice — this spec does **not** pick:

- **Option 1 — conform the code to the runbook.** Restore
  `PRIMARY_MODEL = "z-ai/glm-5.3-flash"`, `FALLBACK_MODEL = "z-ai/glm-5.2:free"`,
  and NVIDIA as the primary base URL. Then the assertions in §1.4 hold and the
  free-only invariant is real. Requires confirming `z-ai/glm-5.3-flash` is
  reachable on the NVIDIA lane and `glm-5.2:free` on OpenRouter.
- **Option 2 — conform the runbook to the code.** Rewrite
  `canonical_heartbeat_runbook.md` §3/§4 and the module docstring to state
  the policy the code actually implements (OpenRouter explicit URL, free
  nemotron primary, `z-ai/glm-5.3-flash` fallback), and keep the
  `FALLBACK_FREE=TRUE` assertion as the real guard.

Recommendation: **Option 1**, with the caveat that the NVIDIA primary must be
re-verified as reachable before the assertion is tightened. If `z-ai/glm-5.3-flash`
is not available on NIM, Option 2 is the honest path and the fallback must be
changed to a genuinely free model rather than documented around.

Either way, **the docstring and the runbook must be made to match the code**,
and the assertions in §1.4 must gate. A documented policy with no gate is the
defect.

### 2.4 The precondition cannot be verified from the record

Attempted 2026-09-28: can `z-ai/glm-5.3-flash` be confirmed reachable on the
NVIDIA NIM lane without spending a new provider call?

**No.** No durable artifact answers it:

- `data/proposals/model_calls.jsonl` records call *rates*, not model names, and
  its last entry is 2026-06-28.
- The store's `world_state.json` and the HB941 evidence export carry no model
  or provider field.
- The only HB941 provider record is the scratch `runner.log` — and that records
  the *configured* resolution, not the *served* one (see §3.5).

So the recommendation above is a recommendation under an **unverified
precondition**, and the verification is precisely what Defect D removes. This
is recorded rather than papered over: choosing Option 1 today means either
trusting the runbook's claim that this model serves on NIM, or authorizing one
probe call to establish it. Choosing Option 2 requires no probe at all, because
it makes the code the source of truth and the documentation follow.

Given that, Option 2 is the lower-risk path for this phase: it closes the
"documentation asserts a guarantee nothing checks" defect without depending on
an unverified external fact, and it leaves the free-only assertion (§1.4 #5)
as the real, enforced guard. Option 1 remains preferable **if and when** the
NVIDIA lane's model list is confirmed, but that confirmation is a separate
authorization, not something this phase should assume.

---

## 3. Defect C — relative evidence path, NFM-021 recurring

### 3.1 What happened

Heartbeat 941 status ended `failed`:

```
status: failed
detail: "recovery evidence export: evidence export exited 0"
```

Exit code 0 is success. The run was misreported as failed.

### 3.2 Root cause

The launcher was invoked with a **relative** evidence path
(`world-sim/.scratch/hb941/evidence.json`). The runner stores it as-is
(`:272`, `evidence = Path(args.evidence)`), then launches the loop script with
`cwd=str(world_sim_root)` (`:329`) and passes the same relative path to the
loop. The loop therefore wrote the evidence relative to the world-sim root,
producing:

```
S:\Genesis Kernel World Sim\world-sim\world-sim\.scratch\hb941\evidence.json
```

The runner then tested the un-doubled path (`:346`, `:225`,
`evidence_path.is_file()`), found nothing, fell through to
`export_state_evidence` (`:354`), which also resolved the doubled path and
reported the doubled-relative failure as `exited 0`.

Confirmed on disk: the evidence file exists at the doubled path; it does not
exist at the intended path.

### 3.3 The cross-system finding

This is **NFM-021** from Paper F verbatim:

> NFM-021: Artifact-resolver only handled absolute paths; relative
> `evidence_exchange.artifact_path` values always rejected.

Same failure mode, different codebase, months apart, different authorial
context. Under the Paper A translation protocol this is exactly the case the
Rosetta Stone claim predicts: the structural failure (relative path resolution
across a cwd boundary) is domain-general; the specific mechanism is not. It is
recorded here as **NFM-037** in the world-sim ledger.

### 3.4 What this phase does

- Resolve `--evidence` (and `--status`, `--log`, `--store-root`) to absolute
  paths at the launcher boundary, before they reach the runner.
- In the runner, resolve `evidence` and `status_path` against
  `world_sim_root` when relative, so a runner launched from any cwd behaves
  identically.
- Add a guard: if the export subprocess exits 0 but the evidence file is not
  present at the **resolved** path, report the resolved path in the failure
  detail rather than a bare returncode. The current message is actively
  misleading — it says `exited 0` when the real problem is `wrote elsewhere`.

---

## 3.5 Defect D — provider provenance is printed but never persisted

Found while attempting to verify Defect B's precondition (see §2.3).

### 3.5.1 What the runbook requires

`docs/canonical_heartbeat_runbook.md:117-121` (§9):

> The run report and the Drive refresh **must record**: `primary_provider_type`,
> `serving_provider_type`, `fallback_used`, `primary_failure_reason` (if any),
> transport attempts/retries per agent (from error memories; absence of error
> memories means single-attempt serves), and sanitized errors only.

### 3.5.2 What is actually recorded

Searched every durable artifact HB941 produced:

| artifact | provider provenance? |
|---|---|
| `status.json` (durable status) | no — carries pid, paths, `detail` only |
| `evidence.json` (133KB, recovered) | no — keys are `authorities`, `claim_scope`, `exported_at_utc`, `exporter`, `goals`, `heartbeat_history`, `identity`, `questions`, `relationship_events_count`, `world_state` |
| `world_state.json` | no — keys are `capability_requests`, `habitat`, `public_messages`, `public_objects`, `schema_version`, `tick`, `tile_occupancy`, `updated_at_utc`, `world_state_id` |
| `data/proposals/model_calls.jsonl` | no — a rate-limit counter (`count_after`, `max_per_hour`, `reason`), and it stopped at 2026-06-28 |
| `runner.log` (scratch) | **yes** — the only place the resolution proof survives |

So the one place the full provider record exists is a scratch log outside the
repo, in a path that this same run wrote to the wrong place (§3). The
durable record of which provider actually served HB941 is **absent**.

### 3.5.3 Why this compounds Defects A and B

Defects A and B are both about a policy that nobody can verify was honored.
Defect D removes the only mechanism that could have detected them
post-hoc. Concretely: we cannot answer, from the record, which model served
HB941, whether the fallback fired, or how many transport attempts occurred. The
resolution proof in the scratch log tells us what was *configured*; nothing
tells us what was *served*.

This is NFM-036's shape — an ungoverned derivation-trust gap — applied to our
own provenance chain. And it is the same class as the Paper F observation that
the verification system is subject to the failure modes it detects.

### 3.5.4 What this phase does

- Persist the resolution proof fields into the durable `status.json` at launch
  (`primary_provider_type`, `primary_model`, `fallback_provider_model`,
  `fallback_free` as resolved), and add a `serving_*` block after the loop
  exits, sourced from the loop's own error memories per the runbook's
  "absence of error memories means single-attempt serves" rule.
- The status file is written by the runner and is already the durable
  operator-facing artifact; provenance belongs there, not in a scratch log.
- Sanitized only. No credential values, no raw provider error bodies.

---

## 4. Test plan (TDD outline for the implementation phase)

Guard (Defect A) — each pinned so the old behavior cannot silently return:

- `resolution_proof` returns `False` when `RESOLUTION_FALLBACK_FREE=FALSE`
- returns `False` when `RESOLUTION_PROVIDER` is not the expected provider
- returns `False` when `RESOLUTION_MODEL` does not match `PRIMARY_MODEL`
- returns `False` when `RESOLUTION_FALLBACK=NONE`
- returns `True` only when all five assertions pass
- an import-guard style test asserting the free-only assertion is present, so
  the guard cannot be quietly deleted (the Paper 8.2 import-guard pattern)

Path handling (Defect C):

- launcher with a relative `--evidence` yields an absolute resolved path
- runner with a relative `--evidence` resolves against `world_sim_root`
- export subprocess exiting 0 with a missing file names the **resolved** path
  in the detail string
- the doubled-path scenario (`world-sim/world-sim/.scratch/...`) is
  impossible after the change — asserted by a tempdir test that runs the
  exporter with a relative path from a different cwd

Compliance:

- no test touches `world-sim/data`, connects to a provider, or runs a daemon
- all tests run against tempdirs and fakes only
- `git diff --check` clean, LF-only

---

## 5. What this phase deliberately does NOT do

- **No heartbeat runs.** Heartbeat 942 is NOT authorized by this document. It
  stays blocked until the guard is real.
- No change to the loop script, the persistence seam, or the store format.
- No change to the no-rerun rule. HB941 persisted; it is never re-executed.
- No change to Gate-7. The runner stays a bounded one-shot process.
- No provider policy decision. §2 presents both options; the operator picks.
- No evidence regeneration for HB941 beyond the already-written recovered
  evidence at the doubled path, which is left in place as the honest record of
  what happened.

---

## 6. The standing rule, restated because it applied to us

The epistemic spec closed with:

> **Standing rule for this project, learned the expensive way: measure the
> board before changing the rules.**

Three defects in our own runner, none of which the agents found, all of which
were invisible because the documentation asserted the guarantee rather than
the code enforcing it. The agents at HB797 found a one-line resource defect in
24 heartbeats. Our runner carried a printed-but-unguarded invariant through an
entire deployment.

**Measure the board. Assert the invariant. Never document a guarantee that
nothing checks.**

---

## 7. Decision requested

Spec approved by the operator 2026-09-28. Three items remain open:

1. **Defect B — Option 1 or Option 2.** §2.4 revises the earlier
   recommendation: Option 1's precondition cannot be verified from any recorded
   artifact, and verifying it would itself require a provider call that is not
   authorized. **Option 2 is now the recommended path** — make the
   documentation match the code, and let the enforced `FALLBACK_FREE=TRUE`
   assertion (§1.4 #5) be the real guard. Option 1 remains correct if and when
   the NVIDIA lane's model list is confirmed as a separate authorization.
2. **Defect D — persist provider provenance** into the durable status file.
   Recommended in scope: the runbook already requires it; this phase makes the
   code do it.
3. **Heartbeat 942 stays blocked** until at minimum the Defect A assertions
   gate. Running a second heartbeat on a runner whose central safety claim is
   unenforced, and whose provenance is unrecorded, would repeat HB941's exact
   condition.

### Implementation-phase prerequisites

Per the phase workflow, implementation follows a docs-only spec phase. Before
any code moves:

- Tests are written first and must **fail** against current behavior — the
  Defect A assertions and the Defect C path tests in particular, since both
  currently pass for the wrong reason.
- No test touches `world-sim/data`, connects to a provider, or runs a daemon.
- The doubled-path artifact `world-sim/world-sim/.scratch/hb941/evidence.json`
  is left in place as the record of Defect C pending an operator decision on
  retention. It is not deleted by this phase.

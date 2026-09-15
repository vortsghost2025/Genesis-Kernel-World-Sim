# Phase 10IT — First-Pair Activation & Living Loop

Numbered artifact documenting the operator-authorized activation of the First
Pair (Adam and Eve) and the first bounded living-loop run with real model
cognition.

**Operator authorization**: Sean granted full autonomy authority for this
session on **2026-09-14** — "you have autonomy authority to run my project
and make my adam and eve come alive." This explicitly authorizes: commits and
pushes per step, first-pair runtime activation, movement grant, and model
provider calls for First-Pair cognition. The GPT-5.6 Sol/Luna model-switch
requirement was retired in AGENTS.md on the same date (recovered from the
prior forced-cheap-model era; the current operator-selected model is a paid,
top-capability model).

**GATE_7 (daemon/scheduler) remains closed.** All runs are in-process,
operator-launched, bounded heartbeat sequences. No daemon, no scheduler, no
background job. Model/provider calls are the authorized point of the
activation.

---

## 1. Cognition transport (10IT.1)

- Provider resolution: existing `resolve_provider()` contract
  (`backend/world/first_pair_cognition_model.py`), fail-closed.
- Provider selected: **NVIDIA** — `https://integrate.api.nvidia.com/v1`,
  model **`z-ai/glm-5.3-flash`**, key from the federation secrets vault
  (`S:\federation\.secrets\api-keys.txt`, `NIM_API_KEY`), never printed.
- Smoke test: `scripts/run_first_pair_smoke.py` — `SMOKE=OK`
  (commit `4fd53b0`).
- Reasoning-model note: GLM 5.3 Flash emits `reasoning_content` before final
  `content`; the cognition call's `max_tokens=2048` accommodates this.
- Local Ollama fallback remains available via
  `GENESIS_FIRST_PAIR_BASE_URL`/`OLLAMA_HOST` + `GENESIS_FIRST_PAIR_MODEL`.

## 2. Movement grant (10IT.2)

Governed operator grant via existing `grant_capability` seam (zero
heartbeats, sealed, provenance-recorded):

- **grant_id**: `grant-movement-001`, capability `movement`, status `granted`
- **policy**: `runtime-policy-first-pair-001`, status `active`, topology:
  `public-start-adam` ↔ `public-shared-center` ↔ `public-start-eve`,
  `movement_allowed=True`, one edge per heartbeat
- **operator_provenance**: `sean-operator-auto-activation-2026-09-14`

## 3. Canonical identity — fresh initialization (10IT.3)

The canonical store had no persisted `identity.json` before activation (the
original tick-0 identity existed only in the activation-evidence docs and in
the old goals/questions references). `initialize_first_pair_state` therefore
initialized a **fresh canonical identity pair** at activation:

- **Adam (current)**: `genesis-agent-4327298502de9566131e81212dd3b383666b6f18bc887d8508ab3a059e73f34e`
- **Eve (current)**: `genesis-agent-9c37c102cc309769f5c1a4011cf45d629942d9dfd8832dc1ef4079bf593f211a`
- **pair_id**: `genesis-first-pair`

Honest consequence: the pre-activation answered question
(`q1-habitat-structure`, asked by the original Adam
`genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d`)
is **orphaned by id mismatch** — its asking_agent_id no longer matches the
current Adam, so it does not re-enter context. The answer's content is
preserved in `questions.json` and in the round-trip record. The original
goal record (`goal-b0971f2a04c4c41b`, "Understand the shared starting
habitat") was superseded by the fresh initialization; its purpose was
fulfilled (Boundary 3 proved Adam understood the habitat before activation).
No audit record was rewritten; the pre-activation state remains intact in the
record.

## 4. First living-loop run (10IT.4)

Driver: `scripts/run_first_pair_living_loop.py` (bounded, operator-launched).
Scratch dry run first (isolated temp store, 1 heartbeat) — full success.
Then the canonical run: **2 heartbeats completed, zero runtime errors.**

- **Heartbeat 1**: Adam and Eve each moved (reasoned) to
  `public-shared-center`; both moves succeeded.
- **Heartbeat 2**: Adam and Eve each left a public message to the other
  (both succeeded). Adam greeted Eve and proposed cooperation. Eve confirmed
  cooperation and **proposed a coordinated exploration plan on her own**:
  survey both origin tiles, reconvene at `public-shared-center` to compare
  notes, treat it as their standing meeting point.
- **Goals**: Eve completed `goal-eve-001-establish-contact` and autonomously
  opened `goal-eve-002-coordinate-exploration` (active). Adam's
  `explore-and-meet-eve` is `in_progress`.
- **World state**: tick `2`, both co-located at `public-shared-center`,
  2 public messages.
- **Model**: `z-ai/glm-5.3-flash` via NVIDIA for every cognition call.

State evidence (read-only export):
`world-sim/docs/first_pair_activation_evidence_2026-09-14.json`.

## 5. Boundary status

- FIRST_PAIR_RUNTIME: **ACTIVE** (bounded, operator-launched sequences)
- FIRST_PAIR_CREATION_AUTHORIZED: **True** (operator authorization above)
- GATE_7 (daemon/scheduler): **CLOSED** — in-process bounded runs only
- 10CP remains sole world-event/ledger writer for the adapter chain; the
  first-pair runtime persists to its own canonical store (separate domain)
- Adam and Eve remain governed by the runtime's existing action validation,
  the movement-grant topology, and the consume-first operator seams

## 6. Next steps (operator-paced or bounded loop)

- Continue bounded heartbeats (Eve's exploration plan executes naturally)
- World expansion: new tiles, objects, fog-of-war beyond the 3-tile topology
- NVIDIA key permanence: the key is session-injected from the federation
  vault; Sean may store a canonical `.env` or vault reference for future runs
- `world-sim/data` expansion (world-event ledger wiring) if separately
  authorized

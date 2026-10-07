# 10JF — Model Route Correction Spec (docs-only)

**Status:** SPEC (docs-only phase). No runtime code in this commit.
**Date:** 2026-10-07
**Phase chain:** 10JF (spec, L) → 10JG (sync, L+1) → 10JH (named implementation candidate, L+2, NOT started, NOT authorized).
**Origin:** Oct-02 freeze (east HB1881–1900 + west HB1275–1327 inert) plus Oct-07 live re-probe. The quota wall is gone; the route is not.

---

## 0. What this spec is and is not

This spec names **one** next authorized candidate, **10JH**, and defines its exact bounds. It does not implement it. No code, tests, backend, runtime, ledger, daemon, scheduler, provider, network, Docker, `world-sim/data`, or key changes are made here.

10JH is a **model-route correction only**: primary model choice plus fallback-lane routing. It is not a heartbeat, not a migration, not a world change, not a new verb, not a capability grant, not an answer to any agent question.

## 1. Measured evidence (not inferred)

1. **Freeze:** east HB1881–1900 (20 beats, `action_taken None`) on `429 free-models-per-day-high-balance, Remaining 0` (`lockstep_east_hb1900_evidence.json:474884`, finished `2026-10-02T16:06:29Z`). West HB1275 `empty_response | fallback 404` (`lockstep_west_hb1275_evidence.json:303617`) then HB1276–1327 inert, HB1327 same 429 (`lockstep_west_hb1327_evidence.json:318664`). Chain logged `OK` throughout (clock advanced, world did not).
2. **Quota reset is real:** `Reset 1790985600000` = `2026-10-03T00:00:00Z`, now past. Live tiny probe 2026-10-07: 0× 429 across 12 calls; dots primary serves `200` on 3/6 pool keys; 3 keys remain `401 User not found` (fingerprints `0ecf…`, `5b3e…`, `2389…`, same as census).
3. **Contract probe 2026-10-07** (`world-sim/.scratch/probe_contract.py:36-41,76-131`, real 340k/401k-char east contexts, `max_tokens 8192`, both agents):
   - `dots-studio/dots-3-note-preview:free` (current primary): Eve `VALID move`, Adam `INVALID goal_updates[0] unknown_field related_question_id/metadata` → **not both-valid**.
   - `inclusionai/ling-3.0-flash-sante:free` (OpenRouter route): **both agents `VALID move`** → only both-valid route.
   - `poolside/laguna-s-2.1:free`: `429` both. `liquid/lfm-2.5-2.6b:free`: `400` both.
4. **Fallback 404 class:** west HB1275 + east HB1900 evidence carry `fallback: 404`. Current code sets `FALLBACK_MODEL = "inclusionai/ling-3.0-flash-sante:free"` (`canonical_heartbeat_runner.py:71`) but `resolve_fallback_provider` sends it down the **NVIDIA direct lane** whenever the primary is not `nvidia` and an NVIDIA key exists (`first_pair_cognition_model.py:518-521`), because the primary resolves as `explicit_url`, not `openrouter`. The `:free` suffix is an OpenRouter convention and is invalid on `integrate.api.nvidia.com`. Display form `nvidia/inclusionai/…` in evidence is `provider_type + '/' + model` (`canonical_heartbeat_runner.py:224`), not the model id itself.

## 2. Root cause, stated once

Two independent defects, each sufficient to keep the world frozen after quota returns:

- **R1 (primary):** dots primary fails Adam's contract validation (extra `goal_updates` fields). A 200 with invalid JSON is content failure, which the era-2 fix routes to fallback — and the fallback cannot serve (R2). Result: inert heartbeats that persist cleanly.
- **R2 (fallback):** any `:free` fallback model is routed to the NVIDIA direct lane under an `explicit_url` primary, where it 404s. The OpenRouter-fallback branch (`first_pair_cognition_model.py:522-530`, free-only guard included) never fires.

Key rotation cannot help: quota is account-wide, and rotation across keys in one account does not clear a per-route or validation failure.

## 3. The 10JH candidate (named, NOT authorized, NOT started)

10JH may change **only** these, behind TDD from §6 and explicit Sean approval:

1. **Primary** → `inclusionai/ling-3.0-flash-sante:free` on the OpenRouter lane (the sole Oct-07 both-valid route). Per-agent overrides (`ADAM_MODEL`, `EVE_MODEL`) follow the same both-valid bar or stay as-is with the reason recorded — no silent per-agent drift.
2. **Fallback routing** → a `:free` fallback model must ride the **OpenRouter lane** (second credential/pool key), never NVIDIA direct. The free-only guard (`model.endswith(':free')`, fail closed) is preserved verbatim. The NVIDIA-first branch must not capture `:free` ids.
3. **Provenance preserved:** `primary_provider_type`, `serving_provider_type`, `fallback_used`, `primary_failure_reason` (10FN.2 fields) plus transport attempts, sanitized errors only. No key values in any new path.
4. **Retry semantics unchanged:** bounded transient retry (10IV), single JSON repair, fail-closed on auth/4xx/validation. No new retry budgets, no truncation escalation (10IW stands).

## 4. What 10JH must NOT do

- No heartbeat launch, no chain run, no canonical writes, no `world-sim/data` changes.
- No new models beyond the Oct-07 both-valid set without a fresh contract probe.
- No paid lanes: any non-`:free` OpenRouter id fails closed at resolution (existing guard).
- No key additions, removals, rotations-policy, or denylist changes.
- No prompt, schema, verb, capability, charter, question, or memory changes.
- No daemon, scheduler, network, provider-endpoint, container, or Docker changes.
- No west HB1328 repair inside 10JH (that is a separate integrity action with its own authorization).

## 5. Boundaries

- **Gate-7 remains closed.** 10CP remains the sole writer. 10HD remains named-only. `FIRST_PAIR_CREATION_AUTHORIZED = False` (creation governance unchanged; the living pairs run under the 10IT activation authority, which this spec neither extends nor re-authorizes).
- This spec reads the live stores only through existing read-only evidence and the Oct-07 probes. It does not open any store for writing.

## 6. Acceptance matrix for 10JH TDD (future, not now)

1. Dots primary + Adam context → `INVALID` with `goal_updates` unknown-field errors (pins R1).
2. Ling OpenRouter + both contexts → `VALID move` both (pins the correction).
3. `:free` fallback under `explicit_url` primary → resolves to `openrouter` lane, never `nvidia` (pins R2).
4. Paid fallback id → `ProviderError` fail-closed at resolution (free-only guard regression).
5. NVIDIA-direct lane + `:free` id → rejected or never selected (404 class structurally impossible).
6. Both lanes fail → combined sanitized error naming neither credential, `fallback_used` accurate.
7. Full first-pair regression green; canonical store byte-identical (no heartbeat executed).

## 7. Preconditions for 10JH (all required, none assumed)

1. Quota live (`Remaining>0` measured, not wall-clock).
2. Fresh contract probe: chosen primary + fallback both-valid for **both** agents on real contexts.
3. West integrity: `count == tick` realigned and `current_run.json` stale `1328-1427` cleared by separate authorized action.
4. Watcher ledger acknowledged (Oct-05 `complete/frozen` replays understood) so a resumed run is read fresh.
5. Explicit Sean approval naming 10JH plus all First Pair creation/activation gates.

## 8. Decision requested

1. Confirm 10JF as the route-correction spec and 10JH as its named (not authorized) implementation candidate.
2. Confirm fallback-riding-OpenRouter as the intended fix direction (vs. a NVIDIA-valid fallback id).
3. Confirm west HB1328 integrity stays a separate authorized action, not bundled into 10JH.

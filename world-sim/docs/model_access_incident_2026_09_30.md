# Model access incident — 2026-09-30

**What happened:** the pair stopped acting for 46 consecutive heartbeats
(HB1198–1243). The chain logged `OK` for every one of them, the tick
advanced normally, and the run monitor reported **"census complete"** to
the operator. Nobody knew the world had been frozen since HB1198.

**Root cause, measured not guessed:** the model route the sim depended on
was dead upstream, and every layer that should have absorbed it was
either unwired or blind.

This document is the record. Nothing here is inferred — every number
below came from a probe whose output is reproducible from the commands
named in each section.

---

## 1. What the evidence said

Read from the evidence files, not from a summary:

| Heartbeats | `action_taken` | `uncertainty` |
|---|---|---|
| HB1144–1196 | real actions | — |
| HB1197–1229 | `null` for both agents | `Provider timeout or error: empty_response` |
| HB1230–1243 | `null` for both agents | `Error code: 429 — free-models-per-day-high-balance`, `X-RateLimit-Remaining: 0`, `limit_source: openrouter_free_tier_daily` |

The configured models were `nvidia/nemotron-3-super-120b-a12b:free`
(primary), `nvidia/nemotron-3-ultra-550b-a55b:free` (Adam and Eve), and
`z-ai/glm-5.2:free` (fallback).

## 2. The credential pool was never wired to the heartbeat

`load_key_pool` and `call_with_key_rotation` existed and were tested, but
a repository-wide search found them called from exactly one place:
`run_memory_synthesis.py`. The heartbeat path built a single client from
the singular `OPENROUTER_API_KEY` and retried that one credential up to
three times.

Full pool census (43 keys, one tiny completion each,
`.scratch/census_key_pool.py`):

| Lane | Keys | Verdicts |
|---|---|---|
| OpenRouter | 7 | **3 live**, 3 × `401 User not found`, 1 × daily-cap 429 |
| NVIDIA | 36 | **0 live** — 18 × `403 Authorization failed`, 18 × timeout |

And the singular key the heartbeats were actually using
(`ab6b62659e54843b`) was **the quota-exhausted one**. Three healthy
credentials were sitting unused in the plural pool for the entire
outage.

## 3. The fallback lane could not have worked

Three independent reasons, each sufficient on its own:

1. **No usable credential.** 0 of 36 NVIDIA keys served a completion.
2. **An invalid model id.** The configured fallback `z-ai/glm-5.2:free`
   does not exist on the NVIDIA lane; the live ids are `z-ai/glm-5.3` and
   `z-ai/glm-5.3-flash`. The `:free` suffix is an OpenRouter convention.
3. **`empty_response` never reached it.** `_call_model_with_repair` only
   entered the fallback branch when the *transport* failed
   (`response is None`). A 200 carrying no content returned early at the
   content check — so the first 33 heartbeats of the outage, the phase
   where the provider was answering `200` with nothing, had no
   degradation path at all.

## 4. The whole NVIDIA family was refused upstream

A sized probe (`.scratch/probe_sized.py`, 200 / 2000 / 12000-token
prompts) returned `502` wrapping `{"status":403,"title":"Forbidden"}` in
0.2–0.4 s on all three nominally-live OpenRouter keys. The same provider
refused our own direct keys. This is upstream, not configuration: a
smaller probe had returned `200` with content minutes earlier.

OpenRouter free-route availability measured on a cognition-shaped request
(`.scratch/probe_free_routes.py`): **5 of 14 free routes served.**

## 5. The fix

Model era 2, verified rather than assumed. A route returning `200` is not
evidence; a **validated action against a real agent context** is
(`.scratch/probe_contract.py` — both east agents, 319k and 367k char
prompts):

| Model | Result |
|---|---|
| `dots-studio/dots-3-note-preview:free` | **both agents valid** — Adam `move`, Eve `gather` |
| `inclusionai/ling-3.0-flash-sante:free` | **both agents valid** — both `gather` |
| `poolside/laguna-s-2.1:free` | 429 / empty |
| `liquid/lfm-2.5-2.6b:free` | HTTP 400 |

Four code changes, each TDD-pinned:

1. **Key rotation on the cognition path** (`test_cognition_key_rotation.py`).
   The pool is built per runner process from the vault, minus every
   denylisted fingerprint. A 429 or a 401/403 advances to the next
   credential instead of retrying into the same wall. An all-denylisted
   pool fails closed; an empty pool keeps the historical single-key path.
   Dead credentials are persisted as fingerprints only.
2. **Content failure is a lane failure** (`test_empty_response_fallback.py`).
   `empty_response` and token truncation now reach the fallback lane, and
   when both lanes answer with nothing the error says so rather than
   blaming one lane.
3. **The denylist is wired in.** `load_denylist_file` /
   `record_dead_key_file` were reachable only from the synthesis script.
   They now live in the backend, anchored to the module rather than the
   working directory (the detached runner launches from the repo root).
4. **A run that does nothing is not a run that succeeded**
   (`test_run_health.py`, `test_chain_watch_frozen.py`). `run_health`
   counts the trailing heartbeats in which no agent acted; five
   consecutive is `frozen`, which overrides `complete` and alerts
   immediately, mid-run, rather than at the end.

One leak was introduced by change 1 and caught by its own test: with
rotation the active credential is usually *not* the configured one, so
pool keys are now redacted from provider errors alongside the configured
key. A live key must never reach the store inside an error string.

## 6. Model era boundary

**HB1245 onward runs on `dots-studio/dots-3-note-preview:free`, not
`nvidia/nemotron-3-ultra-550b-a55b:free`.** Every evidence file records
`model_name`, so the boundary is measurable per heartbeat and the
record stays honest. Behaviour differences after HB1245 must be read with
the model change in mind; this is a confound, and it is stated here
rather than buried.

This is a research-continuity cost, accepted because the alternative was a
frozen world. It is reversible: restore the two `nemotron` model constants
in `canonical_heartbeat_runner.py` when the route serves again.

## 7. Re-verification before trusting this again

A `200` is not availability. Before naming any model in that file, run
`.scratch/probe_contract.py` and require a **validated action for both
agents on a real context**. The route list changes daily; the free tier
resets at 00:00 UTC and the upstream providers refuse independently of
us.

# Heartbeat 4 — Unauthorized-Provider Execution (Protocol-Violation Record)

Append-only record. **Do NOT erase, restore, rewrite, or pretend heartbeat 4
did not happen.** The canonical store record stays intact. However, heartbeat
4 is **NOT a clean accepted NVIDIA heartbeat**: it violated the explicit
operator constraint by running through **OpenRouter (paid provider)**.

- **date**: 2026-09-16 (heartbeat timestamp_utc 2026-09-16T20:45:22Z)
- **provider**: OpenRouter (`run_id="living-loop-openrouter"` — the evidence
  itself records the forbidden lane)
- **accepted head at run time**: `ebc3faed65fc88cafa550a49d07486ce884d8fac`

## What happened

- Adam: `empty_response` error → `Outcome: no_action` → fail-closed, no
  action taken, no world mutation, empty decision summary. Exactly one
  attempt, no retry (validation-path error, correctly never retried).
- Eve: valid cognition → `move` to `public-start-eve` — a real
  provenance-recorded world mutation. Exactly one attempt, no retry.
- Tick advanced 3 → 4. Pair state: Adam `public-shared-center`, Eve
  `public-start-eve`. No new public messages (last still heartbeat 2), no
  new questions, no objects. Adam memory +2 (hb4 error + no_action
  reflection); Eve memory +2 (hb4 decision + success reflection).
- No history rewritten; store parses clean (only the transient
  `.question.store.lock` is non-JSON by design).

## Root cause (corrected)

Live `resolve_provider()` precedence is:
`GENESIS_FIRST_PAIR_BASE_URL` → `NVIDIA_API_KEY` → `OPENROUTER_API_KEY` →
`OLLAMA_HOST`. OpenRouter does **not** outrank NVIDIA. Therefore the run
resolved to OpenRouter because Python saw `NVIDIA_API_KEY` as effectively
empty after `.strip()` in the run environment:

1. The vault first parsed (`S:\federation\.env`) contains **no**
   `NVIDIA_API_KEY` line (it is a KuCoin/CoinGecko vault).
2. The real key lives in `S:\kernel-lane\.env` as `NVIDIA_NIM_API_KEY`.
3. A failed PowerShell `.Trim()` assignment (array-typed pipeline result)
   left `NVIDIA_API_KEY` unset in the run env; an ambient session-level
   `OPENROUTER_API_KEY` then won the precedence chain.
4. `"NVIDIA_API_KEY SET: True"` was not sufficient proof of a usable value.

## Eve's move

Her move actually happened in the runtime and is provenance-recorded. Any
future world-state correction must go through an explicit, auditable
compensating mechanism — not by making the evidence disappear.

## Progression frozen

**No heartbeat 5 until Sean explicitly approves after the
environment-selection proof.**

Environment-selection proof (2026-09-16): **PASS** — clean child environment
with all provider-selection vars unset except `NVIDIA_API_KEY` (from
`S:\kernel-lane\.env` `NVIDIA_NIM_API_KEY`, single match, never printed) and
`GENESIS_FIRST_PAIR_MODEL=z-ai/glm-5.3-flash`; `resolve_provider()`
read-only exact output: `PROVIDER=nvidia`,
`BASE_URL=https://integrate.api.nvidia.com/v1`, `MODEL=z-ai/glm-5.3-flash`,
`KEY_SET=True`; direct NVIDIA smoke (no heartbeat, no TokenRouter, no
OpenRouter, no paid provider): **SMOKE=OK**.

# Phase 10BP — Shared Public Snapshot ID Equality Contract

## Status

10BP is a **pure scalar equality contract**. It is not a knowledge-inference contract, not a snapshot-sharing contract, not a same-map claim, and not a same-observation-time claim.

---

## Overview

Create a deterministic sanitized shared-public-snapshot-id-equality contract artifact from a Phase 10AS two-agent public merge.  10BP formalizes whether two agents' public snapshot IDs are identical, without ever inferring same snapshot, same map, same observation time, same observation content, or same knowledge state.

Snapshot IDs are read from 10AS agent bundles (`agent_a.snapshot_id`, `agent_b.snapshot_id`). 10BP does not read `snapshot_hash` — that is covered by 10AY.

10BP may say:

    "Agent A's public snapshot_id is X."

    "Agent B's public snapshot_id is Y."

    "Both agents report the same public snapshot_id value."
    (public-surface equality only)

10BP may not say:

    "Both agents used the same map snapshot." (map/snapshot content inference)

    "Both agents observed the same things." (observation content inference)

    "Both agents were at the same location." (proximate-location inference)

    "The agents have the same knowledge." (knowledge-state inference)

    "The snapshot IDs imply a relationship." (relationship inference)

    Anything about awareness, communication, cooperation, conflict,
    relationship, trust, proximity, distance, ETA, route, or timing.

---

## Allowed Evidence Sources

This contract may only cite or rely on:

- A valid Phase 10AS two-agent public merge artifact (`merge`)
- `sanitize_public_mapping` from `world_event_sanitizer`

No other file, code path, test, runtime, daemon, scheduler, provider, Docker, network, or `world-sim/data` may be touched or read.

---

## Core Invariant

No one gets to know more than they observed, and every observed claim has a replayable custody trail.

---

## Contract Material

The following fields feed the canonical material hashed to produce `contract_id`:

- `contract_schema_version`
- `claim_scope`
- `source_merge_id`
- `source_merge_hash`
- `agent_a_id`
- `agent_b_id`
- `agent_a_snapshot_id`
- `agent_b_snapshot_id`
- `same_snapshot_id`
- `shared_snapshot_id`

---

## Output Fields

| Field | Type | Description |
|---|---|---|
| `ok` | bool | True if contract produced without errors |
| `contract_schema_version` | str | `"10BP.1"` |
| `contract_type` | str | `"shared_public_snapshot_id_equality_contract"` |
| `contract_id` | str | `"10BP-" + sha256(canonical_material)[:32]` |
| `source_phase` | str | `"10AS"` |
| `source_merge_id` | str or None | From 10AS merge |
| `source_merge_hash` | str or None | sha256 of sanitized merge |
| `source_merge_schema_version` | str or None | From 10AS merge |
| `agent_a_id` | str or None | From 10AS agent bundle |
| `agent_b_id` | str or None | From 10AS agent bundle |
| `agent_a_snapshot_id` | str or None | Sanitized snapshot_id from agent_a bundle |
| `agent_b_snapshot_id` | str or None | Sanitized snapshot_id from agent_b bundle |
| `same_snapshot_id` | bool | True when both are non-None and equal |
| `shared_snapshot_id` | str or None | The shared value when `same_snapshot_id` is True |
| `claim_scope` | str | `"shared_public_snapshot_id_equality_only"` |
| `errors` | list[str] | Empty on success |

---

## Boundaries

- snapshot_id is a public surface identifier only; equality of identifiers does not imply equality of the underlying map state.
- No same-map, same-knowledge, same-observation, same-location, or co-presence inference.
- No caller-supplied snapshot_id kwargs — values come only from 10AS bundles.
- Empty or non-string snapshot_id values become None after sanitization.
- `contract_id` preserves A/B agent orientation (agent_a and agent_b are NOT sorted).

---

## Out-of-Scope List

10BP is explicitly out of scope for:

- Any 10AP, 10AQ, or 10AR direct inputs
- Any parent-body rehashing of snapshot content or map state
- Any full route-intent revalidation or pathfinding
- Any map lookup, topology inference, or adjacency computation
- Any ledger write, candidate event mapping, or verifier inference
- Any runtime, daemon, scheduler, provider, Docker, or network activity
- Any `world-sim/data` access
- Any meeting, awareness, co-presence, or relationship justification
- Any distance, ETA, or timing-window inference
- Any plan inference or route reconstruction
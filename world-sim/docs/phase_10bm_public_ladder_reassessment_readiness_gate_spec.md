# Phase 10BM — Public Ladder Reassessment & Runtime Wiring Readiness Gate

## Status

10BM is a **docs-only readiness gate**, not an equality contract. It does not implement any new comparison, inference, or merge surface. It replaces any implicit "next is another bundle-scalar rung" implication with a written gate that a future rung must satisfy before it may be opened.

10BM does not duplicate 10AW's route-destination coverage or any 10AY–10BL surface. It is the terminal phase of the 10AS bundle-scalar equality ladder sequence.

---

## Coverage Matrix

The following table maps every bundle field produced by 10AS (`create_two_agent_public_merge`) to the existing 10AY–10BL / 10AW contract that witnesses it, or provides an explicit rationale for an intentionally unwitnessed field.

| 10AS bundle field | Witnessed by | Rationale |
|---|---|---|
| `agent_id` | Intentionally unwitnessed | Agent identity is a provenance anchor, not an equality claim. No scalar equality contract compares `agent_id` values. |
| `public_state_hash` | 10BB (Shared Public State Hash Equality Contract) | 10BB witnesses caller-supplied `agent_a_public_state_hash` / `agent_b_public_state_hash` scalar equality over a valid 10AS merge artifact. |
| `snapshot_id` | 10AY (Shared Public Snapshot Hash Equality Contract) | 10AY propagates `agent_a_snapshot_id` / `agent_b_snapshot_id` from bundle or injected fields. |
| `snapshot_hash` | 10AY (Shared Public Snapshot Hash Equality Contract) | 10AY computes `same_snapshot_hash` / `shared_snapshot_hash` from bundle `snapshot_hash` fields. |
| `current_tile_id` | 10BJ (Shared Public Current Tile ID Equality Contract) | 10BJ reads `agent_a.current_tile_id` and `agent_b.current_tile_id` from 10AS agent bundles directly. |
| `known_tile_ids` | 10BL (Shared Public Known Tile IDs Set Equality Contract) | 10BL reads `agent_a.known_tile_ids` and `agent_b.known_tile_ids` from 10AS agent bundles and recomputes set algebra. |
| `route_intent_id` | 10BK (Shared Public Route Intent ID Equality Contract) | 10BK reads `agent_a.route_intent_id` and `agent_b.route_intent_id` from 10AS agent bundles directly. |
| `route_destination_tile_id` | 10AW (Shared Public Route Destination Contract) | 10AW compares `route_destination_tile_id` fields. Cited against the existing shared public route destination contract, **not** against 10BM. No new equality contract is created here. |
| `route_destination_known` | 10AW (Shared Public Route Destination Contract) | 10AW compares `route_destination_known` fields. Cited against the existing shared public route destination contract, **not** against 10BM. No new equality contract is created here. |

Every bundle scalar from the 10AS merge artifact is either witnessed by an existing 10AY–10BL or 10AW contract, or intentionally unwitnessed with documented rationale. No bundle scalar remains unmapped.

---

## Readiness Gate Checklist

A future rung (hypothetically 10BN or later) **must** satisfy all of the following before it may be opened:

1. **New dimension** — Proposes a new dimension not already covered by the coverage matrix above. Examples include temporal window, observation depth, third-party merge, replay-bundle inequality, or another dimension that is not a restatement of a bundle scalar already mapped. A proposed equality on a field already listed in the coverage matrix without a new dimension fails this check.

2. **Prerequisite citation** — Cites prerequisite documentation in `world-sim/docs/future_phases_plan.md` and `world-sim/docs/runtime_wiring_architecture.md`. The citation must identify which existing phases the proposed rung depends on and confirm those phases are complete.

3. **Surface declaration** — Declares the surface it consumes (10AS only, 10AS+caller-supplied overrides, 10AT composite, or another surface). The surface must be a documented, already-existing contract or merge artifact. A future rung may not consume an undocumented or unimplemented surface.

4. **Inference boundary** — Declares the inference boundary it will not cross. This must be a specific, falsifiable list of prohibited inferences (examples: no co-presence inference, no meeting/interaction inference, no route/path/destination/timing/plan inference, no relationship/trust/cooperation/conflict inference). General statements such as "no social inference" without listing the specific prohibited categories are insufficient.

5. **Runtime/safety/network/data boundaries** — Declares the runtime, safety, network, and data boundaries it will not cross. At minimum these must state: no daemon, no scheduler, no provider, no Docker, no network, no `world-sim/data` access. Additional boundaries may be added as appropriate for the proposed dimension.

A rung that fails any checklist item must be revised before it may proceed. The gate is not a veto — it is a qualification criteria.

---

## Out-of-Scope List

The following inferences and operations are explicitly out of scope for any rung constrained by this gate, mirroring every boundary already established in 10AY–10BL docstrings:

- No 10AP/10AQ/10AR direct inputs (these are consumed exclusively by 10AS)
- No parent-body rehashing (re-deriving state that 10AS already merged)
- No full route-intent revalidation (10AS performs initial validation; a future rung may not re-validate route intents)
- No true map lookup, pathfinding, or movement execution
- No ledger write, candidate event mapper change, verifier change, exporter change, or sanitizer change
- No runtime, daemon, scheduler, provider, Docker, or network activity
- No `world-sim/data` access
- No meeting, awareness, co-presence, relationship, trust, cooperation, or conflict inference
- No distance, ETA, route, path, destination, timing, window, or plan inference
- No observation-content inference, exploration-history inference, map-knowledge inference, or place-at-time inference

---

## Forbidden in 10BM

10BM itself is a docs-only phase. The following are strictly forbidden under any pretext:

- No `world-sim/backend/world/*.py` additions (no code changes to any backend module)
- No new test files or pytest discovery additions
- No ledger, mapper, verifier, exporter, or sanitizer changes
- No docker, daemon, scheduler, or provisioner activity
- No network access or network-related changes
- No `world-sim/data` reads or writes
- No edits to catalog, secrets, credentials, or configuration files
- No new rung implementation (no 10BN/10BO/10BP etc. code)
- No bypassing the readiness gate to add a future rung without satisfying the checklist
- No force pushes, no `--no-verify`, no hook bypass, no amend

Violation of any forbidden rule invalidates the phase.

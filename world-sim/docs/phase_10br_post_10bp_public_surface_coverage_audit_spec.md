# Phase 10BR — Post-10BP Public Surface Coverage Audit

## Status

10BR is a **docs-only coverage audit**. It is not an equality contract, not a comparison surface, not an implementation gate, not a runtime-wiring change. It inventories which 10AS public merge agent-bundle fields already have shared-public contract coverage, which are intentionally out of scope, and whether a safe next-rung candidate exists after 10BP.

---

## Allowed Evidence Sources

This audit may only cite or rely on:

- `README.md`
- `world-sim/docs/phase_index.md`
- `world-sim/docs/phase_10bp_shared_public_snapshot_id_equality_contract_spec.md`
- `world-sim/docs/phase_10bo_post_10bn_depth_surface_readiness_audit_spec.md`
- `world-sim/backend/world/local_two_agent_public_merge.py` (read-only)
- `world-sim/backend/world/local_shared_public_*_contract.py` (read-only)
- `world-sim/tests/test_phase10**shared_public**.py` (read-only)
- `.github/workflows/pure-tests.yml`
- `git log` / `git status` proof only

No other file, code path, test, runtime, daemon, scheduler, provider, Docker, network, or `world-sim/data` may be touched or read for this audit.

---

## Baseline Commits

| Commit | Subject |
|---|---|
| `57ee9a3` | docs: sync 10BP metadata and CI coverage |
| `6ba6622` | Phase 10BP: add shared public snapshot id equality contract |

10BR is built directly on the unioned state of these two commits. No code, no tests, no runtime wiring has been added or touched by 10BR.

---

## 10AS Public Merge Agent-Bundle Field Inventory

The immutable 10AS public merge exposes the following fields on every agent bundle (`agent_a` and `agent_b`):

| # | Field | Type | Origin |
|---|---|---|---|
| 1 | `agent_id` | str | Public state projector (10AP) |
| 2 | `current_tile_id` | str | Public state projector |
| 3 | `known_tile_ids` | list[str] | Known-map snapshot (10AQ) |
| 4 | `public_state_hash` | str | Public state hash of the projector output |
| 5 | `route_destination_known` | bool or None | Route intent contract (10AR) |
| 6 | `route_destination_tile_id` | str or None | Route intent contract |
| 7 | `route_intent_id` | str or None | Route intent contract |
| 8 | `snapshot_hash` | str | Known-map snapshot (10AQ) |
| 9 | `snapshot_id` | str | Known-map snapshot (10AQ) |

These are the only fields present on the agent bundles; 10BR does not propose adding, removing, or renaming any of them.

---

## 10AS Coverage Table

| Field | Status | Covered By | Notes |
|---|---|---|---|
| `agent_id` | Intentionally out of scope | n/a | Required distinct for every contract (always compared as identity, never as equality). Not an equality surface. |
| `current_tile_id` | Covered | **10BJ** | Direct bundle equality contract. Scalar, no list/set algebra. |
| `known_tile_ids` | Covered | **10BL** | Set-equality contract. Recomputes set algebra from bundle lists; root set-algebra fields ignored as authority. |
| `public_state_hash` | Covered indirectly | **10BB** | 10BB is a scalar equality contract but it operates on **caller-supplied** `public_state_hash` args (the 10AS bundles retain a `public_state_hash` field but 10BB does not consume it from the bundle). Not a direct bundle round-trip. |
| `route_destination_known` | Covered indirectly | **10AW** | 10AW refuses to publish `shared_route_destination_tile_id` unless **both** `route_destination_known` are `True`. This guards destination equality but is not itself an equality contract over `route_destination_known`. |
| `route_destination_tile_id` | Covered | **10AW** | Direct bundle comparison; equality only when both are known. |
| `route_intent_id` | Covered | **10BK** | Direct bundle equality contract. |
| `snapshot_hash` | Covered | **10AY** | Direct bundle equality contract over a content hash. |
| `snapshot_id` | Covered | **10BP** | Direct bundle equality contract just added. |

Summary:

- **6 of 9 bundle fields** have a direct dedicated equality contract: `current_tile_id` (10BJ), `known_tile_ids` (10BL), `route_destination_tile_id` (10AW), `route_intent_id` (10BK), `snapshot_hash` (10AY), `snapshot_id` (10BP).
- **2 fields** are covered indirectly with safety guards but lack a standalone equality surface: `public_state_hash` (10BB operates on caller-supplied input, not the bundle field) and `route_destination_known` (10AW gates equality on it, but equality over the boolean itself is never asserted).
- **1 field** is intentionally out of scope: `agent_id` (identity, must be distinct).

---

## What 10BP Closed

Before 10BP, the `snapshot_id` field was present on every 10AS agent bundle but had **no** dedicated scalar equality contract. 10BP closes that gap with:

- A bounded pure scalar equality module
- `_sanitize_snapshot_id` that mirrors the 10BG/10BH/10BI sanitizer-collapse guard
- `contract_id` bound to `source_merge_hash` to prevent contract-ID collisions across bundle mutations
- A clear boundary: may say only "same public snapshot_id value"; no map, knowledge, observation, co-presence, or relationship inference

10BP's test is included in `.github/workflows/pure-tests.yml` at line 74. Pure-test count: 22 targeted; 10BI–10BL–10BP regression: 119.

---

## What Remains Unsafe to Infer

The shared-public equality ladder never turns "same X value" into any of the following. These boundaries must be preserved by every future rung:

- Same observation, same observation content, same observation time
- Same temporal window, same active-at-same-time, same tick overlap
- Same place, co-presence, proximity, distance, ETA
- Same map, same knowledge, same memory, same exploration history
- Same snapshot, same snapshot content
- Same plan, same route, same destination, same timing
- Awareness, communication, cooperation, conflict, coordination
- Trust, relationship, intimacy, intentionality

10BR proposes no new rung, no new inference, and no new comparison surface. The intact surface above is what the current ladder already forbids; 10BR simply notes it.

---

## Relation to 10BO / 10BN

10BN introduced `depth_token` (an external non-bundle scalar, caller-supplied) and explicitly **forbade** equality, ranking, ordering, calendarization, or shared-depth reconstruction.

10BO audited the depth surface and confirmed it is closed unless a future rung introduces a new non-comparative dimension beyond depth.

10BR **respects both constraints**:

- 10BR does not propose a depth equality contract.
- 10BR does not propose a depth order, depth rank, depth calendar, or shared-depth algebra.
- 10BR does not extend the depth surface in any direction.

---

## Candidate Next-Rung Recommendation

Walked candidate fields from the table above:

| Field | Safe to add as standalone equality? | Reason |
|---|---|---|
| `agent_id` | No | Identity, not equality surface; must remain distinct. |
| `public_state_hash` | Marginal | Risk of redundancy or inference leak: identity-level matching of two agents' public state hashes may lead to "they share public state" inferences. Acceptable only if restrained to the same boundary text used in 10AY. |
| `route_destination_known` | No (boolean) | Boolean equality is an Oxford-style "both-true/both-false" comparison with no replayable surface. Already indirectly handled by 10AW. |

**Recommendation:** No safe standalone next-rung candidate is produced by 10BR that would add real information beyond the existing ladder. 10BR leaves the public-surface ladder **closed at 10BP** unless and until a future non-comparative dimension (like the depth surface at 10BN) is explicitly designed. The next logical task after 10BR is a **post-ladder runtime-wiring readiness reassessment**, which is a docs-only artefact and would be numbered separately (e.g., 10BS) when the operator chooses to author it.

10BR does **not** name or commit to 10BS; it only points at the operator decision.

---

## No Implementation in 10BR

10BR is documentation-only. The following are strictly forbidden under any pretext:

- No equality contract implementation (incl. `public_state_hash`, `route_destination_known`, or any other 10AS bundle field).
- No new test files.
- No edits to any `world-sim/backend/world/*.py`.
- No edits to any `world-sim/tests/*.py`.
- No edits to `.github/workflows/pure-tests.yml` (10BP coverage is already present).
- No edits to runtime, daemon, scheduler, provider, Docker, network, or `world-sim/data`.
- No force pushes, no `--no-verify`, no amend, no hook bypass.
- No depth equality, depth ranking, depth ordering, depth calendar, or enum expansion.
- No 10BS or later rung implementation.

10BR may be logged in `phase_index.md` and added to the README ladder, nothing more.


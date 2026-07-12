# Phase 10CF - Post-Consumer Vocabulary Coverage Audit

Docs-only audit of the 10BT shared-public contract consumer harness
after the 10BV / 10BX / 10BZ / 10CB / 10CD vocabulary extensions.

This phase performs **no implementation**. It does not touch the 10BT
consumer module, does not add or change tests, does not modify
`pure-tests.yml`, and does not create a new equality contract. It only
documents which shared-public contract vocabulary entries the consumer
now recognizes, which public-merge fields remain intentionally out of
scope, and whether the project is ready for a later runtime-readiness
decision.

10CF is the same shape of checkpoint that 10BR was for the
pre-consumer surface: a deliberate "stop and confirm coverage"
moment before the ladder moves any closer to runtime.

---

## What the consumer now recognizes

The 10BT `_extract_equality_signal` function has explicit
signal-extraction branches for exactly these six shared-public contract
types:

| Contract | Phase | Signal type emitted by the consumer |
|---|---|---|
| `shared_public_snapshot_id_equality_contract` | 10BP | `"snapshot_id_equality"` |
| `shared_snapshot_hash_equality_contract` | 10AY | `"snapshot_hash_equality"` |
| `shared_public_current_tile_id_equality_contract` | 10BJ | `"current_tile_id_equality"` |
| `shared_public_route_intent_id_equality_contract` | 10BK | `"route_intent_id_equality"` |
| `shared_public_known_tile_ids_set_equality_contract` | 10BL | `"known_tile_ids_set_equality"` |
| `shared_public_route_destination_contract` | 10AW | `"route_destination_tile_id_equality"` |

All six branches share the same contract-agnostic envelope:

- The 21-field 10BT decision envelope is unchanged.
- `decision_schema_version` stays `"10BT.1"`.
- `consumer_scope` is `"record_public_equality_signal_only"`.
- The `claim_boundary` names co-presence / awareness /
  relationship / timing as forbidden concepts.
- The hard-coded `runtime_allowed` / `daemon_allowed` /
  `scheduler_allowed` / `network_allowed` flags are all False.
- The module never imports or calls any contract creator; it only
  imports `sanitize_public_mapping` from the public egress
  sanitizer plus stdlib.

Adding any new recognized contract is still a small extension to
`_extract_equality_signal` in the 10BT module only. The envelope,
scope, claim boundary, decision schema version, and runtime block do
**not** change between recognitions.

---

## What remains intentionally out of scope (or indirect)

These public-merge fields are deliberately **not** independent equality
consumer signals:

- **`agent_id`** - identity field. Intentionally out of scope for
  equality consumption. A matching `agent_id` is structurally
  forbidden by every contract creator (the two agent ids must be
  distinct), so it can never be an equality signal.
- **`public_state_hash`** - already handled by earlier
  caller-supplied / hash discipline (10BB asserts it; it is not a
  new consumer runtime signal unless separately designed).
- **`route_destination_known`** - a guard / known-state field
  *inside* 10AW (`both_route_destination_known`). It is the
  precondition for a shared destination to exist; it is not itself an
  independent equality signal.
- **Depth / rank / order / calendar / shared-depth / enum
  expansion fields** - closed by 10BN and 10BO. The consumer
  does not reopen any depth surface and does not extract a "depth
  equality signal."
- **Co-presence, awareness, relationship, timing, path,
  movement, arrival, coordination, cooperation** - forbidden
  inference surfaces. They are never consumer outputs. They appear
  in the `claim_boundary` field only as named *forbidden
  concepts*, never as asserted facts.

No structural vacancy remains in the obvious direct shared-public
equality vocabulary: every scalar, set, and the route-destination
public contract now has a consumer branch.

---

## Coverage assessment

The direct shared-public consumer vocabulary is covered through the
currently safe rungs:

- 10BP -> `snapshot_id_equality`
- 10AY -> `snapshot_hash_equality`
- 10BJ -> `current_tile_id_equality`
- 10BK -> `route_intent_id_equality`
- 10BL -> `known_tile_ids_set_equality`
- 10AW -> `route_destination_tile_id_equality`

All six are public-surface, single-merge, equality-only signals. None
of them infers runtime state, movement, co-presence, awareness,
relationship, or timing.

---

## Recommendation

Do **not** add another equality consumer branch unless a future spec
explicitly designs a new public scalar / set contract. The current
six-branch vocabulary is the complete set of safe, direct,
public-surface equality contracts available on the ladder.

The next safe decision point should be a **separate runtime-readiness
audit** (a 10BS-style checkpoint), not runtime wiring yet. 10CF
confirms the consumer ladder is covered; it does not authorize any
runtime action. The hard-coded runtime / daemon / scheduler /
network block in 10BT remains False on every path and must stay
that way until a dedicated, separately-reviewed runtime-readiness
phase explicitly designs otherwise.

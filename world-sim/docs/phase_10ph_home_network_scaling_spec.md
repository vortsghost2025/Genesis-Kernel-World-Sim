# Phase 10PH — Home-Network Scaling Specification

## Operator request (2026-11-08)

Apply the shelter bonuses to building **one larger home**, not to numerous
small shelters: heat retention, vitality recovery, and food storage should
all scale with the home's roofed footprint. Docs-only; implementation is
Phase 10PJ. Phase chain: 10PH (spec) → 10PI (metadata sync) → 10PJ
(implementation candidate).

## Measured problem

- Live lanes contain 63 (East) and 134 (West) shelter-like objects, split
  across 48 and 39 distinct tiles, while `world_state.compounds` is empty
  in both. New small shelters each conjure base shelter protection for
  their neighborhoods, so scale is obtained by spreading duplicates.
- Thermal tiers exist only for explicit `addon_to` compounds. Connected,
  naturally adjacent shelters are never recognized as one home, so the
  physics rewards count and spread rather than footprint.
- No spoilage/timestamp mechanic exists for deposited food. A home's
  practical storage bonus is therefore expressed through its shared roofed
  footprint and cellar capacity behavior rather than an invented decay
  clock.

## Fix

1. **Roofed footprint network.** Compute the connected network of roofed
   shelter structures reached from the agent's current tile via tile
   adjacency (same continent, Chebyshev 1). Distinct tiles count once;
   `cabin` counts as two footprint units and other shelter/roof kinds
   count one. A single isolated shelter has mass 1; an integrated home
   grows with its roofed footprint.
2. **Tiered home bonuses.** The shelter's warmth floor, cold-decay factor,
   warmth approach, and rest-regeneration scale with connected footprint:
   1, 2, 3–4, 5–7, 8+ footprint units. One small shelter remains the
   baseline; a larger home is strictly better, with diminishing returns.
3. **Storage tie-in.** `storage_cellar` deposits share the home network's
   footprint: a cellar in a footprint-N home exposes a storage budget of
   `N × 20` units. Standalone many cellars do not gain unbounded storage
   from raw count; adding footprint to one connected home does. The budget
   applies per cellar object in the network, not to external containers.
4. **Prompt disclosure.** The cognition model receives the agent's home
   footprint and states the exact current physics in plain fact language:
   cold decay, comfort floor, rest regeneration, and cellar storage budget.
   No banned directive phrasing.

## Verification

1. TDD: unit/runtime tests for a single structure, adjacent 3-, 5-, and
   8-footprint networks; disconnected duplicates must not raise mass;
   duplicates on one tile must not inflate mass; cabin counts heavier.
2. Existing compound and survival suites plus CI list; banned-phrase scan.
3. The implemented change goes live with lockstep heartbeats; no
   `world-sim/data` writes, no migration of existing public objects, no
   prompt directives.

## Out of scope

No camera/viewer work, no taming, no goal injection, no food-spoilage
clock (missing physics is not invented here), no runtime restart.

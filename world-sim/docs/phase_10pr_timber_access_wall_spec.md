# Phase 10PR — The Timber Access Wall (Specification)

## Operator request (2026-11-09)

The operator asked where the sim can improve after the drink-phrasing fix. The
audit nominated the West build wall. Docs-only; implementation is Phase 10PT.
Phase chain: 10PR (spec) → 10PS (metadata sync) → 10PT (implementation
candidate).

## Measured problem (live lanes, 2026-11-09, tick 11,825 west / 11,451 east)

West Eve's build log is the loudest signal in either lane:

| Reason | Count (all time) |
|---|---|
| `Insufficient timber: need 2, hold 0` | 218 |
| `A shelter needs at least 2 structural timber … you declared 0` | 13 |
| `Insufficient timber: need 2, hold 1` | 12 |
| `Insufficient timber: need 3, hold 0` | 3 |
| `Insufficient wood: need 2, hold 0` | 4 |

In the same window West Eve attempted **271 builds and succeeded on 23
(~8.5%)**. The lane's cumulative build success is 407 of 645 (~63%), so this is
a regression in *her* loop specifically, not a global rule problem.

The store explains it exactly. At the same instant:

- `west_eve` holds **timber 4, wood 186, stone_axe 1**
- `west_adam` holds **timber 198, wood 25, stone_axe 1**
- The only shared containers on the west continent hold **clay and wood**:
  `adam_clay_storage_35_51_001 {clay 1}`,
  `adam_clay_storage_35_52_001 {clay 6}`,
  `adam_storage_36_52_001 {clay 10}`,
  `my_wood_container_002 {wood 1}` — **zero timber has ever been deposited.**
- West Adam is the lane's only productive hewer (108 `hew_timber` today vs
  Eve's 14) and his hoard sits in his personal inventory.

So the wall is not that timber is unobtainable. It is that **the one agent who
produces structural timber never puts it anywhere the builder can reach, and
the builder never asks for it.**

East shows the same shape in miniature: 45 `declared 0` rejections and 22 roof
rejections, with East Adam ending at timber 12 and stone_axe 0 (the 10PM wear
system retired his only axe).

## Root cause

Three gaps compound:

1. **No shared-material disclosure.** The cognition prompt states the agent's
   *own* timber/stone/wood (`settlement_lines`) but never states the partner's
   holdings. Eve cannot reason about a hoard she cannot see. This is the same
   class of information-fidelity defect 10OU fixed for the operator channel.
2. **No reachable hand-off channel.** `use_object deposit/extract` is the only
   inventory-to-inventory path, and both require the agent to be standing on
   the container's tile. Adam's containers are ~6 tiles from Eve's build site
   and hold clay, so there is nothing to extract even if she walked there.
3. **No recovery when the tool breaks.** 10PM made axes wear out. East Adam is
   now at `stone_axe 0` with 672 stone and no fallback, so the timber supply
   chain has a single point of failure.

## Fix (Phase 10PT)

### 1. Factual partner-holdings disclosure (facts only, no directives)

`AgentContext` gains `partner_holdings: dict`. The runtime fills it from the
store's other agent inventory, projected to the same bounded resource kinds the
settlement section already uses (`timber`, `wood`, `stone`, `clay`,
`fiber_plants`) plus the count of any durable tools.

The cognition model renders one line, in the settlement register, only when the
partner holds something the agent does not:

```
- Fact: your companion holds timber 198, wood 25, and 1 stone_axe.
```

Bounded to the same 120-char discipline as the other settlement lines. No
banned directive phrasing — it says what is true, never who should move or
what to ask for. Absent when the partner holds nothing relevant, so an empty
store stays silent.

### 2. Adjacent shared-container access

`use_object` deposit and extract currently require the object on the agent's
own tile. Extend both to own-tile-or-adjacent (Chebyshev ≤ 1) for objects whose
type is a container/storage/cache/chest/barrel/crate/well/cellar — the same
adjacency rule the drink path already uses for vessels. Deposit still moves
materials from the agent's inventory into the container's `contents`; extract
still moves them back. Containers built by either agent are usable by both
(contents-based, already true). No new action, no new schema field.

### 3. Stone-knapping fallback when no axe exists

`hew_timber` currently requires `stone_axe`, `iron_axe`, `axe`, `flint_knife`,
`knife`, or `knapped_flint`. When an agent holds **none** of those but holds
≥ 2 stone and ≥ 1 wood, `hew_timber` succeeds at the blade yield (1 timber) by
spending 1 stone and 1 wood to knap a blade first. This is the honest
stone-age fallback: it costs the materials a `flint_knife` would cost, so it
never makes axes redundant, and it removes the single-point-of-failure that
left East Adam unable to produce any timber at all. The rejection message then
names the fallback instead of dead-ending.

## Verification (Phase 10PT)

TDD, in `world-sim/tests/test_timber_access_wall.py`:

1. `partner_holdings` is projected from the store's other agent and is empty
   when the partner holds nothing relevant.
2. The prompt line renders only when the partner holds something the agent
   lacks, carries no banned directive phrase, and is bounded.
3. deposit/extract work from an adjacent container tile for container types,
   and still reject a non-container object and a non-adjacent one.
4. `hew_timber` with no blade falls back to knapping: consumes 1 stone + 1
   wood, yields 1 timber, and does not fire when the agent holds a blade.
5. The fallback rejection names the stone/wood cost when neither is held.
6. `test_load_bearing_construction.py` still passes: the structural minimum and
   the honest-materials rule are unchanged.
7. Full CI list green; `git diff --check` clean; CRLF=0.

## Out of scope

No viewer work, no new agent action, no change to `_STRUCTURAL_TIMBER_MIN`, no
change to the `addon_to` economy, no taming, no goal injection, no change to
live lane stores, no runtime restart. Lockstep spawns fresh subprocesses per
heartbeat, so the fix goes live on the next tick with no daemon change.

## Boundaries

- Viewer-only? No — this phase is backend/cognition only.
- Zero changes to `world-sim/data`, no migration of public objects, no
  mutation of existing inventories. Existing hoards stay exactly where they
  are; only disclosure and reach change.

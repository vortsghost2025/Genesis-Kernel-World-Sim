# World Pressure Spec — Making the World Ask

Status: SPEC (docs-only phase). No runtime code in this commit.

Related: `docs/build_layer_spec.md` (persistent belongings + build verb,
shipped `05f314f`), `docs/mystery_runtime_integration_spec.md` (occupancy
reveals, shipped `2844c35`).

## 1. The problem this solves

Four agents, 670+ heartbeats, and the same converged routines they found by
tick ~110: East runs an alternating patrol-and-handoff ceremony; West Adam
oscillates between two tiles; West Eve has not left `cont_b_origin_001`
since tick 3. They gather constantly and own things now (build layer), but
**not one has ever used `build`, `inspect_public_object`, or
`revise_charter`.**

The build layer gave them hands that remember. It did not give them a
reason to use them. Analysis of the last 70 heartbeats shows the root
cause is not ignorance of the menu — they read it — it is that **the world
asks nothing of them.** Gathering always succeeds, tiles restock every
heartbeat, movement is free, and nothing degrades. In that world the
optimal policy is: stay where food is, gather, talk. A stable equilibrium.

To make the world ask, we change world *physics* — costs and limits — never
agent *behavior*. The runtime proposes nothing. It only stops being free.

## 2. What the map already gives us (grounded discovery)

We do not have to invent scarcity. `data/world/true_map.json` is already
authored with sharp asymmetries (verified 2026-09-26):

| Resource | Records | Total units | Note |
|---|---|---|---|
| `stone` | 25,799 | 72,775 | abundant |
| `wild_berries` | 21,528 | 63,112 | abundant, renewable |
| `wood` | 11,092 | 32,302 | abundant, non-renewable |
| `clay` | 11,040 | 33,078 | abundant |
| `fiber_plants` | 6,887 | 20,430 | abundant |
| `mushrooms` | 4,329 | 12,953 | food, renewable |
| `edible_roots` | 2,609 | 7,825 | food |
| `fish` / `shellfish` | 1,807 / 1,126 | 5,012 / 3,342 | food, coastal |
| `salt` | 1,699 | 5,181 | rare |
| `flint` | 1,073 | 3,245 | rare |
| `iron_ore` | 710 | 2,084 | rare |
| **`fresh_water`** | **1** | **10** | **exactly one tile on the planet** |

Facts that matter:

1. **`fresh_water` lives on exactly one tile: `cont_a_origin_000`
   (Continent A).** It is renewable (amount 10). **Continent B has no
   fresh water at all.** This is the extreme version of "a resource that
   only exists in one place."
2. `cont_a_origin_000` is one `walk` edge from `public-shared-center` —
   the East pair's meeting point. East sits next door to the planet's only
   spring without knowing it. West is an ocean away from any water.
3. **`hazards` is empty.** No threat is authored. Any hazard is our
   invention, not world data.
4. **`travel_edges` has 281,254 edges, all `mode: walk`, and exactly zero
   cross `cont_a`↔`cont_b`.** The East–West wall is in the data. Contact
   needs a new travel mode (boats/sail) or a designed crossing.
5. Food is abundant everywhere; the same resources that feed also build.
   Food and construction goods compete for the same gather actions and the
   same holdings.

## 3. Candidate levers, evaluated against actual behavior

Each lever was checked against what these four agents actually do, because
a pressure that doesn't touch their policy changes nothing.

| Lever | What it adds | Effect on these agents | Verdict |
|---|---|---|---|
| **Hunger** (consume food/tick) | food becomes a standing draw | East already gathers berries nonstop on its route; West Eve sits *on* food tiles. Mostly just more gathering. | Weak alone |
| **Carrying cap** (two ledgers: food ≤ F, goods ≤ G) | the margin has a price | Turns their infinite-gather loop into a decision: East's food habit meets a food ceiling; West's stone/fiber hoards meet a goods ceiling. The *only* lever that touches all four, including West Eve. | **Strong** |
| **Build = storage** (objects hold beyond the cap) | a verb that resolves the limit | Makes `build` *instrumental*, not decorative: the only way to accumulate past the cap. Closes need↔limit↔verb. | **Strong** |
| **Finite tiles** (depletion persists) | gathering can fail | Adds movement/rotation; doesn't by itself cause building. Known limitation today (tiles restock per heartbeat). | Medium, later |
| **Decay** (built things need upkeep) | ongoing commitment | Only matters *after* they build once. Premature. | Later |
| **Threat/hazard** | fear | Nothing authored; pure invention; coercive; risks scripting panic responses. | Later, carefully |
| **Survival water need** | the one spring becomes existential | Dooms West (no water on their continent) with no counterplay. Cruel, and unreachable. | **No** until a West source or crossing exists |

## 4. Recommended package: Provision + Capacity + Build-as-storage

Three physics, all built on mechanics that already exist (inventory,
gather, build). No new verbs. No recipes. No runtime-suggested builds.

### 4.1 Provision (a need)

- Each agent consumes **1 food unit per heartbeat** from holdings.
  Food kinds are an operator-declared set: `wild_berries`, `mushrooms`,
  `edible_roots`, `fish`, `shellfish`. (Food is abundant, so this is a
  standing draw, not a death clock.)
- If the agent holds no food kind, it is **famished** for that heartbeat:
  recorded truthfully in the observation, and `build` is rejected this
  tick ("you cannot build on an empty stomach"). **No death, no damage, no
  scripted flight to food.** Famine is a state the agent can read and
  respond to however it chooses.
- Famine is *derivable from holdings* — consumption is just a decrement.
  No new persisted state file is needed for hunger.
- Stated plainly (design property): `FOOD_PER_HEARTBEAT = 1` against a
  gather yield of 1 unit per heartbeat makes food-gathering at minimum a
  half-time job. Every non-food heartbeat is net burn. For the East pair,
  who have run an alternating patrol-and-handoff ceremony since tick ~110
  and hold ~16 berries each, the ritual as it exists cannot survive
  contact with this rule — ≈32 heartbeats of runway at their current
  cadence. That is the design working, not a side effect to apologize
  for; it is written down here so its cost is chosen, not discovered.

### 4.2 Carrying capacity (a limit)

- Holdings are carried in **two ledgers**, each with its own cap:
  **food ≤ `FOOD_CAP`** (proposed 20) and **non-food goods ≤
  `GOODS_CAP`** (proposed 20). A `gather` that would exceed the
  corresponding ledger's cap is rejected. The agent sees both ledgers
  (`used/cap`) in the prompt.
- Two ledgers instead of one total-cap because a total-cap has a trap:
  an over-cap agent who runs out of food could not legally gather food
  (any gather would exceed the cap), could not build (famished blocks
  it), and could never self-recover. Splitting the ledgers removes the
  trap by construction: food is always gatherable (up to its own
  ceiling), so famishment is always curable by one foraging heartbeat,
  while goods hoards still force the build question undiluted.
- Existing hoards are **grandfathered**: a ledger already over its cap is
  not confiscated, it simply cannot grow (see the exact net-zero rule in
  §5). Fail-closed and fair.
- Stated plainly (design property): with holdings at spec-writing time —
  East Adam berries 16, East Eve berries 16 (food only); West Adam
  goods 65 / food 18; West Eve goods 51 / food 45 — the caps touch the
  East pair lightly and land their entire onset force on the West pair.
  The agent who has never moved (West Eve, `cont_b_origin_001` since
  tick 3) becomes one of the most-pressured agents on the planet: her
  goods ledger is 2.5× over and can never grow again until she builds,
  and her food ledger, at 2.25× over, can hold steady but never grow.
  We consider that a property of the world they built for themselves,
  not grounds to soften the constants — but it is chosen openly here,
  not discovered later.

### 4.3 Build = the way to hold more (the verb's payoff)

- Any public object the agent **owns** grants storage: materials that have
  been put *into* it do **not** count against the owner's carry cap.
- Putting goods into an object is done by `build`: the materials you
  spend leave your carried holdings at build time and are recorded on
  the object. **Contents are locked, not recoverable, in this phase** —
  there is no withdraw or reclaim verb yet (a deliberate candidate,
  §9). The capacity payoff happens at the moment of construction: what
  you built with no longer rides on your back.
- **No object type is privileged.** A wall, a storehouse, a monument — the
  agent names it. Whatever it is, building is what lets you keep more than
  you can carry. The runtime enforces storage as a physical property of
  construction; it never suggests what to construct.

Why this is the right minimal trio: the need (food) draws holdings down,
the limit (cap) stops infinite accumulation, and the verb (build) is the
only way to raise the ceiling — so the three reference each other with no
authored storyline and no instruction to the agent.

### 4.4 The One Spring (available lever, deliberately held back)

`fresh_water` on a single East-continent tile is the map's most dramatic
authored asymmetry, and the user's "resource that only exists in one
place" is literally already here. It is **not** wired into survival in
this spec, because a survival water need has no West counterplay today
(no water on `cont_b`, no crossing). Options for a later, deliberate
phase — each requiring its own spec and a West-viable path first:

- A West fresh-water source authored onto `cont_b`, then water as a
  second provision.
- Or an ocean-crossing mode (`sail`) so West *can* reach `cont_a_origin_000`.

Until then, water is a rare high-value good the build layer already
accepts as a material. If the agents discover it and build around it, that
is their authorship, not our script.

## 5. Exact mechanics and constants (proposed)

```
FOOD_CAP = 20                            # carried food units (FOOD_KINDS)
GOODS_CAP = 20                           # carried non-food units
FOOD_KINDS = {wild_berries, mushrooms, edible_roots, fish, shellfish}
FOOD_PER_HEARTBEAT = 1                    # consumed from holdings each tick
```

Ordering within a heartbeat (per agent), fail-closed:

1. **Consume**: if any food kind is held, decrement 1 of the most-held
   food kind (`add_to_inventory(..., -1)`); else mark famished.
   `famished(t)` therefore reflects holdings at the *start* of the tick:
   food gathered this tick relieves famine from next tick, not this one.
2. **Observe**: build the fog observation; attach additive keys
   `provisions` (`{food_units, famished: bool}`) and `carrying`
   (`{food_used, food_cap, goods_used, goods_cap}`). These are per-agent
   personal state, present every tick, and leak nothing about the hidden
   map.
3. **Act**: `gather` validates the cap rule below; `build` validates
   not-famished, placement, materials, affordability (unchanged from
   `build_layer_spec.md`).

   **Cap rule, precisely.** Split holdings into ledgers: food units `F`
   (sum over `FOOD_KINDS`) and goods units `G` (everything else). `S_F` is
   the food ledger at the start of this heartbeat (pre-consumption).
   **Food gather**: allowed iff post-gather `F ≤ max(FOOD_CAP, S_F)` —
   fill to the cap, or when over the cap replace only what was just
   consumed; an over-cap food ledger also burns down 1 per heartbeat
   toward the cap (the world eats your hoard). **Goods gather**: allowed
   iff post-gather `G ≤ GOODS_CAP` — goods are never consumed, so an
   over-cap goods ledger cannot grow *and cannot even refill*; it shrinks
   only by building. That asymmetry is the point: hoarded food decays
   through appetite, hoarded goods pressure you to construct. Frozen
   rejection strings (contract — the §8 census counts them):
   `"hands full"` (goods), `"food store full"` (food).

   Trap check, by construction: an agent with `F = 0` and `G` over cap
   may still gather food (post-gather `F ≤ max(FOOD_CAP, 0)`), so no
   famished-and-frozen state exists. Famished blocks only `build`, and
   famine is curable in one foraging heartbeat — the build-block is a
   speed bump, never a wall.

   Trap check, by construction: an agent with `F = 0` and `G` over cap
   may still gather food (post-gather `F ≤ max(FOOD_CAP, 0)`), so no
   famished-and-frozen state exists. Famished blocks only `build`, and
   famine is curable in one foraging heartbeat — the build-block is a
   speed bump, never a wall.
4. **Persist**: inventory write via `add_to_inventory`; world state via the
   existing end-of-tick path. Canonical heartbeat history remains
   append-only; nothing already written is rewritten.

Cap accounting: ledger totals are sums over the agent's holdings only.
Built objects never re-enter either ledger: their materials were
deducted from holdings at build time (build layer, shipped) and live on
the object's `materials` field from then on. No new contents structure
is added in this phase. The exporter ships `provisions`, `carrying`,
and the frozen rejection strings so the public show and the §8 census
read the same truth.

## 6. Compliance

- **Fog/no-leak**: `provisions` and `carrying` are personal state, not map
  data. No distance, no hidden tile, no mystery structure enters the
  observation. Fail-closed: any error in the provision step leaves holdings
  unchanged for that tick.
- **Append-only canon**: consumption mutates the inventory file only (the
  same file the build layer writes); it never rewrites heartbeat history,
  provenance, or the true map.
- **One action per heartbeat**: unchanged.
- **Operator vs agent**: the operator sets only these constants (physics).
  The runtime never names a build, never suggests one, never tells an agent
  to eat, move, or gather.

## 7. What this deliberately does NOT do

- No recipes, no tech tree, no privileged "storehouse" type.
- No death, no health bar, no damage. Famine is a readable state, not a
  punishment loop.
- No threat/hazard authoring (the map has none; that is a separate,
  deliberate phase).
- No scripting of responses to scarcity. We add the question; they write
  the answer.
- No water-survival need (see §4.4).
- No confiscation of existing hoards.

## 8. Risks and falsification

The honest risk: **capping out and idling.** Agents may hit the caps,
stop gathering, and do even less — the equilibrium shifts rather than
breaks. Under the two-ledger rule the worst case is a *hold-steady
stall*: West Eve can hover at food 45 forever, eating and re-gathering
one berry a tick, and never build anything. The §5 trap check means
there is no famished-and-frozen state — but note what remains sharp:
famished blocks `build`, so an agent at zero food loses that heartbeat's
build and must spend a tick foraging first. Pressure without a pit.

The wedge this creates, stated openly: West Adam (goods 65, food 18)
cannot grow his goods ledger and burns food every non-foraging tick. He
is not trapped — food is always gatherable — but his comfortable
gather-stone routine is over. The only way his hoard ever grows again
is a build. That is the single most pointed question this spec asks any
agent, and it is asked of him first. If he answers by idling, we will
have learned that limits without stakes are insufficient; that is what
the census below is for.

How we would know, measured over a 100-heartbeat arc (behavior census,
computed from heartbeat-record outcomes using the frozen §5 rejection
strings):

- `cap_hit_rate` — fraction of gather attempts rejected by either
  ledger's cap (`"hands full"` / `"food store full"`).
- `famish_rate` — agent-heartbeats famished.
- `build_rate` — builds per 100 heartbeats (today: 0).
- Action-census shift away from `gather`/`move` toward `build`.
- Whether any agent ever moves toward `cont_a_origin_000` (the spring).

If `build_rate` stays 0 after cap pressure is live, the conclusion is
that a limit alone is insufficient and the next lever is scarcity with
*consequence* — most likely the One Spring with a crafted West path, or a
gentle hazard — not more limits.

## 9. Non-goals / future levers

- Tile depletion persistence (make `renewable` mean something).
- Object decay / upkeep.
- Ocean crossing (`sail` travel mode) — unlocks the One Spring and
  East–West contact in one move.
- Water as a second provision, once §4.4 is satisfied.
- A hazard, authored deliberately (the map has none today).
- `deposit`/`withdraw` verbs so objects are true warehouses rather than
  build-time contents.

## 10. Test plan (TDD outline, for the implementation phase)

Inventory/economy:
- consume picks most-held food kind; no food → famished, holdings unchanged.
- `famished(t)` reflects tick-start holdings: a successful food gather
  this tick does not clear this tick's famished flag.
- famished blocks build; non-famished build unaffected.
- two-ledger cap: food gather fills to `FOOD_CAP` then rejects with
  exactly `"food store full"`; goods gather fills to `GOODS_CAP` then
  rejects with exactly `"hands full"`.
- over-cap grandfathering: an over-cap goods ledger rejects every goods
  gather (it shrinks only by building); an over-cap food ledger may
  replace exactly the 1 unit consumed this heartbeat and no more.
- trap check: an agent at food 0 / goods over cap may still gather food;
  a provision-step error leaves holdings byte-unchanged.
- build materials deducted at build time never re-enter either ledger;
  no reclaim path exists this phase.

Cognition/context:
- prompt shows `provisions` and `carrying` (both ledgers); famished line
  appears only when famished; no map leak (assert hidden tiles/mystery
  ids absent).
- food/build competing for the same holdings is reflected truthfully.

Compliance:
- heartbeat history byte-unchanged by a provision tick; true map untouched.
- fail-closed: a provision-step error leaves holdings as they were.

Behavior (non-unit, observational): the §8 census, run as a live arc.

## 11. Decision requested

Approve the **Provision + Capacity + Build-as-storage** trio (two-ledger
constants in §5) for implementation as the next candidate phase? Or adjust
the caps and food policy first? The One Spring (§4.4) stays held back
pending a West path.

Revision history: v1 (initial spec) → v2 (review pass): one total-cap
split into two ledgers after the famished-and-frozen trap was found in
review; net-zero gather rule made precise; build contents made locked
(deposit/withdraw stays future work); onset asymmetry, the East
treadmill, and the West wedge stated as explicit design properties.

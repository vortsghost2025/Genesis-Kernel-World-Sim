# World Observation Transmission Spec — Closing Three Measured Gaps

**Status:** SPEC (docs-only phase). No runtime code in this commit.
**Date:** 2026-09-28
**Triggered by:** operator question — "if it rained and sucked outside they would be
more inclined to build something to protect from the elements"
**Amends:** nothing. Narrows a proposal that measurement rejected.

---

## 0. Correction to the operator's premise, and to mine

The operator's suggestion was weather as a *shelter incentive*. Measurement
rejects the framing and keeps a smaller, better version of the idea. This
section records both, because a spec that hides its own rejected reasoning is
not worth much.

**The operator's framing is wrong** for the same reason the hunger mechanic was
wrong: it assumes motivation is the binding constraint. Hunger shipped fully
implemented and fired 0 times in 70 heartbeats. The spec's own §0.1 found the
real cause was a board defect plus an untransmitted rules change — not that
hunger is a human concept. "They'd build shelter if it rained" is that same
category of reasoning.

**My own first answer was also wrong**, and worse, because I stated it with
confidence. I told the operator the agents "cannot see they're standing on a
hill" and "cannot see what the tile offers." Both false. I had read
`first_pair_runtime.py:524-554` — the *legacy* observation dict — and missed
that the fog-gate path builds a far richer observation through
`cognition_safe_observation()`. The measured baseline in §1 corrects it.

What survives is narrower and more interesting than either of our proposals.

---

## 1. Measured baseline: what the agents actually receive

Built with the real adapter, real known-map, real true map, 2026-09-28, for
`east_adam` at his HB941 position. This is the board, not a description of it.

```json
{
  "tile_id": "cont_a_gen_1_1",
  "visible_tiles": ["cont_a_gen_1_1", "cont_a_gen_1_2", "cont_a_gen_2_1",
                    "cont_a_origin_001", "cont_a_origin_002"],
  "objects_here": [],
  "visible_tile_details": [
    {"tile_id": "cont_a_gen_1_1", "terrain": "hill", "biome": "highland",
     "landmarks": [], "resources": ["stone"]},
    {"tile_id": "cont_a_gen_1_2", "terrain": "hill", "biome": "temperate_hills",
     "landmarks": [], "resources": ["clay", "stone"]},
    {"tile_id": "cont_a_origin_001", "terrain": "forest", "biome": "temperate_forest",
     "landmarks": [{"landmark_id": "lm_old_oak", "kind": "tree",
                    "description": "An ancient oak standing watch at the forest edge."}],
     "resources": ["wood"]}
  ]
}
```

Rendered verbatim into the prompt at `first_pair_cognition_model.py:945-946`.

**What is already good, and must not be disturbed:**
- terrain and biome, per visible tile
- resources, per visible tile (projection from 89,700 true-map resource entries)
- landmarks with descriptions
- radius-limited visibility, enforced by the known-map merge
- `physics` version notice, `operator_messages`, charter, belongings

**Knowledge is also improving.** Adam is at 16 known tiles and Eve at 17, up
from the 12/14 measured across HB700–800. The recent hill-tile move was real
progress. The "0 new tiles in 100 ticks" figure is stale.

---

## 2. Gap A — `water` is dropped, and there is exactly one drinkable tile in the world

`first_pair_fog_adapter.py:265-271` projects exactly four fields per visible
tile: `tile_id`, `terrain`, `biome`, `landmarks`, `resources`. The true map
carries two more that are silently discarded:

- `water` — `{"type": "sea"|"river", "drinkable": bool}`, present on 11,511
  tiles
- `hazards` — present on the same tile records

**Why this is the highest-value gap in the entire observation.** The world
contains exactly **one** tile carrying `fresh_water`:

| tile | terrain | water | landmark |
|---|---|---|---|
| `cont_a_origin_000` | grassland | river, **drinkable: true** | `lm_origin_river` |

That is one tile in 80,000. The agents have been circling water since the
first live conversation loop in Phase 3E, which converged on "find water
together"; their post-restart goals were explicitly *"verify whether any
animal movement pattern or **hidden water source** exists"* (6T-C, 6V-C); and
they asked the operator to confirm the world's terms 12 times. **They cannot
see it, because `water` is not transmitted.** The one fact their longest
standing question is about is sitting in the observation source and dropped at
the projection boundary.

This is not a new pressure. It is a missing fact in an otherwise rich
observation.

## 3. Gap B — `hazards` is dropped for the same reason

Same projection line, same cause. Lower stakes than water; included because
splitting the fix across two phases doubles the measurement cost for one
mechanical change.

## 4. Gap C — conditions exist, are implemented, and are hardcoded off

This is the part of the operator's weather idea that is real, and it is not a
comfort mechanic at all.

**It already exists, twice over:**
- `state.py:84-85` cycles `weather` through `gentle, warm, cool, gentle` every
  8 ticks.
- `fog_of_war.py:256-265` `_condition_radius()` already implements weather as a
  **dial on observation radius**:
  ```python
  if visibility in {"low", "storm", "fog"} or time_of_day == "night" \
     or terrain in {"cave", "dense_forest"}:
      effective -= 1
  ```

**And it is switched off at the call site.** `first_pair_runtime.py:356-358`:

```python
obs = cognition_safe_observation(
    true_map, position, known_map, None, objects_here, agent_ref
)                       # ^^^^ conditions hardcoded None
```

So weather cannot affect what they see, because the dial is never given a
value.

**This is the same legibility pressure the spec already endorsed.** §0.2 of
`epistemic_pressure_spec.md` withdrew the invented "unverified ground"
mechanic on the grounds that *"the fog already supplies exactly the right
pressure — movement is the only source of new knowledge."* Weather-conditioned
visibility is a **dial on that existing pressure**, not a new human need
imported alongside it. The operator's instinct was pointing at something real;
it was just aimed at shelter rather than sight.

### 4.1 Critical separation: transmission is not pressure

Wiring `conditions` into the radius call **changes behaviour**. Adding `water`
and `hazards` to the projection does not — it only makes facts visible that
were already true and already computed.

They must not ship in the same phase. The epistemic spec's own attribution
rule:

> One pressure per phase is what let us read the "to reduce goods overcapacity"
> framing at all; adding a second new pressure to this one would make any
> improvement unattributable.

**Phase 1 (this spec): transmission only.** `water`, `hazards`, and a
read-only `conditions` field reporting current weather/visibility. Radius
behaviour unchanged. Zero behavioural change; this is a plumbing fix.

**Phase 2 (deferred, separate spec): the dial.** Populate `conditions` at the
call site so storm genuinely narrows sight. That is a pressure change and
deserves its own falsification census.

---

## 5. What this phase deliberately does NOT do

- **No shelter mechanic.** No "build to get warm", no comfort verb, no
  wetness state, no death. That is the operator's original proposal, and
  measurement rejects it: shipping a capability does not cause its use.
- **No behaviour nudge.** No prompt text telling agents to explore, notice,
  build, or look for water. The world states facts; the agents decide.
- **No change to gather, build, or the physics rules.**
- **No change to the fog radius in this phase** (§4.1).
- **No new observation key visible to non-visible tiles.** See §6.

---

## 6. Leak analysis — what must stay hidden

The projection's existing discipline is that only radius-visible tiles appear,
and the known-map merge is untouched. This phase preserves that exactly.

| field | scope | leak risk |
|---|---|---|
| `water` on visible tiles | radius-visible only | none — you can see a river |
| `hazards` on visible tiles | radius-visible only | none — you can see a hazard |
| `conditions` (weather/visibility) | global, positionless | none — the sky is public |

The `_FORBIDDEN_PROMPT_STRINGS` contamination check
(`first_pair_fog_adapter.py:281-287`) runs after the projection and must
continue to run. A new field is added **before** that check so it is covered
by it.

**Deliberately withheld:** the `fresh_water` tile's identity must not be
singled out anywhere in code, prompt, or ordering. The fact that it exists is
legitimately world knowledge. Which tile it is must be learned by walking
there. No hint, no ordering, no "rare resource" annotation.

---

## 7. Persistence gap (recorded, not fixed here)

`heartbeat.json` stores `"observation": {}` for HB941 — the observation is not
recorded, so we cannot audit what an agent was shown. That is a real gap and it
is why §1 had to be reconstructed by calling the adapter directly.

Recorded here rather than fixed, because it changes the heartbeat record shape
and deserves its own decision. **A phase that measures behaviour needs the
measure to exist first.**

---

## 8. Test plan (TDD outline)

Transmission (Phase 1):

- `visible_tile_details` includes `water` for a visible tile carrying water
- `water` is absent (not null, not empty) for a tile with no water
- `hazards` included for a visible tile carrying hazards
- fields appear **before** the contamination check, so a forbidden string in
  water/hazards raises `FogAdapterError`
- the observation still contains no tile outside the visible set — a
  never-seen tile's `water` must not appear anywhere in the serialized
  observation
- the singular `fresh_water` tile is reachable only by observation, never
  referenced by id anywhere in the projection code
- `conditions` is reported in the observation but does **not** change
  `visible_tiles` (Phase 1 has no behavioural change)
- byte/byte regression: with no water/hazards present, the observation is
  unchanged from the current shape

Compliance:

- no test touches `world-sim/data`, connects to a provider, or runs a daemon
- tempdir and fixture true-maps only
- `git diff --check` clean, LF-only

---

## 9. Falsification census

This is a **plumbing** phase, so the decisive test is that nothing regresses
and the facts are now present. Per the epistemic spec: *"a removal that
changes nothing behaviourally is still a success, provided the deadlock is
gone"* — the same standard applies to an addition.

| signal | baseline | passes if |
|---|---|---|
| observation contains `water` | never | present for visible tiles carrying water |
| observation contains `hazards` | never | present for visible tiles carrying hazards |
| observation contains `conditions` | never | present, and read-only |
| `visible_tiles` set | unchanged by this phase | **identical** — proves no pressure was added |
| known-tile growth | 16 / 17 | does not regress |
| action census | as measured | no forced shift toward any new verb |
| food-conversion questions | 0 since the changelog | stays 0 |
| gather rejections on barren tiles | 19 → 4 across the prior arc | stays low |

**The `visible_tiles` row is the guard on this phase.** If it moves, this
phase shipped a pressure change it was explicitly forbidden to make.

---

## 10. Decision requested

1. Approve Phase 1 (transmission only) as specified.
2. Confirm the singular `fresh_water` tile stays a discovery — no hint, no
   annotation, no code reference.
3. Confirm Phase 2 (the radius dial) is deferred to its own spec, and that
   the shelter mechanic stays rejected.
4. Note §7 (observation persistence) as a separate decision; it should land
   before any phase that tries to measure behaviour change.

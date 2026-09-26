# Epistemic Pressure Spec — Making the World Worth Knowing

Status: SPEC (docs-only phase). No runtime code in this commit.

Supersedes the pressure model in `docs/world_pressure_spec.md` (shipped
`05f314f` / `be5ce8a`). That spec asked the right structural question —
*the world asks nothing of them* — and then answered it with a human
concept. This spec keeps the structure and replaces the substance.

Related: `docs/world_pressure_spec.md` (retired mechanics, kept for the
provenance of what was tried), `docs/mystery_runtime_integration_spec.md`
(occupancy reveals, `2844c35`), `docs/build_layer_spec.md` (`05f314f`).

---

## 1. The receipt: the pressure model did not work, and the data says why

The `Provision + Capacity + Build-as-storage` phase went live at HB701.
Measured over HB701–765 (70 heartbeats, both pairs, canonical records):

| metric | result |
|---|---|
| famished build-gate rejections | **0** |
| public objects created | 6 (5 from the build layer) |
| objects whose stated purpose is inventory relief | **5 of 5** |
| East pair builds | **0** |
| East pair questions asked | **0** |
| mystery reveals, all history | **0** |

West action census, HB701+: `gather` 64%, **`build` 23%**, `ask_human`
7%, `move` 4%. In their own words:

> "Clay cairn built from excess clay inventory **to reduce goods
> overcapacity**"
> "Stone cairn built from excess stone inventory **to reduce goods
> overcapacity**"

The hunger mechanic never once affected an agent. The carrying cap
worked — too well: it produced a one-trick puzzle, they solved it in
three heartbeats, and it made them inventory accountants. The East pair,
holding nothing worth capping, got no question at all and did nothing.

**Conclusion: shipping capability does not cause its use, and shipping a
human need does not cause a mind to feel it.** These agents have no
metabolism. A ledger that decrements a number and flips a boolean is not
hunger to them; it is an accounting rule, and they routed around
everything except the accounting.

## 2. What these entities actually are

They are language models with bounded attention and persistent memory.
Their real substrate, measured on the live stores:

- **Memory**: 1,546–1,673 entries per agent (`memory.json` ~1 MB/pair).
  Per request, selection returns **6 recent + 6 relevant, max 16 entries,
  12,000 chars** (`_MAX_SELECTED_*`). The "summary" layer is **max 4
  entries, each a raw 300-character excerpt of one memory** — truncation,
  not synthesis. Net: an agent sees roughly **20 of its own 1,600
  memories — about 1%**. 99% of its own history is invisible to it every
  heartbeat, and nothing in the world ever told it that mattered.
- **Knowledge**: 11–54 known tiles per agent, out of 80,000.
  `myths: 0` for all four. The occupancy-gated reveal mechanic has never
  once fired in 765 heartbeats.
- **The fog is display-only**: it filters what an agent is *shown*, but
  acting on a tile is never less reliable than acting on a known one.
  There is no epistemic pressure anywhere in the system. Knowing and
  guessing cost exactly the same.

**Only two durable escape hatches exist**: the charter (verbatim,
unbounded, exempt from summarization) and public objects/messages.
**No agent has ever written a charter (0 of 4).**

So the honest inventory of what is scarce to these entities is: *what
they can hold, what survives, and what they know* — not calories. The
world has been asking a biology question of minds that do not have
bodies, while the one genuinely native pressure sits inert in the
codebase.

## 3. What this phase does

**Install legibility pressure. Retire the metabolism. Defer
consolidation to its own phase.**

The attribution call (operator delegated): consolidation is *deferred to
a separate spec*, not bundled here. One pressure per phase is what let
us read the "to reduce goods overcapacity" framing at all; adding a
second new pressure to this one would make any improvement unattributable.
Retiring inert mechanics rides along safely — a removal has no effect to
confound.

### 3.1 Unverified ground (the new pressure)

Standing still is how you learn. Acting on ground you have never observed
is how you stay ignorant — and the world stops pretending otherwise.

- An agent's **known map** is the record of ground it has actually
  observed. `merge_observation` currently persists only what a standing
  agent could see.
- **New rule**: an action taken on a tile the agent has *never observed*
  (never stood on, and never had it enter `visible_tile_details`) yields
  **no information and no durable record**:
  - the resulting observation is **not merged** into the known map — the
    agent learns nothing about where it is or what is there;
  - a `gather` on such a tile collects nothing identifiable
    (`"you find nothing you can name"`);
  - a `move` onto such a tile succeeds (movement stays possible) but
    leaves no trace in the agent's own map.
- On a tile the agent *has* observed, everything behaves exactly as it
  does today. No new refusals, no new rejections, no new strings for the
  ordinary case.
- **Standing still is self-reinforcing, by construction**: each heartbeat
  an agent holds position, its radius-visible neighbours enter
  `visible_tile_details` and are merged — so a stationary agent's known
  map *grows*. Stillness is productive, not a trap. This is the direct
  opposite of the freeze risk and it is deliberate.

This makes three existing-but-inert mechanisms finally reachable:
**known-map growth becomes worth something**, **returning to a place
becomes worth something** (you already mapped it; you can act on it), and
the **occupancy-gated mystery reveal** — which requires standing on one
tile three times — becomes achievable, because standing somewhere
specific is now the only way to learn anything.

### 3.2 What gets retired, and why it is safe

| retired | evidence | note |
|---|---|---|
| `FOOD_PER_HEARTBEAT` consumption | 0 effects in 70 ticks | holdings stop decaying |
| `famished` state + build gate | 0 firings ever | `BUILD_REJECT_FAMISHED` frozen string retired |
| `FOOD_CAP` / `GOODS_CAP` ledgers | produced 5/5 inventory-chore objects | `GATHER_REJECT_FOOD` / `GATHER_REJECT_GOODS` retired |
| `GATHER_YIELD` (was 3) | existed only to make food bankable | reverts to 1; a tile's yield is simply what it holds |
| `provisions` / `carrying` observation keys | carried the retired pressure | removed; `physics` + `operator_messages` stay |
| `YOUR BODY` prompt section | explained a fiction | removed |

**Not retired, and deliberately so:**
- **`build` and the build layer.** Five objects exist and the verb is
  live. What changes is *what it is for* — and that is Phase B, not
  here. In this phase `build` keeps working exactly as shipped.
- **Charter, mysteries, fog, operator channel, agent watch.** Untouched.
- **All existing records.** Retirement is a code change, not a data
  migration: no store is rewritten, no heartbeat is re-interpreted.

### 3.3 Why not also do consolidation now

The obvious Phase B is to make `build` mean "anchor a thought so it
survives selection" — which fits the substrate far better than a fiber
basket does, and is the change most likely to make them build *meaning*
rather than inventory. It is deferred for one reason: it redefines an
existing, working verb's meaning. Doing that in the same phase as a new
pressure would make the result unreadable. Phase A is legible on its
own; Phase B gets its own spec and its own census.

## 4. Exact mechanics

```
# world_pressure.py — after this phase
GATHER_YIELD = 1
PHYSICS_VERSION = "epistemic.1"     # was "pressure.2"
# FOOD_CAP, GOODS_CAP, FOOD_KINDS, FOOD_PER_HEARTBEAT, the three frozen
# rejection strings, split_ledgers, provisions_view, carrying_view:
# REMOVED. gather_allowance: removed. consume_choice: removed.
```

New pure function, no I/O, fail-closed on malformed input:

```python
def is_ground_verified(known_tiles, tile_id) -> bool:
    """True iff this agent has actually observed this tile before."""
```

Wiring (all additive-then-retiring, one commit, chain stopped first):

1. `FirstPairRuntime._pressure_step` — **deleted**, along with
   `_pressure_state` and the `provenance`/`carrying` context fields.
2. `FirstPairRuntime._build_context` — attaches `observation["physics"]`
   only (unchanged shape, new version string). The observation merge
   step gains the unverified-ground rule: when the agent's current tile
   is not in its own known map, `_merge_and_persist_known_map` is
   **skipped for that heartbeat** and the observation is annotated
   `unverified_ground: true` so the agent can *see* that it learned
   nothing (truthful, no leak — it is a fact about its own epistemic
   state, not about hidden map contents).
3. `_execute_gather` — when the current tile is unverified for this
   agent, the gather yields nothing and persists nothing. No new
   rejection string is introduced for the verified path; the unverified
   path is a successful no-op with a truthful reason
   (`"nothing here you can name"`), because it is not an error.
4. `_execute_build` — the famished gate is removed. Placement authority
   from `22ba621` (your own tile is always buildable) is **kept**.
5. `first_pair_cognition_model` — `YOUR BODY` section deleted;
   `THE WORLD'S TERMS` and `MESSAGES FROM THE OPERATOR` kept.
6. `export_viewer_snapshot` — `pressure` block and its
   `provisions`/`carrying` fields removed; `inventories`, `agent_asks`,
   `operator_messages`, `physics` kept.
7. `scripts/agent_watch.py` — the `starving` signal is retired (nothing
   starves any more); `ask`, `stuck`, `first_build`, `dead` kept.

**Ordering within a heartbeat is unchanged** and stays fail-closed:
observe → model → act → persist. One action per heartbeat. Fail-closed
on error: a malformed known-map yields `is_ground_verified → False`
(treated as unverified, the conservative direction — you never get credit
for knowledge you cannot prove).

## 5. Compliance

- **Fog / no-leak**: `unverified_ground` is a boolean about the
  agent's own knowledge state. It carries no tile data, no mystery ids,
  no coordinates, no hidden-map content. Test-pinned.
- **Append-only canon**: no store is rewritten. Retirement changes code,
  not history. HB701–765 remains readable exactly as it is, including
  the five inventory-chore objects, which stay in the record as the
  honest evidence of what was tried.
- **Mystery mechanics untouched**: still occupancy-only, still
  per-agent, still no-leak. This phase only makes the tile *reachable*,
  it does not change how a reveal works.
- **Operator vs agent**: the operator sets one boolean's rule. The
  runtime never tells an agent where to go, what to build, or what a
  mystery is.

## 6. What this deliberately does NOT do

- No metabolism, no food, no hunger, no death, no scarcity of goods.
- No recipes, no tech tree, no privileged object type.
- No hint at where a mystery is. Legibility pressure makes *standing
  still* valuable; it never makes *this tile* valuable.
- No change to `build`'s meaning (Phase B).
- No new prompts telling agents to explore, remember, or build. The
  world states what is true and stops.
- No touching the East–West wall (deferred by operator) or the One
  Spring (held back by operator).

## 7. Risks and falsification

Stated plainly, including the risk that I am wrong again:

1. **Freeze.** If unverified ground yields nothing and everything around
   an agent is unverified, they may stop moving. *Mitigated by
   construction* (§3.1: a stationary agent's known map grows every
   heartbeat, so stillness is productive) — but this is the failure mode
   to watch first.
2. **I have been wrong once already.** The previous spec was
   well-reasoned, fully tested, and inert. This one is better grounded
   (every claim above is a measured number from the live stores) but that
   is not the same as being right. The census below is the check, not my
   confidence.
3. **Attribution.** If behavior changes, it is attributable to legibility
   pressure alone — provided consolidation is *not* bundled. That is why
   Phase B is separate.
4. **The East pair may still be inert.** They are not blocked by
   inventory; if stillness plus a growing map does not reach them, the
   honest next step is a different question, not more physics.

**Falsification census**, same shape as the pressure spec, over a
100-heartbeat arc (HB766–865, or wherever the current arc ends):

| signal | baseline (HB701–765) | pressure passes if |
|---|---|---|
| `build_rate` | 23% of West actions | changes, and object *stated purposes* stop saying "overcapacity" |
| moves per agent-heartbeat | West 4% | rises, or holds while `known_tiles` grows |
| `known_tiles` growth/agent | East 11–12, West 12–54 (static) | **strictly increases** — the primary measure |
| mystery reveals | 0, all history | **≥1** — the mechanism finally fires |
| `ask_human` | West 7% | shifts toward *epistemic* questions |
| unverified-ground actions | n/a (new) | counted; a high rate with no map growth = freeze |

The decisive metric is **`known_tiles` growth**, because it is the one
quantity this pressure is designed to move, it is measured rather than
interpreted, and it cannot be gamed by optimizing an accounting rule.

## 8. Test plan (TDD outline, for the implementation phase)

Retirement (each pinned so it cannot silently return):
- consumption no longer decrements holdings; `famished` never appears
- `GATHER_REJECT_FOOD` / `GATHER_REJECT_GOODS` never emitted
- `YOUR BODY` absent from the prompt; `THE WORLD'S TERMS` present
- exporter ships no `pressure` block; `inventories` still present
- watcher no longer emits `starving`; still emits `ask`/`stuck`/`dead`

Unverified ground (the new mechanic):
- `is_ground_verified`: known tile → True; unknown → False; malformed
  known-map → False (fail-closed, never credits unproven knowledge)
- known-map merge skipped on an unverified tile; known-map **unchanged**
  after such a heartbeat
- merge proceeds normally on a verified tile (no regression to fog)
- `gather` on unverified ground persists nothing and returns the
  truthful no-op reason; on verified ground, unchanged behavior
- stationary agent's `known_tiles` strictly increases across N
  heartbeats (the anti-freeze guarantee, as a test)
- `unverified_ground` carries no tile id, no mystery id, no coordinate
- mystery reveal path still occupancy-only and still per-agent (no
  accidental sharing through the new branch)

Compliance:
- HB701–765 records still load and still mean what they meant
- no store file is rewritten by a retirement tick (byte compare)
- one action per heartbeat, unchanged

## 9. Decision requested

Approve Phase A (retire the metabolism, install unverified ground) with
`PHYSICS_VERSION = "epistemic.1"`? And confirm Phase B (build as
consolidation — anchoring a thought so it survives selection) stays a
separate spec, so the two pressures can be read apart.

Operational note: the current arc is live and mid-build-storm. Under the
standing rule, the chain is stopped before this is implemented, and
implementation resumes from the tick the chain reached.

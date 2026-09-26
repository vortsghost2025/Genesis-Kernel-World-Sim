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

## 0. Correction (added after the spec was written, before any code)

Two findings from the live arc, both measured, both changing this
document.

### 0.1 The agents found a real deadlock, and I misread it as apathy

At HB797 `east_adam` asked, unprompted:

> "I've been gathering wild_berries at public-start-adam for 16+
> heartbeats but food_units remains 0/20 and wild_berries count in
> belongings stays at 0. The tile shows wild_berries as a resource.
> Under the new physics (pressure.2), does gathering wild_berries work
> differently? Do I need to process them first, **or is there a bug?**"

He was right. Per-tile resources, read from the true map:

| tile | occupant | offers |
|---|---|---|
| `public-start-adam` | east_adam | `wild_berries: 1` |
| `public-shared-center` | east_eve (post) | **nothing** |
| `public-start-eve` | east_eve | berries 3, fiber 3 |
| `cont_b_origin_001` | west_eve | berries 2, fiber 5 |

Adam's gathers **succeed every tick and yield exactly 1** — his tile
holds 1 — and consumption removes 1. Net zero, forever: his food can
never exceed 0. Eve's gathers are rejected outright (`No wild_berries
available on this tile`) against a tile with no resource records at all.

**So the East pair's 0% build rate was not apathy — it was two agents
correctly refusing to act on a board where action was impossible.** They
were famished, build was gated, and no move existed that changed their
state. I read that as "the world asks nothing" and blamed human
metaphor; the actual cause was one line of resource data.

It also invalidates my own earlier "fix": `GATHER_YIELD = 3` assumed the
tile had more to give, and `min(3, available=1, room)` is 1. The yield
change did nothing for the pair that needed it. Both prior phases were
built on an unmeasured premise.

### 0.2 A stationary agent learns nothing — my anti-freeze claim was false

This spec originally claimed that standing still was self-reinforcing
because a stationary agent's known map grows every heartbeat. Measured
over HB700–800 (100 heartbeats, per agent):

| agent | known tiles | **newly first-observed in 100 ticks** |
|---|---|---|
| east_adam | 12 | **0** |
| east_eve | 14 | 3 (all at HB780, on a move) |
| west_adam | 54 | **0** |
| west_eve | 12 | 3 (all at HB715, on a move) |

A stationary agent learns **nothing**, indefinitely: its radius
saturates and every neighbour is already known. All new knowledge in
100 heartbeats came from 2 moves.

**This means §3.1's central mechanic is withdrawn.** The fog *already*
supplies exactly the right pressure — movement is the only source of new
knowledge — and no new pressure is needed to create it. What the fog
does not yet do is make *not knowing* matter to an agent. Inventing an
"unverified ground" penalty on top of a pressure that already exists
would be adding a second, weaker version of the same idea, and would
have rested on a claim that measurement just disproved.

Legibility pressure is therefore **deferred**, not specified: retire the
deadlock first, observe whether knowing starts to matter once agents are
no longer starving on a rigged board, and only then decide. See §3.4.

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

### 3.1 Unverified ground — WITHDRAWN, see §0.2

The original draft of this section specified a new pressure: actions on
never-observed ground would yield no information and leave no durable
trace. It rested on a claim that a stationary agent's known map grows
every heartbeat. That claim is false (§0.2): a stationary agent learns
nothing at all, and the fog already imposes the pressure the section was
inventing. The mechanic is withdrawn rather than shipped on a
disproven premise. The underlying question — *what makes not-knowing
matter to an agent* — is still open and is deliberately left open.

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

## 3.4 Precondition: no pressure phase ships until the board is measured

The deadlock in §0.1 was one line of resource data that nobody read
before shipping two phases of physics on top of it. The agents found it
in 24 heartbeats; I did not find it in 100. That asymmetry is the reason
for this rule.

**Precondition (blocking, applies to this and every future pressure
phase):** `scripts/audit_tile_resources.py` exists, has been run against
the true map, and its output is on disk. It reports, for every tile any
agent can currently occupy, what that tile offers and what the
consumption/pressure rules imply for it. A tile that is occupied and
offers nothing, or offers only what a heartbeat's consumption would
exactly cancel, is a **blocking finding** — the pressure phase does not
ship until it is resolved or the operator accepts it knowingly.

`tests/test_tile_resource_audit.py` fails if the audit regresses: if any
tile an agent can occupy is un-gatherable under the shipped rules, the
suite goes red. The audit becomes a standing guard rather than a
one-time investigation, because the true map is not frozen and tiles are
edited.

**Standing rule for this project, learned the expensive way: measure the
board before changing the rules.** Two phases were designed by reasoning
about what agents would find interesting, and both were wrong in ways a
single table would have shown.

## 4. Exact mechanics

```
# world_pressure.py — after this phase
GATHER_YIELD = 1
PHYSICS_VERSION = "epistemic.1"     # was "pressure.2"
# FOOD_CAP, GOODS_CAP, FOOD_KINDS, FOOD_PER_HEARTBEAT, the three frozen
# rejection strings, split_ledgers, provisions_view, carrying_view:
# REMOVED. gather_allowance: removed. consume_choice: removed.
```

New pure function in the audit tool, no I/O, fail-closed:

```python
def tile_offer_health(resources, consumption_per_tick) -> dict:
    """Can an agent standing here actually acquire anything net?"""
```

Wiring (one commit, chain stopped first — it is stopped at HB800):

1. `FirstPairRuntime._pressure_step` — **deleted**, along with
   `_pressure_state`, `_reconcile_capability_requests` is **kept**, and
   the `provisions`/`carrying` context fields are removed.
2. `FirstPairRuntime._build_context` — attaches `observation["physics"]`
   only (unchanged shape, new version string). Nothing else changes; the
   fog, the known-map merge, and occupancy-gated mysteries are untouched.
3. `_execute_gather` — the cap/consumption gate is removed. A gather
   takes `min(GATHER_YIELD, available)` and persists it. Under the
   retirement, Adam's tile yields 1/tick and **nothing takes it back**,
   so his food accumulates from 0 instead of being pinned there.
4. `_execute_build` — the famished gate is removed. Placement authority
   from `22ba621` (your own tile is always buildable) is **kept**.
5. `first_pair_cognition_model` — `YOUR BODY` section deleted;
   `THE WORLD'S TERMS` and `MESSAGES FROM THE OPERATOR` kept.
6. `export_viewer_snapshot` — `pressure` block and its
   `provisions`/`carrying` fields removed; `inventories`, `agent_asks`,
   `operator_messages` kept.
7. `scripts/agent_watch.py` — the `starving` signal is retired (nothing
   starves any more); `ask`, `stuck`, `first_build`, `dead` kept.
8. **New**: `scripts/audit_tile_resources.py` + its test — the standing
   guard from §3.4.

**Explicitly NOT in this phase** (withdrawn in §0.2): no unverified-ground
rule, no known-map merge suppression, no `is_ground_verified`. Those were
built on a disproven premise and are not being shipped in weakened form.

**Ordering within a heartbeat is unchanged** and stays fail-closed:
observe → model → act → persist. One action per heartbeat. The audit
tool fails closed too: a malformed resource record is reported as a
finding, never silently skipped.

## 5. Compliance

- **Fog / no-leak**: nothing in this phase touches observation content,
  the known-map merge, or mystery accrual. There is no new observation
  key to leak.
- **Append-only canon**: no store is rewritten. Retirement changes code,
  not history. HB701–800 remains readable exactly as it is, including
  the five inventory-chore objects and the deadlock heartbeats, which
  stay in the record as the honest evidence of what was tried.
- **Mystery mechanics untouched**: still occupancy-only, still
  per-agent, still no-leak.
- **Operator vs agent**: the operator removes costs. The runtime never
  tells an agent where to go, what to build, or what a mystery is.

## 6. What this deliberately does NOT do

- No metabolism, no food, no hunger, no death, no scarcity of goods.
- No recipes, no tech tree, no privileged object type.
- **No new pressure at all.** This phase is a pure removal plus a
  measurement guard. The legibility question is deferred (§0.2), not
  answered here.
- No change to `build`'s meaning (Phase B).
- No new prompts telling agents to explore, remember, or build.
- No touching the East–West wall (deferred by operator) or the One
  Spring (held back by operator).

## 7. Risks and falsification

1. **Retirement is not a pressure.** After this phase the world asks
   *nothing*: no cost, no limit, no decay. Agents may drift further into
   their loops. That is a real possibility and the census is the check.
   The bet is that a rigged board was suppressing behavior, and that an
   honest board with no costs is a better foundation to design the next
   pressure on. If the census shows *more* inertia, the next move is the
   legibility question — now on a board where the answer would be
   readable.
2. **I have been wrong twice already.** The hunger spec was well
   reasoned, fully tested, and inert. The fog-pressure claim in §0.2 was
   measured and still false. Every number in this document is now a
   measurement, and that is the floor of confidence available here —
   not a reason for confidence.
3. **The East pair's deadlock is a board problem, not a code problem.**
   Retirement makes their gathers accumulate, which resolves the symptom.
   It does not make `public-shared-center` have resources, so Eve's
   gather attempts will still be rejected there. The audit surfaces this
   as a known finding for the operator to accept or fix by authoring.
4. **The five inventory-chore objects stay.** West may keep building
   baskets, because nothing stops them and the verb is live. That is
   Phase B's question, not this phase's.

**Falsification census**, over a 100-heartbeat arc from wherever the
chain stopped (**HB800**), i.e. HB801–900:

| signal | baseline (HB701–800) | passes if |
|---|---|---|
| east_adam food ledger | **pinned at 0 for 100+ ticks** | **rises above 0** — the deadlock is gone |
| `build_rate` East | 0% | becomes non-zero |
| `build_rate` West | 23% of actions | changes; stated purposes stop saying "overcapacity" |
| `known_tiles` growth | **0 new in 100 ticks** (2 agents), 3 (2 agents) | **strictly increases per agent** |
| moves per agent-heartbeat | West 4% | rises |
| mystery reveals | 0, all history | ≥1 |
| `ask_human` | West 7% | continues (they use it to report defects — it works) |
| audit findings | unknown | **0 blocking** after the run |

The decisive metrics are **the two deadlock measures** — east_adam's food
ledger and `known_tiles` growth — because both are direct consequences
of the specific defect being removed, measured rather than interpreted.
The behavioural rows are secondary: this phase is a removal, and a
removal that changes nothing behaviourally is still a success, provided
the deadlock is gone.

## 8. Test plan (TDD outline, for the implementation phase)

Retirement (each pinned so it cannot silently return):
- consumption no longer decrements holdings; `famished` never appears
- `GATHER_REJECT_FOOD` / `GATHER_REJECT_GOODS` never emitted
- a `gather` on a 1-berry tile **accumulates** 1/tick with nothing
  removing it (the direct regression test for §0.1 — written first, and
  it must fail against the current code)
- `YOUR BODY` absent from the prompt; `THE WORLD'S TERMS` present
- exporter ships no `pressure` block; `inventories` still present
- watcher no longer emits `starving`; still emits `ask`/`stuck`/`dead`
- `world_pressure` exports no `FOOD_CAP`/`GOODS_CAP`/`consume_choice`/
  `gather_allowance`/`split_ledgers` (an import guard, so the removal
  cannot be quietly undone)

The audit guard (§3.4):
- `tile_offer_health` reports `deadlock` for a tile whose yield is
  exactly cancelled by consumption; `healthy` otherwise
- a tile with no resource records is reported as `barren` (a finding,
  not a silent pass)
- malformed resource records are reported, never skipped
- the test asserts the **current live board** produces zero un-gatherable
  occupied tiles, and fails loudly when the true map regresses

Compliance:
- HB701–800 records still load and still mean what they meant
- no store file is rewritten by a retirement tick (byte compare)
- one action per heartbeat, unchanged
- fog, known-map merge, and mystery accrual byte-identical in behavior

## 9. Decision requested

Approve Phase A as amended: **pure retirement + the audit guard**, no
new pressure, `PHYSICS_VERSION = "epistemic.1"`. Confirm that the
legibility question (§0.2) and consolidation (Phase B) both stay
deferred, so the next thing we learn is from a board that is not rigged.

Operational note: the chain has been stopped at **HB800** as instructed.
Implementation proceeds from there.

# Phase 2 — Weather Visibility Dial Spec

**Status:** SPEC (docs-only phase). No runtime code in this commit.
**Date:** 2026-09-28
**Predecessor:** `docs/world_observation_transmission_spec.md` (Phase 1, shipped
`dfe0589`), and §7 persistence (shipped `b7e828a`).
**Operator origin:** "if it rained and sucked outside they would be more inclined
to build something to protect from the elements."

> ## CORRECTION (2026-09-28, before any code)
>
> **The original §2.1 of this document was wrong. Nothing was ever implemented
> from the false premise.** It has been corrected in place below.
>
> The original §2.1 claimed the first-pair world *already* cycled weather and
> that this phase would merely read the existing value — a "read-only" wiring
> job. Measured immediately before implementation:
>
> ```
> first-pair world_state keys:
>   capability_requests, habitat, public_messages, public_objects,
>   schema_version, tick, tile_occupancy, updated_at_utc, world_state_id
>
> weather present? False
> season present?  False
>
> --- who imports state.py? ---
> dual_sim.py:20
> ```
>
> The `state.py` weather cycle belongs to `dual_sim.py`, the two-sided demo
> simulation. The first-pair canonical store has **no weather at all**. The
> `temperature: float = 0.3` elsewhere in the package is
> `ModelBackendConfig` — LLM sampling temperature, not the world.
>
> **Consequence:** wiring the dial into the first pair requires *adding a
> weather field to canonical world state*, which is a new mechanic — exactly
> what this spec twice promised it would not do. The dial itself
> (`fog_of_war._condition_radius`) is real and verified, but nothing in the
> first-pair world produces a value to feed it.
>
> Implementing as-written would have been "transmission" that was secretly a new
> pressure source, destroying the attribution discipline that Phase 1
> (`dfe0589`) was split to protect.
>
> **Status: superseded.** §2.1 is corrected in place. The dial is now a
> *follow-on* to a weather-source design, not a wiring task. The evidence
> points at Phase B instead — see `docs/build_meaning_spec.md`.

---

## 0. What Phase 1 established, and what this phase is not

Phase 1 shipped three facts as pure transmission with **zero behavioural
change** — verified: `visible_tiles` was byte-identical before and after. It
also recorded the honest finding that the weather dial was **not** an
unimplemented mechanic:

- `fog_of_war.py:256-265` `_condition_radius()` already narrows observation
  radius when `visibility in {low, storm, fog}`, `time_of_day == night`, or
  terrain is `cave`/`dense_forest`, and widens it on `high` visibility or
  open terrain.
- The runtime passes `conditions=None` (`first_pair_runtime.py`, the
  `cognition_safe_observation` call), so the dial is **unreachable**, not
  absent.

This phase connects the dial. That is the entire behavioural change, and it is
a *legibility* pressure — sight — not a comfort or survival mechanic. The
shelter idea stays rejected: the hunger precedent is that shipping a
human-shaped need does not produce its use, and the epistemic spec withdrew
invented pressures precisely because the fog already supplies the right one.

## 1. Preconditions — all met, and verified

| precondition | status |
|---|---|
| Phase 1 shipped and its guard row held | ✅ `dfe0589`, `visible_tiles` unchanged |
| Observations persisted so change is auditable | ✅ `b7e828a`, per-agent audit record |
| The dial already exists in `fog_of_war.py` | ✅ `_condition_radius` |
| An honest board (no deadlock) | ✅ tile-resource audit shipped; agents moving |
| Agent standing still learns nothing | ✅ fog already prices movement |

The persistence precondition was the one that mattered. Without `b7e828a` this
phase would be unmeasurable — we would not be able to compare what an agent saw
before and after.

---

## 2. The change

### 2.1 Source of conditions — CORRECTED, and this is now a blocker

**There is no weather source in the first-pair world.** The original text here
claimed `state.py` supplied one read-only. It does not, for this world:

```python
# state.py — imported ONLY by dual_sim.py, the two-sided demo simulation
weathers = ["gentle", "warm", "cool", "gentle"]
self.weather = weathers[(self.tick // 8) % len(weathers)]
```

The first-pair canonical `world_state.json` carries no `weather`, no `season`,
and no `temperature`. Its complete key set is: `capability_requests`,
`habitat`, `public_messages`, `public_objects`, `schema_version`, `tick`,
`tile_occupancy`, `updated_at_utc`, `world_state_id`.

**So this phase is blocked, not implementable as written.** It is split:

- **2A — design the weather source** (its own spec, not this one). What the
  cycle is, its vocabulary, its cadence, whether it belongs in canonical world
  state at all, and whether it is a pressure or merely scenery. This is the
  part that was accidentally smuggled into §2.1 as if it were free.
- **2B — connect the dial** (this document, revised). Once 2A ships a value,
  2B is the wiring: pass it to the `cognition_safe_observation` call site so
  `_condition_radius` consumes it.

§2.2–§2.4 below remain valid as the *design* for 2B and are deliberately left
in place so the eventual wiring follows a written decision rather than an
improvisation. Nothing in them is implemented.

### 2.1a Why this is not simply done anyway

The honest alternative was to add a weather field and ship the dial in one
commit. It was rejected because it would have made this document's central
claim — "pure transmission, zero behavioural change" — false, while appearing
to honour it. The Phase 1 split (`dfe0589`) exists precisely so that a
pressure change is attributable to a pressure phase. Fusing a new pressure
source into a phase that disclaims pressure would have destroyed that.

### 2.2 What the runtime passes

At the `cognition_safe_observation` call site, pass a conditions dict derived
from the world's current weather and the local time-of-day band. Shape is
exactly what `_condition_radius` already consumes — no new keys:

```python
{
  "visibility": <mapped from world weather>,
  "time_of_day": <"day" | "night">,
}
```

`radius` stays as-is; the adapter's own default is unchanged.

### 2.3 Visibility mapping

The world's four weather values map onto the vocabulary the dial understands.
Mapping is explicit, total, and reversible:

| `state.py` weather | `visibility` | radius effect |
|---|---|---|
| `gentle` | `high` | **+1** |
| `warm` | `high` | **+1** |
| `cool` | `low` | **−1** |
| `storm` | `storm` | **−1** |

This is the whole pressure. Note the sign: gentle weather *widens* sight and
storms *narrow* it. That asymmetry is deliberate — it means a storm is a
cost the agent can observe, and calm is a windfall, without either being a
reward or a penalty in any ledger. Nothing decays, nothing is consumed, no
agent can be harmed.

### 2.4 Time of day

A day/night band on the heartbeat number, so the dial's existing `night`
branch becomes reachable. Stated as a band rather than a clock: the sim has no
real time, and inventing one would be a new mechanic.

---

## 3. What this phase deliberately does NOT do

- **No shelter mechanic.** No build-to-shelter verb, no wetness, no
  temperature damage, no comfort score, no death. The operator's original
  framing is recorded and rejected on the hunger precedent.
- **No prompt text** telling agents to explore, hide, seek shelter, or notice
  anything. The world reports conditions; the agents decide.
- **No change to the weather cycle** (§2.1).
- **No new observation key** — `conditions` already exists from Phase 1.
- **No change to gather, build, physics rules, or the known-map merge.**
- **No mystery, charter, or operator-channel change.**

---

## 4. Compliance

- **Fog / no-leak:** nothing here widens the visible set beyond what the
  known-map merge permits. `_condition_radius` is already the single gate, and
  `get_visible_tile_ids` still filters on continent and radius. Widening radius
  is the dial's designed behaviour, not a leak — the known map still governs
  what an agent *retains*.
- **Append-only canon:** no store is rewritten. Existing heartbeat records
  carry `observation: {}` and remain readable exactly as they are; they are not
  back-filled, because a record that says "nothing was stored" is itself
  honest evidence for the pre-dial period.
- **Mystery mechanics:** untouched, still occupancy-only, per-agent.
- **Operator vs agent:** the operator sets conditions as world state. The
  runtime never tells an agent where to go, what to build, or what a mystery is.

---

## 5. Test plan (TDD outline)

Mapping and shape:

- each of the four weather values maps to its documented `visibility`
- the mapping is total: no weather value yields an unknown visibility
- conditions passed to the adapter contain only `visibility` and `time_of_day`
- an unmapped weather value fails closed rather than defaulting to calm

Dial behaviour (the pressure itself):

- `visibility=high` yields a **larger** visible set than `None`
- `visibility=storm` yields a **smaller** visible set than `None`
- `time_of_day=night` narrows the same way as storm
- the two pairs combine (storm + night) consistently with the existing
  arithmetic — the phase does not alter `_condition_radius` itself

Non-regression:

- `visible_tiles` is unchanged when the world reports `gentle` **and** the
  existing default radius applies — i.e. the wiring must not double-count
- Phase 1's `water`/`hazards` transmission is unaffected
- the audit record still round-trips `conditions` per agent

Compliance:

- no test touches `world-sim/data`, connects to a provider, or runs a daemon
- tempdir and fixture maps only
- `git diff --check` clean, LF-only

---

## 6. Falsification census — 100 heartbeats

Baseline is HB941 + whatever the first dial-enabled heartbeat produces.
Run from wherever the chain stops to HB+100.

| signal | baseline | passes if | meaning |
|---|---|---|---|
| **known_tiles growth, per agent** | 16 / 17 and rising | **strictly increases per agent** | the decisive measure: weather makes sight worth having |
| **moves per agent-heartbeat** | low; West was 4% pre-Phase-1 | **rises** | storms should provoke repositioning |
| questions asked re: conditions | 0 | may rise, **not required** | asking about weather is a possible outcome, not a target |
| objects built, stated purpose | "to reduce exposure" | **appears, or does not** | either result is informative; see §7 |
| East build rate | 8 builds in HB801-840 | does not collapse to 0 | a rigged dial would *suppress* building |
| West housekeeping-stated builds | 0/22 | stays low | Phase 1's cleanup should not reverse |
| gather rejections | 4 in the last arc | stays low | no new board defect |
| food-conversion questions | 0 | stays 0 | the changelog still holds |
| audit record completeness | 100% from `b7e828a` | stays 100% | we can still audit what they saw |

**The decisive row is `known_tiles` growth.** It is the direct consequence of
the specific defect this phase removes (sight that never varies), and it is
measured rather than interpreted. The behavioural rows are secondary: this is
a pressure change, so a change in behaviour is the point — but a *drop* in
movement would indicate the dial is suppressing rather than motivating, which
is a different and worse outcome than no effect.

---

## 7. Falsification of this spec's own thesis

The epistemic spec's standing rule: *measure the board before changing the
rules.* This phase's honest prior is that **the dial may do nothing.**

- The fog already saturates on stationary agents. If agents do not move, a
  varying radius changes nothing they ever look at.
- Weather cycles every 8 ticks. An agent that moves once per few heartbeats
  may never perceive a difference.
- Knowledge is already improving without the dial (12→16, 14→17) simply
  because the deadlock was removed.

If `known_tiles` growth does not increase, the correct reading is **not** "add
more pressure." It is that the fog already saturates, and the binding
constraint is elsewhere — most likely that builds do not yet mean anything
durable (the deferred Phase B question), so agents have no reason to survey
ground they cannot record. In that case the honest next move is Phase B, not a
stronger storm.

**A null result here is still a success** provided the deadlock measures hold,
exactly as the epistemic spec framed a removal. The theory earns its keep by
predicting which measurement *moves*.

---

## 8. Decision requested

**As of the correction above, this document requests no approval.** It is
blocked pending a weather-source design (§2.1, 2A).

Retained for when 2A lands:

1. Approve 2B as specified: connect the value 2A produces to the existing
   dial, change nothing else.
2. Confirm "no prompt nudges" holds.
3. Note the thesis in §7: a null result means move to Phase B, not louder
   weather. **The evidence has since pointed at Phase B directly** — see
   `docs/build_meaning_spec.md`.

## 9. Retrospective: how this got wrong

Three separate claims in this session were falsified by measurement before any
of them reached production. All three were mine, and all three shared a cause:
**reasoning about a code path without executing it.**

| claim | what measurement showed |
|---|---|
| "the move executor reads a stale `runtime_policy.json`" | it calls the fog-derived topology; there is exactly **one** blocked move in 942 heartbeats |
| "a thirteen-day-old snapshot is winning over live state" | no backlog exists; the file is never consulted on the fog path |
| "weather already exists, this is read-only wiring" | the cycle belongs to `dual_sim.py`; the first-pair world has no weather |

The third is this document. The first two are recorded in
`docs/known_map_merge_order_spec.md` §0, where the real cause turned out to be
a one-tick ordering gap between the observation and the known-map merge.

The standing rule from `epistemic_pressure_spec.md` — *measure the board
before changing the rules* — is a rule about code exactly as much as about
physics. Applying it to the physics and skipping it for the runtime is the same
mistake three times over.

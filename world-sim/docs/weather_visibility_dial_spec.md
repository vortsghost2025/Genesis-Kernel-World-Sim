# Phase 2 — Weather Visibility Dial Spec

**Status:** SPEC (docs-only phase). No runtime code in this commit.
**Date:** 2026-09-28
**Predecessor:** `docs/world_observation_transmission_spec.md` (Phase 1, shipped
`dfe0589`), and §7 persistence (shipped `b7e828a`).
**Operator origin:** "if it rained and sucked outside they would be more inclined
to build something to protect from the elements."

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

### 2.1 Source of conditions

`state.py:84-85` already cycles weather every 8 ticks:

```python
weathers = ["gentle", "warm", "cool", "gentle"]
self.weather = weathers[(self.tick // 8) % len(weathers)]
```

**Constraint, not a new mechanic:** this phase does not change the weather
cycle, its period, or its vocabulary. It reads the existing value and reports
it. Changing the cycle would confound "did the dial do anything" with "did I
change the weather".

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

1. Approve Phase 2 as specified: connect the existing dial, change nothing else.
2. Confirm the weather cycle and its vocabulary are read-only inputs here.
3. Confirm the shelter mechanic stays rejected, and that "no prompt nudges"
   holds.
4. Confirm the audit precondition is satisfied by `b7e828a`, and that this
   phase runs **after** it (already true).
5. Note the thesis in §7: a null result means move to Phase B, not louder
   weather.

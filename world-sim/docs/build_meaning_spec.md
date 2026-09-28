# Phase B — Build Meaning Spec: Making a Built Thing Carry a Thought

**Status:** SPEC (docs-only phase). No runtime code in this commit.
**Date:** 2026-09-28
**Origin:** deferred by `epistemic_pressure_spec.md` §3.3; promoted here by
measurement. Replaces the weather-dial direction — see
`weather_visibility_dial_spec.md` §9 for why that was abandoned.

---

## 0. Why this, and not weather

The weather dial was specced first and corrected as unbuildable
(`a25a775`): the first-pair world has no weather source, so "wiring" it would
have quietly introduced a new mechanic. That correction pointed somewhere else,
because the same measurement produced a different result:

**HB943 (measured, not inferred):**
- `east_adam` → `cont_a_gen_1_1` → `cont_a_gen_1_2`, **success**, on the first
  attempt, for a tile he had been blocked from at HB942.
- His stated reason: *"move to `cont_a_gen_1_2` (hill, temperate_hills) which
  has clay and stone resources **visible**. This is the next tile in systematic
  hill survey after completing forest survey."*
- `east_eve` moved to `cont_a_gen_-1_0` pursuing *"the unexplored hill tiles
  Adam proposed at hb"* — she is tracking his plan across heartbeats.

He knows the terrain, the biome, and the materials **before arriving**. He is
surveying systematically, by name, and she is following his proposal. That is
not the behavior of an agent that has nothing worth recording.

The constraint on his survey is therefore not *perception* — perception is now
working. It is that **a survey he cannot write down is a survey he must
redo.** The agents know more each heartbeat than the substrate can carry into
the next one.

## 1. The measured substrate problem

From `epistemic_pressure_spec.md` §2, on the live stores:

| | |
|---|---|
| private memories per agent | **1,546 – 1,673** |
| selected per request | 6 recent + 6 relevant, max 16 entries, 12,000 chars |
| "summary" layer | max 4 entries, each a **raw 300-character excerpt** — truncation, not synthesis |
| **visible share of own history** | **≈ 1%** |
| durable escape hatches | charter (verbatim, unbounded, exempt from summarization); public objects |
| charters ever written | **0 of 4** |

**99% of an agent's own experience is invisible to it every heartbeat, and
nothing in the world ever told it that mattered.**

Phase 1 fixed a *transmission* gap (water/hazards dropped at the projection
boundary). §7 persistence fixed an *audit* gap. Neither touches this one. This
is a retention gap, and it is the last structural deficit.

## 2. Why the charter alone does not solve it

The charter is the right idea and it is already built: verbatim, unbounded,
exempt from summarization, injected every heartbeat
(`first_pair_cognition_model.py:861-879`). Its own prompt text tells the agent
it "is never summarized, compressed, or forgotten by the runtime; everything
else you have experienced may eventually be compressed."

**And 0 of 4 agents have ever written one.** Not because they refuse — because
nothing in their experience made the trade legible. A charter says *who you
are*; a survey finding says *what you learned*. The substrate has a slot for
identity and no slot for **findings**, and the agents are full of findings.

## 3. What this phase does

Give a built public object the charter's structural property: **an agent's own
words, attached to a thing it made, survive selection.**

The mechanism already exists and is the smallest possible change: public
objects are already in the prompt
(`first_pair_cognition_model.py:765-772`) and already carry agent-authored
`public_description` text. Today they are rendered as **JSON inside a shared
list** — one undifferentiated block, mixed with every other agent's objects,
competing for attention with the observation.

Phase B separates the two kinds of object by **authorship**:

| | authored by | rendered as | budget |
|---|---|---|---|
| **Anchored work** — objects *this agent* created | you | a dedicated section, verbatim, per object | unbounded, like the charter |
| **Everything else** — other agents' objects, and yours not marked as anchors | others | the existing JSON list | as today |

**No new verb. No new action. No new object type.** `build` and
`create_public_object` keep their exact meaning. What changes is that when an
agent writes a thing down, the runtime *presents it back to that agent,
verbatim, forever* — the same guarantee the charter already provides.

This is deliberately the conservative reading of "make `build` mean anchor a
thought": the persistence and presentation are structural, not semantic. The
agent decides what a thing means by what it writes. The runtime only stops
forgetting.

## 4. What this phase does NOT do

- **No new action, verb, or object type.** `build` is unchanged.
- **No change to `create_public_object` semantics**, placement authority, or
  the materials rules.
- **No change to memory selection budgets** (`_MAX_SELECTED_*`). Anchors sit
  outside that pipeline, exactly as the charter does.
- **No requirement to build.** An agent that never builds is unaffected, and
  no prompt line says or implies it should.
- **No new prompt instruction** to build, record, or remember more. If this
  works, the census will show it; a prompt telling them to build would make the
  census unfalsifiable.
- **No weather, no fog change, no movement change.** The dial stays deferred.
- **No back-fill.** Objects built before this phase render as today.

## 5. Design decisions this spec does not make

Left open deliberately, and each is a smaller decision than the whole phase:

1. **Which objects anchor.** All of an agent's own objects, or only those whose
   description reads as a finding? Recommendation: *all of the agent's own*.
   A structural rule is legible; a classifier is not, and a wrong classifier
   silently loses thoughts.
2. **Ordering and truncation.** Anchors are unbounded in principle; a real
   bound must be chosen (oldest-dropped? most-recent? capped count?). The
   charter is 2,000 chars; an anchor set needs its own honest bound, and
   hitting it must be **visible to the agent**, never silent.
3. **Whether the other agent sees anchors differently.** They already see the
   object in the shared list. Phase B does not change what others see.

## 6. Test plan (TDD outline)

Presentation:

- an agent's own objects appear in a dedicated anchors section
- another agent's objects do **not** appear in it
- anchor text is reproduced **verbatim**, not summarized, truncated, or
  re-rendered
- an object with no description does not produce an empty anchor block
- an agent with no objects gets the same neutral text the charter gives an
  unwritten charter — never an empty or error section

Invariance:

- the existing shared-objects list still contains every object, unchanged, so
  the other agent's view is byte-identical to today
- memory selection budgets and outputs are untouched
- a build still places, still spends materials, still persists

Compliance:

- no test touches `world-sim/data`, connects to a provider, or runs a daemon
- tempdir and fixture objects only
- `git diff --check` clean, LF-only

## 7. Falsification census — 100 heartbeats

| signal | baseline (HB943) | passes if | reading |
|---|---|---|---|
| **anchors per agent** | **0** (feature does not exist) | **> 0** | the decisive row: agents *use* the slot when it exists |
| objects built per agent | 8 builds / 40 ticks pre-Phase-1 | **does not fall** | a decline would mean anchors suppressed building |
| anchors referencing prior heartbeats | n/a | rises | anchors accumulate meaning across time |
| moves per agent-heartbeat | 2 of 2 at HB943 | holds or rises | unchanged behavior is a success |
| known_tiles growth | 18 / 17, rising | keeps rising | Phase 1 is not disturbed |
| questions asked | low since the changelog | stays low | no new confusion |
| reachability blocks | **0** | stays 0 | the `677f2a2` fix holds |
| food-conversion questions | 0 | stays 0 | the changelog still holds |

**The decisive row is `anchors per agent`.** The honest prior is again that
this may do nothing: the charter has been available and unwritten for
hundreds of heartbeats, so an agent may equally ignore an anchor slot. But
the two differ in one measurable way — an anchor is *attached to a thing the
agent already chose to make*, so it requires no new decision from the agent.
That is the whole hypothesis, and `anchors > 0` tests it directly.

**A null result is still informative.** It would say that what agents want
durable is not findings but identity, and the right next move would be to
investigate why the charter — which *is* identity — goes unwritten. That
would be a finding about the prompt, not about the agents.

## 8. Decision requested

1. Approve Phase B in the conservative structural form (§3): authorship
   separates anchors, no new verb, no new object type, verbatim, unbounded.
2. Confirm decision 5.1 — *all* of an agent's own objects anchor, no
   classifier.
3. Note that the anchor budget (5.2) must be chosen and made **visible** when
   hit, never silent. This is the one place Phase B could quietly lose a
   thought, and the whole point of the phase is that thoughts stop being lost.
4. Confirm no prompt line is added, so the census stays falsifiable.

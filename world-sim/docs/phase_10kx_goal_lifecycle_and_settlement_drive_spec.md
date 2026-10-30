# Phase 10KX Specification: Goal Lifecycle, Deduplication & Settlement Awareness

> **Phase Chain:** 10KM (impl, Done `afdb0db`) -> 10KW (metadata sync, Done `5a7106b`, hash-corrected `ef51b95`) -> 10KX (specification, this document) -> 10KY (metadata sync) -> 10KZ (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to candidate Phase 10KZ following explicit operator authorization.

---

## 1. Verified Diagnosis

Phase 10KM (load-bearing construction) shipped and **has never been exercised in the field**. Tick attribution against the `afdb0db` commit showed zero structural build attempts, zero craft attempts, zero rejections from the new timber floor. A follow-up diagnostic isolated why.

### 1.1 Goal saturation

East Valley's goal register at HB 6111:

| | Adam | Eve |
|---|---|---|
| Active `in_progress` goals | 15 | 19 |
| **Distinct** goal descriptions | **6** | **7** |
| Goals the prompt actually sees (`[-8:]` from 10JR) | 8 | 8 |
| Of those 8, near-identical duplicates | **7** | **7** |

Adam's exposed window is *"Continue exploring uncharted hill terrain and gather resources"* repeated seven times with one `…and gather stone` variant. Eve's is *"Continue systematic survey of western hill cluster tile by tile along the y=-5 boundary"* repeated eight times. Verified verbatim from `.runtime/first-pair/goals.json`.

### 1.2 The duplicate window crowds out everything

Every one of the 8 slots per agent is consumed by exploration. There is no buried construction goal being displaced — after deduplication Adam has 6 distinct goals and Eve has 7, **and all of them are still explore/survey goals**. So deduplication alone does not produce building; it only frees slots that nothing is currently waiting to fill.

Eve's distinct set contains one genuinely stale entry, *"pause berry gathering and pivot to productive activity"*, plus *"test whether gather works for me under physics.epistemic.3"* — neither has been retired.

### 1.3 Material hoard with no construction

| | Adam | Eve |
|---|---|---|
| `stone` | **441** | 125 |
| `wild_berries` | 3 | **748** |
| `wood` | **2** | **0** |
| `timber` | **0** | **0** |
| `stone_axe` / `flint_knife` | 0 / 0 | 0 / 0 |

Adam cannot satisfy `_STRUCTURAL_TIMBER_MIN = 2` even if he tried. East's last structural build was `shelter-006-15_1` at HB 5345 — **766 ticks ago**. East's observed behavior over the last 50 heartbeats is 37 moves / 8 gathers for Adam and 49 moves for Eve, at roughly a 154:1 move-to-build ratio.

### 1.4 The awareness gap

The cognition prompt already exposes two relevant things, and misses two:

- **Belongings are dumped raw** (`first_pair_cognition_model.py:1427-1439`) — the agent can see `stone: 441`, but it is an unranked list with no derived meaning.
- **A derived food fact line already exists** (lines 1568-1589): *"Fact: you are carrying edible food in your belongings: …"*. This is the precedent for stating a derived condition as a fact rather than an instruction.
- **No structural-timber fact exists.** The word `timber` appears 3 times, all inside action descriptions.
- **No shelter-status fact exists.** `in_shelter` appears **0 times** in the entire cognition model, despite the runtime computing it for every agent every heartbeat (`first_pair_runtime.py:689`).

So an agent can carry 441 stone, hold 0 timber, and own no shelter, and never be told any of those three as a *state*.

---

## 2. Scope

### 2.1 In Scope (Phase 10KZ Candidate)

1. **Goal deduplication at context build.** Collapse identical goal descriptions before the `[-MAX_ACTIVE_GOALS_EXPOSED:]` slice, so duplicates cannot consume the entire window.
2. **Goal staleness retirement.** Retire goals whose satisfying condition has clearly ceased to hold.
3. **Settlement-awareness fact lines.** State derived, unambiguous state facts — timber holdings, shelter ownership, tool holdings — following the existing food-fact-line pattern.

### 2.2 Out of Scope

- **Injecting goals.** The runtime must not author goals on the agent's behalf. Phase 10JR's invariant 1 stands: *"the agent's cognitive authority is strictly preserved… the engine only provides prompt filtering, hygiene boundaries, and valid action validation."*
- Any new mechanic (recipes, attraction, compounds, cultivation). Mechanics are not the blocker.
- Live store edits, goal surgery, operator messaging.
- Changes to the LLM's goal-generation prompt wording beyond what is needed to render the new facts.

---

## 3. Design Invariants

1. **Facts, never directives.** Every new prompt line states a condition that is true. No line says what to do about it. Standing Rule 7's line between fact and strategy is the same line used for the food facts.
2. **Preserved cognitive authority.** Deduplication and staleness retire *redundant* goals. They do not create goals, reorder priorities, or choose actions.
3. **No history destruction.** Retired goals remain in `goals.json` with their status changed. Nothing is deleted.
4. **Bounded, idempotent behaviour.** Dedup is a pure function of goal ordering; retirement is driven by measurable state (age, inventory, region coverage), never by wall-clock.
5. **Determinism untouched.** No RNG or seeding change.

---

## 4. Architectural Specifications

### 4.1 Goal deduplication in `_build_context`

Current (`first_pair_runtime.py:602`):

```python
agent_goals = [
    g for g in self._goals
    if g.agent_id == view["agent_id"] and getattr(g, "status", "") in ("active", "in_progress")
][-MAX_ACTIVE_GOALS_EXPOSED:]
```

Phase 10KZ collapses duplicates **by normalized description**, keeping first occurrence order, then applies the slice:

```python
def _dedupe_goals(goals):
    seen = set()
    unique = []
    for g in goals:
        key = " ".join(str(getattr(g, "description", "") or "").lower().split())
        if key and key in seen:
            continue
        seen.add(key)
        unique.append(g)
    return unique
```

Applied as: `_dedupe_goals(agent_goals)[-MAX_ACTIVE_GOALS_EXPOSED:]`.

Requirements:
- `goal_id` and `created_heartbeat` are preserved on the surviving record; only presentation is deduplicated. All duplicate records remain in `self._goals` and on disk.
- Test: Adam's 15 active goals (6 distinct) must expose no duplicate description; Eve's 19 active (7 distinct) likewise.
- Test: a store with 20 genuinely distinct goals must still expose exactly the most recent 8 — dedup must not hide variety.
- Test: `active_goal_ids` (the 10JR fix for line 851) must be unaffected in count semantics.

### 4.2 Goal staleness retirement

A goal is **retired** when its satisfying condition has objectively ceased to hold. 10KZ implements a conservative, measurable rule set:

- **Region surveyed.** A survey/mapping goal referencing a specific tile range is retired when the agent's `known_map` already covers that range (no partial credit, no guessing).
- **Resource acquired.** A gather goal for a specific `resource_kind` is retired when the agent holds at least the amount that goal implies, using `ANIMAL_FOOD_TRUST`-style explicit thresholds — not an arbitrary number.
- **Stale test goals.** A goal whose description matches the historical *"test whether … works"* pattern and which is older than a defined `STALE_GOAL_AGE_HB` is retired.

Constraints:
- Retirement writes `status = "retired"` through the existing `goal_updates` write path. **No out-of-band editing of `goals.json`.**
- If any rule cannot be satisfied unambiguously, the goal is **not** retired. Fail closed.
- Tests: a survey goal for a fully-covered range retires; the same goal with partial coverage does not; a gather goal retires only at or above threshold; a fresh test goal survives.

### 4.3 Settlement-awareness fact lines (`first_pair_cognition_model.py`)

Add a fact block to the same `_lines` pattern the food facts use. Rendering all applicable lines as facts:

```text
Fact: you hold no structural timber. Felling a tree into timber requires hew_timber with an axe or knapped blade.
Fact: you own no shelter of your own.
Fact: you hold 441 stone and 2 wood in your belongings.
```

Rules:
- **Presence and absence are both stated.** *"You hold X"* and *"You hold no X"* are equally facts; the food-fact precedent already does exactly this (`"You currently hold no food in your belongings."`).
- Structural timber, `stone`, `wood`, and shelter ownership are the initial set. Do not enumerate every resource — the belongings dump already does that.
- Zero banned directive phrases (reuse `_BANNED_DIRECTIVE_PHRASES` from `first_pair_runtime`).
- Shelter ownership is derived from `world_state.public_objects` for this agent, mirroring `is_agent_sheltered`'s shelter-kind list, and is exposed via `AgentContext` — **not** by importing the runtime into the cognition model (circular-import constraint learned in 10KM).
- Tests: an agent with 0 timber gets the timber fact; an agent with 5 does not; agent with 441 stone sees the count; agent owning a shelter does not get the no-shelter fact; the rendered block contains no banned phrase.

---

## 5. Required Test Coverage for Phase 10KZ

In `tests/test_goal_lifecycle.py`:

1. `test_build_context_deduplicates_goal_descriptions` — Adam's and Eve's real shapes.
2. `test_build_context_still_slices_most_recent_when_all_distinct` — 20 distinct goals → exactly 8 exposed, most recent.
3. `test_dedupe_preserves_all_records_on_disk` — no goal is removed from `self._goals` or `goals.json`.
4. `test_survey_goal_retires_when_region_covered`.
5. `test_survey_goal_survives_with_partial_coverage`.
6. `test_gather_goal_retires_at_threshold_only`.
7. `test_fresh_test_goal_survives_age_rule`.
8. `test_timber_fact_line_absent_when_timber_held`.
9. `test_no_shelter_fact_line_absent_when_shelter_owned`.
10. `test_belonging_counts_stated_as_facts`.
11. `test_settlement_facts_contain_no_directives`.
12. `test_agent_context_exposes_shelter_ownership`.

---

## 6. Governance & Progression

- **Phase Chain:**
  - `10KW`: Sync 10KM Metadata (Done `5a7106b`, hash-corrected `ef51b95`).
  - `10KX`: Goal Lifecycle, Deduplication & Settlement Awareness Specification (this document) -- Docs only.
  - `10KY`: Metadata Sync -- Record 10KX hash in `phase_index.md`, name 10KZ candidate.
  - `10KZ`: Implementation candidate -- TDD implementation of dedup, staleness retirement, and settlement-awareness facts.
- **Note on the 10K-series record.** Phases 10KN and 10KP were consumed by the 10KN correction audit and its sync; the 10KM sync was renumbered 10KW to avoid the collision, and the 10K-series now runs 10KM -> 10KW -> 10KX -> 10KY -> 10KZ.
- **Constitutional Guardrails:**
  - Docs-only specification; no implementation code is authorized under Phase 10KX.
  - No goal injection, no goal surgery, no operator messaging.
  - Retire goals only through the existing `goal_updates` path; never delete history.
  - Stage ONLY `world-sim/docs/phase_10kx_goal_lifecycle_and_settlement_drive_spec.md`. Never `git add -A` or `git add .`.
  - Pure LF line endings (`CRLF=0`).

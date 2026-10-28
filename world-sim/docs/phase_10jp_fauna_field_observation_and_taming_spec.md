# Phase 10JP Specification: Fauna Field Observation, Taming Verification & Cognitive Goal Hygiene

> **Phase Chain:** 10JP (spec, L) -> 10JQ (metadata sync, L+1) -> 10JR (implementation candidate, L+2, NOT started, NOT authorized)  
> **Constitutional Notice:** Docs-only specification. Implementation is strictly unauthorized until explicit operator authorization.

---

## 1. Problem Statement & Live Field Evidence

Phase 10JN landed the physical foundations of domesticatable fauna and the snake hazard (pure `fauna.py`, durable interaction transaction journal `fauna_interactions.py`, runtime tick, action execution, combat, and nutrition parity). The 4 pure fauna test suites (64 tests) and the broader 14-suite regression gate (439 tests) pass cleanly. In environments where default temporary paths encounter local permission restrictions, directing pytest via `--basetemp` provides clean execution. Commit `a0fc04e` has added the 4 fauna suites to `.github/workflows/pure-tests.yml`.

However, real-world inspection of long-running civilizations (West at Heartbeat 7110+) revealed a critical cognitive bottleneck that prevents agents from engaging with living fauna:

1. **Unbounded Goal Clutter (186 Legacy Goals, 22k+ Tokens):**
   In `FirstPairRuntime._build_context()`, agent goals are selected via:
   ```python
   agent_goals = [g for g in self._goals if g.agent_id == view["agent_id"]]
   ```
   This query does not filter by status and imposes no count limit. In West, `goals.json` has accumulated **186 goals** across 7,100+ heartbeats: **181 `completed`** and **5 `in_progress`** (the status `active` is not used in the live agent vocabulary). Over **85 of these goals** are obsolete failed test goals from Heartbeats 1000-2400 (e.g. `test_use_object_extract_operator_claim`, `resolve_contents_anomaly_decisive`, `test_extract_under_claimed_change`). When serialized as `json.dumps(context.goals, indent=2)`, these 186 goals consume **88,637 characters (approximately 22,159 tokens)**, flooding the prompt context window every single cycle.
   
   *Critical Invariant Note:* Because the live status vocabulary uses `in_progress` rather than `active`, any filter targeting only `status == "active"` would evaluate to empty (`{"goals": []}`), dropping genuine in-progress goals (`survive_night`, `standing_by`, etc.). The filter must target `status in ("active", "in_progress")`. Additionally, a latent bug in `first_pair_runtime.py:851` (`active_goal_ids = {g.goal_id for g in agent_goals if g.status == "active"}`) currently resolves to an empty set for the same reason.

2. **Charter and Public Message Entrainment:**
   At Heartbeat 2419 (and reaffirmed at Heartbeat 4216), West Adam revised his charter to vow *"honest stillness: I will not invent activity, I will not repeat falsified tests, and I will not fill silence with noise. Standing by is my choice..."* Eve reads this charter and Adam's public messages. The overwhelming weight of ancient failed-test goals and charter stillness suppresses autonomous engagement with newly spawned fauna.

3. **Missing Multi-Step Behavioral Integration Verification:**
   While unit tests verified individual methods (`_execute_offer_food`, `_execute_milk_animal`, `fauna_tick`), no integration harness verified the full multi-step lifecycle: an agent perceiving a fauna entity in observation, forming a relevant goal, moving adjacent to it, offering food repeatedly until tamed, and subsequently milking the ready cow.

---

## 2. Scope

### 2.1 In Scope (Phase 10JR Candidate)
1. **Cognitive Goal Hygiene & Active Filtering:**
   - In `_build_context()`, filter goals by `status in ("active", "in_progress")`. Completed, abandoned, or retired goals must never be injected into `context.goals`.
   - Update `first_pair_runtime.py:851` to use `g.status in ("active", "in_progress")` so `active_goal_ids` correctly reflects held active goals.
   - Impose an upper bound on active goals exposed to prompt context (most recent $N = 8$ active/in-progress goals), prioritizing current operational focus over ancient history.
   - Introduce an automated or agent-accessible mechanism to retire obsolete goals whose target objects, materials, or premises have been superseded by world updates.
2. **Fauna Sensory Field Prompt Enhancement:**
   - Enhance `build_system_prompt()` in `first_pair_cognition_model.py` so that nearby fauna (<= 6 tiles) explicitly state their distance in the prompt line (e.g. `A cow is nearby (4 tiles away); it is untamed [id: cow-6864-0].`), and when adjacent (<= 1 tile), prompt clear actionable verbs (`offer_food`, `milk_animal`).
   - Verify that perceiving an untamed animal grounds the agent's observation summary and allows the generation of animal-interaction goals (`approach`, `offer_food`).
3. **Taming & Milking Lifecycle Verification:**
   - Multi-step behavioral test verifying:
     a) Perception of wild cow/horse with specific entity ID.
     b) Movement into reach (<= 1 tile).
     c) Sequential `offer_food` actions building trust (+15 for berries, +18 for roots, +20 for apples, etc.) up to the taming threshold (60 for cow, 70 for horse).
     d) Transition to `tamed: True` with home `anchor_tile` assignment.
     e) Cooldown advance toward `milk_ready: True` using the canonical `MILK_READY_HEARTBEATS = 144` constant (`backend.world.fauna:40`).
     f) Execution of `milk_animal`, receipt of `milk: 1`, and hunger satisfaction via `eat milk` (28.0).
4. **CI Workflow Verification:**
   - Maintain the inclusion of all four fauna suites (`test_fauna_pure.py`, `test_fauna_interactions.py`, `test_fauna_runtime.py`, `test_fauna_cognition.py`) in `.github/workflows/pure-tests.yml`.

### 2.2 Out of Scope
- Horse riding, mounted movement, speed alterations, or expanded carrying capacity (remains companion-only in Phase 1).
- Predator wildlife modifications (wolves and deer remain autonomous under `wildlife.py`).
- Automatic deletion of historical goal records from disk (historical goals remain archived in `goals.json`; only prompt projection is filtered and bounded).
- Manual modifications to live civilization stores (`.runtime/`) during the specification phase.

---

## 3. Design Invariants

1. **Constitutional Precedence:** The agent's cognitive authority is strictly preserved. Goals are the agent's internal steering mechanism; the engine only provides prompt filtering, hygiene boundaries, and valid action validation.
2. **No Data Loss:** In `goals.json`, all historical goals are retained for auditing. The runtime only filters the slice projected into `AgentContext.goals`.
3. **Canonical Vocabulary Compatibility:** Goal filtering must accept both `in_progress` (the live agent standard) and `active` (the programmatic default).
4. **Single Source of Truth for Nutrition & Timing:** Food satisfaction values in prompts must derive dynamically from `survival.EAT_SATISFACTION` (meat: 40.0, milk: 28.0, cooked_meal: 75.0, etc.), and milking cooldown must use `fauna.MILK_READY_HEARTBEATS` (144).
5. **Pure Determinism:** Fauna spawning, grazing, and snake strikes continue using seeded RNG (`heartbeat_number * 31 + (crc32(pair_id) % 100000)`, see `first_pair_runtime.py:1454`), ensuring reproducibility across test harnesses.
6. **Fail-Closed Interactions:** Any `offer_food` or `milk_animal` action referencing a missing animal, an animal out of reach ($dist > 1$), an invalid food kind, or an unready state must fail closed with explicit descriptive rejection reasons without mutating inventory.

---

## 4. Architectural Specifications

### 4.1 Goal Hygiene in `FirstPairRuntime`

In `backend/world/first_pair_runtime.py`, `_build_context()` must be updated from:
```python
agent_goals = [g for g in self._goals if g.agent_id == view["agent_id"]]
```
to:
```python
MAX_ACTIVE_GOALS_EXPOSED = 8

agent_goals = [
    g for g in self._goals
    if g.agent_id == view["agent_id"] and getattr(g, "status", "") in ("active", "in_progress")
][-MAX_ACTIVE_GOALS_EXPOSED:]
```

And line 851 of `first_pair_runtime.py` must be updated from:
```python
active_goal_ids = {g.goal_id for g in agent_goals if g.status == "active"}
```
to:
```python
active_goal_ids = {g.goal_id for g in agent_goals if getattr(g, "status", "") in ("active", "in_progress")}
```

#### Goal Retirement Protocol
When a goal's premise is no longer applicable (e.g. testing an old physics version that has been superseded, or referencing an object that has been removed or fully explored), agents may update its status to `"retired"` or `"completed"` via `goal_updates` in cognitive cycle output:
```json
{
  "goal_id": "test_use_object_extract_operator_claim",
  "status": "retired",
  "description": "Retiring obsolete extract test goal; causal crafting and living fauna are now active."
}
```
Furthermore, the runtime should safely mark goals older than 2,000 heartbeats with no updates as `"superseded"` if they block prompt capacity.

### 4.2 Fauna Sensory Field Prompt Enhancement

In `first_pair_cognition_model.py`, `build_system_prompt()` will be enhanced in Phase 10JR to include distance and adjacency affordance verbs:
- If untamed cow/horse is nearby ($2 \le dist \le 6$ tiles):
  ```text
  - A cow is nearby (4 tiles away); it is untamed [id: cow-6864-0]. You can move closer to interact.
  ```
- If untamed cow/horse is adjacent ($dist \le 1$ tile):
  ```text
  - A cow is nearby (adjacent); it is untamed [id: cow-6864-0]. You can offer animal foods (wild_berries, edible_roots, wild_apples, wild_grain, fiber_plants) using offer_food to build trust.
  ```
- If tamed cow is adjacent and milk is ready:
  ```text
  - A cow is nearby (adjacent); it is tamed and milk is ready [id: cow-6864-0]. You can milk it using milk_animal.
  ```

---

## 5. Required Test Coverage for Phase 10JR

Phase 10JR must implement the following tests in `tests/test_fauna_field_observation.py` and `tests/test_goal_hygiene.py`:

1. `test_build_context_filters_inactive_goals`:
   - Setup: Store containing goals with mixed statuses (active, in_progress, completed, retired).
   - Assertion: `ctx.goals` contains only goals with `status in ("active", "in_progress")`, capped at `MAX_ACTIVE_GOALS_EXPOSED` (8).
2. `test_build_context_preserves_most_recent_active_goals`:
   - Setup: 12 `in_progress` goals with distinct creation heartbeats.
   - Assertion: Exactly the 8 newest `in_progress` goals are returned in `ctx.goals`.
3. `test_active_goal_ids_recognizes_in_progress_status`:
   - Setup: Agent goals where all active items have `status == "in_progress"`.
   - Assertion: `active_goal_ids` at line 851 contains all 5 IDs, not an empty set.
4. `test_fauna_field_observation_prompt_enhancement`:
   - Setup: Agent with cow at distance 4, horse at distance 1.
   - Assertion: System prompt contains exact IDs, distances, and valid interaction affordances per Section 4.2.
5. `test_multistep_cow_taming_and_milking_lifecycle`:
   - Step 1: Agent observes wild cow `cow-test-1` at distance 2.
   - Step 2: Agent moves to distance 1.
   - Step 3: Agent executes `offer_food` with `wild_berries` (trust increases from 0 to 15).
   - Step 4: Agent executes `offer_food` 3 more times until trust reaches 60.
   - Step 5: Verify cow `tamed == True` and `anchor_tile == [x, y]`.
   - Step 6: Advance heartbeat past milk cooldown (`MILK_READY_HEARTBEATS = 144`).
   - Step 7: Agent executes `milk_animal`, receives `1 milk`.
   - Step 8: Agent executes `eat resource_kind milk`, satisfying 28.0 hunger.
6. `test_github_ci_workflow_fauna_suites_present`:
   - Verifies that `.github/workflows/pure-tests.yml` includes all four fauna suites.

---

## 6. Phase Chain & Governance

- **Phase Chain:**
  - `10JP`: Specification (this document)  --  Docs only.
  - `10JQ`: Metadata Sync  --  Record 10JP hash in `phase_index.md`, name 10JR candidate.
  - `10JR`: Implementation candidate  --  TDD implementation of goal hygiene, prompt enhancement, and multi-step fauna verification tests.
- **Constitutional Guardrails:**
  - Do not edit live stores (`.runtime/`) or daemon scripts.
  - Do not modify canonical world state.
  - Line endings must remain pure LF (`CRLF=0`).
  - Stage ONLY `world-sim/docs/phase_10jp_fauna_field_observation_and_taming_spec.md`. Never `git add -A` or `git add .` to avoid sweeping untracked cinema/viewer files or local experiments into git history.
  - No implementation code is authorized under Phase 10JP.

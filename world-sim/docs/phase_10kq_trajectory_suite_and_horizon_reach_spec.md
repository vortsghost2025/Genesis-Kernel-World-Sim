# Phase 10KQ Specification: Multi-Step Trajectory Suite & Horizon Reach Behavioral Harness

> **Phase Chain:** 10KN (audit, Done `1518b46`) -> 10KP (metadata sync, Done `5fa3642`, hash-corrected `825b60d`) -> 10KQ (specification, this document) -> 10KR (metadata sync) -> 10KS (implementation candidate, NOT started, NOT authorized)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to candidate Phase 10KS following explicit operator authorization.

---

## 1. Executive Summary: The Shift from Validation to Reach

Phase 10KN corrected the causal attribution of the East Valley convergence and documented that West Dawn's epistemic impasse was not unblocked by factual speech. Following that correction, independent cross-verification by both the human operator and the agent established a decisive empirical fact:

**The Phase 10KH distance-gain pastoral attraction gradient is rigorously validated.** Across 1,000 independent seeds over a 50-step trajectory horizon, untamed grazers starting at distances 6, 9, 12, and 14 achieve **99.4%–100.0% settlement arrival** with an average arrival time of 9 to 22.5 ticks, compared to a 0.6%–23.1% arrival rate and a 4.5%–63.4% escape rate under the unguided uniform random walk.

**The core architectural problem is therefore reach, not validation:**
1. **The Basin Boundary:** The pastoral attraction gradient operates within `PASTORAL_ATTRACTION_RADIUS = 16`. Inside radius 16, arrival is essentially guaranteed. Outside radius 16, weight is identically 1.0 (pure uniform diffusion).
2. **West Dawn's Spatial Reality:** West Dawn's grazers sit at distance 33 (`horse-6866-1` at `[9, 18]`) and distance 44 (`cow-6864-0` at `[-9, 94]`). Because West agents remain stationary at `[35, 51]`, the settlement cannot exert pastoral pull, and the animals will not enter the 16-tile basin by random chance.
3. **The Horizon Sighting Gap:** Horizon sighting (`HORIZON_SIGHT_MIN = 7` to `HORIZON_SIGHT_MAX = 15`) was shipped in Phase 10KH to bridge the gap between prompt perception and settlement range. However, forensic inspection reveals that horizon sighting is currently:
   - **Directionless:** It emits only scalar distance, withholding cardinal bearing or relative coordinates.
   - **Demotivating:** It explicitly tells the agent *"It is too far to interact with now."*
   - **Untested Behaviourally:** No test verifies whether an agent receiving a horizon sighting will generate a directional `move` step toward the sighted animal.

Phase 10KQ specifies the implementation for **Phase 10KS**:
- **Priority 1:** Lock the multi-step trajectory benchmark into the test harness (`tests/test_pastoral_attraction.py`), replacing the single-step derivative floor with definitive arrival and retention assertions.
- **Priority 2:** Upgrade horizon sighting with cardinal directionality and actionable affordance copy, and build the behavioral evaluation harness to measure agent navigational response.
- **Priority 3:** Establish the empirical escape-rate protocol for calibrating future reach levers (`PASTORAL_ATTRACTION_RADIUS` widening and spawn placement).

---

## 2. Priority 1: Multi-Step Trajectory Regression Suite

### 2.1 Cross-Verified Empirical Benchmark

Both the human operator and agent independently ran 1,000-trial, 50-step trajectory simulations comparing the Uniform Control Arm (`signal_xys=None`) against the 10KH Gain Gradient Arm (`signal_xys=[(0, 0)]`), with arrival defined as Chebyshev distance $\le 1$ and escape defined as Chebyshev distance $> 16$:

| Start Dist | Arm | Agent Arrival | Operator Arrival | Agent Mean Steps | Operator Mean Steps | Escape Rate (No Arrival) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **6** | Control (Uniform Walk) | 22.4% | 23.1% | 23.3 | 23.8 | 4.5% – 28.2% |
| | **10KH Gain Gradient** | **100.0%** | **100.0%** | **9.1** | **9.0** | **0.0%** |
| **9** | Control (Uniform Walk) | 7.8% | 8.3% | 30.1 | 32.5 | 12.4% – 46.1% |
| | **10KH Gain Gradient** | **99.9%** | **99.9%** | **14.4** | **14.1** | **0.0%** |
| **12** | Control (Uniform Walk) | 2.6% | 2.1% | 36.0 | 35.9 | 22.3% – 58.7% |
| | **10KH Gain Gradient** | **99.8%** | **99.9%** | **19.4** | **18.9** | **0.0%** |
| **14** | Control (Uniform Walk) | 0.6% | 1.0% | 42.0 | 40.1 | 34.5% – 63.4% |
| | **10KH Gain Gradient** | **99.6%** | **99.4%** | **22.5** | **22.4** | **0.0%** |

### 2.2 Test Suite Modernization Specification

In `world-sim/tests/test_pastoral_attraction.py`, replace the single-step derivative test (`test_attraction_reduces_mean_distance_to_signal`, which checks $\Delta \ge 0.40$ on a single step) with two trajectory-level tests:

1. `test_multistep_arrival_distribution(start_dist, expected_min_arrival, max_mean_steps)`:
   - Parametrized across `start_dist` in `[6, 9, 12, 14]`.
   - Simulates 500 independent seeds over 50 steps.
   - Asserts arrival rate $\ge 98.0\%$ under gradient arm at all distances.
   - Asserts mean arrival steps within verified bounds:
     - $d=6 \implies \le 12.0$ steps
     - $d=9 \implies \le 18.0$ steps
     - $d=12 \implies \le 22.0$ steps
     - $d=14 \implies \le 26.0$ steps
   - Asserts control arm arrival is strictly below treatment arm by a factor of $\ge 4\times$.

2. `test_multistep_retention_against_escape(start_dist)`:
   - Asserts that for all start distances $\le 14$, zero grazer paths ever cross the outer boundary ($dist > 16$) under the gradient arm ($0.0\%$ escape), while the control arm exhibits significant outward escape.

---

## 3. Priority 2: Horizon Sighting Reach & Directionality Harness

### 3.1 Forensic Diagnosis of Shipped Horizon Sighting

Inspection of `backend/world/first_pair_runtime.py:1405` (`_fauna_visible`) and `backend/world/first_pair_cognition_model.py:1254` (`_format_fauna_lines`) reveals three structural flaws that render horizon sighting inert:

1. **Information Destruction:** `_fauna_visible` calculates `dist = max(abs(tile[0] - pos[0]), abs(tile[1] - pos[1]))`, but discards the entity coordinate `tile` and agent coordinate `pos`. It returns only `{"kind": kind, "id": id, "distance": dist}`.
2. **Directional Blindness:** The cognition prompt receives `dist = 12`, but has no bearing. On a 2D grid, an agent choosing a movement direction has an 87.5% chance (7 of 8 neighbors) of moving orthogonal to or away from the animal.
3. **Inhibitory Copy:** `_format_fauna_lines` renders:
   ```
   On the horizon: a cow grazes about 12 tiles away [id: cow-5058-0]. It is too far to interact with now.
   ```
   To an LLM evaluating actions against goals, *"It is too far to interact with now"* explicitly signals that no productive interaction is possible, actively depressing motivation to investigate.

### 3.2 Directional Horizon Sighting Specification

1. **Runtime Cardinal Bearing Extraction (`first_pair_runtime.py`):**
   - Add a pure helper `_cardinal_bearing(from_xy: tuple[int, int], to_xy: tuple[int, int]) -> str` returning one of the 8 compass directions (`"north"`, `"northeast"`, `"east"`, `"southeast"`, `"south"`, `"southwest"`, `"west"`, `"northwest"`).
   - In `_fauna_visible`, include `bearing` in the `distant` item record:
     ```python
     item = {
         "kind": kind,
         "id": entity.get("id"),
         "distance": dist,
         "bearing": self._cardinal_bearing(pos, tile),
     }
     ```

2. **Actionable Affordance Formatting (`first_pair_cognition_model.py`):**
   - Update `_format_fauna_lines` to format distant grazers with actionable navigational affordance:
     ```python
     bearing = animal.get("bearing", "")
     bearing_str = f" to the {bearing}" if bearing else ""
     lines.append(
         f"On the horizon: a {kind} grazes ~{dist} tiles away{bearing_str} [id: {aid}]. "
         f"Moving in that direction can bring it within pastoral range."
     )
     ```
   - Retains exclusion of snakes from horizon sightings.
   - Retains exclusion of taming action verbs (`offer_food`, `milk_animal`) until the animal is actually `nearby`.

### 3.3 Behavioral Evaluation Test Harness

In `world-sim/tests/test_horizon_sighting.py`, add behavioral evaluation tests:

1. `test_horizon_sighting_includes_directional_bearing`:
   - Verifies that `_fauna_visible` returns accurate compass bearings for all 8 octants.
2. `test_horizon_prompt_renders_actionable_navigation_line`:
   - Verifies that `_format_fauna_lines` renders the directional bearing and the navigational affordance sentence without the inhibitory *"too far to interact"* phrase.
3. `test_horizon_prompt_affordance_generates_pursuit_context`:
   - Builds a full `build_system_prompt` context with a horizon-sighted cow.
   - Verifies prompt structure guarantees directional clarity for the agent's movement planner.

---

## 4. Priority 3: Reach Levers & Escape-Rate Calibration Protocol

### 4.1 The Reach Problem

The pastoral gradient guarantees settlement arrival within radius 16. However, if an animal spawns or drifts beyond 16 tiles while agents are immobilized, the gradient never activates.

Three mechanical levers exist to bridge this gap:
1. **Lever 1: Horizon Sighting Navigation (Priority 2):** Agents perceive animals at distances 7–15 and walk toward them, dragging the pastoral basin along with their movement.
2. **Lever 2: Widening `PASTORAL_ATTRACTION_RADIUS`:** Expanding radius from 16 to 20, 24, or 32.
3. **Lever 3: Settlement Spawn Bias:** Constraining new grazer spawns to within $R \le 16$ of active settlement signals.

### 4.2 Escape-Rate Protocol for Radius Expansion

Widening `PASTORAL_ATTRACTION_RADIUS` carries the risk of creating an unphysical "global tractor beam" that pulls animals across entire continents.

Before any change to `PASTORAL_ATTRACTION_RADIUS` is authorized in code, the implementation must evaluate candidate radii ($R \in [16, 20, 24, 32]$) against the **Multi-Step Escape Protocol**:
- Start distance $d = R - 2$.
- Measure escape rate over 50 steps under both Control and Gradient arms.
- **Safety Criterion:** The escape rate of neutral/wild animals outside the pastoral radius must remain non-zero and consistent with regional ecology.
- **Decision:** Lever 1 (directional horizon sighting) must be evaluated first. Lever 2 remains blocked until empirical calibration data is reviewed.

---

## 5. Non-Goals & Constitutional Boundaries

1. **No Second Operator Message:**
   - As established in Phase 10KN, delivering further operator statements to West Dawn is forbidden. West converts factual descriptions into requests for externally-supplied purpose, creating a dependency loop prohibited by Standing Rule 7.
2. **No Runtime Surgery on Agent Goals:**
   - The 7 active standby goals in West Dawn will not be deleted, modified, or cleared via out-of-band scripts. The agent cognition architecture must resolve or supersede its own goals through mechanical environmental stimuli.
3. **No Live Taming Enforcement:**
   - No attempt will be made to force taming transactions in the live simulation while West animals are at distance 44 and East agents are executing stone collection. Taming will be observed when spatial contact occurs naturally.
4. **Docs-Only Phase Discipline (Standing Rule 1):**
   - Phase 10KQ is strictly a documentation specification.
   - All files must be pure LF (`CRLF=0`).
   - Stop before commit unless Sean explicitly authorizes commit/push.

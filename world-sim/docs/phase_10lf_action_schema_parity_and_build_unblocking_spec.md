# Phase 10LF Specification: Action Schema Parity & Build Unblocking

> **Phase Chain:** 10LD (impl, Done `e9ce99f`) -> 10LE (metadata sync, Done `3aa0d7a`, hash-corrected `cd0305d`) -> 10LF (specification, this document) -> 10LG (metadata sync) -> 10LH (implementation candidate)
> **Constitutional Notice:** Docs-only specification. Implementation code is deferred to Phase 10LH.

---

## 1. Purpose & Live Evidence

Earlier audits at HB 6296 observed zero `hew_timber`, zero `addon_to`, and zero `craft` actions and concluded the load-bearing construction chain (10KM) and settlement-awareness layer (10KZ) were behaviourally inert. Inspection of the subsequent live export (`viewer/viewer_data.js`, `exported_tick = 6366`) disproves that conclusion and isolates the actual blocker: **the cognition schema validator in `first_pair_cognition_model.py` rejects `hew_timber`, `plant_crop`, `harvest_crop`, and `build` with `addon_to` before they ever reach `first_pair_runtime.py`.**

### 1.1 Exact Sequence in East Valley (HB 6353–6365)

| Heartbeat | Agent | Action | Outcome | Significance |
| :--- | :--- | :--- | :--- | :--- |
| **6353** | `east_adam` | `build` (`shelter-001-north000`, `shelter`) | `rejected` | Receives 10KM error: *"A shelter needs at least 2 structural timber to bear its own weight; you declared 0. Fell trees with hew_timber once you hold an axe (stone_axe, iron_axe) or knapped blade (flint_knife)."* |
| **6354** | `east_adam` | `build` (`crafting_surface-001`, `crafting_surface`, `{"stone": 2, "wood": 2}`) | **`success`** | Reads 10KM recipe disclosure and constructs a crafting surface. |
| **6355** | `east_adam` | `use_object` (`craft`, `{"stone": 2, "wood": 1}`) | **`success`** | Crafts `stone_axe` (`inventories["east_adam"]["stone_axe"] == 1`). |
| **6359** | `east_adam` | `move` (`cont_a_north_000`) | `success` | Moves onto a forest tile (`reason: "Move to cont_a_north_000 to build shelter and gain warmth."`). |
| **6360, 6361, 6363** | `east_adam` | `None` | Turn dropped | Proposes `hew_timber`; `validate_action_exact` returns `["invalid_action_type"]`, invalidating the entire `ModelOutput`. |

---

## 2. Three Concrete Defects Verified at Source

### Defect A: Prompt-to-Validator Schema Drift (`first_pair_cognition_model.py`)

When Phase 10JX (`f26b137`) introduced `hew_timber`, `plant_crop`, `harvest_crop`, and `addon_to` on `build`:
- `_AVAILABLE_ACTIONS_DESC` (`first_pair_cognition_model.py:1349-1352`) advertised all four in the system prompt.
- `FirstPairRuntime._execute_action` (`first_pair_runtime.py:2135-2143`) dispatched all four.
- **However, `_VALID_ACTIONS` (`first_pair_cognition_model.py:409-426`) and `_ACTION_SCHEMAS` (`504-537`) were never updated:**
  - `"hew_timber" in _VALID_ACTIONS` is `False` -> returns `["invalid_action_type"]`.
  - `"plant_crop" in _VALID_ACTIONS` is `False` -> returns `["invalid_action_type"]`.
  - `"harvest_crop" in _VALID_ACTIONS` is `False` -> returns `["invalid_action_type"]`.
  - `"addon_to" in _ACTION_SCHEMAS["build"]` is `False` -> `_reject_unknown_fields` returns `["actionunknown_field:addon_to"]`.

Because `validate_model_output` (`881-885`) appends `action_errors` to top-level `errors`, any proposal using these advertised capabilities marks `validated.is_valid = False`, causing `observe_and_orient` (`2064-2076`) to discard the agent's action as `None`. Existing tests in `test_compound_architecture.py`, `test_cultivation.py`, and `test_load_bearing_construction.py` called `runtime._execute_action(...)` directly, bypassing `validate_action_exact`.

### Defect B: Off-Tile `Duplicate object_id` Collisions (`first_pair_runtime.py`)

In East Valley's last 50 heartbeats (HB 6317–6366), agents attempted 30 `build` actions (8 succeeded, 22 rejected). Of the 22 rejections:
- 10 were legitimate 10KM structural-timber rejections (which drove Adam to craft `stone_axe`).
- **12 (55%) were `Duplicate object_id` collisions** (`shelter-001` x3, `shelter-001-adam` x5, `campfire_001` x2, `shelter-012` x1, `campfire_new` x1).

An agent's observation only exposes objects on its **current** tile, whereas `_execute_build` (`first_pair_runtime.py:2391`) checks `if object_id in self._world_state.public_objects:` across all 83+ historical objects on the continent. When an agent moves to a fresh tile with no shelter and proposes `"shelter-001"`, it collides with an unseen object built thousands of heartbeats earlier on a distant tile.

### Defect C: Chronicle Omission of Tool Crafting and Timber Hewing (`export_viewer_snapshot.py`)

`build_chronicle` (`scripts/export_viewer_snapshot.py:244-274`) only emits events for `build`, `create_public_object`, `eat`, `attack`, `ask_human`, and `collapse`. When `east_adam` crafted `stone_axe` via `use_object` at HB 6355, no chronicle entry was emitted, making the tool-crafting milestone invisible in the Observatory narrative.

---

## 3. Architectural Specifications for Phase 10LH

### 3.1 Full Action Schema Parity (`first_pair_cognition_model.py`)

1. Add `"hew_timber"`, `"plant_crop"`, and `"harvest_crop"` to `_VALID_ACTIONS`.
2. Update `_ACTION_SCHEMAS`:
   - `"build"`: add optional `"addon_to"` and `"reason"` to `frozenset({"action_type", "object_id", "object_type", "description", "tile_id", "materials", "addon_to", "reason"})`.
   - `"hew_timber"`: `frozenset({"action_type", "reason", "tool", "tile_id", "target_id"})`.
   - `"plant_crop"`: `frozenset({"action_type", "target_id", "target_object_id", "resource_kind", "reason"})`.
   - `"harvest_crop"`: `frozenset({"action_type", "target_id", "target_object_id", "reason"})`.
   - `"use_object"`: allow optional `"target_id"` (normalized to `"target_object_id"`) and `"reason"`.
3. In `validate_action_exact`:
   - For `"build"`: if `"addon_to"` is present and not `None`, validate it is a non-empty safe ID string (`_is_safe_id`).
   - For `"hew_timber"`: validate optional `"reason"` and `"tool"` lengths if present.
   - For `"plant_crop"`: accept `"target_id"` or `"target_object_id"` (normalizing to `"target_id"`), require non-empty `"target_id"` and `"resource_kind"`.
   - For `"harvest_crop"`: accept `"target_id"` or `"target_object_id"` (normalizing to `"target_id"`), require non-empty `"target_id"`.

### 3.2 Off-Tile `object_id` Disambiguation (`first_pair_runtime.py`)

In `_execute_build`:
- If `object_id in self._world_state.public_objects`:
  - Inspect `existing_obj = self._world_state.public_objects[object_id]`.
  - If `existing_obj.get("tile_id") == tile_id` (same tile): **reject** with `"Duplicate object_id: ..."` as before (preserving `test_build_duplicate_id_rejected` in `test_build_layer.py`, since the agent can see objects on its own tile).
  - If `existing_obj.get("tile_id") != tile_id` (different tile, invisible in current tile observation): deterministically disambiguate `object_id` as `f"{object_id}-hb{heartbeat_number}"` (or append a numeric suffix if needed) so valid builds on new tiles are not rejected for unseen historical IDs.

### 3.3 Chronicle Coverage (`scripts/export_viewer_snapshot.py`)

In `build_chronicle`:
- When `at == "hew_timber"` and `outcome.get("status") == "success"`: emit `{"hb": hb, "kind": "hew_timber", "who": name, "text": f"hewed {outcome.get('timber_yield', 1)} structural timber"}`.
- When `at == "use_object"` and `outcome.get("status") == "success"`:
  - If `outcome.get("crafted")` or `action.get("operation") == "craft"`: emit `{"hb": hb, "kind": "craft", "who": name, "text": f"crafted {outcome.get('crafted') or 'a tool'}"}`.
  - If `action.get("operation") == "cook"`: emit `{"hb": hb, "kind": "cook", "who": name, "text": "cooked a hot meal"}`.
  - If `action.get("operation") == "smelt"`: emit `{"hb": hb, "kind": "smelt", "who": name, "text": "smelted metal"}`.
- When `at in ("plant_crop", "harvest_crop")` and `outcome.get("status") == "success"`: emit a corresponding cultivation chronicle event.

---

## 4. Required Test Coverage for Phase 10LH

In `tests/test_action_schema_parity.py`:

1. `test_prompt_validator_runtime_action_set_parity` — asserts that every action bullet in `_AVAILABLE_ACTIONS_DESC`, every entry in `_VALID_ACTIONS`, every key in `_ACTION_SCHEMAS`, and every `action_type` branch in `FirstPairRuntime._execute_action` (plus `"no_action"`) are in exact 1-to-1 parity.
2. `test_hew_timber_passes_validate_action_exact_and_model_output` — verifies `hew_timber` with `reason` (and optional `tool`) validates cleanly through both `validate_action_exact` and `validate_model_output`.
3. `test_build_with_addon_to_passes_validate_action_exact` — verifies `build` with `addon_to` validates cleanly and rejects unsafe `addon_to` IDs.
4. `test_plant_and_harvest_crop_pass_validate_action_exact` — verifies `plant_crop` and `harvest_crop` validate cleanly and reject missing `target_id`.
5. `test_end_to_end_cognition_to_runtime_hew_timber_and_shelter_build` — full round-trip from raw JSON model output (`validate_model_output`) -> `runtime._execute_action` for `hew_timber` (yielding 2 timber with `stone_axe`) followed by `build` (`shelter` with 2 timber).
6. `test_build_same_tile_duplicate_id_still_rejected` — preserves existing contract when colliding on the same tile.
7. `test_build_off_tile_duplicate_id_disambiguated_and_succeeds` — verifies proposing `"shelter-001"` on a new tile when `"shelter-001"` exists on a distant tile disambiguates the ID and succeeds.
8. `test_build_chronicle_records_craft_and_hew_timber` — verifies `build_chronicle` emits entries for successful `use_object` (`craft`) and `hew_timber` actions.

---

## 5. Governance & Guardrails

- **Phase Chain:** `10LF` (spec) -> `10LG` (metadata sync) -> `10LH` (implementation) -> `10LI` (metadata sync).
- **No new mechanics:** All changes wire and unblock already-specified mechanics (10JX, 10KM).
- **Pure LF line endings (`CRLF=0`).**

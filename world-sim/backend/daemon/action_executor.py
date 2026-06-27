"""
Action executor skeleton for daemon mode.

Provides a controlled way to apply world changes based on agent decisions.
Supports copy/test mode only in Phase 6B. No live world mutations.

Phase 6B: WorldMutationGuardHarness
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.world.safe_world_write import (
    atomic_json_write,
    backup_before_write,
    compute_md5,
    log_mutation,
    safe_world_write,
)

logger = logging.getLogger("world.action_executor")

# Supported action types (Phase 6B — skeleton only)
SUPPORTED_ACTIONS = {"observe", "rest", "gather"}

# Keyword lists for action detection
_GATHER_KEYWORDS = [
    "gather", "harvest", "collect", "forage", "pick", "fetch",
    "hunt", "fish", "draw water", "fetch water",
]

_REST_KEYWORDS = [
    "rest", "sleep", "sit", "meditate", "watch", "wait", "pause",
]

# ---------------------------------------------------------------------------
# Phase 6H: Executor-level gather content validation
# Defense-in-depth against unsafe gather content even if called directly
# (not via agent_daemon.py).
# ---------------------------------------------------------------------------

# Minimum non-trivial content length for a grounded gather.
_GATHER_MIN_LEN = 4

# Phrases that imply an unobserved water source / location. Models frequently
# invent these; they must not drive gather actions.
_GATHER_UNOBSERVED_SOURCE_PHRASES = [
    "hidden water source",
    "the hidden water source",
    "water location",
    "the water location",
    "known water source",
    "where the water is",
]

# Phrases that imply animal movement/calls/guidance without world-state support.
# World state records no dove/lamb movement/calls.
_GATHER_UNOBSERVED_MOVEMENT_PHRASES = [
    "follow their movements",
    "i see dove and lamb movements",
    "they are leading",
    "they are guiding",
    "listen for their calls",
    "they know where water is",
    # Phase 6K hardening: closes the gap where "follow dove and lamb movements"
    # slipped past the dynamic-style regex above. These phrases are literal
    # patterns the model has actually surfaced in earlier phases.
    "follow dove and lamb movements",
    "dove and lamb movements",
    "animal movements",
    "follow animal movements",
    "follow the animals",
]

# Phase 6K hardening. Pair an animal present name with a behavior keyword
# implies an unrecorded pattern (movement/calls/guide/lead/follow/track).
_GATHER_ANIMAL_NAMES = ["dove", "lamb", "lion", "eagle", "serpent"]
_GATHER_BEHAVIOR_KEYWORDS = [
    "movement", "movements",
    "follow",
    "guide", "guiding",
    "lead", "leading",
    "call", "calls",
    "track", "tracking",
]


def _gather_invents_animal_behavior(ltext):
    """
    If any behavior keyword in _GATHER_BEHAVIOR_KEYWORDS co-occurs with an
    animal present name in ltext (token-level match), return a string
    describing the matched animals and behaviors. Otherwise return None.
    """
    tokens = set(ltext.split())
    animals_here = [a for a in _GATHER_ANIMAL_NAMES if a in tokens]
    if not animals_here:
        return None
    behaviors_here = [k for k in _GATHER_BEHAVIOR_KEYWORDS if k in ltext]
    if not behaviors_here:
        return None
    return (
        f"animal behavior invention "
        f"(animals={animals_here} behaviors={behaviors_here})"
    )


def _validate_gather_content(action_text: str) -> tuple:
    """
    Return (ok, error_message). error_message starts with 'invalid_gather: '
    when ok=False.

    Rules (Phases 6H + 6K):
      1. Reject empty / whitespace-only / trivially short content.
      2. Reject content containing any _GATHER_UNOBSERVED_SOURCE_PHRASES term.
      3. Reject content containing any _GATHER_UNOBSERVED_MOVEMENT_PHRASES term.
      4. Pattern: reject content where any behavior keyword (movement[s],
         follow, guide, guiding, lead, leading, calls, call) co-occurs
         with an animal present name (dove, lamb, lion, eagle, serpent).
    """
    text = (action_text or "").strip()
    if not text or len(text) < _GATHER_MIN_LEN:
        return False, "invalid_gather: empty or trivially short content"

    lower = text.lower()
    for phrase in _GATHER_UNOBSERVED_SOURCE_PHRASES:
        if phrase in lower:
            return False, f"invalid_gather: unobserved source phrase ({phrase!r})"
    for phrase in _GATHER_UNOBSERVED_MOVEMENT_PHRASES:
        if phrase in lower:
            return False, f"invalid_gather: unobserved movement phrase ({phrase!r})"
    invented = _gather_invents_animal_behavior(lower)
    if invented:
        return False, f"invalid_gather: {invented}"
    return True, ""


def detect_action_type(action_text: str) -> str:
    """
    Detect action type from agent action text.
    Returns one of: "gather", "rest", "observe", or "unknown".
    """
    text_lower = action_text.lower()
    
    for kw in _GATHER_KEYWORDS:
        if kw in text_lower:
            return "gather"
    
    for kw in _REST_KEYWORDS:
        if kw in text_lower:
            return "rest"
    
    # Default to observe (read-only)
    return "observe"


def apply_gather_to_world(world_data: dict[str, Any]) -> dict[str, Any]:
    """
    Apply a controlled gather action to world data.
    Returns the modified world data (does not write to disk).
    
    Phase 6B: Controlled resource change only.
    """
    resources = world_data.get("resources", {})
    
    # Small controlled resource gain
    current_food = resources.get("food", 0.5)
    current_materials = resources.get("materials", 0.5)
    
    new_food = min(1.0, current_food + 0.05)
    new_materials = min(1.0, current_materials + 0.03)
    
    resources["food"] = round(new_food, 3)
    resources["materials"] = round(new_materials, 3)
    
    world_data["resources"] = resources
    return world_data


def execute_action(
    agent_id: str,
    action_type: str,
    action_text: str,
    world_path: Path,
    *,
    copy_mode: bool = True,
    allow_canonical: bool = False,
    require_backup: bool = False,
    audit_log_path: Path | None = None,
    backup_dir: Path | None = None,
    use_canonical_fog: bool = False,
    canonical_data_root: Path | str | None = None,
) -> dict[str, Any]:
    """
    Execute a world action with safety guards.
    
    Phase 6B: copy_mode=True is enforced. No canonical world mutations.
    Phase 6G: Canonical write gates added for controlled gather mutations.
    Phase 7K: use_canonical_fog=True uses canonical fog-of-war observation (read-only).

    Args:
        agent_id: ID of the agent performing the action
        action_type: One of: "observe", "rest", "gather"
        action_text: The raw action text from the agent
        world_path: Path to the world-state JSON file
        copy_mode: If True, operate on a copy only (enforced in Phase 6B)
        allow_canonical: Must be True to allow canonical writes (Phase 6G)
        require_backup: Must be True to allow canonical writes (Phase 6G)
        audit_log_path: Path to the audit log file (required for canonical)
        backup_dir: Directory for backups
        use_canonical_fog: If True, use canonical fog-of-war observation (read-only, requires canonical_data_root)
        canonical_data_root: Root directory for canonical fog files (world/ and agents/ subdirs)
    
    Returns:
        Result dict with ok, action_type, world_changed, before_md5, after_md5, changes, output_path
    """
    world_path = Path(world_path)
    
    # Validate action type
    if action_type not in SUPPORTED_ACTIONS:
        return {
            "ok": False,
            "action_type": action_type,
            "world_changed": False,
            "before_md5": "",
            "after_md5": "",
            "changes": {},
            "output_path": None,
            "error": f"unsupported_action: {action_type} (supported: {SUPPORTED_ACTIONS})",
        }
    
    # Phase 7K: Canonical fog-of-war observation (read-only, no world_path needed)
    if action_type == "observe" and use_canonical_fog:
        if canonical_data_root is None:
            return {
                "ok": False,
                "action_type": action_type,
                "world_changed": False,
                "before_md5": "",
                "after_md5": "",
                "changes": {},
                "output_path": None,
                "error": "use_canonical_fog=True requires canonical_data_root",
            }
        try:
            from backend.world.fog_of_war import build_canonical_observation
            root = Path(canonical_data_root) if not isinstance(canonical_data_root, Path) else canonical_data_root
            conditions = {"radius": 1}  # Default radius for canonical observe
            observation = build_canonical_observation(agent_id, root, conditions)
            return {
                "ok": True,
                "action_type": "observe",
                "world_changed": False,
                "before_md5": "",
                "after_md5": "",
                "changes": {},
                "output_path": None,
                "observation": observation,
                "error": None,
            }
        except FileNotFoundError as e:
            return {
                "ok": False,
                "action_type": action_type,
                "world_changed": False,
                "before_md5": "",
                "after_md5": "",
                "changes": {},
                "output_path": None,
                "error": f"canonical_file_missing: {e}",
            }
        except Exception as e:
            return {
                "ok": False,
                "action_type": action_type,
                "world_changed": False,
                "before_md5": "",
                "after_md5": "",
                "changes": {},
                "output_path": None,
                "error": f"canonical_observation_error: {e}",
            }

    # Enforce copy mode in Phase 6B, allow canonical with gates (Phase 6G)
    canonical_mode = False
    if not copy_mode:
        # Check if all canonical gates are present
        if allow_canonical and require_backup and audit_log_path is not None:
            canonical_mode = True
            logger.info("canonical_write_gates_met: agent=%s action=%s", agent_id, action_type)
        else:
            logger.warning("copy_mode=False rejected: gates not met (allow_canonical=%s require_backup=%s audit_path=%s) agent=%s action=%s",
                          allow_canonical, require_backup, audit_log_path is not None, agent_id, action_type)
            return {
                "ok": False,
                "action_type": action_type,
                "world_changed": False,
                "before_md5": "",
                "after_md5": "",
                "changes": {},
                "output_path": None,
                "error": f"copy_mode=False rejected: canonical gates not met (allow_canonical={allow_canonical}, require_backup={require_backup}, audit_path={audit_log_path is not None})",
            }
    
    # Load world data
    if not world_path.exists():
        return {
            "ok": False,
            "action_type": action_type,
            "world_changed": False,
            "before_md5": "",
            "after_md5": "",
            "changes": {},
            "output_path": None,
            "error": f"world_path_not_found: {world_path}",
        }
    
    try:
        world_data = json.loads(world_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {
            "ok": False,
            "action_type": action_type,
            "world_changed": False,
            "before_md5": "",
            "after_md5": "",
            "changes": {},
            "output_path": None,
            "error": f"json_parse_error: {e}",
        }
    
    # Compute before MD5
    before_md5 = compute_md5(world_path)
    
    # Apply action to a copy of world data
    import copy
    test_world = copy.deepcopy(world_data)
    changes = {}
    world_changed = False
    
    if action_type == "observe":
        # Read-only, no mutation
        changes = {"observation": "read-only world snapshot"}
        world_changed = False
    
    elif action_type == "rest":
        # No mutation in Phase 6B
        changes = {"rest": "no world change"}
        world_changed = False
    
    elif action_type == "gather":
        # Phase 6H: validate gather content BEFORE any mutation.
        # Defense-in-depth: same rules as agent_daemon.py:828-836 but enforced here too.
        content_ok, content_err = _validate_gather_content(action_text)
        if not content_ok:
            logger.warning(
                "executor_gather_invalid: agent=%s reason=%s action_text=%r",
                agent_id, content_err, action_text,
            )
            return {
                "ok": False,
                "action_type": action_type,
                "world_changed": False,
                "before_md5": "",
                "after_md5": "",
                "changes": {},
                "output_path": None,
                "error": content_err,
            }
        # Apply controlled resource change
        old_resources = dict(test_world.get("resources", {}))
        test_world = apply_gather_to_world(test_world)
        new_resources = dict(test_world.get("resources", {}))
        changes = {"resources": {"old": old_resources, "new": new_resources}}
        world_changed = True
    
    if canonical_mode and world_changed:
        # Canonical write via safe_world_write (backup + atomic + audit)
        write_result = safe_world_write(
            path=world_path,
            data=test_world,
            actor=agent_id,
            action=action_type,
            changes=changes,
            audit_log_path=audit_log_path,
            backup_dir=backup_dir,
        )
        if not write_result.get("ok"):
            return {
                "ok": False,
                "action_type": action_type,
                "world_changed": False,
                "before_md5": before_md5,
                "after_md5": write_result.get("after_md5", ""),
                "changes": changes,
                "output_path": None,
                "error": write_result.get("error", "canonical_write_failed"),
            }
        return {
            "ok": True,
            "action_type": action_type,
            "world_changed": True,
            "before_md5": write_result.get("before_md5", before_md5),
            "after_md5": write_result.get("after_md5", ""),
            "changes": changes,
            "output_path": str(world_path),
            "backup_path": write_result.get("backup_path"),
            "error": None,
        }
    elif canonical_mode and not world_changed:
        # Canonical read-only action (observe/rest) - no write needed
        pass
    
    # Write to test copy path (copy mode)
    output_dir = world_path.parent / "test_worlds"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_name = f"test_{agent_id}_{action_type}_{timestamp}.json"
    output_path = output_dir / output_name
    
    if world_changed:
        ok = atomic_json_write(output_path, test_world)
        if not ok:
            return {
                "ok": False,
                "action_type": action_type,
                "world_changed": False,
                "before_md5": before_md5,
                "after_md5": "",
                "changes": changes,
                "output_path": None,
                "error": "atomic_write_failed",
            }
        after_md5 = compute_md5(output_path)
    else:
        output_path = None
        after_md5 = before_md5
    
    # Audit log (copy mode)
    if audit_log_path and world_changed:
        log_mutation(
            audit_log_path,
            actor=agent_id,
            action=action_type,
            target_file=str(output_path),
            before_md5=before_md5,
            after_md5=after_md5,
            changes=changes,
        )
    
    return {
        "ok": True,
        "action_type": action_type,
        "world_changed": world_changed,
        "before_md5": before_md5,
        "after_md5": after_md5,
        "changes": changes,
        "output_path": str(output_path) if output_path else None,
        "error": None,
    }

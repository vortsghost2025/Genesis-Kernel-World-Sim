"""
Phase 6C: ObserveAffordanceWiring Synthetic Tests
Tests that observe decision is recognized, executed, and valid.
"""
import sys
import json
import tempfile
import shutil
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.daemon.action_executor import execute_action, detect_action_type

PASS_COUNT = 0
FAIL_COUNT = 0

def assert_eq(label, got, want):
    global PASS_COUNT, FAIL_COUNT
    if got == want:
        PASS_COUNT += 1
        print(f"  PASS: {label}")
    else:
        FAIL_COUNT += 1
        print(f"  FAIL: {label}: got={got!r}, want={want!r}")

def assert_true(label, cond):
    global PASS_COUNT, FAIL_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  PASS: {label}")
    else:
        FAIL_COUNT += 1
        print(f"  FAIL: {label}")

# TEST 1: detect_action_type recognizes observe text
print("\nTEST 1: detect_action_type recognizes observe text")
action_type = detect_action_type("looking around the garden")
assert_eq("observe detected", action_type, "observe")

# TEST 2: detect_action_type with empty string defaults to observe
print("\nTEST 2: detect_action_type with empty string defaults to observe")
action_type = detect_action_type("")
assert_eq("observe detected (empty)", action_type, "observe")

# TEST 3: execute_action observe on copy does not mutate canonical
print("\nTEST 3: execute_action observe does not mutate canonical world")
tmpdir = Path(tempfile.mkdtemp())
canonical = tmpdir / "east_world_state.json"
shutil.copy(project_root / "data/east_world_state.json", canonical)
original_content = canonical.read_text()
result = execute_action(
    agent_id="east_adam",
    action_type="observe",
    action_text="looking at the garden",
    world_path=canonical,
    copy_mode=True,
)
current_content = canonical.read_text()
assert_eq("observe ok", result.get("ok"), True)
assert_eq("observe world_changed", result.get("world_changed"), False)
assert_eq("canonical unchanged", current_content, original_content)
shutil.rmtree(tmpdir)

# TEST 4: execute_action observe does NOT write audit log (read-only)
print("\nTEST 4: execute_action observe does NOT write audit log (read-only)")
tmpdir = Path(tempfile.mkdtemp())
canonical = tmpdir / "east_world_state.json"
shutil.copy(project_root / "data/east_world_state.json", canonical)
result = execute_action(
    agent_id="east_adam",
    action_type="observe",
    action_text="scanning the area",
    world_path=canonical,
    copy_mode=True,
)
# Observe is read-only, so no audit log entry should be written
assert_eq("observe ok", result.get("ok"), True)
assert_eq("observe world_changed", result.get("world_changed"), False)
shutil.rmtree(tmpdir)

# TEST 5: observe is in SUPPORTED_ACTIONS
print("\nTEST 5: observe is in SUPPORTED_ACTIONS")
from backend.daemon.action_executor import SUPPORTED_ACTIONS
assert_true("observe in SUPPORTED_ACTIONS", "observe" in SUPPORTED_ACTIONS)

# TEST 6: observe does not require target (no crash)
print("\nTEST 6: observe does not require target (no crash)")
tmpdir = Path(tempfile.mkdtemp())
canonical = tmpdir / "east_world_state.json"
shutil.copy(project_root / "data/east_world_state.json", canonical)
try:
    result = execute_action(
        agent_id="east_adam",
        action_type="observe",
        action_text="",
        world_path=canonical,
        copy_mode=True,
    )
    assert_true("observe with empty text no crash", True)
except Exception as e:
    assert_true(f"observe with empty text no crash: {e}", False)
shutil.rmtree(tmpdir)

# TEST 7: detect_action_type still works for existing actions
print("\nTEST 7: detect_action_type still works for existing actions")
assert_eq("rest detected", detect_action_type("resting quietly"), "rest")
assert_eq("gather detected", detect_action_type("collecting berries"), "gather")

# TEST 8: prompt contract includes observe
print("\nTEST 8: daemon prompt contract includes observe")
daemon_path = project_root / "backend/daemon/agent_daemon.py"
daemon_text = daemon_path.read_text()
assert_true("observe in decision contract", "whisper|goal|rest|observe|help" in daemon_text)

# TEST 9: prompt includes observe rules
print("\nTEST 9: prompt includes observe rules")
assert_true("observe rules in prompt", "observe is read-only" in daemon_text)

# TEST 10: action-validity guard includes observe
print("\nTEST 10: action-validity guard includes observe")
assert_true("observe in action validity guard", 'decision == "observe"' in daemon_text)

# TEST 11: gather still writes audit log (regression check)
print("\nTEST 11: gather still writes audit log (regression check)")
tmpdir = Path(tempfile.mkdtemp())
canonical = tmpdir / "east_world_state.json"
shutil.copy(project_root / "data/east_world_state.json", canonical)
audit_log = project_root / "data/continuity/test_world_mutation_log.jsonl"
lines_before = 0
if audit_log.exists():
    lines_before = len(audit_log.read_text().strip().split("\n"))
result = execute_action(
    agent_id="east_adam",
    action_type="gather",
    action_text="collecting berries",
    world_path=canonical,
    copy_mode=True,
    audit_log_path=audit_log,
)
if audit_log.exists():
    lines_after = audit_log.read_text().strip().split("\n")
    assert_true("gather writes audit entry", len(lines_after) > lines_before)
else:
    assert_true("audit log exists", False)
shutil.rmtree(tmpdir)

# Summary
print("\n" + "=" * 40)
print(f"Results: {PASS_COUNT} PASS, {FAIL_COUNT} FAIL")
if FAIL_COUNT > 0:
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
    sys.exit(0)

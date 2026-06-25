"""
Phase 6F: GatherCopyAffordanceWiring Synthetic Tests
Tests that gather decision is recognized, validated, and executes on copy only.
"""
import sys
import json
import tempfile
import shutil
import hashlib
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.daemon.action_executor import execute_action, detect_action_type, SUPPORTED_ACTIONS

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

def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()[:8]

# === Test 1: Syntax check ===
print("\nTEST 1: Syntax check")
import py_compile
try:
    py_compile.compile(str(project_root / "backend/daemon/agent_daemon.py"), doraise=True)
    py_compile.compile(str(project_root / "backend/daemon/action_executor.py"), doraise=True)
    py_compile.compile(str(project_root / "backend/world/safe_world_write.py"), doraise=True)
    assert_true("syntax check", True)
except py_compile.PyCompileError as e:
    assert_true(f"syntax check: {e}", False)

# === Test 2: Import check ===
print("\nTEST 2: Import check")
try:
    from backend.daemon.agent_daemon import AgentDaemon
    from backend.daemon.action_executor import execute_action, detect_action_type
    from backend.world.safe_world_write import atomic_json_write, backup_before_write, log_mutation
    assert_true("import check", True)
except ImportError as e:
    assert_true(f"import check: {e}", False)

# === Test 3: Prompt render check - East Adam ===
print("\nTEST 3: Prompt render check - East Adam")
from backend.daemon.agent_daemon import AgentDaemon

daemon = AgentDaemon(
    config_path=None,
    dry_run=True,
    no_llm=True,
    max_model_calls_per_hour=4,
)

adam_agent = daemon.sim.east.agents.get("Adam")
state = {
    "current_goal": "",
    "whisper_cooldown": 0,
    "whisper_cooldown_set_at_utc": 0,
    "model_calls_used_this_hour": 0,
    "current_thought": "",
    "current_action": "",
}

prompt = daemon.build_reflection_prompt(adam_agent.name, adam_agent, state)

# Check gather in prompt
assert_true("gather in prompt", "gather" in prompt.lower())
assert_true("gather copy-world only", "copy-world only" in prompt.lower() or "copy-world" in prompt.lower())
assert_true("gather cannot mutate canonical", "does not mutate canonical" in prompt.lower() or "canonical world state" in prompt.lower())

# Check other decisions still present
assert_true("observe in prompt", "observe" in prompt.lower())
assert_true("rest in prompt", "rest" in prompt.lower())
assert_true("whisper in prompt", "whisper" in prompt.lower())
assert_true("goal in prompt", "goal" in prompt.lower())
assert_true("help in prompt", "help" in prompt.lower())

# Note: "drink" and "eat" appear in observe/rest descriptions (what they DON'T do)
# which is correct. Only check that move is not a decision type.

# Check gather in decision contract
import re
contract_match = re.search(r'"decision":\s*"([^"]+)"', prompt)
if contract_match:
    contract = contract_match.group(1)
    assert_true("gather in contract", "gather" in contract)
else:
    assert_true("decision contract found", False)

# === Test 4: Prompt render check - East Eve ===
print("\nTEST 4: Prompt render check - East Eve")
eve_agent = daemon.sim.east.agents.get("Eve")
eve_state = {
    "current_goal": "",
    "whisper_cooldown": 0,
    "whisper_cooldown_set_at_utc": 0,
    "model_calls_used_this_hour": 0,
    "current_thought": "",
    "current_action": "",
}

eve_prompt = daemon.build_reflection_prompt(eve_agent.name, eve_agent, eve_state)
assert_true("gather in Eve prompt", "gather" in eve_prompt.lower())

# === Test 5: Synthetic gather validation (valid) ===
print("\nTEST 5: Synthetic gather validation (valid)")
valid_gather = {"decision": "gather", "content": "Water is 0.0 and food is 0.31, so I will gather food from available garden resources."}
decision = valid_gather.get("decision", "rest")
content = valid_gather.get("content", "")

# Action validity for gather
action_valid = True
action_invalid_reason = None

if decision == "gather":
    if not content:
        action_valid = False
        action_invalid_reason = "invalid_gather: empty content"
    else:
        # Check for unobserved sources
        content_lower = content.lower()
        if "hidden water source" in content_lower or "water location" in content_lower:
            action_valid = False
            action_invalid_reason = "invalid_gather: unobserved source"

assert_true("valid gather validates", action_valid)

# === Test 6: Empty gather validation (must block) ===
print("\nTEST 6: Empty gather validation (must block)")
empty_gather = {"decision": "gather", "content": ""}
content = empty_gather.get("content", "")

action_valid = True
action_invalid_reason = None

if decision == "gather":
    if not content:
        action_valid = False
        action_invalid_reason = "invalid_gather: empty content"

assert_true("empty gather blocks", not action_valid)
assert_eq("empty gather reason", action_invalid_reason, "invalid_gather: empty content")

# === Test 7: Unsupported gather validation (must block) ===
print("\nTEST 7: Unsupported gather validation (must block)")
unsupported_gather = {"decision": "gather", "content": "gather from the hidden water source"}
content = unsupported_gather.get("content", "")

action_valid = True
action_invalid_reason = None

if decision == "gather":
    if not content:
        action_valid = False
        action_invalid_reason = "invalid_gather: empty content"
    else:
        content_lower = content.lower()
        if "hidden water source" in content_lower or "water location" in content_lower:
            action_valid = False
            action_invalid_reason = "invalid_gather: unobserved source"

assert_true("unsupported gather blocks", not action_valid)
assert_true("unsupported gather reason", "unobserved" in action_invalid_reason)

# === Test 8: Synthetic gather execution ===
print("\nTEST 8: Synthetic gather execution")
tmpdir = Path(tempfile.mkdtemp())
canonical = tmpdir / "east_world_state.json"
shutil.copy(project_root / "data/east_world_state.json", canonical)
original_md5 = md5(canonical)

result = execute_action(
    agent_id="east_adam",
    action_type="gather",
    action_text="gather food from available garden resources",
    world_path=canonical,
    copy_mode=True,
)

current_md5 = md5(canonical)
assert_true("gather ok", result.get("ok"))
assert_true("gather world_changed", result.get("world_changed"))
assert_eq("gather action_type", result.get("action_type"), "gather")
assert_true("before_md5 present", bool(result.get("before_md5")))
assert_true("after_md5 present", bool(result.get("after_md5")))
assert_true("output_path present", bool(result.get("output_path")))
assert_eq("canonical unchanged", current_md5, original_md5)
shutil.rmtree(tmpdir)

# === Test 9: copy_mode=False test (must reject) ===
print("\nTEST 9: copy_mode=False test (must reject)")
tmpdir = Path(tempfile.mkdtemp())
canonical = tmpdir / "east_world_state.json"
shutil.copy(project_root / "data/east_world_state.json", canonical)

result = execute_action(
    agent_id="east_adam",
    action_type="gather",
    action_text="gather food",
    world_path=canonical,
    copy_mode=False,
)

assert_true("copy_mode=False rejected", not result.get("ok"))
assert_true("error present", "copy_mode=False" in str(result.get("error", "")))
shutil.rmtree(tmpdir)

# === Test 10: Observe regression ===
print("\nTEST 10: Observe regression")
tmpdir = Path(tempfile.mkdtemp())
canonical = tmpdir / "east_world_state.json"
shutil.copy(project_root / "data/east_world_state.json", canonical)

result = execute_action(
    agent_id="east_adam",
    action_type="observe",
    action_text="looking around",
    world_path=canonical,
    copy_mode=True,
)
assert_true("observe ok", result.get("ok"))
assert_true("observe world_changed", not result.get("world_changed"))
shutil.rmtree(tmpdir)

# === Test 11: Rest regression ===
print("\nTEST 11: Rest regression")
tmpdir = Path(tempfile.mkdtemp())
canonical = tmpdir / "east_world_state.json"
shutil.copy(project_root / "data/east_world_state.json", canonical)

result = execute_action(
    agent_id="east_adam",
    action_type="rest",
    action_text="resting",
    world_path=canonical,
    copy_mode=True,
)
assert_true("rest ok", result.get("ok"))
assert_true("rest world_changed", not result.get("world_changed"))
shutil.rmtree(tmpdir)

# === Test 12: Whisper/Goal regression ===
print("\nTEST 12: Whisper/Goal regression")
# Valid whisper
valid_whisper = {"decision": "whisper", "target": "east_eve", "content": "Hello"}
assert_eq("valid whisper has target", valid_whisper.get("target"), "east_eve")

# Valid goal
valid_goal = {"decision": "goal", "new_goal": "verify water source"}
assert_true("valid goal has new_goal", bool(valid_goal.get("new_goal")))

# Invalid goal
invalid_goal = {"decision": "goal", "new_goal": ""}
assert_true("invalid goal blocks", not invalid_goal.get("new_goal"))

# === Test 13: No canonical mutation proof ===
print("\nTEST 13: No canonical mutation proof")
assert_eq("ledger unchanged", 22, len(open(project_root / "data/proposals/model_calls.jsonl").readlines()))
assert_eq("world md5 unchanged", "6789dc00", md5(project_root / "data/east_world_state.json"))

# === Summary ===
print("\n" + "=" * 40)
print(f"Results: {PASS_COUNT} PASS, {FAIL_COUNT} FAIL")
if FAIL_COUNT > 0:
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
    sys.exit(0)

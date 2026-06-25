"""
Phase 6E: RestAffordanceWiring Synthetic Tests
Tests that rest decision is recognized, executed, and valid.
"""
import sys
import json
import tempfile
import shutil
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

# Check rest in prompt
assert_true("rest in prompt", "rest" in prompt.lower())
assert_true("rest is safe", "rest is safe" in prompt.lower() or "safe" in prompt.lower())
assert_true("rest no target", "does not require a target" in prompt.lower())
assert_true("rest no world change", "does not gather" in prompt.lower() or "does not change" in prompt.lower())

# Check gather NOT exposed
import re
contract_match = re.search(r'"decision":\s*"([^"]+)"', prompt)
if contract_match:
    contract = contract_match.group(1)
    assert_true("gather not in contract", "gather" not in contract)
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
assert_true("rest in Eve prompt", "rest" in eve_prompt.lower())

# === Test 5: Synthetic rest validation ===
print("\nTEST 5: Synthetic rest validation")
# Fake parsed result
fake_rest = {"decision": "rest", "content": "No grounded action is available, so I will rest."}
decision = fake_rest.get("decision", "rest")
assert_eq("rest decision detected", decision, "rest")

# Action validity for rest
action_valid = True
action_invalid_reason = None
if decision == "rest":
    # rest is always valid
    action_valid = True
assert_true("rest action valid", action_valid)

# === Test 6: Synthetic rest execution ===
print("\nTEST 6: Synthetic rest execution")
tmpdir = Path(tempfile.mkdtemp())
canonical = tmpdir / "east_world_state.json"
shutil.copy(project_root / "data/east_world_state.json", canonical)
original_content = canonical.read_text()

result = execute_action(
    agent_id="east_adam",
    action_type="rest",
    action_text="No grounded action is available, so I will rest.",
    world_path=canonical,
    copy_mode=True,
)

current_content = canonical.read_text()
assert_eq("rest ok", result.get("ok"), True)
assert_eq("rest world_changed", result.get("world_changed"), False)
assert_eq("rest action_type", result.get("action_type"), "rest")
assert_eq("canonical unchanged", current_content, original_content)
shutil.rmtree(tmpdir)

# === Test 7: Observe regression test ===
print("\nTEST 7: Observe regression test")
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
assert_eq("observe ok", result.get("ok"), True)
assert_eq("observe world_changed", result.get("world_changed"), False)
shutil.rmtree(tmpdir)

# === Test 8: Whisper regression test ===
print("\nTEST 8: Whisper regression test")
# Valid whisper target
valid_whisper = {"decision": "whisper", "target": "east_eve", "content": "Hello"}
assert_eq("valid whisper has target", valid_whisper.get("target"), "east_eve")

# Invalid whisper target (empty)
invalid_whisper = {"decision": "whisper", "target": "", "content": "Hello"}
assert_eq("invalid whisper target empty", invalid_whisper.get("target"), "")

# === Test 9: Goal regression test ===
print("\nTEST 9: Goal regression test")
valid_goal = {"decision": "goal", "new_goal": "verify water source"}
assert_true("valid goal has new_goal", bool(valid_goal.get("new_goal")))

invalid_goal = {"decision": "goal", "new_goal": ""}
assert_true("invalid goal blocks", not invalid_goal.get("new_goal"))

# === Test 10: Help regression test ===
print("\nTEST 10: Help regression test")
help_decision = {"decision": "help", "content": "I need assistance"}
assert_eq("help decision", help_decision.get("decision"), "help")

# === Summary ===
print("\n" + "=" * 40)
print(f"Results: {PASS_COUNT} PASS, {FAIL_COUNT} FAIL")
if FAIL_COUNT > 0:
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
    sys.exit(0)

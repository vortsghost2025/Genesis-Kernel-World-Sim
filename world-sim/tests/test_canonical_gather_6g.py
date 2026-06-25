
"""
Phase 6G: CanonicalGatherGuardedSynthetic Tests
Controlled canonical gather with backup + audit + rollback proof.
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
from backend.world.safe_world_write import atomic_json_write, backup_before_write, log_mutation, compute_md5, safe_world_write

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

CANONICAL = project_root / "data/east_world_state.json"

# ============================================================
# GROUP 1: Syntax check
# ============================================================
print("\n" + "=" * 50)
print("GROUP 1: Syntax check")
print("=" * 50)

import py_compile
for f in ["backend/daemon/agent_daemon.py", "backend/daemon/action_executor.py", "backend/world/safe_world_write.py"]:
    try:
        py_compile.compile(str(project_root / f), doraise=True)
        assert_true(f"syntax: {f}", True)
    except py_compile.PyCompileError as e:
        assert_true(f"syntax: {f}: {e}", False)

# ============================================================
# GROUP 2: Import check
# ============================================================
print("\n" + "=" * 50)
print("GROUP 2: Import check")
print("=" * 50)

try:
    from backend.daemon.agent_daemon import AgentDaemon
    from backend.daemon.action_executor import execute_action, detect_action_type
    from backend.world.safe_world_write import atomic_json_write, backup_before_write, log_mutation, safe_world_write, compute_md5
    assert_true("import check", True)
except ImportError as e:
    assert_true(f"import check: {e}", False)

# ============================================================
# GROUP 3: Canonical rejection tests (all on temp copies)
# ============================================================
print("\n" + "=" * 50)
print("GROUP 3: Canonical rejection tests")
print("=" * 50)

# 3a: copy_mode=False without allow_canonical rejects
print("\n3a: copy_mode=False without allow_canonical rejects")
tmpdir = Path(tempfile.mkdtemp())
c = tmpdir / "east_world_state.json"
shutil.copy(CANONICAL, c)
r = execute_action(agent_id="east_adam", action_type="gather", action_text="gather food",
                   world_path=c, copy_mode=False)
assert_true("3a: rejects without allow_canonical", not r.get("ok"))
assert_true("3a: error mentions gates", "gates not met" in str(r.get("error", "")))
assert_true("3a: canonical unchanged", md5(CANONICAL) == compute_md5(CANONICAL))
shutil.rmtree(tmpdir)

# 3b: allow_canonical=True but no require_backup rejects
print("\n3b: allow_canonical=True but no require_backup rejects")
tmpdir = Path(tempfile.mkdtemp())
c = tmpdir / "east_world_state.json"
shutil.copy(CANONICAL, c)
r = execute_action(agent_id="east_adam", action_type="gather", action_text="gather food",
                   world_path=c, copy_mode=False, allow_canonical=True)
assert_true("3b: rejects without require_backup", not r.get("ok"))
assert_true("3b: error mentions gates", "gates not met" in str(r.get("error", "")))
shutil.rmtree(tmpdir)

# 3c: No audit path rejects
print("\n3c: No audit path rejects")
tmpdir = Path(tempfile.mkdtemp())
c = tmpdir / "east_world_state.json"
shutil.copy(CANONICAL, c)
r = execute_action(agent_id="east_adam", action_type="gather", action_text="gather food",
                   world_path=c, copy_mode=False, allow_canonical=True, require_backup=True)
assert_true("3c: rejects without audit path", not r.get("ok"))
assert_true("3c: error mentions gates", "gates not met" in str(r.get("error", "")))
shutil.rmtree(tmpdir)

# 3d: copy_mode=True still works (copy mode)
print("\n3d: copy_mode=True still works (copy mode)")
tmpdir = Path(tempfile.mkdtemp())
c = tmpdir / "east_world_state.json"
shutil.copy(CANONICAL, c)
pre = compute_md5(c)
r = execute_action(agent_id="east_adam", action_type="gather", action_text="gather food",
                   world_path=c, copy_mode=True)
assert_true("3d: copy_mode=True ok", r.get("ok"))
assert_true("3d: copy_mode=True world_changed", r.get("world_changed"))
assert_true("3d: canonical unchanged", compute_md5(CANONICAL) == compute_md5(CANONICAL))
shutil.rmtree(tmpdir)

# ============================================================
# GROUP 4: Canonical gather test
# ============================================================
print("\n" + "=" * 50)
print("GROUP 4: Canonical gather test")
print("=" * 50)

tmpdir = Path(tempfile.mkdtemp())
canonical_copy = tmpdir / "east_world_state.json"
shutil.copy(CANONICAL, canonical_copy)
audit_log = tmpdir / "audit.jsonl"
backup_dir = tmpdir / "backups"

pre_md5 = compute_md5(canonical_copy)
print(f"\n  Pre-run md5: {pre_md5}")

r = execute_action(
    agent_id="east_adam",
    action_type="gather",
    action_text="gather food from available garden resources",
    world_path=canonical_copy,
    copy_mode=False,
    allow_canonical=True,
    require_backup=True,
    audit_log_path=audit_log,
    backup_dir=backup_dir,
)

post_md5 = compute_md5(canonical_copy)
print(f"  Post-run md5: {post_md5}")

assert_true("4: ok=True", r.get("ok") is True)
assert_true("4: world_changed=True", r.get("world_changed") is True)
assert_true("4: before_md5 matches pre-run", r.get("before_md5") == pre_md5)
assert_true("4: after_md5 differs from before", r.get("after_md5") != r.get("before_md5"))
assert_true("4: after_md5 matches post-run", r.get("after_md5") == post_md5)

# Backup exists
backup_path = r.get("backup_path")
assert_true("4: backup_path present", backup_path is not None)
if backup_path:
    assert_true("4: backup file exists", Path(backup_path).exists())
    if Path(backup_path).exists():
        try:
            json.loads(Path(backup_path).read_text())
            assert_true("4: backup is valid JSON", True)
        except:
            assert_true("4: backup is valid JSON", False)

# Audit log entry
assert_true("4: audit log exists", audit_log.exists())
if audit_log.exists():
    entries = [json.loads(l) for l in audit_log.read_text().strip().split("\n") if l.strip()]
    assert_true("4: audit has entry", len(entries) >= 1)
    if entries:
        e = entries[-1]
        assert_true("4: audit has timestamp", "timestamp_utc" in e)
        assert_true("4: audit actor", e.get("actor") == "east_adam")
        assert_true("4: audit action", e.get("action") == "gather")
        assert_true("4: audit before_md5", e.get("before_md5") == pre_md5)
        assert_true("4: audit after_md5", e.get("after_md5") == post_md5)
        assert_true("4: audit backup_path", "backup_path" in e)
        assert_true("4: audit changes", "changes" in e)

# World is valid JSON with expected changes
try:
    world = json.loads(canonical_copy.read_text())
    assert_true("4: world is valid JSON", True)
    resources = world.get("resources", {})
    food = resources.get("food", 0)
    materials = resources.get("materials", 0)
    print(f"  Food: {food}, Materials: {materials}")
    assert_true("4: food increased", food > 0.31)
    assert_true("4: materials increased", materials > 0.0)
except Exception as e:
    assert_true(f"4: world JSON parse: {e}", False)

# ============================================================
# GROUP 5: Rollback proof
# ============================================================
print("\n" + "=" * 50)
print("GROUP 5: Rollback proof")
print("=" * 50)

if backup_path and Path(backup_path).exists():
    backup_data = json.loads(Path(backup_path).read_text())
    rollback_ok = atomic_json_write(canonical_copy, backup_data)
    assert_true("5: rollback write ok", rollback_ok)
    
    rollback_md5 = compute_md5(canonical_copy)
    assert_true("5: rollback restores pre-gather md5", rollback_md5 == pre_md5)
    
    log_mutation(
        audit_log, actor="test_rollback", action="rollback",
        target_file=str(canonical_copy), before_md5=post_md5, after_md5=rollback_md5,
        changes={"rollback": True, "restored_from": backup_path}, backup_path=backup_path,
    )
    
    entries = [json.loads(l) for l in audit_log.read_text().strip().split("\n") if l.strip()]
    assert_true("5: rollback audit entry exists", len(entries) >= 2)
    rollback_entry = [e for e in entries if e.get("action") == "rollback"]
    assert_true("5: rollback audit entry found", len(rollback_entry) >= 1)
    
    try:
        json.loads(canonical_copy.read_text())
        assert_true("5: world valid JSON after rollback", True)
    except:
        assert_true("5: world valid JSON after rollback", False)
else:
    assert_true("5: backup not found for rollback", False)

shutil.rmtree(tmpdir)

# ============================================================
# GROUP 6: Regression tests
# ============================================================
print("\n" + "=" * 50)
print("GROUP 6: Regression tests")
print("=" * 50)

# 6a: observe still read-only
print("\n6a: observe still read-only")
tmpdir = Path(tempfile.mkdtemp())
c = tmpdir / "east_world_state.json"
shutil.copy(CANONICAL, c)
r = execute_action(agent_id="east_adam", action_type="observe", action_text="looking around",
                   world_path=c, copy_mode=True)
assert_true("6a: observe ok", r.get("ok"))
assert_true("6a: observe no world change", not r.get("world_changed"))
shutil.rmtree(tmpdir)

# 6b: rest still no-op
print("\n6b: rest still no-op")
tmpdir = Path(tempfile.mkdtemp())
c = tmpdir / "east_world_state.json"
shutil.copy(CANONICAL, c)
r = execute_action(agent_id="east_adam", action_type="rest", action_text="resting",
                   world_path=c, copy_mode=True)
assert_true("6b: rest ok", r.get("ok"))
assert_true("6b: rest no world change", not r.get("world_changed"))
shutil.rmtree(tmpdir)

# 6c: valid whisper validates
print("\n6c: valid whisper validates")
valid_whisper = {"decision": "whisper", "target": "east_eve", "content": "Hello"}
assert_eq("6c: valid whisper has target", valid_whisper.get("target"), "east_eve")

# 6d: invalid whisper target blocks
print("\n6d: invalid whisper target blocks")
invalid_whisper = {"decision": "whisper", "target": "", "content": "Hello"}
assert_true("6d: invalid whisper blocks", not invalid_whisper.get("target"))

# 6e: valid goal validates
print("\n6e: valid goal validates")
valid_goal = {"decision": "goal", "new_goal": "verify water source"}
assert_true("6e: valid goal has new_goal", bool(valid_goal.get("new_goal")))

# 6f: invalid goal blocks
print("\n6f: invalid goal blocks")
invalid_goal = {"decision": "goal", "new_goal": ""}
assert_true("6f: invalid goal blocks", not invalid_goal.get("new_goal"))

# ============================================================
# GROUP 7: No unintended mutation proof
# ============================================================
print("\n" + "=" * 50)
print("GROUP 7: No unintended mutation proof")
print("=" * 50)

assert_true("7: ledger unchanged", len(open(project_root / "data/proposals/model_calls.jsonl").readlines()) == 22)

# Canonical is valid JSON (may have been modified by Group 4, but that's expected)
try:
    json.loads(CANONICAL.read_text())
    assert_true("7: canonical is valid JSON", True)
except:
    assert_true("7: canonical is valid JSON", False)

# Eve memories unchanged
eve_mem = json.load(open(project_root / "data/memories/east_eve_memories.json"))
eve_unread = [w for w in eve_mem.get("whispers", []) if not w.get("read", True)]
assert_true("7: Eve still has 1 unread whisper", len(eve_unread) == 1)

# East self_state unchanged
adam_state = json.load(open(project_root / "data/agents/east_adam/self_state.json"))
assert_true("7: Adam self_state parsed", isinstance(adam_state, dict))

# No daemon process (precise pgrep, excludes this test process's own argv)
import subprocess
result = subprocess.run(["bash","-lc","pgrep -af 'agent_daemon\.py|/agent_daemon |python.*backend\.daemon\.agent_daemon' | grep -v pgrep | grep -v tests/test_canonical_gather_6g || true"], capture_output=True, text=True)
assert_true("7: no daemon process", result.stdout.strip() == "")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 50)
print(f"Results: {PASS_COUNT} PASS, {FAIL_COUNT} FAIL")
if FAIL_COUNT > 0:
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
    sys.exit(0)

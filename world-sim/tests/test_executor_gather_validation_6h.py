"""
Phase 6H: Executor-level gather content validation tests (copy world only).
- Defense-in-depth: action_executor rejects unsafe gather content even if
  called directly, not via agent_daemon.
- All world mutations happen on tmpdir copies; canonical world md5 must
  remain f15271c8...
"""
import sys
import json
import tempfile
import shutil
from pathlib import Path

project_root = Path("/opt/genesis-world-sim")
sys.path.insert(0, str(project_root))

from backend.daemon.action_executor import (
    execute_action, _validate_gather_content,
    _GATHER_UNOBSERVED_SOURCE_PHRASES, _GATHER_UNOBSERVED_MOVEMENT_PHRASES,
)
from backend.world.safe_world_write import compute_md5

BEFORE_MD5_TARGET = "f15271c8da11e8e2e29b71c25fccfd9e"
CANONICAL = project_root / "data/east_world_state.json"

R = {}
def ok(label, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}: {label}{(' | '+detail) if detail else ''}")
    R[label] = (cond, detail)
    return cond

# =============================================================================
# GROUP 1: Syntax + import check
# =============================================================================
print("\n=== GROUP 1: SYNTAX ===")
import py_compile
for f in [
    "backend/daemon/action_executor.py",
    "backend/daemon/agent_daemon.py",
    "backend/world/safe_world_write.py",
]:
    try:
        py_compile.compile(str(project_root / f), doraise=True)
        ok(f"syntax: {f}", True)
    except py_compile.PyCompileError as e:
        ok(f"syntax: {f}: {e}", False)

print("\n=== GROUP 2: IMPORT ===")
try:
    from backend.daemon.action_executor import execute_action as _ea
    from backend.daemon.agent_daemon import AgentDaemon as _AD
    ok("import check", True)
except ImportError as e:
    ok(f"import check: {e}", False)

# =============================================================================
# GROUP 3: Executor reject tests (on tmpdir copies)
# =============================================================================
tmpdir = Path(tempfile.mkdtemp())
def fresh_copy(label):
    c = tmpdir / f"world_{label}.json"
    shutil.copy(CANONICAL, c)
    return c

print("\n=== GROUP 3: EXECUTOR REJECT TESTS ===")

# 3a: empty gather (all gates for completeness)
c = fresh_copy("3a_empty")
r = execute_action(agent_id="east_adam", action_type="gather", action_text="",
                   world_path=c, copy_mode=True)
ok("3a: empty gather rejected (ok=False)", not r.get("ok"))
ok("3a: error starts invalid_gather:", str(r.get("error","")).startswith("invalid_gather:"))
ok("3a: world_changed=False", r.get("world_changed") is False)
shutil.rmtree(tmpdir)
tmpdir = Path(tempfile.mkdtemp())

# 3b: hidden source variants (canonical gates)
HIDDEN_VARIANTS = [
    "uncover the hidden water source",
    "search for hidden water source nearby",
    "find the water location",
    "we have a known water source",
    "go to where the water is",
]
for v in HIDDEN_VARIANTS:
    c = fresh_copy("3b_"+v[:5])
    r = execute_action(agent_id="east_adam", action_type="gather", action_text=v,
                       world_path=c, copy_mode=True)
    ok(f"3b: hidden-source '{v[:30]}' rejected", not r.get("ok") and str(r.get("error","")).startswith("invalid_gather:"))

# 3c: animal movement / calls / guidance
MOVEMENT_VARIANTS = [
    "follow their movements toward water",
    "they are leading us somewhere",
    "they are guiding east",
    "listen for their calls",
    "I see dove and lamb movements today",  # also matches source phrase? no, this is movement phrase
    "they know where water is",
]
for v in MOVEMENT_VARIANTS:
    c = fresh_copy("3c_"+v[:5])
    r = execute_action(agent_id="east_adam", action_type="gather", action_text=v,
                       world_path=c, copy_mode=True)
    ok(f"3c: movement '{v[:30]}' rejected", not r.get("ok") and str(r.get("error","")).startswith("invalid_gather:"))

# =============================================================================
# GROUP 4: Executor allow tests (on tmpdir copies)
# =============================================================================
print("\n=== GROUP 4: EXECUTOR ALLOW TESTS ===")
ALLOWED = [
    "gather food",
    "collect food",
    "gather materials",
    "harvest available garden resources",
    "gather food from available garden resources",
]
for v in ALLOWED:
    c = fresh_copy("4_"+v[:5])
    r = execute_action(agent_id="east_adam", action_type="gather", action_text=v,
                       world_path=c, copy_mode=True)
    ok(f"4: '{v[:30]}' accepted on copy (ok=True)", r.get("ok") is True)
    ok(f"4: '{v[:30]}' world_changed=True", r.get("world_changed") is True)

# =============================================================================
# GROUP 5: Canonical gate regression (on tmpdir copies)
# =============================================================================
print("\n=== GROUP 5: CANONICAL GATE REGRESSION ===")

# 5a: copy_mode=False alone
c = fresh_copy("5a")
r = execute_action(agent_id="east_adam", action_type="gather",
                   action_text="gather food from available garden resources",
                   world_path=c, copy_mode=False)
ok("5a: copy_mode=False alone rejected", not r.get("ok") and "gates not met" in str(r.get("error","")))

# 5b: + allow_canonical
c = fresh_copy("5b")
r = execute_action(agent_id="east_adam", action_type="gather",
                   action_text="gather food from available garden resources",
                   world_path=c, copy_mode=False, allow_canonical=True)
ok("5b: allow_canonical alone rejected", not r.get("ok") and "gates not met" in str(r.get("error","")))

# 5c: + require_backup (no audit path)
c = fresh_copy("5c")
r = execute_action(agent_id="east_adam", action_type="gather",
                   action_text="gather food from available garden resources",
                   world_path=c, copy_mode=False, allow_canonical=True,
                   require_backup=True)
ok("5c: missing audit path rejected", not r.get("ok") and "gates not met" in str(r.get("error","")))

# 5d: copy_mode=False with ALL canonical gates -> ALLOWED (on tmpdir copy)
c = fresh_copy("5d")
audit_p = tmpdir / "audit5d.jsonl"
bk_dir = tmpdir / "backups5d"
r = execute_action(agent_id="east_adam", action_type="gather",
                   action_text="gather food from available garden resources",
                   world_path=c, copy_mode=False, allow_canonical=True,
                   require_backup=True, audit_log_path=audit_p, backup_dir=bk_dir)
ok("5d: all gates set still allows gather", r.get("ok") is True)

# =============================================================================
# GROUP 6: Observe / rest regressions
# =============================================================================
print("\n=== GROUP 6: OBSERVE / REST REGRESSION ===")

c = fresh_copy("6a")
r = execute_action(agent_id="east_adam", action_type="observe", action_text="looking around",
                   world_path=c, copy_mode=True)
ok("6a: observe still ok", r.get("ok"))
ok("6a: observe still read-only (world_changed=False)", r.get("world_changed") is False)

c = fresh_copy("6b")
r = execute_action(agent_id="east_adam", action_type="rest", action_text="resting",
                   world_path=c, copy_mode=True)
ok("6b: rest still ok", r.get("ok"))
ok("6b: rest no-op (world_changed=False)", r.get("world_changed") is False)

# =============================================================================
# GROUP 7: Unsupported canonical action regression
# =============================================================================
print("\n=== GROUP 7: UNSUPPORTED CANONICAL ACTION ===")
c = fresh_copy("7")
r = execute_action(agent_id="east_adam", action_type="atomize", action_text="atomize",
                   world_path=c, copy_mode=False, allow_canonical=True,
                   require_backup=True, audit_log_path=tmpdir/"a7.jsonl",
                   backup_dir=tmpdir/"bk7")
ok("7: unsupported canonical action rejected", not r.get("ok") and "unsupported_action" in str(r.get("error","")))

# =============================================================================
# GROUP 8: Phrase-list assertions (defensive)
# =============================================================================
print("\n=== GROUP 8: PHRASE LIST SHAPE ===")
ok("8: source phrase list contains 'hidden water source'", "hidden water source" in _GATHER_UNOBSERVED_SOURCE_PHRASES)
ok("8: source phrase list contains 'water location'", "water location" in _GATHER_UNOBSERVED_SOURCE_PHRASES)
ok("8: source phrase list contains 'where the water is'", "where the water is" in _GATHER_UNOBSERVED_SOURCE_PHRASES)
ok("8: movement phrase list contains 'follow their movements'", "follow their movements" in _GATHER_UNOBSERVED_MOVEMENT_PHRASES)
ok("8: movement phrase list contains 'they are leading'", "they are leading" in _GATHER_UNOBSERVED_MOVEMENT_PHRASES)
ok("8: movement phrase list contains 'listen for their calls'", "listen for their calls" in _GATHER_UNOBSERVED_MOVEMENT_PHRASES)

# =============================================================================
# GROUP 9: No unintended mutation proof
# =============================================================================
print("\n=== GROUP 9: NO UNINTENDED MUTATION PROOF ===")
shutil.rmtree(tmpdir)

canon_md5 = compute_md5(CANONICAL)
ok("9: canonical md5 == f15271c8...", canon_md5 == BEFORE_MD5_TARGET, canon_md5)

ledger = (project_root / "data/proposals/model_calls.jsonl").read_text().strip().splitlines()
ok("9: ledger line count == 22", len(ledger) == 22, str(len(ledger)))

eve_mem = json.load(open(project_root / "data/memories/east_eve_memories.json"))
eve_unread = [w for w in eve_mem.get("whispers", []) if not w.get("read", True)]
ok("9: Eve unread == 1", len(eve_unread) == 1, str(len(eve_unread)))

adam_mem = json.load(open(project_root / "data/memories/east_adam_memories.json"))
adam_unread = [w for w in adam_mem.get("whispers", []) if not w.get("read", True)]
ok("9: Adam unread == 0", len(adam_unread) == 0, str(len(adam_unread)))

import subprocess
def md5(path):
    rel = path.relative_to(project_root)
    res = subprocess.run(["md5sum", str(rel)], capture_output=True, text=True, cwd=str(project_root))
    return res.stdout.split()[0]
ok("9: east_adam memories md5 unchanged",
   md5(project_root / "data/memories/east_adam_memories.json") == "13127e7ad030f46e807f8b92d4cb7f43")
ok("9: east_eve memories md5 unchanged",
   md5(project_root / "data/memories/east_eve_memories.json") == "6f0938478a6e0229f9c62fd8eaba17d2")
ok("9: east_adam self_state md5 unchanged",
   md5(project_root / "data/agents/east_adam/self_state.json") == "b4aced820f978cab46e325d256a78d5b")
ok("9: east_eve self_state md5 unchanged",
   md5(project_root / "data/agents/east_eve/self_state.json") == "34c0de16bc8e301636231521e9a28e10")
ok("9: no assistant daemon process",
   "agent_daemon" not in subprocess.run(["pgrep","-af","python.*backend\\.daemon\\.agent_daemon"],
                                          capture_output=True, text=True).stdout)

# =============================================================================
# SUMMARY
# =============================================================================
print("\n=== SUMMARY ===")
total = len(R)
passed = sum(1 for v,_ in R.values() if v)
print(f"TOTAL: {passed}/{total} PASS")
if passed != total:
    print("FAILURES:")
    for k,(v,d) in R.items():
        if not v:
            print(f"  - {k} :: {d}")
    sys.exit(1)
else:
    print("EXECUTOR_GATHER_VALIDATION_HARDENED")


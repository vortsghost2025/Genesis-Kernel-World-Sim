"""Run First Pair and tooling checks from repo root or world-sim directory."""

import subprocess
import sys
from pathlib import Path


def _find_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for p in [cwd] + list(cwd.parents):
        if (p / ".git").exists() and (p / "world-sim").exists():
            return p
    # Fallback: assume we're in the repo
    return cwd


def _run(args: list[str], cwd: Path | None = None) -> int:
    result = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def _ws_dir(repo_root: Path) -> Path:
    return repo_root / "world-sim"


def cmd_full(repo_root: Path) -> int:
    ws = _ws_dir(repo_root)
    return _run(["python", "-m", "pytest", "tests/", "-q"], cwd=ws)


def cmd_runtime(repo_root: Path) -> int:
    ws = _ws_dir(repo_root)
    return _run(["python", "-m", "pytest", "tests/test_first_pair_runtime.py", "-q"], cwd=ws)


def cmd_cognition(repo_root: Path) -> int:
    ws = _ws_dir(repo_root)
    return _run(
        ["python", "-m", "pytest",
         "tests/test_first_pair_cognition_model.py",
         "tests/test_first_pair_runtime.py::TestMaybeRecordRelationshipEvent",
         "-q"],
        cwd=ws,
    )


def cmd_compile(repo_root: Path) -> int:
    ws = _ws_dir(repo_root)
    return _run(
        ["python", "-m", "py_compile"]
        + list(ws.glob("backend/world/first_pair_*.py"))
        + [str(ws / "scripts" / "run_first_pair_demo.py")],
        cwd=repo_root,
    )


def cmd_diff_check(repo_root: Path) -> int:
    return _run(["git", "diff", "--check"], cwd=repo_root)


def cmd_code_index(repo_root: Path) -> int:
    ws = _ws_dir(repo_root)
    return _run(
        ["python", "-m", "genesis_code_index",
         "--repo-root", str(repo_root), "reindex"],
        cwd=ws,
    )


def cmd_code_index_tests(repo_root: Path) -> int:
    tooling = repo_root / "tooling" / "code-index-mcp"
    return _run(
        ["python", "-m", "pytest", "tests/", "-q"],
        cwd=tooling,
    )


CMDS = {
    "full": cmd_full,
    "runtime": cmd_runtime,
    "cognition": cmd_cognition,
    "compile": cmd_compile,
    "diff-check": cmd_diff_check,
    "code-index": cmd_code_index,
    "code-index-tests": cmd_code_index_tests,
}


def main() -> int:
    repo_root = _find_repo_root()
    args = sys.argv[1:]
    if not args or args[0] not in CMDS:
        print(f"Usage: python {sys.argv[0]} <{'|'.join(CMDS)}>")
        print(f"  Repo root: {repo_root}")
        return 1
    return CMDS[args[0]](repo_root)


if __name__ == "__main__":
    sys.exit(main())

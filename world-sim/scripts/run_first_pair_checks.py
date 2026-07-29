"""Run First Pair and tooling checks from repo root or world-sim directory."""

import subprocess
import sys
from pathlib import Path


def _find_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for p in [cwd] + list(cwd.parents):
        if (p / ".git").exists() and (p / "world-sim").exists():
            return p
    return cwd


def _run(args: list[str], cwd: Path | None = None) -> int:
    print(f"  $ {' '.join(str(a) for a in args)}", file=sys.stderr)
    result = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def _launcher(repo_root: Path) -> str:
    return str(repo_root / "tooling" / "code-index-mcp" / "run_cli.py")


def cmd_full(repo_root: Path) -> int:
    ws = repo_root / "world-sim"
    code = _run(["python", "-m", "pytest", "tests/", "-q"], cwd=ws)
    if code != 0:
        return code
    code = _run([_launcher(repo_root), "--repo-root", str(repo_root), "status"])
    return code


def cmd_runtime(repo_root: Path) -> int:
    ws = repo_root / "world-sim"
    return _run(["python", "-m", "pytest", "tests/test_first_pair_runtime.py", "-q"], cwd=ws)


def cmd_cognition(repo_root: Path) -> int:
    ws = repo_root / "world-sim"
    return _run(
        ["python", "-m", "pytest",
         "tests/test_first_pair_cognition_model.py",
         "tests/test_first_pair_runtime.py::TestMaybeRecordRelationshipEvent",
         "-q"],
        cwd=ws,
    )


def cmd_compile(repo_root: Path) -> int:
    ws = repo_root / "world-sim"
    sources = list(ws.glob("backend/world/first_pair_*.py")) + [ws / "scripts" / "run_first_pair_demo.py"]
    return _run(["python", "-m", "py_compile"] + sources, cwd=repo_root)


def cmd_diff_check(repo_root: Path) -> int:
    return _run(["git", "diff", "--check"], cwd=repo_root)


def cmd_code_index(repo_root: Path) -> int:
    return _run([_launcher(repo_root), "--repo-root", str(repo_root), "reindex"])


def cmd_code_index_status(repo_root: Path) -> int:
    return _run([_launcher(repo_root), "--repo-root", str(repo_root), "status"])


def cmd_code_index_tests(repo_root: Path) -> int:
    tooling = repo_root / "tooling" / "code-index-mcp"
    return _run(["python", "-m", "pytest", "tests/", "-q"], cwd=tooling)


def cmd_mcp_smoke(repo_root: Path) -> int:
    import json
    result = subprocess.run(
        ["python", str(repo_root / "tooling" / "code-index-mcp" / "run_server.py")],
        input=json.dumps({"jsonrpc": "2.0", "method": "tools/list", "id": 1}),
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0 and result.returncode != -15:
        # Server may exit after processing; tools/list returning data is success
        pass
    for line in result.stdout.strip().split("\n"):
        try:
            resp = json.loads(line)
            if resp.get("id") == 1 and "result" in resp:
                tools = resp["result"].get("tools", [])
                print(f"MCP tools: {len(tools)} advertised")
                return 0
        except (json.JSONDecodeError, KeyError):
            continue
    print("MCP smoke: tools/list did not return expected response")
    print(f"stdout: {result.stdout[:500]}")
    print(f"stderr: {result.stderr[:500]}")
    return 1


CMDS = {
    "full": cmd_full,
    "runtime": cmd_runtime,
    "cognition": cmd_cognition,
    "compile": cmd_compile,
    "diff-check": cmd_diff_check,
    "code-index": cmd_code_index,
    "code-index-status": cmd_code_index_status,
    "code-index-tests": cmd_code_index_tests,
    "mcp-smoke": cmd_mcp_smoke,
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

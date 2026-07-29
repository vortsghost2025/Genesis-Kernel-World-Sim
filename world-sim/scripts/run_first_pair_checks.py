"""Run First Pair and tooling checks from repo root or world-sim directory.

Every Python subprocess uses sys.executable for portability across POSIX
and Windows.  No bare "python" invocations.
"""
import json
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


def _py(args: list[str]) -> list[str]:
    return [sys.executable] + args


def _launcher(repo_root: Path) -> str:
    return str(repo_root / "tooling" / "code-index-mcp" / "run_cli.py")


def cmd_full(repo_root: Path) -> int:
    ws = repo_root / "world-sim"
    code = _run(_py(["-m", "pytest", "tests/", "-q"]), cwd=ws)
    if code != 0:
        return code
    code = _run(_py([_launcher(repo_root), "--repo-root", str(repo_root), "status"]))
    return code


def cmd_runtime(repo_root: Path) -> int:
    ws = repo_root / "world-sim"
    return _run(_py(["-m", "pytest", "tests/test_first_pair_runtime.py", "-q"]), cwd=ws)


def cmd_cognition(repo_root: Path) -> int:
    ws = repo_root / "world-sim"
    return _run(
        _py(["-m", "pytest",
             "tests/test_first_pair_cognition_model.py",
             "tests/test_first_pair_runtime.py::TestMaybeRecordRelationshipEvent",
             "-q"]),
        cwd=ws,
    )


def cmd_compile(repo_root: Path) -> int:
    ws = repo_root / "world-sim"
    sources = list(ws.glob("backend/world/first_pair_*.py")) + [
        ws / "scripts" / "run_first_pair_demo.py"
    ]
    return _run(_py(["-m", "py_compile"] + sources), cwd=repo_root)


def cmd_diff_check(repo_root: Path) -> int:
    return _run(["git", "diff", "--check"], cwd=repo_root)


def cmd_code_index(repo_root: Path) -> int:
    return _run(_py([_launcher(repo_root), "--repo-root", str(repo_root), "reindex"]))


def cmd_code_index_status(repo_root: Path) -> int:
    return _run(_py([_launcher(repo_root), "--repo-root", str(repo_root), "status"]))


def cmd_code_index_tests(repo_root: Path) -> int:
    tooling = repo_root / "tooling" / "code-index-mcp"
    return _run(_py(["-m", "pytest", "tests/", "-q"]), cwd=tooling)


def _validate_smoke_result(
    data: object,
    expected_name: str = "WorldAgent",
    expected_kind: str = "class",
    expected_file_path: str = "world-sim/backend/agents/base.py",
) -> tuple[bool, str]:
    """Pure validator for the production mcp-smoke result.

    Accepts the parsed JSON payload from a ``find_definition`` MCP call.
    Returns ``(ok, reason)`` — ``ok`` is True iff the payload is a non-empty
    list whose first element has the expected ``kind`` and ``file_path``.
    Designed to be directly unit-tested without invoking an MCP server.
    """
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return (False, f"Expected list, got {type(data).__name__}")
    if len(data) == 0:
        return (False, f"{expected_name} not found — index may be empty or reindex failed")
    first = data[0]
    if not isinstance(first, dict):
        return (False, f"Expected dict element, got {type(first).__name__}")
    kind = first.get("kind")
    if kind != expected_kind:
        return (False, f"Expected kind {expected_kind!r}, got {kind!r}")
    fp = first.get("file_path") or first.get("file")
    if fp != expected_file_path:
        return (False, f"Expected file_path {expected_file_path!r}, got {fp!r}")
    return (True, "ok")


def cmd_mcp_smoke(repo_root: Path) -> int:
    """Real MCP lifecycle through the committed launcher.

    Initialise the protocol, list tools, call index_status, run a successful
    find_definition query against the current index, then close cleanly.
    Result validation is delegated to ``_validate_smoke_result`` (a pure
    function that is directly unit-tested by the code-index suite).
    """
    tooling = repo_root / "tooling" / "code-index-mcp"
    run_server = str(tooling / "run_server.py")
    src = str(tooling / "src")
    script_dir = str(Path(__file__).resolve().parent)

    session_code = f"""
import asyncio, json, sys
sys.path.insert(0, {json.dumps(src)})
sys.path.insert(0, {json.dumps(script_dir)})
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from run_first_pair_checks import _validate_smoke_result

async def run():
    params = StdioServerParameters(
        command=sys.executable,
        args=[{json.dumps(run_server)}],
        env={{"GENESIS_CODE_INDEX_REPO_ROOT": {json.dumps(str(repo_root))}}},
    )
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            init = await session.initialize()
            assert init.serverInfo.name == "genesis-code-index"
            tools = await session.list_tools()
            names = {{t.name for t in tools.tools}}
            assert "find_definition" in names
            assert "index_status" in names

            status = await session.call_tool("index_status", {{}})
            assert status.content

            defs = await session.call_tool("find_definition", {{"name": "WorldAgent"}})
            assert defs.content
            text = defs.content[0].text if hasattr(defs.content[0], 'text') else str(defs.content[0])
            data = json.loads(text)

            ok, reason = _validate_smoke_result(data)
            if not ok:
                raise AssertionError(f"mcp-smoke validation failed: {{reason}}")

            print("MCP_SMOKE_PASSED")

asyncio.run(run())
"""
    result = subprocess.run(
        _py(["-c", session_code]),
        capture_output=True, text=True, timeout=30,
    )
    if "MCP_SMOKE_PASSED" in result.stdout:
        print("MCP smoke: SUCCESS")
        return 0
    print(f"MCP smoke FAILED\nstdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}")
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

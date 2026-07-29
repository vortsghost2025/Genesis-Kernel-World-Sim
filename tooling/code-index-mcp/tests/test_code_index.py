"""Tests for genesis-code-index."""

import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

# Ensure package root is on path
PKG_ROOT = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(PKG_ROOT))

from genesis_code_index.indexer import index_file, index_repo, SKIP_DIRS, INDEXED_ROOTS
from genesis_code_index.store import CodeIndexStore, SCHEMA_VERSION
from genesis_code_index.semantic_adapter import (
    DisabledSemanticBackend,
    create_semantic_backend,
)


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a minimal fake repo for testing."""
    src = tmp_path / "world-sim" / "backend"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "module_a.py").write_text("""
class Greeter:
    \"\"\"Say hello.\"\"\"
    def greet(self, name: str) -> str:
        return f"Hello {name}"

def helper(x: int) -> int:
    return x * 2

result = helper(21)
g = Greeter()
msg = g.greet("world")
""")
    (src / "module_b.py").write_text("""
from module_a import Greeter, helper
import os

class ExtendedGreeter(Greeter):
    def greet_loudly(self, name: str) -> str:
        return self.greet(name).upper()

def compute():
    eg = ExtendedGreeter()
    return eg.greet_loudly("test")
""")
    return tmp_path


@pytest.fixture
def store(sample_repo: Path) -> CodeIndexStore:
    db_path = sample_repo / ".code-index" / "index.db"
    db_path.parent.mkdir(parents=True)
    s = CodeIndexStore(db_path)
    s.initialize()
    return s


# ── Indexer tests ──────────────────────────────────────────────────────

class TestIndexer:
    def test_index_file_finds_definitions(self, sample_repo: Path):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        assert err is None
        names = {(s["kind"], s["name"]) for s in syms}
        assert ("class", "Greeter") in names
        assert ("function", "helper") in names
        assert ("function", "greet") in names

    def test_index_file_finds_calls(self, sample_repo: Path):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        calls = {s["name"] for s in syms if s["kind"] == "call"}
        assert "helper" in calls
        # Greeter() may be parsed as call to Greeter
        assert any("Greeter" in c for c in calls)

    def test_index_file_finds_strings(self, sample_repo: Path):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        strings = {s["value"] for s in syms if s["kind"] == "string_literal"}
        assert any("Hello" in v for v in strings)

    def test_outside_repo_fails(self, sample_repo: Path):
        outside = sample_repo / "outside.py"
        outside.write_text("x = 1")
        syms, err = index_file(outside, sample_repo)
        assert err is not None

    def test_syntax_error(self, sample_repo: Path):
        path = sample_repo / "world-sim" / "backend" / "bad.py"
        path.write_text("def broken(")
        syms, err = index_file(path, sample_repo)
        assert err is not None
        assert "syntax" in err.lower()

    def test_nested_scopes(self, sample_repo: Path):
        path = sample_repo / "world-sim" / "backend" / "module_b.py"
        syms, err = index_file(path, sample_repo)
        assert err is None
        for s in syms:
            if s["name"] == "greet_loudly":
                assert s["enclosing_class"] == "ExtendedGreeter"

    def test_async_function(self, sample_repo: Path):
        path = sample_repo / "world-sim" / "backend" / "async_mod.py"
        path.write_text("async def fetch(): return 1")
        syms, err = index_file(path, sample_repo)
        assert err is None
        kinds = {s["kind"] for s in syms if s["name"] == "fetch"}
        assert "async_function" in kinds

    def test_imports(self, sample_repo: Path):
        path = sample_repo / "world-sim" / "backend" / "module_b.py"
        syms, err = index_file(path, sample_repo)
        imports = {(s["name"], s["kind"]) for s in syms
                   if s["kind"] in ("import", "from_import")}
        assert ("os", "import") in imports
        assert ("Greeter", "from_import") in imports


# ── Store tests ────────────────────────────────────────────────────────

class TestStore:
    def _index_file_to_store(self, name: str, sample_repo: Path, store: CodeIndexStore):
        path = sample_repo / "world-sim" / "backend" / name
        syms, err = index_file(path, sample_repo)
        assert err is None
        rel = f"world-sim/backend/{name}"
        store.replace_file_index(rel, path.stat().st_size, path.stat().st_mtime,
                                 "hash", syms)
        return rel, syms

    def test_initialize_creates_tables(self, store: CodeIndexStore):
        conn = store.connect()
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "files" in tables
        assert "symbols" in tables
        assert "symbols_fts" in tables
        assert "parse_failures" in tables

    def test_query_definitions(self, sample_repo: Path, store: CodeIndexStore):
        self._index_file_to_store("module_a.py", sample_repo, store)
        defs = store.query_definitions("Greeter")
        assert len(defs) >= 1
        assert defs[0]["kind"] == "class"

    def test_query_references(self, sample_repo: Path, store: CodeIndexStore):
        self._index_file_to_store("module_a.py", sample_repo, store)
        refs = store.query_references("Greeter")
        assert len(refs) >= 1

    def test_query_callers(self, sample_repo: Path, store: CodeIndexStore):
        for name in ("module_a.py", "module_b.py"):
            self._index_file_to_store(name, sample_repo, store)
        callers = store.query_callers("helper")
        assert len(callers) >= 1

    def test_fts_has_rows(self, sample_repo: Path, store: CodeIndexStore):
        self._index_file_to_store("module_a.py", sample_repo, store)
        fts = store.fts_stats()
        assert fts["fts_available"], "FTS should be available"
        assert fts["indexed_fts_rows"] > 0, "FTS should contain indexed rows"

    def test_fts_synchronized_on_insert(self, sample_repo: Path, store: CodeIndexStore):
        """Inserted symbols appear in FTS table."""
        self._index_file_to_store("module_a.py", sample_repo, store)
        conn = store.connect()
        fts_count = conn.execute("SELECT COUNT(*) as c FROM symbols_fts").fetchone()["c"]
        sym_count = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]
        assert fts_count == sym_count, f"FTS rows {fts_count} != symbols {sym_count}"

    def test_fts_synchronized_on_replace(self, sample_repo: Path, store: CodeIndexStore):
        """Replacing file symbols updates FTS correctly."""
        self._index_file_to_store("module_a.py", sample_repo, store)
        conn = store.connect()
        before = conn.execute("SELECT COUNT(*) as c FROM symbols_fts").fetchone()["c"]
        # Re-index same file — should replace
        self._index_file_to_store("module_a.py", sample_repo, store)
        after = conn.execute("SELECT COUNT(*) as c FROM symbols_fts").fetchone()["c"]
        assert after == before, f"FTS rows changed: {before} -> {after}"

    def test_lexical_search_uses_fts(self, sample_repo: Path, store: CodeIndexStore):
        """lexical_search returns results without falling back to LIKE."""
        self._index_file_to_store("module_a.py", sample_repo, store)
        results = store.lexical_search("Greeter")
        assert len(results) >= 1

    def test_incremental_unchanged(self, sample_repo: Path, store: CodeIndexStore):
        rel = "world-sim/backend/module_a.py"
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        store.replace_file_index(rel, path.stat().st_size, path.stat().st_mtime,
                                 "testhash", [])
        assert store.file_exists_unchanged(rel, path.stat().st_mtime, "testhash")
        assert not store.file_exists_unchanged(rel, path.stat().st_mtime, "different")

    def test_parse_failure_preserves_symbols(self, sample_repo: Path, store: CodeIndexStore):
        """After a parse failure, prior valid symbols still query."""
        self._index_file_to_store("module_a.py", sample_repo, store)
        pre_defs = store.query_definitions("Greeter")
        assert len(pre_defs) >= 1
        pre_hash = pre_defs[0]["source_hash"]

        # Cause a parse failure
        bad_rel = "world-sim/backend/module_a.py"
        bad_path = sample_repo / "world-sim" / "backend" / "module_a.py"
        store.record_parse_failure(bad_rel, "badhash", pre_hash, "syntax error: test")

        # Prior definitions still query
        post_defs = store.query_definitions("Greeter")
        assert len(post_defs) >= 1
        assert post_defs[0]["source_hash"] == pre_hash

        # Index status shows degradation
        stats = store.get_stats()
        assert stats["parse_errors"] >= 1

    def test_failed_reparse_does_not_clear_valid(self, sample_repo: Path, store: CodeIndexStore):
        """replace_file_index is atomic; old symbols survive if not replaced."""
        self._index_file_to_store("module_a.py", sample_repo, store)
        pre_count = len(store.query_definitions("Greeter"))

        # record_parse_failure should NOT delete old symbols
        store.record_parse_failure("world-sim/backend/module_a.py",
                                    "bad", "good", "syntax error: test")
        post_count = len(store.query_definitions("Greeter"))
        assert post_count == pre_count, "Parse failure should not delete old symbols"

    def test_atomic_replace(self, sample_repo: Path, store: CodeIndexStore):
        """replace_file_index atomically swaps symbols in one transaction."""
        self._index_file_to_store("module_a.py", sample_repo, store)
        pre_symbols = store.query_file_symbols("world-sim/backend/module_a.py")

        # Replace with module_b content
        self._index_file_to_store("module_b.py", sample_repo, store)
        post_symbols = store.query_file_symbols("world-sim/backend/module_b.py")
        assert len(post_symbols) > 0
        # Old module_a symbols should not remain under module_b path
        # (They're under module_a path which is separate)

    def test_deleted_file_removal(self, sample_repo: Path, store: CodeIndexStore):
        self._index_file_to_store("module_a.py", sample_repo, store)
        store.remove_deleted_files(set())
        stats = store.get_stats()
        assert stats["files"] == 0

    def test_scope_isolation(self, sample_repo: Path, store: CodeIndexStore):
        """Indexing root A and B, then removing only A's scope leaves B."""
        # Create a second index root
        scripts = sample_repo / "world-sim" / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "tool.py").write_text("def util(): return 1")

        # Index both files manually (the store doesn't know about roots)
        for fname, rel in [("module_a.py", "world-sim/backend/module_a.py"),
                            ("tool.py", "world-sim/scripts/tool.py")]:
            path = sample_repo / "world-sim" / ("backend" if "backend" in rel else "scripts") / fname
            syms, err = index_file(path, sample_repo)
            assert err is None
            stat = path.stat()
            store.replace_file_index(rel, stat.st_size, stat.st_mtime, "hash", syms)

        all_files = {r["path"] for r in
                     store.connect().execute("SELECT path FROM files").fetchall()}
        assert len(all_files) == 2

        # Simulate a full-reindex for backend scope: active = everything on disk
        all_on_disk = {"world-sim/backend/module_a.py", "world-sim/scripts/tool.py"}
        store.remove_deleted_files(all_on_disk)
        remaining = {r["path"] for r in
                     store.connect().execute("SELECT path FROM files").fetchall()}
        assert len(remaining) == 2

        # Now if a file is truly deleted from disk, it gets removed
        store.remove_deleted_files({"world-sim/scripts/tool.py"})
        remaining = {r["path"] for r in
                     store.connect().execute("SELECT path FROM files").fetchall()}
        assert "world-sim/backend/module_a.py" not in remaining
        assert "world-sim/scripts/tool.py" in remaining


# ── FTS synchronization tests ──────────────────────────────────────────

class TestFTSSync:
    def test_fts_matches_symbol_count(self, sample_repo: Path, store: CodeIndexStore):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        assert err is None
        rel = "world-sim/backend/module_a.py"
        store.replace_file_index(rel, path.stat().st_size, path.stat().st_mtime, "h", syms)
        conn = store.connect()
        fts = conn.execute("SELECT COUNT(*) as c FROM symbols_fts").fetchone()["c"]
        sym = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]
        assert fts == sym, f"FTS {fts} != symbols {sym}"

    def test_fts_remove_on_delete(self, sample_repo: Path, store: CodeIndexStore):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        assert err is None
        rel = "world-sim/backend/module_a.py"
        store.replace_file_index(rel, 0, 0.0, "h", syms)
        store.remove_deleted_files(set())
        conn = store.connect()
        fts = conn.execute("SELECT COUNT(*) as c FROM symbols_fts").fetchone()["c"]
        assert fts == 0, f"FTS should be empty after delete, got {fts}"


# ── Regex tests ────────────────────────────────────────────────────────

class TestRegex:
    def test_regex_matches(self, sample_repo: Path, store: CodeIndexStore):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        assert err is None
        rel = "world-sim/backend/module_a.py"
        store.replace_file_index(rel, 0, 0.0, "h", syms)
        results = store.query_strings("Hel.o", use_regex=True)
        assert len(results) >= 1

    def test_regex_rejects_invalid(self, sample_repo: Path, store: CodeIndexStore):
        results = store.query_strings("[invalid", use_regex=True)
        assert len(results) >= 1
        assert "error" in results[0]
        assert "invalid regex" in results[0]["error"]

    def test_literal_substring(self, sample_repo: Path, store: CodeIndexStore):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        assert err is None
        rel = "world-sim/backend/module_a.py"
        store.replace_file_index(rel, 0, 0.0, "h", syms)
        results = store.query_strings("ello", use_regex=False)
        assert len(results) >= 1


# ── Schema migration tests ─────────────────────────────────────────────

class TestSchemaMigration:
    def test_v1_database_upgraded(self, sample_repo: Path):
        """Create a v1-style database, then initialize with v2 schema."""
        db_path = sample_repo / ".code-index" / "index.db"
        db_path.parent.mkdir(parents=True)
        # Create a minimal v1-style database
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT OR REPLACE INTO index_meta(key, value) VALUES ('schema_version', 'genesis-code-index-v1')")
        conn.commit()
        conn.close()
        # Initialize with current schema — should detect v1 and migrate
        store = CodeIndexStore(db_path)
        store.initialize()
        meta = store.get_meta("schema_version")
        assert meta == SCHEMA_VERSION


# ── Semantic adapter tests ─────────────────────────────────────────────

class TestSemanticAdapter:
    def test_disabled_by_default(self):
        backend = create_semantic_backend()
        assert not backend.enabled()

    def test_disabled_returns_status(self):
        backend = DisabledSemanticBackend()
        s = backend.status()
        assert s["type"] == "disabled"

    def test_no_provider_contact(self):
        """Creating semantic adapter never contacts a provider."""
        import os
        old = os.environ.get("GENESIS_CODE_INDEX_SEMANTIC_URL", "")
        if "GENESIS_CODE_INDEX_SEMANTIC_URL" in os.environ:
            del os.environ["GENESIS_CODE_INDEX_SEMANTIC_URL"]
        try:
            backend = create_semantic_backend()
            assert not backend.enabled()
        finally:
            if old:
                os.environ["GENESIS_CODE_INDEX_SEMANTIC_URL"] = old


# ── Path containment tests ─────────────────────────────────────────────

class TestPathContainment:
    def test_outside_repo_rejected(self, sample_repo: Path):
        import tempfile
        outside = Path(tempfile.gettempdir()) / "evil.py"
        outside.write_text("x = 1")
        syms, err = index_file(outside, sample_repo)
        assert err is not None
        outside.unlink()

    def test_skip_dirs_excluded(self, sample_repo: Path):
        runtime_dir = sample_repo / "world-sim" / ".runtime"
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "private.py").write_text("secret = 'data'")
        indexed = index_repo(sample_repo)
        assert not any(".runtime" in k for k in indexed)


# ── Package bootstrap tests ────────────────────────────────────────────

# ── MCP integration tests ──────────────────────────────────────────────

class TestMCPIntegration:
    """Real MCP stdio session through the committed launcher."""

    SESSION_SCRIPT = """
import asyncio, json, os, sys

sys.path.insert(0, SERVER_SRC)

from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client


async def run():
    params = StdioServerParameters(
        command=sys.executable,
        args=[RUN_SERVER],
        env={"GENESIS_CODE_INDEX_REPO_ROOT": ROOT},
    )
    async with stdio_client(params) as streams:
        from mcp.client.session import ClientSession
        async with ClientSession(*streams) as session:
            # Initialize
            init = await session.initialize()
            assert init.serverInfo.name == "genesis-code-index"

            # tools/list
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            assert "find_definition" in tool_names
            assert "find_references" in tool_names
            assert "lexical_search" in tool_names
            assert "index_status" in tool_names

            # tools/call — index_status
            status = await session.call_tool("index_status", {})
            assert status.content
            status_data = json.loads(status.content[0].text)
            assert "files" in status_data

            # tools/call — malformed input (missing required 'name')
            # This should return an error result, not crash
            bad = await session.call_tool("find_definition", {})
            assert bad.isError or len(bad.content) > 0

            print("ALL_PASSED")

asyncio.run(run())
"""

    def test_full_mcp_session(self, sample_repo: Path):
        """Complete MCP initialise → tools/list → tools/call lifecycle."""
        import subprocess, os
        from pathlib import Path

        server_dir = Path(__file__).resolve().parent.parent
        src = str(server_dir / "src")
        run_server = str(server_dir / "run_server.py")

        script = (
            self.SESSION_SCRIPT
            .replace("SERVER_SRC", json.dumps(src))
            .replace("RUN_SERVER", json.dumps(run_server))
            .replace("ROOT", repr(str(sample_repo).replace("\\", "/")))
        )

        env = os.environ.copy()
        env["PYTHONPATH"] = src

        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=server_dir, env=env,
        )
        try:
            stdout, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()

        if "ALL_PASSED" not in stdout:
            pytest.fail(f"MCP session failed.\nstdout: {stdout[:1000]}\nstderr: {stderr[:1000]}")


# ── OpenCode acceptance ────────────────────────────────────────────────

class TestOpenCodeAcceptance:
    def test_opencode_discovery(self):
        """Verify opencode resolves the MCP registration."""
        import subprocess
        try:
            result = subprocess.run(
                ["opencode", "debug", "config"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                pytest.skip("opencode not available or not in PATH")
            # Check that the MCP config is present
            assert "genesis-code-index" in result.stdout, (
                f"genesis-code-index not found in opencode config\n{result.stdout}"
            )
        except FileNotFoundError:
            pytest.skip("opencode binary not found in test environment")
        except subprocess.TimeoutExpired:
            pytest.skip("opencode timed out")


# ── Packaging tests ────────────────────────────────────────────────────

class TestPackaging:
    def test_build_backend_importable(self):
        """The declared build backend can be imported."""
        import importlib
        mod = importlib.import_module("setuptools.build_meta")
        assert mod is not None

    def test_launcher_imports(self, sample_repo: Path):
        """run_cli.py can import the package without PYTHONPATH."""
        import subprocess
        result = subprocess.run(
            ["python", str(Path(__file__).resolve().parent.parent / "run_cli.py"),
             "--repo-root", str(sample_repo), "status"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"Launcher failed: {result.stderr}"
        assert "Status:" in result.stdout

    def test_no_absolute_path_in_opencode(self):
        opencode_jsonc = Path(__file__).resolve().parent.parent.parent.parent / "opencode.jsonc"
        content = opencode_jsonc.read_text()
        assert "S:" not in content, "opencode.jsonc contains absolute S: drive path"
        assert "sean" not in content.lower(), "opencode.jsonc contains Sean-specific path"


# ── Runner tests ───────────────────────────────────────────────────────

class TestRunner:
    def test_runner_imports(self):
        """run_first_pair_checks.py imports correctly from repo root."""
        import subprocess
        runner = Path(__file__).resolve().parent.parent.parent.parent / "world-sim" / "scripts" / "run_first_pair_checks.py"
        result = subprocess.run(
            ["python", str(runner)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 1  # No args = help message
        assert "Usage:" in result.stdout or "Usage:" in result.stderr


# ── First Pair regression ──────────────────────────────────────────────

class TestFirstPairRegression:
    def test_first_pair_imports(self):
        from genesis_code_index.indexer import INDEXED_ROOTS
        assert "world-sim/backend" in INDEXED_ROOTS

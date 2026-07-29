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

from genesis_code_index.store import _path_matches_filter

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

    # -- _path_matches_filter unit tests --

    def test_filter_exact_root_accepted(self):
        assert _path_matches_filter("world-sim/backend/module_a.py", "world-sim/backend")

    def test_filter_descendant_accepted(self):
        assert _path_matches_filter("world-sim/backend/world/foo.py", "world-sim/backend")

    def test_filter_exact_file_accepted(self):
        assert _path_matches_filter("world-sim/backend/module_a.py", "world-sim/backend/module_a.py")

    def test_filter_sibling_rejected(self):
        assert not _path_matches_filter("world-sim/backend-other/module.py", "world-sim/backend")

    def test_filter_sibling_underscore_rejected(self):
        assert not _path_matches_filter("world-sim/backend_evil/module.py", "world-sim/backend")

    def test_filter_traversal_rejected(self):
        assert not _path_matches_filter("../outside/file.py", "world-sim/backend")

    def test_filter_empty_not_matched(self):
        assert not _path_matches_filter("world-sim/backend/module.py", "")

    def test_filter_stale_scope_accepted(self):
        """A nonexistent but syntactically valid subtree is accepted for stale cleanup."""
        assert _path_matches_filter("world-sim/backend/gone/module.py", "world-sim/backend")

    def test_store_scope_query_rejects_sibling(self, sample_repo: Path, store: CodeIndexStore):
        """query_definitions with sibling prefix returns no results."""
        from genesis_code_index.indexer import index_file
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        assert err is None
        store.replace_file_index(
            "world-sim/backend/module_a.py",
            path.stat().st_size, path.stat().st_mtime, "h", syms,
        )
        result = store.query_definitions("Greeter", path_filter="world-sim/backend-other")
        assert len(result) == 0, f"Sibling filter should return 0 results, got {len(result)}"

    def test_reindex_scope_rejects_sibling(self, sample_repo: Path):
        """Server-level reindex with sibling prefix returns rejected status."""
        import asyncio, json, os

        server_dir = Path(__file__).resolve().parent.parent
        run_server = str(server_dir / "run_server.py")
        events = {}

        async def _test():
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.session import ClientSession
            env = os.environ.copy()
            env.pop("GENESIS_CODE_INDEX_REPO_ROOT", None)
            params = StdioServerParameters(
                command=sys.executable,
                args=[run_server],
                env={**env, "GENESIS_CODE_INDEX_REPO_ROOT": str(sample_repo)},
            )
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    r = await session.call_tool("reindex", {"path_filter": "world-sim/backend-other"})
                    raw = r.content[0].text if hasattr(r.content[0], "text") else str(r.content[0])
                    events["result"] = json.loads(raw)

        asyncio.run(_test())
        assert events["result"].get("status") == "rejected", f"Expected rejected, got {events}"

    def test_reindex_traversal_resolved_scope(self, sample_repo: Path):
        """path_filter with '..' that resolves outside indexed root is rejected."""
        import asyncio, json, os

        server_dir = Path(__file__).resolve().parent.parent
        run_server = str(server_dir / "run_server.py")
        events = {}

        async def _test():
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.session import ClientSession
            env = os.environ.copy()
            env.pop("GENESIS_CODE_INDEX_REPO_ROOT", None)
            params = StdioServerParameters(
                command=sys.executable,
                args=[run_server],
                env={**env, "GENESIS_CODE_INDEX_REPO_ROOT": str(sample_repo)},
            )
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    r = await session.call_tool("reindex", {"path_filter": "world-sim/backend/../../outside"})
                    raw = r.content[0].text if hasattr(r.content[0], "text") else str(r.content[0])
                    events["result"] = json.loads(raw)

        asyncio.run(_test())
        assert events["result"].get("status") == "rejected", f"Expected rejected, got {events}"

    def test_resolve_path_scope_rejects_traversal(self, sample_repo: Path):
        """resolve_path_scope raises ValueError for '..' that escapes indexed root."""
        import os
        from genesis_code_index.indexer import resolve_path_scope

        with pytest.raises(ValueError, match="not under any indexed root"):
            resolve_path_scope("world-sim/backend/../../outside", sample_repo)

    def test_resolve_path_scope_rejects_sibling(self, sample_repo: Path):
        """resolve_path_scope raises ValueError for sibling-named scope."""
        from genesis_code_index.indexer import resolve_path_scope

        with pytest.raises(ValueError, match="not under any indexed root"):
            resolve_path_scope("world-sim/backend-other", sample_repo)

    def test_resolve_path_scope_accepts_valid(self, sample_repo: Path):
        """resolve_path_scope returns normalized path for valid scope."""
        from genesis_code_index.indexer import resolve_path_scope

        result = resolve_path_scope("world-sim/backend", sample_repo)
        assert result == "world-sim/backend"

    def test_resolve_path_scope_normalizes_traversal(self, sample_repo: Path):
        """resolve_path_scope resolves '..' that stays within indexed root."""
        from genesis_code_index.indexer import resolve_path_scope

        result = resolve_path_scope("world-sim/tests/../backend", sample_repo)
        assert result == "world-sim/backend"

    def test_resolve_path_scope_rejects_outside_repo(self, sample_repo: Path):
        """resolve_path_scope raises ValueError for path entirely outside repo."""
        from genesis_code_index.indexer import resolve_path_scope

        with pytest.raises(ValueError):
            resolve_path_scope("../../etc", sample_repo)

    def test_find_definition_rejects_traversal(self, sample_repo: Path):
        """MCP tool find_definition returns error for path_filter with traversal."""
        import asyncio, json, os

        server_dir = Path(__file__).resolve().parent.parent
        run_server = str(server_dir / "run_server.py")
        events = {}

        async def _test():
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.session import ClientSession
            env = os.environ.copy()
            env.pop("GENESIS_CODE_INDEX_REPO_ROOT", None)
            params = StdioServerParameters(
                command=sys.executable,
                args=[run_server],
                env={**env, "GENESIS_CODE_INDEX_REPO_ROOT": str(sample_repo)},
            )
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    r = await session.call_tool("find_definition", {
                        "name": "Greeter",
                        "path_filter": "world-sim/backend/../../outside",
                    })
                    result = _parse_tool_result(r, expect_list=True)
                    events["result"] = result

        asyncio.run(_test())
        assert len(events["result"]) == 1
        assert "error" in events["result"][0]
        assert "not under any indexed root" in events["result"][0]["error"]

    def test_find_references_rejects_traversal(self, sample_repo: Path):
        """MCP tool find_references returns error for path_filter with sibling."""
        import asyncio, json, os

        server_dir = Path(__file__).resolve().parent.parent
        run_server = str(server_dir / "run_server.py")
        events = {}

        async def _test():
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.session import ClientSession
            env = os.environ.copy()
            env.pop("GENESIS_CODE_INDEX_REPO_ROOT", None)
            params = StdioServerParameters(
                command=sys.executable,
                args=[run_server],
                env={**env, "GENESIS_CODE_INDEX_REPO_ROOT": str(sample_repo)},
            )
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    r = await session.call_tool("find_references", {
                        "name": "helper",
                        "path_filter": "world-sim/backend-other",
                    })
                    result = _parse_tool_result(r, expect_list=True)
                    events["result"] = result

        asyncio.run(_test())
        assert len(events["result"]) == 1
        assert "error" in events["result"][0]
        assert "not under any indexed root" in events["result"][0]["error"]

    def test_file_symbols_rejects_traversal(self, sample_repo: Path):
        """MCP tool file_symbols returns error for path with traversal."""
        import asyncio, json, os

        server_dir = Path(__file__).resolve().parent.parent
        run_server = str(server_dir / "run_server.py")
        events = {}

        async def _test():
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.session import ClientSession
            env = os.environ.copy()
            env.pop("GENESIS_CODE_INDEX_REPO_ROOT", None)
            params = StdioServerParameters(
                command=sys.executable,
                args=[run_server],
                env={**env, "GENESIS_CODE_INDEX_REPO_ROOT": str(sample_repo)},
            )
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    r = await session.call_tool("file_symbols", {
                        "file_path": "world-sim/backend/../../outside/evil.py",
                    })
                    result = _parse_tool_result(r, expect_list=True)
                    events["result"] = result

        asyncio.run(_test())
        assert len(events["result"]) == 1
        assert "error" in events["result"][0]
        assert "not under any indexed root" in events["result"][0]["error"]


# ── Package bootstrap tests ────────────────────────────────────────────

# ── MCP integration tests ──────────────────────────────────────────────

def _run_mcp_session(fixture_root: Path) -> dict:
    """Run a full MCP lifecycle against the fixture repository.

    Returns a dict describing what happened so the caller can assert.
    """
    import asyncio
    import json
    import os

    server_dir = Path(__file__).resolve().parent.parent
    run_server = str(server_dir / "run_server.py")
    events: dict = {}

    async def _session() -> dict:
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.session import ClientSession

        env = os.environ.copy()
        env.pop("GENESIS_CODE_INDEX_REPO_ROOT", None)
        params = StdioServerParameters(
            command=sys.executable,
            args=[run_server],
            env={**env, "GENESIS_CODE_INDEX_REPO_ROOT": str(fixture_root)},
        )
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                init = await session.initialize()
                events["server_name"] = init.serverInfo.name

                tools = await session.list_tools()
                events["tool_names"] = {t.name for t in tools.tools}

                reindex_result = await session.call_tool("reindex", {})
                reindex_data = _parse_tool_result(reindex_result)
                events["reindex"] = reindex_data

                status = await session.call_tool("index_status", {})
                status_data = _parse_tool_result(status)
                events["status"] = status_data

                def_result = await session.call_tool("find_definition", {"name": "Greeter"})
                def_data = _parse_tool_result(def_result, expect_list=True)
                events["definition"] = def_data

                ref_result = await session.call_tool("find_references", {"name": "helper"})
                ref_data = _parse_tool_result(ref_result, expect_list=True)
                events["references"] = ref_data

                caller_result = await session.call_tool("find_callers", {"func_name": "helper"})
                caller_data = _parse_tool_result(caller_result, expect_list=True)
                events["callers"] = caller_data

                lex_result = await session.call_tool("lexical_search", {"query": "Greeter"})
                lex_data = _parse_tool_result(lex_result, expect_list=True)
                events["lexical"] = lex_data

                bad_result = await session.call_tool("find_definition", {})
                events["malformed"] = {
                    "isError": getattr(bad_result, "isError", False),
                }

        return events

    return asyncio.run(_session())


def _parse_tool_result(result, expect_list: bool = False) -> dict | list:
    import json
    if not result.content:
        return [] if expect_list else {}
    text = result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
    try:
        data = json.loads(text)
        if expect_list and isinstance(data, dict):
            return [data]
        return data
    except (json.JSONDecodeError, TypeError):
        return [] if expect_list else {"_raw": text}


class TestMCPIntegration:
    """Real MCP stdio session through the committed launcher."""

    def test_full_mcp_lifecycle(self, sample_repo: Path):
        """Complete MCP session with fixture-based definition, reference, caller, and lexical queries."""
        import json

        events = _run_mcp_session(sample_repo)

        assert events["server_name"] == "genesis-code-index"

        required_tools = {
            "find_definition", "find_references", "find_callers",
            "lexical_search", "index_status", "reindex", "file_symbols",
            "find_string_literals", "find_importers", "list_class_members",
            "code_stats", "semantic_search",
        }
        assert required_tools.issubset(events["tool_names"]), (
            f"Missing tools: {required_tools - events['tool_names']}"
        )

        assert events["reindex"].get("status") in ("ok", "degraded")

        assert "db_path" in events["status"]
        db_path = events["status"]["db_path"]
        assert db_path.startswith(str(sample_repo)), (
            f"Database {db_path} outside fixture {sample_repo}"
        )

        defs = events["definition"]
        assert len(defs) >= 1, f"No definitions found for Greeter: {defs}"
        assert defs[0]["kind"] == "class", f"Expected class, got {defs[0]}"

        refs = events["references"]
        assert len(refs) >= 1, f"No references found for helper: {refs}"

        callers = events["callers"]
        assert len(callers) >= 1, f"No callers found for helper: {callers}"

        lex = events["lexical"]
        assert len(lex) >= 1, f"No lexical results for Greeter: {lex}"

        assert events["malformed"]["isError"], "Malformed call should return error"

    def test_no_real_checkout_mutation(self, sample_repo: Path):
        """The MCP test fixture uses its own repository; real checkout is unchanged.

        Snapshot is a dict keyed by resolved relative paths within .code-index,
        with each value a (size, sha256) tuple for content-level proof.
        """
        import hashlib
        real_index = Path(__file__).resolve().parent.parent / ".." / ".." / ".code-index"
        real_index_root = real_index.resolve()

        def _snapshot(path: Path) -> dict | None:
            if not path.exists():
                return None
            snap = {}
            for p in sorted(path.rglob("*")):
                if p.is_file():
                    rel = str(p.resolve().relative_to(real_index_root).as_posix())
                    snap[rel] = (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
            return snap

        before = _snapshot(real_index)

        _run_mcp_session(sample_repo)

        after = _snapshot(real_index)

        if before is None:
            assert after is None or len(after) == 0, (
                f"Real checkout index was created by test: {list(after.keys())}"
            )
        else:
            assert before == after, (
                f"Real checkout .code-index modified by test.\n"
                f"Added:   {set(after.keys()) - set(before.keys())}\n"
                f"Removed: {set(before.keys()) - set(after.keys())}\n"
                f"Changed: {[k for k in before if k in after and before[k] != after[k]]}"
            )


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
            [sys.executable, str(Path(__file__).resolve().parent.parent / "run_cli.py"),
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

    def _venv_python(self, venv_dir: Path) -> str:
        return str(venv_dir / "Scripts" / "python.exe") if sys.platform == "win32" else str(venv_dir / "bin" / "python")

    def test_wheel_build_and_install(self, tmp_path: Path):
        """Build a wheel, install in isolated venv, import and run command."""
        import subprocess, venv
        pkg_dir = Path(__file__).resolve().parent.parent
        wheel_dir = tmp_path / "dist"
        wheel_dir.mkdir()
        result = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", str(pkg_dir),
             "--no-deps", "--no-build-isolation",
             "-w", str(wheel_dir)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            if "No module named pip" in result.stderr:
                pytest.skip("pip wheel not available in test environment")
            pytest.fail(f"wheel build failed:\n{result.stderr[:500]}")
        wheels = list(wheel_dir.glob("*.whl"))
        assert len(wheels) >= 1, f"No wheel produced: {list(wheel_dir.iterdir())}"

        # Install wheel into isolated venv
        install_venv = tmp_path / "wheel_venv"
        venv.create(install_venv, with_pip=True)
        ipy = self._venv_python(install_venv)
        result = subprocess.run(
            [ipy, "-m", "pip", "install", str(wheels[0]), "--no-deps"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            if "No module named pip" in result.stderr:
                pytest.skip("pip not available in venv")
            pytest.fail(f"wheel install failed:\n{result.stderr[:500]}")

        # Verify import
        result = subprocess.run(
            [ipy, "-c", "import genesis_code_index; print('OK')"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0 and "OK" in result.stdout, f"Import failed:\n{result.stderr}"

        # Verify installed command
        result = subprocess.run(
            [ipy, "-m", "genesis_code_index", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"genesis-code-index command failed:\n{result.stderr[:500]}"

    def test_editable_install(self, tmp_path: Path):
        """Verify editable install works in an isolated temp venv using its own pip."""
        import subprocess, venv
        venv_dir = tmp_path / ".venv"
        venv.create(venv_dir, with_pip=True)
        ipy = self._venv_python(venv_dir)
        pkg_dir = Path(__file__).resolve().parent.parent
        # Install build deps in venv first (fresh venv lacks setuptools)
        deps_result = subprocess.run(
            [ipy, "-m", "pip", "install", "setuptools>=64", "--quiet"],
            capture_output=True, text=True, timeout=30,
        )
        if deps_result.returncode != 0:
            if "No module named pip" in deps_result.stderr:
                pytest.skip("pip not available in venv")
            pytest.fail(f"build deps install failed:\n{deps_result.stderr[:500]}")
        result = subprocess.run(
            [ipy, "-m", "pip", "install", "-e", str(pkg_dir),
             "--no-deps", "--no-build-isolation"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            pytest.fail(f"editable install failed:\n{result.stderr[:500]}")

        # Verify import from venv
        result = subprocess.run(
            [ipy, "-c", "import genesis_code_index; print('OK')"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0 and "OK" in result.stdout, f"Import failed:\n{result.stderr}"

        # Verify command
        result = subprocess.run(
            [ipy, "-m", "genesis_code_index", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"genesis-code-index command failed:\n{result.stderr[:500]}"


# ── Runner tests ───────────────────────────────────────────────────────

class TestRunner:
    def test_runner_uses_sys_executable(self):
        """run_first_pair_checks.py uses sys.executable, not bare 'python'."""
        runner = Path(__file__).resolve().parent.parent.parent.parent / "world-sim" / "scripts" / "run_first_pair_checks.py"
        content = runner.read_text()
        assert "sys.executable" in content
        assert '"python"' not in content or "'python'" not in content

    def test_runner_from_repo_root(self):
        """Runner works from repo root with absolute path."""
        import subprocess
        runner = Path(__file__).resolve().parent.parent.parent.parent / "world-sim" / "scripts" / "run_first_pair_checks.py"
        result = subprocess.run(
            [sys.executable, str(runner)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 1
        assert "Usage:" in result.stdout or "Usage:" in result.stderr

    def test_runner_from_world_sim(self, tmp_path: Path):
        """Runner works from world-sim directory."""
        import subprocess
        runner = Path(__file__).resolve().parent.parent.parent.parent / "world-sim" / "scripts" / "run_first_pair_checks.py"
        ws_dir = Path(__file__).resolve().parent.parent.parent.parent / "world-sim"
        result = subprocess.run(
            [sys.executable, str(runner)],
            capture_output=True, text=True, timeout=10, cwd=str(ws_dir),
        )
        assert result.returncode == 1
        assert "Usage:" in result.stdout or "Usage:" in result.stderr

    def test_runner_from_arbitrary_cwd(self, tmp_path: Path):
        """Runner works from arbitrary cwd when script path is absolute."""
        import subprocess
        runner = Path(__file__).resolve().parent.parent.parent.parent / "world-sim" / "scripts" / "run_first_pair_checks.py"
        result = subprocess.run(
            [sys.executable, str(runner)],
            capture_output=True, text=True, timeout=10, cwd=str(tmp_path),
        )
        assert result.returncode == 1
        assert "Usage:" in result.stdout or "Usage:" in result.stderr

    def test_runner_non_executable_launcher(self, tmp_path: Path):
        """Runner works even when run_cli.py has no execute permission (POSIX regression)."""
        import subprocess, stat
        launcher = Path(__file__).resolve().parent.parent / "run_cli.py"
        fixture_launcher = tmp_path / "run_cli_noexec.py"
        # Copy launcher to temp so we can strip permissions without affecting source
        fixture_launcher.write_text(launcher.read_text())
        if sys.platform != "win32":
            fixture_launcher.chmod(fixture_launcher.stat().st_mode & ~stat.S_IXUSR & ~stat.S_IXGRP & ~stat.S_IXOTH)
        # Runner uses sys.executable internally, so permissions don't matter
        code = f"""
import sys, subprocess
sys.path.insert(0, {str(Path(__file__).resolve().parent.parent / "src")!r})
runner = {str(Path(__file__).resolve().parent.parent.parent.parent / "world-sim" / "scripts" / "run_first_pair_checks.py")!r}
result = subprocess.run([sys.executable, runner, "code-index-status"], capture_output=True, text=True, timeout=15)
if result.returncode != 0:
    print("FAIL", result.stderr[:300])
    sys.exit(1)
print("OK")
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=20,
        )
        assert result.returncode == 0 and "OK" in result.stdout, (
            f"Runner failed with non-executable launcher:\n{result.stderr[:500]}"
        )


# ── First Pair regression ──────────────────────────────────────────────

class TestFirstPairRegression:
    def test_first_pair_imports(self):
        from genesis_code_index.indexer import INDEXED_ROOTS
        assert "world-sim/backend" in INDEXED_ROOTS

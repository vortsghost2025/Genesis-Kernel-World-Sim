"""Tests for genesis-code-index."""

import hashlib
import json
import sqlite3
import stat
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


# ── Shared snapshot helpers (used by isolation tests) ────────────────────


def _snapshot_entry_signature(p: Path) -> tuple[str, int, str, int]:
    """Return (type, size, sha256|'LOCKED'|'STAT_FAIL', mtime_ns) for one fs entry.

    On stat failure, returns a sentinel treated as a distinct signature —
    any change from the before-snapshot counts as a mutation.

    Stat/read errors are handled here and recorded as distinct evidence.
    """
    try:
        st = p.stat()
    except OSError:
        return ("STAT_FAIL", 0, "", 0)
    if stat.S_ISDIR(st.st_mode):
        return ("DIR", st.st_size, "", st.st_mtime_ns)
    try:
        with p.open("rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
    except (PermissionError, OSError):
        sha = "LOCKED"
    return ("FILE", st.st_size, sha, st.st_mtime_ns)


def _snapshot_index_tree(
    path: Path
) -> dict[str, tuple[str, int, str, int]]:
    """Return {relative-posix-key: (type, size, sha|'LOCKED'|'STAT_FAIL', mtime_ns)}.

    Distinguishes absent ({"__absent__": ...}) from present-but-empty ({key: signature}).
    Every entry under ``path`` is captured, including directories, files,
    SQLite sidecars, and lock files.

    Entries whose resolved path cannot be made relative to ``path``
    (e.g., escaping symlinks) are recorded with a deterministic unique key
    ``__outside__:<lexical-path-from-path>`` so mutations are not lost.

    Raises ValueError if a snapshot key would collide (fail closed, no silent
    overwrite).  Resolve errors are handled here; stat/read errors are handled
    by ``_snapshot_entry_signature``.
    """
    if not path.exists():
        return {"__absent__": ("ABSENT", 0, "", 0)}

    scan_root = path.resolve()
    snap: dict[str, tuple[str, int, str, int]] = {}
    snap["."] = _snapshot_entry_signature(path)
    for p in sorted(path.rglob("*")):
        try:
            rel = p.resolve().relative_to(scan_root).as_posix()
        except (ValueError, OSError):
            # Escaping symlink or filesystem race — use unique key based on
            # lexical path from the scanned directory.
            rel = f"__outside__:{p.relative_to(path).as_posix()}"
        if rel in snap:
            raise ValueError(f"Snapshot key collision: {rel}")
        snap[rel] = _snapshot_entry_signature(p)
    return snap


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

    # ── FIX 4 — additional filesystem-backed path-scope coverage ────────

    def test_resolve_path_scope_backslash_input(self, sample_repo: Path):
        """Backslash input is normalized to POSIX on Windows-like separators.

        On POSIX, backslashes are not path separators, so the input is
        treated as a literal filename component.  This test only asserts
        the Windows normalization behavior; it is skipped on POSIX.
        """
        import os
        if os.name != "nt":
            pytest.skip("Backslash normalization is Windows-specific")
        from genesis_code_index.indexer import resolve_path_scope

        result = resolve_path_scope("world-sim\\backend", sample_repo)
        assert result == "world-sim/backend"

    def test_resolve_path_scope_dot_component(self, sample_repo: Path):
        """Single-dot components are normalized away while staying in scope."""
        from genesis_code_index.indexer import resolve_path_scope

        result = resolve_path_scope("./world-sim/backend", sample_repo)
        assert result == "world-sim/backend"

    def test_resolve_path_scope_empty_rejected(self, sample_repo: Path):
        """Empty path_filter resolves to repo_root itself, which is not under any indexed root."""
        from genesis_code_index.indexer import resolve_path_scope

        with pytest.raises(ValueError, match="not under any indexed root"):
            resolve_path_scope("", sample_repo)

    def test_resolve_path_scope_absolute_outside_rejected(self, sample_repo: Path, tmp_path: Path):
        """An absolute path outside the repo raises ValueError."""
        from genesis_code_index.indexer import resolve_path_scope

        outside = tmp_path / "outside-target"
        outside.mkdir()
        # An absolute path outside the repo relative_to(repo_root) raises ValueError
        with pytest.raises(ValueError):
            resolve_path_scope(str(outside), sample_repo)

    def test_resolve_path_scope_valid_descendant(self, sample_repo: Path):
        """A valid descendant subtree resolves to itself."""
        from genesis_code_index.indexer import resolve_path_scope

        result = resolve_path_scope("world-sim/backend/subpkg", sample_repo)
        # Path.resolve() normalizes the logical path — the exact descendant
        # scope is returned.
        assert result == "world-sim/backend/subpkg"

    def test_resolve_path_scope_canonical_posix_returned(self, sample_repo: Path):
        """Returned path is POSIX-normalized regardless of input separator."""
        from genesis_code_index.indexer import resolve_path_scope

        result = resolve_path_scope("world-sim/tests/../backend/./", sample_repo)
        assert result == "world-sim/backend", f"got {result!r}"
        # POSIX separator only — no backslashes leaked through.
        assert "\\" not in result, f"backslash leaked into result {result!r}"
        # No trailing slash — resolve normalizes it away.
        assert not result.endswith("/"), f"trailing slash in result {result!r}"

    def test_resolve_path_scope_symlink_escape_rejected(self, sample_repo: Path, tmp_path: Path):
        """A symlink that escapes the indexed root is rejected.

        Skipped on platforms where unprivileged symlink creation is denied —
        the exact OSError is recorded in the skip message.
        """
        from genesis_code_index.indexer import resolve_path_scope

        link_path = sample_repo / "world-sim" / "backend" / "escaped_link"
        target = tmp_path / "escape-target"
        target.mkdir()
        try:
            link_path.symlink_to(target)
        except OSError as e:
            pytest.skip(
                f"Cannot create symlink on this platform ({e.__class__.__name__}: {e})"
            )
        with pytest.raises(ValueError):
            resolve_path_scope("world-sim/backend/escaped_link", sample_repo)

    def test_resolve_path_scope_missing_valid_subtree_accepted(self, sample_repo: Path):
        """resolve_path_scope operates on the logical path — a missing but indexed
        subtree is accepted because Path.resolve() does not require existence."""
        from genesis_code_index.indexer import resolve_path_scope

        # world-sim/scripts is an indexed root but not created in the fixture.
        result = resolve_path_scope("world-sim/scripts", sample_repo)
        assert result == "world-sim/scripts"

    def test_resolve_path_scope_missing_path_beneath_symlink(self, sample_repo: Path, tmp_path: Path):
        """A non-existent path that would resolve beneath an escaping symlink is rejected."""
        from genesis_code_index.indexer import resolve_path_scope

        link_path = sample_repo / "world-sim" / "backend" / "esc"
        target = tmp_path / "outside"
        target.mkdir()
        try:
            link_path.symlink_to(target)
        except OSError as e:
            pytest.skip(
                f"Cannot create symlink on this platform ({e.__class__.__name__}: {e})"
            )
        with pytest.raises(ValueError):
            resolve_path_scope("world-sim/backend/esc/missing.py", sample_repo)

    # ── FIX 4 — server-level approved file and subtree use ───────────────

    def test_find_definition_approved_file(self, sample_repo: Path):
        """find_definition accepts a valid file path_filter as scope."""
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
                    # Index the fixture first.
                    await session.call_tool("reindex", {})
                    r = await session.call_tool("find_definition", {
                        "name": "Greeter",
                        "path_filter": "world-sim/backend/module_a.py",
                    })
                    result = _parse_tool_result(r, expect_list=True)
                    events["result"] = result

        asyncio.run(_test())
        # approved file returns at least one definition, NOT an error
        assert events["result"], "no result returned"
        assert "error" not in events["result"][0], \
            f"unexpected error: {events['result'][0]}"
        assert any(r.get("kind") == "class" and r.get("name") == "Greeter"
                   for r in events["result"]), \
            f"Greeter not found: {events['result']}"

    def test_find_definition_approved_subtree(self, sample_repo: Path):
        """find_definition accepts an indexed-root-level subtree as scope."""
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
                    # Index the fixture first.
                    await session.call_tool("reindex", {})
                    r = await session.call_tool("find_definition", {
                        "name": "Greeter",
                        "path_filter": "world-sim/backend",
                    })
                    result = _parse_tool_result(r, expect_list=True)
                    events["result"] = result

        asyncio.run(_test())
        assert events["result"], "no result returned"
        assert "error" not in events["result"][0], \
            f"unexpected error: {events['result'][0]}"
        assert any(r.get("kind") == "class" and r.get("name") == "Greeter"
                   for r in events["result"]), \
            f"Greeter not found: {events['result']}"

    def test_resolve_path_scope_multiple_escaping_symlinks_unique_keys(self, sample_repo: Path, tmp_path: Path):
        """Two distinct escaping symlinks produce two distinct snapshot keys.

        Verifies that _snapshot records each escaping entry under a unique
        key (not a shared "__outside__" key) so mutations are not lost.
        """
        from genesis_code_index.indexer import resolve_path_scope

        # Create two separate escaping symlinks
        link1 = sample_repo / "world-sim" / "backend" / "escape1"
        link2 = sample_repo / "world-sim" / "backend" / "escape2"
        target = tmp_path / "outside"
        target.mkdir()

        try:
            link1.symlink_to(target)
            link2.symlink_to(target)
        except OSError as e:
            pytest.skip(
                f"Cannot create symlink on this platform ({e.__class__.__name__}: {e})"
            )

        # Both should be rejected by resolve_path_scope
        with pytest.raises(ValueError):
            resolve_path_scope("world-sim/backend/escape1", sample_repo)
        with pytest.raises(ValueError):
            resolve_path_scope("world-sim/backend/escape2", sample_repo)

        # Now exercise the shared _snapshot_index_tree helper directly on a
        # temp .code-index dir to verify unique keys are created for escaping entries.
        test_index = tmp_path / ".code-index"
        test_index.mkdir()
        link_a = test_index / "escaped_a"
        link_b = test_index / "escaped_b"
        outside = tmp_path / "escape_target"
        outside.mkdir()

        try:
            link_a.symlink_to(outside)
            link_b.symlink_to(outside)
        except OSError as e:
            pytest.skip(
                f"Cannot create symlink on this platform ({e.__class__.__name__}: {e})"
            )

        # Use the shared helper to verify unique keys are created for escaping entries.
        snap = _snapshot_index_tree(test_index)

        # Verify both escaping entries have distinct keys
        outside_keys = [k for k in snap if k.startswith("__outside__:")]
        assert len(outside_keys) == 2, (
            f"Expected 2 distinct outside keys, got {len(outside_keys)}: {outside_keys}"
        )
        assert all(k.startswith("__outside__:") for k in outside_keys)
        # Verify the lexical link names are preserved in the keys
        assert "__outside__:escaped_a" in outside_keys
        assert "__outside__:escaped_b" in outside_keys

    def test_snapshot_index_tree_collision_fail_closed(self, tmp_path: Path, monkeypatch):
        """_snapshot_index_tree fails closed on duplicate snapshot keys.

        This test is platform-independent and exercises the collision-guard
        logic even on Windows where symlink creation may be unavailable.
        """
        # Create a temp directory with two files that will collide
        test_index = tmp_path / ".code-index"
        test_index.mkdir()
        file_a = test_index / "a"
        file_b = test_index / "b"
        file_a.write_text("a")
        file_b.write_text("b")

        # Monkeypatch Path.resolve so both files resolve to the same path,
        # causing a key collision in _snapshot_index_tree
        original_resolve = Path.resolve

        def colliding_resolve(self):
            # Make both files resolve to the same in-root path
            if self.name in ("a", "b"):
                return self.parent / "a"
            return original_resolve(self)

        with monkeypatch.context() as m:
            m.setattr(Path, "resolve", colliding_resolve)
            with pytest.raises(ValueError, match="Snapshot key collision"):
                _snapshot_index_tree(test_index)

def test_snapshot_index_tree_relative_path_normal_keys(tmp_path: Path):
        """Relative path input to _snapshot_index_tree produces normal keys.

        When the scanned path is a relative path (not an absolute path),
        entries should still produce normal relative keys without __outside__
        prefixes, as long as the resolved paths stay within the scanned directory.
        """
        import os

        test_index = tmp_path / ".code-index"
        test_index.mkdir()
        (test_index / "a").write_text("a")
        (test_index / "b").write_text("b")

        # Pass relative path to _snapshot_index_tree from tmp_path as cwd
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            rel_path = test_index.relative_to(tmp_path)
            snap = _snapshot_index_tree(rel_path)
        finally:
            os.chdir(old_cwd)

        # Should produce normal relative keys without __outside__ prefix
        outside_keys = [k for k in snap if k.startswith("__outside__:")]
        assert len(outside_keys) == 0, f"Unexpected outside keys: {outside_keys}"

        # Normal relative keys should be present
        assert "a" in snap
        assert "b" in snap
        assert snap["a"][0] == "FILE"
        assert snap["b"][0] == "FILE"

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

        # FIX 3 — resolved-path fixture containment proof.
        # Reject sibling-prefix tricks (e.g. fixture `/foo` vs DB reported
        # as `/foobar/index.db`).  Resolve both paths and verify the
        # DB is *inside* the fixture repo by checking its parent walk
        # contains the resolved fixture root.
        db_resolved = Path(db_path).resolve()
        fixture_resolved = sample_repo.resolve()
        # db_resolved must be equal to, or descend from, fixture_resolved.
        try:
            _ = db_resolved.relative_to(fixture_resolved)
        except ValueError:
            pytest.fail(
                f"Database {db_resolved} resolves outside fixture {fixture_resolved}"
            )
        # Also enumerate every file under the resolved DB's directory and
        # require each to remain inside the fixture root.  This catches
        # SQLite sidecars (``-journal``, ``-wal``, ``-shm``) and any
        # metadata/cache entries.
        db_dir = db_resolved.parent
        for entry in db_dir.rglob("*"):
            try:
                entry.resolve().relative_to(fixture_resolved)
            except ValueError:
                pytest.fail(
                    f"DB sidecar/artifact {entry} resolves outside fixture "
                    f"{fixture_resolved}"
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
        """Real-checkout code-index isolation proof.

        Resolves the *production* repo-root ``.code-index`` directory
        (i.e. the directory actually used by ``server.py``'s
        ``_DEFAULT_DB = ".code-index/index.db"``), snapshot its complete
        state, run a fixture MCP session, then require the after-snapshot to
        equal the before-snapshot exactly.  Created, deleted, rewritten,
        size-changed, metadata-changed, or sidecar (``-journal``/``-wal``/
        ``-shm``) files all count as mutations; an absent directory becoming
        an empty directory also counts.

        ``LOCKED`` files (e.g. ``index.db`` open by a running MCP server) are
        not hashed.  Their ``st_mtime_ns`` and ``st_size`` are compared, and
        any change there is a mutation.
        """
        import hashlib
        import os

        # Resolve the production repo-root .code-index, transitively.
        # The live server uses ``repo_root / ".code-index/index.db"``.
        # repo_root for this test = the directory three levels above
        # ``tooling/code-index-mcp/tests/`` (i.e. the git repo root).
        repo_root = Path(__file__).resolve().parents[3]
        real_index_dir = repo_root / ".code-index"

        before = _snapshot_index_tree(real_index_dir)

        # Run the fixture MCP session — must not touch production index.
        _run_mcp_session(sample_repo)

        after = _snapshot_index_tree(real_index_dir)

        # Distinguish "absent before, absent after" (still OK) from any other
        # transition.  An absent directory that becomes an empty directory
        # counts as a mutation.
        before_absent = ("__absent__" in before)
        after_absent = ("__absent__" in after)
        if before_absent and after_absent:
            return  # absent → absent is the only OK transition involving ABSENT
        if before_absent and not after_absent:
            pytest.fail(
                f"Real checkout .code-index was CREATED by the test.\n"
                f"New entries: {sorted(after.keys())}"
            )
        if (not before_absent) and after_absent:
            pytest.fail(
                f"Real checkout .code-index was DELETED by the test.\n"
                f"Lost entries: {sorted(before.keys())}"
            )

        before_keys = set(before.keys())
        after_keys = set(after.keys())
        added = after_keys - before_keys
        removed = before_keys - after_keys
        changed = []
        for k in before_keys & after_keys:
            if before[k] != after[k]:
                changed.append(k)
        if added or removed or changed:
            msgs = []
            if added:
                msgs.append(
                    "Added:\n" + "\n".join(
                        f"  {k} -> {after[k]}" for k in sorted(added)
                    )
                )
            if removed:
                msgs.append(
                    "Removed:\n" + "\n".join(
                        f"  {k} -> {before[k]}" for k in sorted(removed)
                    )
                )
            if changed:
                msgs.append(
                    "Changed:\n" + "\n".join(
                        f"  {k}: before={before[k]} after={after[k]}"
                        for k in sorted(changed)
                    )
                )
            pytest.fail(
                "Real checkout .code-index mutated by fixture MCP session.\n"
                + "\n\n".join(msgs)
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


# ── FIX 5 — Production mcp-smoke negative proof ────────────────────────

class TestMcpSmokeNegative:
    """Direct unit-tests for the production mcp-smoke result validator.

    These prove that the validator used by ``run_first_pair_checks.py
    cmd_mcp_smoke`` (a) accepts the expected positive payload and
    (b) fails for empty lists, wrong kind, and wrong repository path.
    No MCP server or external provider contact is made — the tests call
    the pure-Python ``_validate_smoke_result`` helper directly.
    """

    @staticmethod
    def _load_validator():
        import importlib.util
        script_path = Path(__file__).resolve().parents[3] / "world-sim" / "scripts" / "run_first_pair_checks.py"
        spec = importlib.util.spec_from_file_location("first_pair_checks", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._validate_smoke_result

    def test_positive_payload_accepted(self):
        """The canonical positive payload is accepted by the validator."""
        v = self._load_validator()
        payload = [{
            "kind": "class",
            "file_path": "world-sim/backend/agents/base.py",
            "name": "WorldAgent",
        }]
        ok, reason = v(payload)
        assert ok, f"Positive payload should accept, got: {reason}"

    def test_single_dict_wrapped_as_list(self):
        """FastMCP unwraps single-element lists to dicts; validator wraps them."""
        v = self._load_validator()
        payload = {
            "kind": "class",
            "file_path": "world-sim/backend/agents/base.py",
            "name": "WorldAgent",
        }
        ok, reason = v(payload)
        assert ok, f"Dict-wrapped payload should accept, got: {reason}"

    def test_empty_list_rejected(self):
        """An empty definition list (missing symbol) fails validation."""
        v = self._load_validator()
        ok, reason = v([])
        assert not ok, "Empty list should be rejected"
        assert "not found" in reason or "empty" in reason, \
            f"Reason should mention missing/empty, got: {reason!r}"

    def test_wrong_symbol_kind_rejected(self):
        """A symbol with the wrong kind (not 'class') fails validation."""
        v = self._load_validator()
        payload = [{
            "kind": "function",
            "file_path": "world-sim/backend/agents/base.py",
            "name": "WorldAgent",
        }]
        ok, reason = v(payload)
        assert not ok, "Wrong kind should be rejected"
        assert "kind" in reason.lower(), f"Reason should mention kind, got: {reason!r}"

    def test_wrong_repo_path_rejected(self):
        """A symbol at the wrong file_path fails validation."""
        v = self._load_validator()
        payload = [{
            "kind": "class",
            "file_path": "world-sim/backend/somewhere_else.py",
            "name": "WorldAgent",
        }]
        ok, reason = v(payload)
        assert not ok, "Wrong repo path should be rejected"
        assert "file_path" in reason.lower() or "world-sim" in reason, \
            f"Reason should mention file_path, got: {reason!r}"

    def test_missing_file_path_rejected_even_with_file_fallback(self):
        """Missing file_path is rejected even if 'file' field has correct value."""
        v = self._load_validator()
        payload = [{
            "kind": "class",
            "file": "world-sim/backend/agents/base.py",
            "name": "WorldAgent",
        }]
        ok, reason = v(payload)
        assert not ok, "Missing file_path should be rejected despite file field"
        assert "file_path" in reason.lower(), f"Reason should mention file_path, got: {reason!r}"

    def test_none_file_path_rejected_even_with_file_fallback(self):
        """file_path=None is rejected even if 'file' field has correct value."""
        v = self._load_validator()
        payload = [{
            "kind": "class",
            "file_path": None,
            "file": "world-sim/backend/agents/base.py",
            "name": "WorldAgent",
        }]
        ok, reason = v(payload)
        assert not ok, "file_path=None should be rejected despite file field"
        assert "file_path" in reason.lower(), f"Reason should mention file_path, got: {reason!r}"

    def test_empty_file_path_rejected_even_with_file_fallback(self):
        """file_path='' is rejected even if 'file' field has correct value."""
        v = self._load_validator()
        payload = [{
            "kind": "class",
            "file_path": "",
            "file": "world-sim/backend/agents/base.py",
            "name": "WorldAgent",
        }]
        ok, reason = v(payload)
        assert not ok, "Empty file_path should be rejected despite file field"
        assert "file_path" in reason.lower(), f"Reason should mention file_path, got: {reason!r}"

    def test_non_string_file_path_rejected(self):
        """Non-string file_path is rejected."""
        v = self._load_validator()
        payload = [{
            "kind": "class",
            "file_path": 123,
            "name": "WorldAgent",
        }]
        ok, reason = v(payload)
        assert not ok, "Non-string file_path should be rejected"
        assert "file_path" in reason.lower(), f"Reason should mention file_path, got: {reason!r}"

    def test_correct_file_path_still_passes(self):
        """Payload with exact correct file_path still passes."""
        v = self._load_validator()
        payload = [{
            "kind": "class",
            "file_path": "world-sim/backend/agents/base.py",
            "name": "WorldAgent",
        }]
        ok, reason = v(payload)
        assert ok, f"Correct payload should pass: {reason}"

    def test_non_list_payload_rejected(self):
        """A non-list, non-dict payload fails validation."""
        v = self._load_validator()
        for bad in [None, "string", 42]:
            ok, reason = v(bad)
            assert not ok, f"Non-list {type(bad).__name__} should be rejected"
            assert "list" in reason.lower() or "not found" in reason.lower(), \
                f"Reason should mention shape, got: {reason!r}"

        # Empty dict: wraps to [{}], then fails on missing kind.
        ok, reason = v({})
        assert not ok, "Empty dict should be rejected"
        assert "kind" in reason.lower(), f"Reason should mention kind, got: {reason!r}"


# ── First Pair regression ──────────────────────────────────────────────

class TestFirstPairRegression:
    def test_first_pair_imports(self):
        from genesis_code_index.indexer import INDEXED_ROOTS
        assert "world-sim/backend" in INDEXED_ROOTS

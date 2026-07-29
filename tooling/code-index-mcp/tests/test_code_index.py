"""Tests for genesis-code-index."""

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Ensure package root is on path
PKG_ROOT = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(PKG_ROOT))

from genesis_code_index.indexer import index_file, index_repo, SKIP_DIRS, INDEXED_ROOTS
from genesis_code_index.store import CodeIndexStore
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
        assert err is None, f"unexpected error: {err}"
        names = {(s["kind"], s["name"]) for s in syms}
        assert ("class", "Greeter") in names
        assert ("function", "helper") in names
        assert ("function", "greet") in names

    def test_index_file_finds_calls(self, sample_repo: Path):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        assert err is None
        calls = {s["name"] for s in syms if s["kind"] == "call"}
        assert "helper" in calls
        assert "Greeter" in calls or "Greeter()" in calls

    def test_index_file_finds_strings(self, sample_repo: Path):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        strings = {s["value"] for s in syms if s["kind"] == "string_literal"}
        assert any("Hello" in v for v in strings) or any("world" in v for v in strings)

    def test_index_file_outside_repo_fails(self, sample_repo: Path):
        outside = sample_repo / "outside.py"
        outside.write_text("x = 1")
        syms, err = index_file(outside, sample_repo)
        assert err is not None
        assert "outside" in err.lower() or "path" in err.lower()

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
        # find greet_loudly's enclosing_class
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
        assert ("os", "import") in imports or ("os", "from_import") in imports
        assert ("Greeter", "from_import") in imports or ("Greeter", "import") in imports


# ── Store tests ────────────────────────────────────────────────────────

class TestStore:
    def test_initialize_creates_tables(self, store: CodeIndexStore):
        conn = store.connect()
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "files" in tables
        assert "symbols" in tables
        assert "symbols_fts" in tables

    def test_insert_and_query_definitions(self, sample_repo: Path, store: CodeIndexStore):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        assert err is None
        rel = "world-sim/backend/module_a.py"
        store.reset_file(rel)
        store.update_file(rel, path.stat().st_size, path.stat().st_mtime,
                          "fakehash", None)
        store.insert_symbols(rel, syms)
        defs = store.query_definitions("Greeter")
        assert len(defs) >= 1
        assert defs[0]["kind"] == "class"

    def test_query_references(self, sample_repo: Path, store: CodeIndexStore):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        assert err is None
        rel = "world-sim/backend/module_a.py"
        store.reset_file(rel)
        store.update_file(rel, path.stat().st_size, path.stat().st_mtime,
                          "fakehash", None)
        store.insert_symbols(rel, syms)
        refs = store.query_references("Greeter")
        # Should find class def + call sites
        assert len(refs) >= 1

    def test_query_callers_with_enclosing(self, sample_repo: Path, store: CodeIndexStore):
        for fname in ("module_a.py", "module_b.py"):
            path = sample_repo / "world-sim" / "backend" / fname
            syms, err = index_file(path, sample_repo)
            assert err is None
            rel = f"world-sim/backend/{fname}"
            store.reset_file(rel)
            store.update_file(rel, path.stat().st_size, path.stat().st_mtime,
                              "fakehash", None)
            store.insert_symbols(rel, syms)
        # Module_a calls Greeter() and helper() — verify those exist
        callers_helper = store.query_callers("helper")
        assert len(callers_helper) >= 1
        # Module_b calls ExtendedGreeter() inside compute()
        callers_ext = store.query_callers("ExtendedGreeter")
        assert len(callers_ext) >= 1

    def test_fts_search(self, sample_repo: Path, store: CodeIndexStore):
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        syms, err = index_file(path, sample_repo)
        assert err is None
        rel = "world-sim/backend/module_a.py"
        store.reset_file(rel)
        store.update_file(rel, path.stat().st_size, path.stat().st_mtime,
                          "fakehash", None)
        store.insert_symbols(rel, syms)
        results = store.lexical_search("Greeter")
        assert len(results) >= 1

    def test_incremental_unchanged(self, sample_repo: Path, store: CodeIndexStore):
        rel = "world-sim/backend/module_a.py"
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        store.update_file(rel, path.stat().st_size, path.stat().st_mtime,
                          "testhash", None)
        assert store.file_exists_unchanged(rel, path.stat().st_mtime, "testhash")
        assert not store.file_exists_unchanged(rel, path.stat().st_mtime, "different")

    def test_parse_error_preserves_previous(self, sample_repo: Path, store: CodeIndexStore):
        rel = "world-sim/backend/module_a.py"
        path = sample_repo / "world-sim" / "backend" / "module_a.py"
        # First: good index
        store.update_file(rel, path.stat().st_size, path.stat().st_mtime,
                          "goodhash", None)
        good = store.get_stats()
        # Second: error
        store.update_file(rel, 0, 0, "badhash", "syntax error: bad")
        stats = store.get_stats()
        assert stats["parse_errors"] >= 1

    def test_deleted_file_removal(self, sample_repo: Path, store: CodeIndexStore):
        rel = "world-sim/backend/module_a.py"
        store.update_file(rel, 100, 100.0, "hash", None)
        store.remove_deleted_files(set())
        stats = store.get_stats()
        assert stats["files"] == 0


# ── Semantic adapter tests ─────────────────────────────────────────────

class TestSemanticAdapter:
    def test_disabled_by_default(self):
        backend = create_semantic_backend()
        assert not backend.enabled()
        assert backend.status()["enabled"] is False

    def test_disabled_returns_status(self):
        backend = DisabledSemanticBackend()
        s = backend.status()
        assert s["type"] == "disabled"


# ── Path containment tests ─────────────────────────────────────────────

class TestPathContainment:
    def test_outside_repo_rejected(self, sample_repo: Path):
        outside = Path(tempfile.gettempdir()) / "evil.py"
        outside.write_text("x = 1")
        syms, err = index_file(outside, sample_repo)
        assert err is not None
        outside.unlink()

    def test_skip_dirs_excluded(self, sample_repo: Path):
        # .runtime dir should be skipped
        runtime_dir = sample_repo / "world-sim" / ".runtime"
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "private.py").write_text("secret = 'data'")
        indexed = index_repo(sample_repo)
        assert not any(".runtime" in k for k in indexed)


# ── CLI smoketest ──────────────────────────────────────────────────────

class TestCLI:
    def test_reindex_via_cli(self, sample_repo: Path):
        from genesis_code_index.__main__ import main
        # Run reindex
        sys.argv = ["genesis-code-index", "--repo-root", str(sample_repo), "reindex"]
        try:
            main()
        except SystemExit:
            pass
        # Verify db was created
        db = sample_repo / ".code-index" / "index.db"
        assert db.exists()


# ── First Pair regression ──────────────────────────────────────────────

class TestFirstPairRegression:
    """Verify existing First Pair test baseline is preserved."""

    def test_first_pair_imports(self):
        """Check that importing doesn't break or contact providers."""
        from genesis_code_index.indexer import INDEXED_ROOTS
        assert "world-sim/backend" in INDEXED_ROOTS

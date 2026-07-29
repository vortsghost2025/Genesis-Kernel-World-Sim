"""Real MCP server using FastMCP — exposes code index via stdio transport."""

import hashlib
import os
import time
from pathlib import Path
from typing import Any

from mcp.server import FastMCP

from genesis_code_index.indexer import index_file, SKIP_DIRS, INDEXED_ROOTS
from genesis_code_index.store import CodeIndexStore
from genesis_code_index.semantic_adapter import create_semantic_backend


REPO_ROOT_HINT = "GENESIS_CODE_INDEX_REPO_ROOT"
_DEFAULT_DB = ".code-index/index.db"


def _resolve_repo_root() -> Path:
    env = os.environ.get(REPO_ROOT_HINT, "").strip()
    if env:
        return Path(env).resolve()
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists():
            return parent
    return cwd


def _file_hash(pyfile: Path) -> str:
    return hashlib.sha256(pyfile.read_bytes()).hexdigest()


def _build_mcp() -> FastMCP:
    repo_root = _resolve_repo_root()
    db_path = repo_root / _DEFAULT_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = CodeIndexStore(db_path)
    store.initialize()
    semantic = create_semantic_backend()

    mcp = FastMCP("genesis-code-index")

    @mcp.tool()
    def find_definition(name: str, kind: str | None = None,
                        path_filter: str | None = None) -> list[dict]:
        """Find exact symbol definitions (class, function, method)."""
        return store.query_definitions(name, kind, path_filter)

    @mcp.tool()
    def find_references(name: str, path_filter: str | None = None) -> list[dict]:
        """Find actual AST reference nodes (name, attribute, call)."""
        return store.query_references(name, path_filter)

    @mcp.tool()
    def find_callers(func_name: str) -> list[dict]:
        """Find call sites for a function."""
        return store.query_callers(func_name)

    @mcp.tool()
    def find_string_literals(pattern: str, use_regex: bool = False,
                             limit: int = 30) -> list[dict]:
        """Find string literals matching a pattern (literal or regex)."""
        return store.query_strings(pattern, use_regex, limit)

    @mcp.tool()
    def find_importers(module_name: str) -> list[dict]:
        """Find import statements for a module."""
        return store.query_importers(module_name)

    @mcp.tool()
    def list_class_members(class_name: str) -> list[dict]:
        """List methods/members of a class."""
        return store.query_class_members(class_name)

    @mcp.tool()
    def file_symbols(file_path: str) -> list[dict]:
        """List all indexed symbols in a file."""
        return store.query_file_symbols(file_path)

    @mcp.tool()
    def lexical_search(query: str, limit: int = 30) -> list[dict]:
        """Full-text search via FTS5 across names, docstrings and excerpts."""
        return store.lexical_search(query, limit)

    @mcp.tool()
    def semantic_search(query: str, limit: int = 10) -> list[dict]:
        """Semantic vector search (requires external endpoint)."""
        if not semantic.enabled():
            return [{"error": "semantic search disabled. Set GENESIS_CODE_INDEX_SEMANTIC_URL to enable."}]
        return semantic.search(query, limit)

    @mcp.tool()
    def reindex(path_filter: str | None = None) -> dict:
        """Full or incremental reindex.

        When path_filter is provided, only files under that relative subtree
        are affected.  All other indexed files are left untouched.
        """
        t0 = time.time()
        reindexed = 0
        skipped = 0
        errors = 0

        # Determine scope — component-aware validation
        # A filter is valid only when it exactly equals an indexed root or
        # is a descendant (separator-boundary check, not substring).
        if path_filter:
            norm_filter = path_filter.replace("\\", "/").strip("/")
            scope_roots = [
                r for r in INDEXED_ROOTS
                if norm_filter == r or norm_filter.startswith(r + "/")
            ]
            if not scope_roots:
                return {"error": f"path_filter '{path_filter}' is not under any indexed root",
                        "reindexed": 0, "skipped": 0, "errors": 0,
                        "elapsed_seconds": 0.0, "status": "rejected"}
            indexed_scope = {norm_filter}
            active: set[str] = set()
        else:
            indexed_scope = INDEXED_ROOTS
            active = set()

        for root_str in indexed_scope:
            root = repo_root / root_str
            if not root.exists():
                continue
            for pyfile in sorted(root.rglob("*.py")):
                if any(part in SKIP_DIRS for part in pyfile.parts):
                    continue
                try:
                    rel = str(pyfile.resolve().relative_to(repo_root.resolve()).as_posix())
                except ValueError:
                    continue
                active.add(rel)
                stat = pyfile.stat()
                fhash = _file_hash(pyfile)
                if store.file_exists_unchanged(rel, stat.st_mtime, fhash):
                    skipped += 1
                    continue
                # Parse first; only replace on success
                syms, parse_err = index_file(pyfile, repo_root)
                if parse_err:
                    prev = store.get_file(rel)
                    prev_hash = prev["file_hash"] if prev else ""
                    store.record_parse_failure(rel, fhash, prev_hash, parse_err)
                    errors += 1
                else:
                    store.replace_file_index(rel, stat.st_size, stat.st_mtime,
                                             fhash, syms)
                    reindexed += 1

        # For a full reindex, remove files that no longer exist on disk.
        # For a filtered reindex, scope deletion to that subtree only.
        if not path_filter:
            store.remove_deleted_files(active)
        else:
            scope = {norm_filter}
            store.remove_deleted_files(active, scope_prefixes=scope)

        elapsed = time.time() - t0
        stats = store.get_stats()
        return {
            "reindexed": reindexed,
            "skipped": skipped,
            "errors": errors,
            "elapsed_seconds": round(elapsed, 2),
            "status": "degraded" if errors > 0 else "ok",
            "files": stats.get("files"),
            "symbols": stats.get("symbols"),
            "fts": stats.get("fts"),
        }

    @mcp.tool()
    def index_status() -> dict:
        """Show code index database status."""
        stats = store.get_stats()
        stats["db_path"] = str(db_path)
        stats["semantic"] = semantic.status()
        stats["failures"] = store.get_failures(5)
        return stats

    @mcp.tool()
    def code_stats() -> dict:
        """Aggregate codebase statistics."""
        return store.get_stats()

    return mcp


def main_stdio() -> None:
    """Run the MCP stdio server."""
    import asyncio
    mcp = _build_mcp()
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main_stdio()

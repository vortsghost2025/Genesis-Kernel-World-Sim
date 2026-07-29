"""Real MCP server using FastMCP — exposes code index via stdio transport."""

import os
import time
from pathlib import Path
from typing import Any

from mcp.server import FastMCP

from genesis_code_index.indexer import index_file, index_repo, SKIP_DIRS, INDEXED_ROOTS
from genesis_code_index.store import CodeIndexStore
from genesis_code_index.semantic_adapter import create_semantic_backend


REPO_ROOT_HINT = "GENESIS_CODE_INDEX_REPO_ROOT"
_DEFAULT_DB = ".code-index/index.db"


def _resolve_repo_root() -> Path:
    env = os.environ.get(REPO_ROOT_HINT, "").strip()
    if env:
        return Path(env).resolve()
    # Walk up from cwd
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists():
            return parent
    return cwd


def _build_mcp() -> FastMCP:
    repo_root = _resolve_repo_root()
    db_path = repo_root / _DEFAULT_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = CodeIndexStore(db_path)
    store.initialize()
    semantic = create_semantic_backend()

    mcp = FastMCP("genesis-code-index")

    # ── tool: find_definition ──────────────────────────────────────────
    @mcp.tool()
    def find_definition(name: str, kind: str | None = None,
                        path_filter: str | None = None) -> list[dict]:
        """Find exact symbol definitions (class, function, method)."""
        return store.query_definitions(name, kind, path_filter)

    # ── tool: find_references ──────────────────────────────────────────
    @mcp.tool()
    def find_references(name: str, path_filter: str | None = None) -> list[dict]:
        """Find actual AST reference nodes (name, attribute, call)."""
        return store.query_references(name, path_filter)

    # ── tool: find_callers ─────────────────────────────────────────────
    @mcp.tool()
    def find_callers(func_name: str) -> list[dict]:
        """Find call sites for a function with enclosing scope."""
        return store.query_callers(func_name)

    # ── tool: find_string_literals ─────────────────────────────────────
    @mcp.tool()
    def find_string_literals(pattern: str, use_regex: bool = False,
                             limit: int = 30) -> list[dict]:
        """Find string literals matching a pattern."""
        return store.query_strings(pattern, use_regex, limit)

    # ── tool: find_importers ───────────────────────────────────────────
    @mcp.tool()
    def find_importers(module_name: str) -> list[dict]:
        """Find import statements for a module."""
        return store.query_importers(module_name)

    # ── tool: list_class_members ───────────────────────────────────────
    @mcp.tool()
    def list_class_members(class_name: str) -> list[dict]:
        """List methods/members of a class."""
        return store.query_class_members(class_name)

    # ── tool: file_symbols ─────────────────────────────────────────────
    @mcp.tool()
    def file_symbols(file_path: str) -> list[dict]:
        """List all indexed symbols in a file."""
        return store.query_file_symbols(file_path)

    # ── tool: lexical_search ───────────────────────────────────────────
    @mcp.tool()
    def lexical_search(query: str, limit: int = 30) -> list[dict]:
        """Full-text search across symbol names, docstrings and excerpts."""
        return store.lexical_search(query, limit)

    # ── tool: semantic_search ──────────────────────────────────────────
    @mcp.tool()
    def semantic_search(query: str, limit: int = 10) -> list[dict]:
        """Semantic vector search (requires external endpoint)."""
        if not semantic.enabled():
            return [{"error": "semantic search disabled. Set GENESIS_CODE_INDEX_SEMANTIC_URL to enable."}]
        return semantic.search(query, limit)

    # ── tool: reindex ──────────────────────────────────────────────────
    @mcp.tool()
    def reindex(path_filter: str | None = None) -> dict:
        """Full or incremental reindex. If path_filter set, only that subtree."""
        t0 = time.time()
        # Collect active file information
        active = set()
        reindexed = 0
        skipped = 0
        errors = 0

        for root_str in INDEXED_ROOTS:
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
                if path_filter and path_filter not in rel:
                    continue
                active.add(rel)
                stat = pyfile.stat()
                fhash = indexer_file_hash(pyfile)
                if store.file_exists_unchanged(rel, stat.st_mtime, fhash):
                    skipped += 1
                    continue
                syms, err = index_file(pyfile, repo_root)
                store.reset_file(rel)
                if err:
                    store.update_file(rel, stat.st_size, stat.st_mtime, fhash, err)
                    errors += 1
                else:
                    store.update_file(rel, stat.st_size, stat.st_mtime, fhash, None)
                    store.insert_symbols(rel, syms)
                    reindexed += 1

        store.remove_deleted_files(active)
        elapsed = time.time() - t0
        return {
            "reindexed": reindexed,
            "skipped": skipped,
            "errors": errors,
            "elapsed_seconds": round(elapsed, 2),
            "status": "degraded" if errors > 0 else "ok",
        }

    # ── tool: index_status ─────────────────────────────────────────────
    @mcp.tool()
    def index_status() -> dict:
        """Show code index database status."""
        stats = store.get_stats()
        stats["db_path"] = str(db_path)
        stats["semantic"] = semantic.status()
        return stats

    # ── tool: code_stats ───────────────────────────────────────────────
    @mcp.tool()
    def code_stats() -> dict:
        """Aggregate codebase statistics."""
        return store.get_stats()

    return mcp


def indexer_file_hash(pyfile: Path) -> str:
    import hashlib
    return hashlib.sha256(pyfile.read_bytes()).hexdigest()


def main_stdio() -> None:
    """Run the MCP stdio server."""
    import asyncio
    mcp = _build_mcp()
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main_stdio()

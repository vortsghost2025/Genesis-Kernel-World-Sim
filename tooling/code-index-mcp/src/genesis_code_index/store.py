"""SQLite + FTS5 storage layer for the code index."""

import sqlite3
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "genesis-code-index-v1"

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    file_hash TEXT NOT NULL,
    indexed_at REAL NOT NULL,
    parse_error TEXT,
    schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    line INTEGER NOT NULL,
    col INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    end_col INTEGER NOT NULL,
    enclosing_class TEXT DEFAULT '',
    enclosing_function TEXT DEFAULT '',
    ctx TEXT DEFAULT '',
    module TEXT DEFAULT '',
    as_name TEXT DEFAULT '',
    docstring TEXT DEFAULT '',
    bases TEXT DEFAULT '',
    decorators TEXT DEFAULT '',
    params TEXT DEFAULT '',
    value TEXT DEFAULT '',
    source_excerpt TEXT DEFAULT '',
    source_hash TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name, docstring, source_excerpt, value,
    content='symbols',
    content_rowid='id'
);

CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_enclosing ON symbols(enclosing_class, enclosing_function);

CREATE TABLE IF NOT EXISTS index_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class CodeIndexStore:
    """SQLite-backed code index with FTS5."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=OFF")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def initialize(self) -> None:
        conn = self.connect()
        conn.executescript(CREATE_SQL)
        conn.commit()
        self._set_meta("schema_version", SCHEMA_VERSION)
        self._set_meta("created_at", str(time.time()))

    def _set_meta(self, key: str, value: str) -> None:
        conn = self.connect()
        conn.execute(
            "INSERT OR REPLACE INTO index_meta(key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()

    def get_meta(self, key: str) -> str | None:
        conn = self.connect()
        row = conn.execute("SELECT value FROM index_meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def update_file(self, path: str, size: int, mtime: float,
                    file_hash: str, parse_error: str | None) -> None:
        conn = self.connect()
        conn.execute(
            """INSERT OR REPLACE INTO files
               (path, size, mtime, file_hash, indexed_at, parse_error, schema_version)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (path, size, mtime, file_hash, time.time(), parse_error, SCHEMA_VERSION),
        )
        conn.commit()

    def file_exists_unchanged(self, path: str, mtime: float, file_hash: str) -> bool:
        conn = self.connect()
        row = conn.execute(
            "SELECT file_hash FROM files WHERE path = ? AND mtime = ? AND parse_error IS NULL",
            (path, mtime),
        ).fetchone()
        if row and row["file_hash"] == file_hash:
            return True
        return False

    def reset_file(self, path: str) -> None:
        conn = self.connect()
        conn.execute("DELETE FROM symbols WHERE file_path = ?", (path,))
        conn.execute("DELETE FROM files WHERE path = ?", (path,))
        conn.commit()

    def insert_symbols(self, path: str, symbols: list[dict]) -> None:
        conn = self.connect()
        conn.execute("DELETE FROM symbols WHERE file_path = ?", (path,))
        for sym in symbols:
            conn.execute(
                """INSERT INTO symbols
                   (file_path, kind, name, line, col, end_line, end_col,
                    enclosing_class, enclosing_function, ctx, module, as_name,
                    docstring, bases, decorators, params, value,
                    source_excerpt, source_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    path, sym["kind"], sym.get("name", ""),
                    sym.get("line", 0), sym.get("col", 0),
                    sym.get("end_line", 0), sym.get("end_col", 0),
                    sym.get("enclosing_class", ""), sym.get("enclosing_function", ""),
                    sym.get("ctx", ""), sym.get("module", ""), sym.get("as_name", ""),
                    sym.get("docstring", ""), str(sym.get("bases", [])),
                    str(sym.get("decorators", [])), str(sym.get("params", [])),
                    sym.get("value", ""), sym.get("source_excerpt", ""),
                    sym["source_hash"],
                ),
            )
        conn.commit()

    def remove_deleted_files(self, active_paths: set[str]) -> None:
        conn = self.connect()
        existing = {r["path"] for r in conn.execute("SELECT path FROM files").fetchall()}
        deleted = existing - active_paths
        for path in deleted:
            conn.execute("DELETE FROM symbols WHERE file_path = ?", (path,))
            conn.execute("DELETE FROM files WHERE path = ?", (path,))
        if deleted:
            conn.commit()

    def query_definitions(self, name: str, kind: str | None = None,
                          path_filter: str | None = None) -> list[dict]:
        conn = self.connect()
        parts = ["kind IN ('class', 'function', 'async_function')", "name = ?"]
        params: list[Any] = [name]
        if kind:
            parts.append("kind = ?")
            params.append(kind)
        if path_filter:
            parts.append("file_path LIKE ?")
            params.append(f"%{path_filter}%")
        sql = f"SELECT * FROM symbols WHERE {' AND '.join(parts)} ORDER BY file_path, line"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def query_references(self, name: str, path_filter: str | None = None) -> list[dict]:
        conn = self.connect()
        parts = ["kind IN ('name_ref', 'attr_ref', 'call')", "name = ?"]
        params: list[Any] = [name]
        if path_filter:
            parts.append("file_path LIKE ?")
            params.append(f"%{path_filter}%")
        sql = f"SELECT * FROM symbols WHERE {' AND '.join(parts)} ORDER BY file_path, line"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def query_callers(self, func_name: str) -> list[dict]:
        """Find call sites for a function, including enclosing scope."""
        conn = self.connect()
        rows = conn.execute(
            """SELECT * FROM symbols
               WHERE kind = 'call' AND name = ?
               ORDER BY file_path, line""",
            (func_name,),
        ).fetchall()
        # Enrich with enclosing scope
        results = []
        for r in rows:
            d = dict(r)
            d["enclosing_function"] = self._resolve_enclosing(
                r["file_path"], r["line"], "function"
            )
            d["enclosing_class"] = self._resolve_enclosing(
                r["file_path"], r["line"], "class"
            )
            results.append(d)
        return results

    def query_strings(self, pattern: str, use_regex: bool = False, limit: int = 30) -> list[dict]:
        conn = self.connect()
        if use_regex:
            try:
                rows = conn.execute(
                    """SELECT * FROM symbols
                       WHERE kind = 'string_literal' AND value REGEXP ?
                       ORDER BY file_path, line LIMIT ?""",
                    (pattern, limit),
                ).fetchall()
                return [dict(r) for r in rows]
            except sqlite3.OperationalError:
                pass  # Fall through to FTS
        # FTS5 or LIKE fallback
        try:
            rows = conn.execute(
                """SELECT s.* FROM symbols_fts f
                   JOIN symbols s ON s.id = f.rowid
                   WHERE symbols_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (f'"*{pattern}*"', limit),
            ).fetchall()
            if rows:
                return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            pass
        # LIKE fallback
        rows = conn.execute(
            """SELECT * FROM symbols
               WHERE kind = 'string_literal' AND value LIKE ?
               ORDER BY file_path, line LIMIT ?""",
            (f"%{pattern}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def query_importers(self, module_name: str) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT * FROM symbols
               WHERE kind IN ('import', 'from_import')
               AND (name = ? OR module = ? OR as_name = ?)
               ORDER BY file_path, line""",
            (module_name, module_name, module_name),
        ).fetchall()
        return [dict(r) for r in rows]

    def query_class_members(self, class_name: str) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT * FROM symbols
               WHERE kind IN ('function', 'async_function')
               AND enclosing_class = ?
               ORDER BY line""",
            (class_name,),
        ).fetchall()
        return [dict(r) for r in rows]

    def query_file_symbols(self, file_path: str) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT * FROM symbols
               WHERE file_path = ?
               ORDER BY line""",
            (file_path,),
        ).fetchall()
        return [dict(r) for r in rows]

    def lexical_search(self, query: str, limit: int = 30) -> list[dict]:
        """Full-text search across names, docstrings, and source excerpts."""
        conn = self.connect()
        try:
            rows = conn.execute(
                """SELECT s.* FROM symbols_fts f
                   JOIN symbols s ON s.id = f.rowid
                   WHERE symbols_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limit),
            ).fetchall()
            if rows:
                return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            pass
        # LIKE fallback
        rows = conn.execute(
            """SELECT * FROM symbols
               WHERE name LIKE ? OR source_excerpt LIKE ?
               ORDER BY file_path, line LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def _resolve_enclosing(self, file_path: str, line: int, kind: str) -> str:
        """Find the enclosing function or class for a given line."""
        conn = self.connect()
        kind_map = {"function": "function", "async_function": "function", "class": "class"}
        db_kind = kind_map.get(kind, kind)
        row = conn.execute(
            """SELECT name FROM symbols
               WHERE file_path = ? AND kind = ?
                 AND line <= ? AND end_line >= ?
               ORDER BY line DESC LIMIT 1""",
            (file_path, db_kind if db_kind != "class" else "class", line, line),
        ).fetchone()
        return row["name"] if row else ""

    def get_stats(self) -> dict:
        conn = self.connect()
        files = conn.execute("SELECT COUNT(*) as c FROM files").fetchone()["c"]
        symbols = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]
        errors = conn.execute(
            "SELECT COUNT(*) as c FROM files WHERE parse_error IS NOT NULL"
        ).fetchone()["c"]
        return {
            "files": files,
            "symbols": symbols,
            "parse_errors": errors,
            "schema_version": self.get_meta("schema_version") or "unknown",
        }

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

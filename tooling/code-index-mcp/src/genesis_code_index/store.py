"""SQLite + FTS5 storage layer for the code index."""

import re as _re
import sqlite3
import time
from pathlib import Path
from typing import Any


def _path_matches_filter(file_path: str, path_filter: str) -> bool:
    """Component-aware scope check: path_filter must equal a path component
    or be a proper prefix (separator-boundary, not substring)."""
    nf = path_filter.replace("\\", "/").strip("/")
    fp = file_path.replace("\\", "/")
    return fp == nf or fp.startswith(nf + "/")


SCHEMA_VERSION = "genesis-code-index-v2"

CREATE_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

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
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_enclosing ON symbols(enclosing_class, enclosing_function);

CREATE TABLE IF NOT EXISTS index_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parse_failures (
    path TEXT PRIMARY KEY,
    attempted_hash TEXT NOT NULL,
    attempted_at REAL NOT NULL,
    error_message TEXT NOT NULL,
    previous_valid_hash TEXT NOT NULL
);
"""

# FTS synchronization triggers (external-content)
FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS trg_symbols_fts_insert AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, docstring, source_excerpt, value)
    VALUES (new.id, new.name, new.docstring, new.source_excerpt, new.value);
END;

CREATE TRIGGER IF NOT EXISTS trg_symbols_fts_delete AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, docstring, source_excerpt, value)
    VALUES ('delete', old.id, old.name, old.docstring, old.source_excerpt, old.value);
END;

CREATE TRIGGER IF NOT EXISTS trg_symbols_fts_update AFTER UPDATE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, docstring, source_excerpt, value)
    VALUES ('delete', old.id, old.name, old.docstring, old.source_excerpt, old.value);
    INSERT INTO symbols_fts(rowid, name, docstring, source_excerpt, value)
    VALUES (new.id, new.name, new.docstring, new.source_excerpt, new.value);
END;
"""

# SQLite REGEXP function
def _regexp(pattern: str, value: str) -> int:
    return 1 if _re.search(pattern, str(value)) else 0


class CodeIndexStore:
    """SQLite-backed code index with FTS5."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.create_function("REGEXP", 2, _regexp)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def initialize(self) -> None:
        conn = self.connect()
        conn.executescript(CREATE_SQL)
        # Create FTS triggers (run separately to avoid script limitation)
        conn.executescript(FTS_TRIGGERS)
        conn.commit()
        existing = self.get_meta("schema_version")
        if existing and existing != SCHEMA_VERSION:
            self._migrate(existing)
        self._set_meta("schema_version", SCHEMA_VERSION)
        self._set_meta("created_at", str(time.time()))

    def _migrate(self, from_version: str) -> None:
        """Rebuild the index on schema version mismatch."""
        conn = self.connect()
        # V1 used synchronous=OFF and foreign_keys=OFF and no FTS triggers
        # A clean rebuild is safest
        if from_version < SCHEMA_VERSION:
            conn.executescript("""
                DROP TABLE IF EXISTS symbols_fts;
                DROP TABLE IF EXISTS parse_failures;
                DROP TRIGGER IF EXISTS trg_symbols_fts_insert;
                DROP TRIGGER IF EXISTS trg_symbols_fts_delete;
                DROP TRIGGER IF EXISTS trg_symbols_fts_update;
            """)
            conn.executescript(CREATE_SQL)
            conn.executescript(FTS_TRIGGERS)
            conn.commit()

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

    def file_exists_unchanged(self, path: str, mtime: float, file_hash: str) -> bool:
        conn = self.connect()
        row = conn.execute(
            "SELECT file_hash FROM files WHERE path = ? AND mtime = ? AND parse_error IS NULL",
            (path, mtime),
        ).fetchone()
        return bool(row and row["file_hash"] == file_hash)

    def replace_file_index(self, path: str, size: int, mtime: float,
                           file_hash: str, symbols: list[dict],
                           parse_error: str | None = None) -> None:
        """Atomic replacement: in one transaction, update file metadata,
        delete old symbols, insert new symbols, clear parse failures,
        and commit.  FTS triggers handle index synchronization."""
        conn = self.connect()
        conn.execute("BEGIN")
        try:
            conn.execute(
                """INSERT OR REPLACE INTO files
                   (path, size, mtime, file_hash, indexed_at, parse_error, schema_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (path, size, mtime, file_hash, time.time(), parse_error, SCHEMA_VERSION),
            )
            conn.execute("DELETE FROM symbols WHERE file_path = ?", (path,))
            conn.execute("DELETE FROM parse_failures WHERE path = ?", (path,))
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
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def record_parse_failure(self, path: str, attempted_hash: str,
                             previous_valid_hash: str, error: str) -> None:
        conn = self.connect()
        conn.execute(
            """INSERT OR REPLACE INTO parse_failures
               (path, attempted_hash, attempted_at, error_message, previous_valid_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (path, attempted_hash, time.time(), error[:500], previous_valid_hash),
        )
        conn.commit()
        # Mark the file metadata with the error
        conn.execute(
            "UPDATE files SET parse_error = ? WHERE path = ?",
            (error[:500], path),
        )
        conn.commit()

    def get_failure_count(self) -> int:
        conn = self.connect()
        row = conn.execute("SELECT COUNT(*) as c FROM parse_failures").fetchone()
        return row["c"] if row else 0

    def get_failures(self, limit: int = 20) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM parse_failures ORDER BY attempted_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_file(self, path: str) -> dict | None:
        conn = self.connect()
        row = conn.execute("SELECT * FROM files WHERE path = ?", (path,)).fetchone()
        return dict(row) if row else None

    def query_definitions(self, name: str, kind: str | None = None,
                          path_filter: str | None = None) -> list[dict]:
        conn = self.connect()
        parts = ["kind IN ('class', 'function', 'async_function')", "name = ?"]
        params: list[Any] = [name]
        if kind:
            parts.append("kind = ?")
            params.append(kind)
        rows = conn.execute(
            f"SELECT * FROM symbols WHERE {' AND '.join(parts)} ORDER BY file_path, line",
            params,
        ).fetchall()
        if path_filter:
            rows = [r for r in rows if _path_matches_filter(r["file_path"], path_filter)]
        return [dict(r) for r in rows]

    def query_references(self, name: str, path_filter: str | None = None) -> list[dict]:
        conn = self.connect()
        parts = ["kind IN ('name_ref', 'attr_ref', 'call')", "name = ?"]
        params: list[Any] = [name]
        rows = conn.execute(
            f"SELECT * FROM symbols WHERE {' AND '.join(parts)} ORDER BY file_path, line",
            params,
        ).fetchall()
        if path_filter:
            rows = [r for r in rows if _path_matches_filter(r["file_path"], path_filter)]
        return [dict(r) for r in rows]

    def query_callers(self, func_name: str) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT * FROM symbols
               WHERE kind = 'call' AND name = ?
               ORDER BY file_path, line""",
            (func_name,),
        ).fetchall()
        return [dict(r) for r in rows]

    def query_strings(self, pattern: str, use_regex: bool = False, limit: int = 30) -> list[dict]:
        conn = self.connect()
        if use_regex:
            try:
                _re.compile(pattern)  # Validate
            except _re.error as e:
                return [{"error": f"invalid regex: {e}"}]
            rows = conn.execute(
                """SELECT * FROM symbols
                   WHERE kind = 'string_literal' AND value REGEXP ?
                   ORDER BY file_path, line LIMIT ?""",
                (pattern, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        # Literal substring via FTS (exact phrase if quoted, else LIKE)
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
        """FTS5 full-text search. Falls back to LIKE only when FTS returns empty."""
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
        rows = conn.execute(
            """SELECT * FROM symbols
               WHERE name LIKE ? OR source_excerpt LIKE ?
               ORDER BY file_path, line LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def remove_deleted_files(self, active_paths: set[str],
                             scope_prefixes: set[str] | None = None) -> int:
        """Remove files and symbols for paths no longer on disk.

        When scope_prefixes is provided, only files under those prefixes are
        eligible for deletion.  Prefix matching uses path-component semantics
        (``prefix/name`` does not match ``prefix/another/name`` as a prefix,
        but it does match ``prefix/name`` itself).

        An empty active_paths set with scope_prefixes removes every file
        within scope.  An empty active_paths without scope_prefixes removes
        every indexed file.
        """
        conn = self.connect()
        existing = {r["path"] for r in
                    conn.execute("SELECT path FROM files").fetchall()}

        # Limit to scope when provided
        if scope_prefixes:
            scoped = set()
            for ep in existing:
                for sp in scope_prefixes:
                    norm_sp = sp.replace("\\", "/").rstrip("/")
                    norm_ep = ep.replace("\\", "/")
                    if norm_ep == norm_sp or norm_ep.startswith(norm_sp + "/"):
                        scoped.add(ep)
                        break
            existing = scoped

        deleted = existing - active_paths
        for path in deleted:
            conn.execute("DELETE FROM symbols WHERE file_path = ?", (path,))
            conn.execute("DELETE FROM files WHERE path = ?", (path,))
            conn.execute("DELETE FROM parse_failures WHERE path = ?", (path,))
        if deleted:
            conn.commit()
        return len(deleted)

    def fts_stats(self) -> dict:
        conn = self.connect()
        try:
            row = conn.execute("SELECT COUNT(*) as c FROM symbols_fts").fetchone()
            fts_count = row["c"] if row else 0
            fts_ok = True
        except sqlite3.OperationalError:
            fts_count = 0
            fts_ok = False
        return {
            "fts_available": fts_ok,
            "fts_enabled": fts_ok,
            "indexed_fts_rows": fts_count,
            "fallback_mode": not fts_ok,
        }

    def get_stats(self) -> dict:
        conn = self.connect()
        files = conn.execute("SELECT COUNT(*) as c FROM files").fetchone()["c"]
        symbols = conn.execute("SELECT COUNT(*) as c FROM symbols").fetchone()["c"]
        fts = self.fts_stats()
        failures = self.get_failure_count()
        return {
            "files": files,
            "symbols": symbols,
            "parse_errors": failures,
            "fts": fts,
            "schema_version": self.get_meta("schema_version") or "unknown",
        }

    def close(self) -> None:
        if self._conn:
            self._conn.execute("PRAGMA optimize")
            self._conn.close()
            self._conn = None

"""Incremental AST indexer with scope tracking and parse-failure resilience."""

import ast
import hashlib
from pathlib import Path
from typing import Any


SKIP_DIRS = frozenset({
    ".git", ".runtime", ".code-index", "node_modules",
    "__pycache__", ".venv", ".mypy_cache", ".ruff_cache",
    ".basedpyright", ".pytest_cache",
})

INDEXED_ROOTS = frozenset({"world-sim/backend", "world-sim/scripts", "world-sim/tests"})


def _is_under_repo_root(path: Path, repo_root: Path) -> bool:
    try:
        path.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False


def _is_indexed(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
        rel_str = rel.as_posix()
        return any(rel_str == r or rel_str.startswith(r + "/") for r in INDEXED_ROOTS)
    except ValueError:
        return False


def resolve_path_scope(path_filter: str, repo_root: Path) -> str:
    """Validate and normalize a path_filter against INDEXED_ROOTS.

    Resolves ``..`` traversal and symlinks, then checks the result stays
    within an indexed root.  Raises ``ValueError`` on escape; returns the
    normalized POSIX relative path on success.
    """
    resolved = (repo_root / path_filter).resolve()
    rel = resolved.relative_to(repo_root.resolve())
    rel_str = rel.as_posix()
    if not any(rel_str == r or rel_str.startswith(r + "/") for r in INDEXED_ROOTS):
        raise ValueError(
            f"path_filter '{path_filter}' resolves to '{rel_str}' "
            f"which is not under any indexed root"
        )
    return rel_str


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk_ast(tree: ast.AST, filename: str, source: str) -> list[dict]:
    """Walk AST with explicit scope tracking."""
    symbols: list[dict] = []
    scope_stack: list[str] = []

    class _Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            doc = ast.get_docstring(node) or ""
            symbols.append({
                "kind": "class",
                "name": node.name,
                "file": filename,
                "line": node.lineno,
                "col": node.col_offset,
                "end_line": node.end_lineno or node.lineno,
                "end_col": node.end_col_offset or node.col_offset,
                "enclosing_class": scope_stack[-1] if scope_stack else "",
                "enclosing_function": "",
                "docstring": doc[:200],
                "bases": [ast.unparse(b) for b in node.bases],
                "source_hash": "",
            })
            scope_stack.append(node.name)
            self.generic_visit(node)
            scope_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._handle_function(node, is_async=False)

        def visit_AsyncFunctionDef(self, node: ast.FunctionDef) -> None:
            self._handle_function(node, is_async=True)

        def _handle_function(self, node: ast.FunctionDef, is_async: bool) -> None:
            doc = ast.get_docstring(node) or ""
            enclosing_cls = scope_stack[-1] if scope_stack else ""
            symbols.append({
                "kind": "async_function" if is_async else "function",
                "name": node.name,
                "file": filename,
                "line": node.lineno,
                "col": node.col_offset,
                "end_line": node.end_lineno or node.lineno,
                "end_col": node.end_col_offset or node.col_offset,
                "enclosing_class": enclosing_cls,
                "enclosing_function": "",
                "docstring": doc[:200],
                "decorators": [ast.unparse(d) for d in node.decorator_list],
                "params": [ast.unparse(a) for a in node.args.args],
                "source_hash": "",
            })
            scope_stack.append(node.name)
            self.generic_visit(node)
            scope_stack.pop()

        def visit_Name(self, node: ast.Name) -> None:
            enclosing_cls = scope_stack[-1] if scope_stack else ""
            symbols.append({
                "kind": "name_ref",
                "name": node.id,
                "file": filename,
                "line": node.lineno,
                "col": node.col_offset,
                "end_line": node.end_lineno or node.lineno,
                "end_col": node.end_col_offset or node.col_offset,
                "enclosing_class": enclosing_cls,
                "enclosing_function": "",
                "ctx": type(node.ctx).__name__.replace("Load", "load").replace("Store", "store").replace("Del", "del"),
                "source_hash": "",
            })

        def visit_Attribute(self, node: ast.Attribute) -> None:
            enclosing_cls = scope_stack[-1] if scope_stack else ""
            symbols.append({
                "kind": "attr_ref",
                "name": f"{ast.unparse(node.value)}.{node.attr}",
                "file": filename,
                "line": node.lineno,
                "col": node.col_offset,
                "end_line": node.end_lineno or node.lineno,
                "end_col": node.end_col_offset or node.col_offset,
                "enclosing_class": enclosing_cls,
                "enclosing_function": "",
                "ctx": type(node.ctx).__name__.replace("Load", "load").replace("Store", "store").replace("Del", "del"),
                "source_hash": "",
            })

        def visit_Call(self, node: ast.Call) -> None:
            enclosing_cls = scope_stack[-1] if scope_stack else ""
            try:
                callee = ast.unparse(node.func)
            except Exception:
                callee = "<unparseable>"
            symbols.append({
                "kind": "call",
                "name": callee,
                "file": filename,
                "line": node.lineno,
                "col": node.col_offset,
                "end_line": node.end_lineno or node.lineno,
                "end_col": node.end_col_offset or node.col_offset,
                "enclosing_class": enclosing_cls,
                "enclosing_function": "",
                "source_hash": "",
            })

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                symbols.append(self._import_sym(alias, filename, node.lineno, "import"))

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            mod = node.module or ""
            for alias in node.names:
                symbols.append(self._import_sym(alias, filename, node.lineno, "from_import", module=mod))

        @staticmethod
        def _import_sym(alias: ast.alias, filename: str, lineno: int,
                        kind: str, module: str = "") -> dict:
            return {
                "kind": kind,
                "name": alias.name,
                "as_name": alias.asname or alias.name,
                "file": filename,
                "line": lineno,
                "col": 0,
                "end_line": lineno,
                "end_col": 0,
                "enclosing_class": "",
                "enclosing_function": "",
                "module": module,
                "source_hash": "",
            }

        def visit_Constant(self, node: ast.Constant) -> None:
            if isinstance(node.value, str) and len(node.value.strip()) >= 4:
                enclosing_cls = scope_stack[-1] if scope_stack else ""
                val = node.value[:200]
                symbols.append({
                    "kind": "string_literal",
                    "name": val,
                    "value": val,
                    "file": filename,
                    "line": node.lineno,
                    "col": node.col_offset,
                    "end_line": node.end_lineno or node.lineno,
                    "end_col": node.end_col_offset or node.col_offset,
                    "enclosing_class": enclosing_cls,
                    "enclosing_function": "",
                    "source_hash": "",
                })

    _Visitor().visit(tree)
    return symbols


def index_file(path: Path, repo_root: Path) -> tuple[list[dict], str | None]:
    """Index a single Python file. Returns (symbols, error_string_or_None)."""
    if not _is_under_repo_root(path, repo_root):
        return [], f"path outside repo: {path}"
    if not _is_indexed(path, repo_root):
        return [], f"path not in indexed roots: {path}"
    if path.suffix != ".py":
        return [], "not a Python file"

    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        return [], f"read error: {e}"

    fhash = _file_hash(path)
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        return [], f"syntax error: {e}"

    rel = str(path.resolve().relative_to(repo_root.resolve()).as_posix())
    symbols = _walk_ast(tree, rel, source)
    for s in symbols:
        s["source_hash"] = fhash
        # Add source excerpt
        lines = source.split("\n")
        excerpt_lines = lines[max(0, s["line"] - 2):s["end_line"] + 1]
        s["source_excerpt"] = "\n".join(excerpt_lines)[:300]
    return symbols, None


def index_repo(repo_root: Path, file_filter: set[Path] | None = None) -> dict:
    """Index all Python files under indexed roots.

    If file_filter is set, only index those paths.
    Returns {relative_posix_path: (symbols, error_or_None)}.
    """
    result: dict[str, tuple[list[dict], str | None]] = {}
    roots_to_scan = [repo_root / r for r in INDEXED_ROOTS]

    for root in roots_to_scan:
        if not root.exists():
            continue
        for pyfile in sorted(root.rglob("*.py")):
            if any(part in SKIP_DIRS for part in pyfile.parts):
                continue
            if file_filter and pyfile not in file_filter:
                continue
            try:
                rel = str(pyfile.resolve().relative_to(repo_root.resolve()).as_posix())
            except ValueError:
                continue
            syms, err = index_file(pyfile, repo_root)
            result[rel] = (syms, err)

    return result

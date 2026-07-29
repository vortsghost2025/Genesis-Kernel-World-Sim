"""CLI entry point for genesis-code-index."""

import argparse
import hashlib
import sys
import time
from pathlib import Path


def _file_hash(pyfile: Path) -> str:
    return hashlib.sha256(pyfile.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Genesis code index")
    parser.add_argument("--repo-root", default="",
                        help="Repository root path (default: auto-detect)")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("reindex", help="Rebuild the code index")
    sub.add_parser("status", help="Show index status")

    args = parser.parse_args()

    from genesis_code_index.server import _resolve_repo_root
    from genesis_code_index.indexer import index_file, SKIP_DIRS, INDEXED_ROOTS
    from genesis_code_index.store import CodeIndexStore

    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        repo_root = _resolve_repo_root()

    db_path = repo_root / ".code-index" / "index.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = CodeIndexStore(db_path)
    store.initialize()

    if args.command == "reindex":
        t0 = time.time()
        reindexed = 0
        skipped = 0
        errors = 0
        active: set[str] = set()

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
                active.add(rel)
                stat = pyfile.stat()
                fhash = _file_hash(pyfile)
                if store.file_exists_unchanged(rel, stat.st_mtime, fhash):
                    skipped += 1
                    continue
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

        store.remove_deleted_files(active)
        elapsed = time.time() - t0
        stats = store.get_stats()
        print(f"Reindexed {reindexed} files, skipped {skipped}, errors {errors}")
        print(f"Elapsed: {elapsed:.2f}s")
        print(f"Files: {stats['files']}, Symbols: {stats['symbols']}")
        print(f"FTS: {stats['fts']}")
        if errors:
            print("Index status: DEGRADED (parse errors)")
        else:
            print("Index status: OK")

    elif args.command == "status":
        stats = store.get_stats()
        print(f"Files:         {stats['files']}")
        print(f"Symbols:       {stats['symbols']}")
        print(f"Parse errors:  {stats['parse_errors']}")
        print(f"DB path:       {db_path}")
        print(f"Schema:        {stats['schema_version']}")
        fts = stats.get("fts", {})
        print(f"FTS available: {fts.get('fts_available', False)}")
        print(f"FTS rows:      {fts.get('indexed_fts_rows', 0)}")
        failures = store.get_failures(5)
        if failures:
            print(f"Recent failures: {len(failures)}")
            for f in failures:
                print(f"  {f['path']}: {f['error_message'][:80]}")
        if stats['parse_errors']:
            print("Status: DEGRADED")
        else:
            print("Status: OK")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

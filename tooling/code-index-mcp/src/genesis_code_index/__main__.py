"""CLI entry point for genesis-code-index."""

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Genesis code index")
    parser.add_argument("--repo-root", default="",
                        help="Repository root path (default: auto-detect)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("reindex", help="Rebuild the code index")
    sub.add_parser("status", help="Show index status")

    args = parser.parse_args()

    from genesis_code_index.server import _resolve_repo_root, _build_mcp, indexer_file_hash
    from genesis_code_index.indexer import index_file, index_repo, SKIP_DIRS, INDEXED_ROOTS
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
        import time
        t0 = time.time()
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
        print(f"Reindexed {reindexed} files, skipped {skipped}, errors {errors}")
        print(f"Elapsed: {elapsed:.2f}s")
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
        if stats['parse_errors']:
            print("Status: DEGRADED")
        else:
            print("Status: OK")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

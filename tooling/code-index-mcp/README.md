# Genesis Code Index MCP

AST-based, SQLite-backed, MCP-served code index for the Genesis Kernel World Sim.

## Quick start

```bash
# Reindex from scratch
cd world-sim && python -m genesis_code_index --repo-root "S:/Genesis Kernel World Sim" reindex

# Show index status
cd world-sim && python -m genesis_code_index --repo-root "S:/Genesis Kernel World Sim" status

# Start MCP stdio server
cd world-sim && python -m genesis_code_index.server
```

## MCP tools

| Tool | Description |
|---|---|
| `find_definition` | Find exact symbol definitions |
| `find_references` | Find AST reference nodes |
| `find_callers` | Find call sites with enclosing scope |
| `find_string_literals` | Find string literals (substring or regex) |
| `find_importers` | Find import statements |
| `list_class_members` | List methods of a class |
| `file_symbols` | List all symbols in a file |
| `lexical_search` | FTS5 full-text search |
| `semantic_search` | Optional vector search (requires external endpoint) |
| `reindex` | Full or incremental reindex |
| `index_status` | Database status |
| `code_stats` | Aggregate statistics |

## Semantic adapter

Set `GENESIS_CODE_INDEX_SEMANTIC_URL` to enable vector search against an
existing endpoint.  The adapter expects a `POST /search` with JSON body
`{"query": ..., "collection": ..., "limit": ...}`.

## OpenCode integration

Add to `opencode.jsonc`:

```json
{
  "mcp": {
    "genesis-code-index": {
      "type": "local",
      "command": ["python", "-m", "genesis_code_index.server"],
      "cwd": "world-sim"
    }
  }
}
```

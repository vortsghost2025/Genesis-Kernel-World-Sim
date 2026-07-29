"""Semantic search adapter — optional external vector backend."""

import json
import os
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError


ENV_URL = "GENESIS_CODE_INDEX_SEMANTIC_URL"
ENV_COLLECTION = "GENESIS_CODE_INDEX_SEMANTIC_COLLECTION"
ENV_TIMEOUT = "GENESIS_CODE_INDEX_SEMANTIC_TIMEOUT"

_DEFAULT_TIMEOUT = 10


class SemanticSearchBackend:
    """Abstract semantic search backend."""

    def enabled(self) -> bool:
        return False

    def search(self, query: str, limit: int = 10) -> list[dict]:
        raise NotImplementedError

    def status(self) -> dict:
        return {"enabled": False, "type": "none"}


class DisabledSemanticBackend(SemanticSearchBackend):
    def status(self) -> dict:
        return {"enabled": False, "type": "disabled",
                "hint": "Set GENESIS_CODE_INDEX_SEMANTIC_URL to enable"}


class HttpSemanticBackend(SemanticSearchBackend):
    """Adapter for a compatible HTTP vector-search endpoint."""

    def __init__(self, url: str, collection: str, timeout: int = _DEFAULT_TIMEOUT):
        self._url = url.rstrip("/")
        self._collection = collection
        self._timeout = timeout

    def enabled(self) -> bool:
        return True

    def search(self, query: str, limit: int = 10) -> list[dict]:
        payload = json.dumps({
            "query": query,
            "collection": self._collection,
            "limit": limit,
        }).encode()
        req = Request(
            f"{self._url}/search",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urlopen(req, timeout=self._timeout)
            data = json.loads(resp.read().decode())
            results = data.get("results", data if isinstance(data, list) else [])
            return [
                {
                    "path": r.get("path", ""),
                    "line": r.get("line", 0),
                    "score": r.get("score", 0.0),
                    "excerpt": r.get("excerpt", ""),
                    "source_hash": r.get("source_hash", ""),
                }
                for r in results[:limit]
            ]
        except (URLError, json.JSONDecodeError, OSError) as e:
            return [{"error": f"semantic search failed: {e}"}]

    def status(self) -> dict:
        return {"enabled": True, "type": "http",
                "url": self._url, "collection": self._collection}


def create_semantic_backend() -> SemanticSearchBackend:
    """Factory that reads environment variables."""
    url = os.environ.get(ENV_URL, "").strip()
    collection = os.environ.get(ENV_COLLECTION, "code-index").strip()
    if not url:
        return DisabledSemanticBackend()
    try:
        timeout = int(os.environ.get(ENV_TIMEOUT, str(_DEFAULT_TIMEOUT)).strip())
    except (ValueError, TypeError):
        timeout = _DEFAULT_TIMEOUT
    return HttpSemanticBackend(url, collection, timeout)

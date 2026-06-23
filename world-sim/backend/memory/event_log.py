"""
Event log — persists simulation events to JSONL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EventLog:
    """Append-only event log persisted to JSONL."""

    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = log_path or Path("data/events.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.events: list[dict[str, Any]] = []

    def append(self, event: dict[str, Any]) -> None:
        """Append an event to the log and persist."""
        self.events.append(event)
        self._persist(event)

    def _persist(self, event: dict[str, Any]) -> None:
        """Append a single event to the JSONL file."""
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def load_all(self) -> list[dict[str, Any]]:
        """Load all events from the JSONL file."""
        if not self.log_path.exists():
            return []
        events = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        self.events = events
        return events

    def recent(self, n: int = 50) -> list[dict[str, Any]]:
        """Return the n most recent events."""
        return self.events[-n:] if self.events else []

    def by_agent(self, agent_name: str) -> list[dict[str, Any]]:
        """Return all events for a specific agent."""
        return [e for e in self.events if e.get("agent") == agent_name]

    def clear(self) -> None:
        """Clear the event log."""
        self.events = []
        if self.log_path.exists():
            self.log_path.unlink()

    def summary(self) -> dict[str, Any]:
        """Return a summary of the event log."""
        by_agent: dict[str, int] = {}
        for event in self.events:
            agent = event.get("agent", "unknown")
            by_agent[agent] = by_agent.get(agent, 0) + 1

        return {
            "total_events": len(self.events),
            "by_agent": by_agent,
            "latest_tick": self.events[-1].get("tick", 0) if self.events else 0,
        }

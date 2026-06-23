"""
Persistent Memory System for World Sim Agents.

Each agent has their own long-term memory that persists across sessions.
Memories are stored as JSON files and can be retrieved, consolidated, and searched.

Memory types:
- event: Something that happened
- idea: A thought or concept the agent developed
- relationship: Feelings about another agent
- skill: Something the agent learned to do
- observation: Something the agent noticed about the world
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Memory:
    """A single memory entry."""
    id: str
    agent_name: str
    memory_type: str  # event, idea, relationship, skill, observation
    content: str
    tick: int
    timestamp: float = field(default_factory=time.time)
    importance: float = 1.0  # 0.0 to 1.0, how important this memory is
    accessed_count: int = 0
    last_accessed: float = 0.0
    related_memories: list[str] = field(default_factory=list)  # IDs of related memories

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "memory_type": self.memory_type,
            "content": self.content,
            "tick": self.tick,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "accessed_count": self.accessed_count,
            "last_accessed": self.last_accessed,
            "related_memories": self.related_memories,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Memory":
        return cls(
            id=data["id"],
            agent_name=data["agent_name"],
            memory_type=data["memory_type"],
            content=data["content"],
            tick=data["tick"],
            timestamp=data.get("timestamp", time.time()),
            importance=data.get("importance", 1.0),
            accessed_count=data.get("accessed_count", 0),
            last_accessed=data.get("last_accessed", 0.0),
            related_memories=data.get("related_memories", []),
        )


class PersistentMemory:
    """
    Persistent memory store for an agent.
    
    Memories are saved to disk and loaded on startup.
    Supports retrieval by type, recency, importance, and relevance.
    """

    def __init__(self, agent_name: str, storage_dir: Path | None = None) -> None:
        self.agent_name = agent_name
        self.storage_dir = storage_dir or Path("data/memories")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.storage_dir / f"{agent_name.lower()}_memories.json"
        self.memories: list[Memory] = []
        self.whispers: list[dict[str, Any]] = []
        self._next_id = 0
        
        # Load existing memories
        self._load()

    def _load(self) -> None:
        """Load memories from disk."""
        if self.memory_file.exists():
            data = json.loads(self.memory_file.read_text(encoding="utf-8"))
            self.memories = [Memory.from_dict(m) for m in data.get("memories", [])]
            self.whispers = data.get("whispers", [])
            self._next_id = data.get("next_id", len(self.memories))

    def _save(self) -> None:
        """Save memories to disk."""
        data = {
            "agent_name": self.agent_name,
            "next_id": self._next_id,
            "memories": [m.to_dict() for m in self.memories],
            "whispers": self.whispers,
        }
        self.memory_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(
        self,
        memory_type: str,
        content: str,
        tick: int,
        importance: float = 1.0,
        related_ids: list[str] | None = None,
    ) -> Memory:
        """Add a new memory."""
        memory = Memory(
            id=f"{self.agent_name.lower()}_{self._next_id}",
            agent_name=self.agent_name,
            memory_type=memory_type,
            content=content,
            tick=tick,
            importance=importance,
            related_memories=related_ids or [],
        )
        self.memories.append(memory)
        self._next_id += 1
        self._save()
        return memory

    def add_event(self, content: str, tick: int, importance: float = 1.0) -> Memory:
        """Add an event memory."""
        return self.add("event", content, tick, importance)

    def add_idea(self, content: str, tick: int, importance: float = 1.0) -> Memory:
        """Add an idea memory."""
        return self.add("idea", content, tick, importance)

    def add_relationship(self, content: str, tick: int, importance: float = 1.0) -> Memory:
        """Add a relationship memory."""
        return self.add("relationship", content, tick, importance)

    def add_skill(self, content: str, tick: int, importance: float = 1.0) -> Memory:
        """Add a skill memory."""
        return self.add("skill", content, tick, importance)

    def add_observation(self, content: str, tick: int, importance: float = 1.0) -> Memory:
        """Add an observation memory."""
        return self.add("observation", content, tick, importance)

    def get_recent(self, n: int = 10) -> list[Memory]:
        """Get the n most recent memories."""
        return sorted(self.memories, key=lambda m: m.tick, reverse=True)[:n]

    def get_by_type(self, memory_type: str) -> list[Memory]:
        """Get all memories of a specific type."""
        return [m for m in self.memories if m.memory_type == memory_type]

    def get_important(self, n: int = 5, min_importance: float = 0.7) -> list[Memory]:
        """Get the n most important memories above a threshold."""
        important = [m for m in self.memories if m.importance >= min_importance]
        return sorted(important, key=lambda m: m.importance, reverse=True)[:n]

    def get_context_for_prompt(self, tick: int, max_memories: int = 5) -> str:
        """
        Get relevant memories for building an agent prompt.
        
        Returns a formatted string of recent and important memories.
        """
        # Get recent memories (last 10 ticks)
        recent = [m for m in self.memories if m.tick > tick - 10]
        
        # Get important memories
        important = self.get_important(3, min_importance=0.7)
        
        # Combine and deduplicate
        seen_ids = set()
        context_memories = []
        for m in recent + important:
            if m.id not in seen_ids:
                seen_ids.add(m.id)
                context_memories.append(m)
        
        # Sort by tick (most recent first)
        context_memories.sort(key=lambda m: m.tick, reverse=True)
        context_memories = context_memories[:max_memories]
        
        if not context_memories:
            return "You have no memories yet."
        
        lines = ["Your memories:"]
        for m in context_memories:
            lines.append(f"- [{m.memory_type}] (tick {m.tick}): {m.content}")
        
        return "\n".join(lines)

    def consolidate(self, max_memories: int = 100) -> None:
        """
        Consolidate old memories to save space.
        
        Keeps the most important and recent memories, summarizes the rest.
        """
        if len(self.memories) <= max_memories:
            return
        
        # Sort by importance and recency
        scored = []
        for m in self.memories:
            score = m.importance * 0.6 + (m.tick / max(m.tick, 1)) * 0.4
            scored.append((score, m))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Keep top memories
        self.memories = [m for _, m in scored[:max_memories]]
        self._save()

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        by_type: dict[str, int] = {}
        for m in self.memories:
            by_type[m.memory_type] = by_type.get(m.memory_type, 0) + 1
        
        return {
            "agent_name": self.agent_name,
            "total_memories": len(self.memories),
            "by_type": by_type,
            "earliest_tick": min((m.tick for m in self.memories), default=0),
            "latest_tick": max((m.tick for m in self.memories), default=0),
            "avg_importance": sum(m.importance for m in self.memories) / max(len(self.memories), 1),
        }

    def clear(self) -> None:
        """Clear all memories."""
        self.memories = []
        self.whispers = []
        self._next_id = 0
        self._save()

    def add_whisper(self, from_agent: str, content: str, tick: int, importance: float = 0.7) -> dict[str, Any]:
        """Add a whisper received from another agent."""
        whisper = {
            "id": f"whisper_{self.agent_name.lower()}_{len(self.whispers)}",
            "from": from_agent,
            "content": content,
            "tick": tick,
            "importance": importance,
            "read": False,
            "timestamp": time.time(),
        }
        self.whispers.append(whisper)
        self._save()
        return whisper

    def get_whispers_for(self, agent_name: str, unread_only: bool = False) -> list[dict[str, Any]]:
        """Get whispers directed at this agent (optionally unread only)."""
        if unread_only:
            return [w for w in self.whispers if not w.get("read", False)]
        return list(self.whispers)

    def get_unread_whispers(self) -> list[dict[str, Any]]:
        """Get all unread whispers."""
        return [w for w in self.whispers if not w.get("read", False)]

    def mark_whispers_read(self) -> int:
        """Mark all whispers as read. Returns count marked."""
        count = 0
        for w in self.whispers:
            if not w.get("read", False):
                w["read"] = True
                count += 1
        if count:
            self._save()
        return count

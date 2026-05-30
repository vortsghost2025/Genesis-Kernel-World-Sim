"""
Agent base class for World Sim.

All agents (Adam, Eve, and future characters) inherit from this.
Uses persistent memory system for long-term memory development.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.providers.base import BaseProvider, MockProvider, call_log
from backend.memory.persistent_memory import PersistentMemory

logger = logging.getLogger("world.agent")


@dataclass
class WorldAgent:
    """Base agent for the world simulation."""

    name: str = ""
    role: str = ""
    region: str = "east"  # east or west hemisphere
    traits: dict[str, float] = field(default_factory=dict)
    provider: BaseProvider = field(default_factory=lambda: MockProvider())
    persistent_memory: PersistentMemory | None = None

    # Internal state
    current_thought: str = ""
    current_action: str = ""
    tick: int = 0
    enabled: bool = True

    def __post_init__(self) -> None:
        """Initialize persistent memory if not provided."""
        if self.persistent_memory is None:
            self.persistent_memory = PersistentMemory(self.name)

    def set_provider(self, provider: BaseProvider) -> None:
        """Set the LLM provider for this agent."""
        self.provider = provider

    def decide(self, world_snapshot: dict[str, Any]) -> dict[str, Any]:
        """Observe world, think, choose an action. Returns action dict."""
        if not self.enabled:
            return {
                "agent": self.name,
                "tick": self.tick,
                "thought": "",
                "action": f"{self.name} is not active.",
                "enabled": False,
            }

        self.tick += 1
        prompt = self._build_prompt(world_snapshot)

        try:
            response = self.provider.generate(prompt, self.name, self.tick, world_snapshot)
            thought, action = self._parse_response(response, world_snapshot)
        except Exception as e:
            logger.warning("Agent %s provider failed: %s — falling back to mock", self.name, e)
            call_log.record(
                provider=self.provider.name,
                agent=self.name,
                tick=self.tick,
                success=False,
                error=f"Provider failure: {type(e).__name__}",
            )
            thought, action = self._mock_think_action(world_snapshot)

        self.current_thought = thought
        self.current_action = action

        # Store thought as an idea memory
        if thought and len(thought) > 10:
            self.persistent_memory.add_idea(thought, self.tick, importance=0.5)

        return {
            "agent": self.name,
            "tick": self.tick,
            "thought": thought,
            "action": action,
            "traits_snapshot": dict(self.traits),
            "enabled": True,
        }

    def _build_prompt(self, world: dict[str, Any]) -> str:
        """Build a prompt for the provider based on world state and persistent memory."""
        # Get context from persistent memory
        memory_context = self.persistent_memory.get_context_for_prompt(self.tick, max_memories=8)

        prompt = f"You are {self.name}. Role: {self.role}.\n"
        prompt += f"Region: {self.region.title()} Hemisphere.\n\n"
        
        prompt += f"## World State\n"
        for key, value in world.items():
            prompt += f"- {key}: {value}\n"

        prompt += f"\n## Your Memories\n{memory_context}\n"

        if self.traits:
            prompt += f"\n## Your Traits\n"
            for k, v in self.traits.items():
                prompt += f"- {k}: {v}\n"

        prompt += (
            f"\n## Output Format\n"
            f"Respond with JSON ONLY. No markdown, no explanation.\n"
            f'{{"thought": "your internal thought", "action": "what you do"}}\n'
        )

        prompt += f"\n\nWhat do you think and do right now? Return ONLY valid JSON."
        return prompt

    def _parse_response(self, response: str, world: dict[str, Any]) -> tuple[str, str]:
        """Parse provider response into thought and action."""
        if response.startswith("{"):
            try:
                data = json.loads(response)
                thought = data.get("thought", "")
                action = data.get("action", "")
                if thought and action:
                    return thought, action
            except json.JSONDecodeError:
                pass

        return self._mock_think_action(world)

    def _mock_think_action(self, world: dict[str, Any]) -> tuple[str, str]:
        """Fallback mock thought/action generation."""
        return (
            f"{self.name} observes the world.",
            f"{self.name} performs a basic action.",
        )

    def remember_event(self, content: str, importance: float = 1.0) -> None:
        """Remember an event that happened."""
        self.persistent_memory.add_event(content, self.tick, importance)

    def remember_idea(self, content: str, importance: float = 1.0) -> None:
        """Remember an idea or thought."""
        self.persistent_memory.add_idea(content, self.tick, importance)

    def remember_relationship(self, content: str, importance: float = 1.0) -> None:
        """Remember something about a relationship."""
        self.persistent_memory.add_relationship(content, self.tick, importance)

    def remember_skill(self, content: str, importance: float = 1.0) -> None:
        """Remember a skill learned."""
        self.persistent_memory.add_skill(content, self.tick, importance)

    def remember_observation(self, content: str, importance: float = 1.0) -> None:
        """Remember an observation about the world."""
        self.persistent_memory.add_observation(content, self.tick, importance)

    def get_memory_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        return self.persistent_memory.get_stats()

    def consolidate_memories(self, max_memories: int = 100) -> None:
        """Consolidate old memories to save space."""
        self.persistent_memory.consolidate(max_memories)

    def save_state(self, path: Path) -> None:
        """Persist agent state to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "role": self.role,
            "region": self.region,
            "tick": self.tick,
            "traits": self.traits,
            "current_thought": self.current_thought,
            "current_action": self.current_action,
            "enabled": self.enabled,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_state(self, path: Path) -> None:
        """Restore agent state from JSON."""
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self.tick = data.get("tick", 0)
        self.traits = data.get("traits", self.traits)
        self.region = data.get("region", self.region)
        self.current_thought = data.get("current_thought", "")
        self.current_action = data.get("current_action", "")
        self.enabled = data.get("enabled", True)

"""
Agent base class for World Sim.

All agents (Adam, Eve, and future characters) inherit from this.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.providers.base import BaseProvider, MockProvider, call_log

logger = logging.getLogger("world.agent")


@dataclass
class WorldAgent:
    """Base agent for the world simulation."""

    name: str = ""
    role: str = ""
    traits: dict[str, float] = field(default_factory=dict)
    memory: list[dict[str, Any]] = field(default_factory=list)
    provider: BaseProvider = field(default_factory=lambda: MockProvider())

    # Internal state
    current_thought: str = ""
    current_action: str = ""
    tick: int = 0
    enabled: bool = True

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

        return {
            "agent": self.name,
            "tick": self.tick,
            "thought": thought,
            "action": action,
            "traits_snapshot": dict(self.traits),
            "enabled": True,
        }

    def _build_prompt(self, world: dict[str, Any]) -> str:
        """Build a prompt for the provider based on world state."""
        recent = self.memory[-5:] if self.memory else []
        context = "; ".join(r.get("summary", "") for r in recent) if recent else "nothing yet remembered"

        prompt = f"You are {self.name}. Role: {self.role}.\n\n"
        prompt += f"## World State\n"
        for key, value in world.items():
            prompt += f"- {key}: {value}\n"

        prompt += f"\n## Recent Memories\n{context}\n"

        if self.traits:
            prompt += f"\n## Current Traits\n"
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

    def remember(self, event: dict[str, Any]) -> None:
        """Add a consequence/event to memory."""
        self.memory.append({
            "tick": event.get("tick", 0),
            "summary": event.get("consequence_summary", ""),
            "label": event.get("label", "SIMULATION_EVENT"),
        })
        # Keep memory manageable
        if len(self.memory) > 50:
            self.memory = self.memory[-50:]

    def save_state(self, path: Path) -> None:
        """Persist agent state to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "role": self.role,
            "tick": self.tick,
            "traits": self.traits,
            "current_thought": self.current_thought,
            "current_action": self.current_action,
            "memory": self.memory,
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
        self.current_thought = data.get("current_thought", "")
        self.current_action = data.get("current_action", "")
        self.memory = data.get("memory", [])
        self.enabled = data.get("enabled", True)

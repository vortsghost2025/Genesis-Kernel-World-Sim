"""
Consequence engine — resolves agent actions into world changes.
Handles discovery, relationships, skill learning, and inter-agent whispers.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("world.consequence")


class ConsequenceEngine:
    """Deterministic consequence engine for the world simulation."""

    def __init__(self) -> None:
        self._discovery_keywords = [
            "discover", "find", "found", "uncover", "stumble", "encounter",
            "spot", "notice", "reveal", "explore", "locate",
        ]
        self._social_keywords = [
            "speak", "talk", "tell", "share", "ask", "answer", "discuss",
            "whisper", "listen", "comfort", "argue", "disagree", "agree",
            "teach", "learn from", "help", "invite", "greet", "call",
        ]
        self._build_keywords = [
            "build", "construct", "make", "craft", "create", "shape",
            "carve", "assemble", "erect", "plant", "grow",
        ]
        self._gather_keywords = [
            "gather", "harvest", "collect", "forage", "pick", "fetch",
            "hunt", "fish", "draw water", "fetch water",
        ]
        self._rest_keywords = [
            "rest", "sleep", "sit", "meditate", "watch", "wait", "pause",
        ]
        self._explore_keywords = [
            "explore", "wander", "walk", "travel", "climb", "go",
            "move", "run", "seek", "survey", "scout", "journey",
        ]

    def resolve(
        self,
        agent_actions: list[dict[str, Any]],
        world_state: dict[str, Any],
        agents: dict[str, Any] | None = None,
        mechanics: Any | None = None,
    ) -> dict[str, Any]:
        """
        Resolve consequences from all agent actions.

        Returns a consequence dict with per-agent summaries and world changes.
        Also triggers whispers between agents in the same hemisphere.
        """
        tick = agent_actions[0].get("tick", 0) if agent_actions else 0
        world_changes: dict[str, Any] = {}
        agent_results = []
        whisper_queue: list[dict[str, Any]] = []

        for action in agent_actions:
            agent_name = action.get("agent", "Unknown")
            agent_action = action.get("action", "")
            agent_thought = action.get("thought", "")
            result = self._resolve_action(
                agent_name, agent_action, agent_thought, world_state,
            )
            agent_results.append(result)

            if "resources" in result.get("world_changes", {}):
                if "resources" not in world_changes:
                    world_changes["resources"] = {}
                for k, v in result["world_changes"]["resources"].items():
                    world_changes["resources"][k] = world_changes["resources"].get(k, 0) + v

            if "structure" in result.get("world_changes", {}):
                world_changes["structure"] = result["world_changes"]["structure"]

            if "harmony_level" in result.get("world_changes", {}):
                current = world_changes.get("harmony_level", world_state.get("harmony_level", 1.0))
                world_changes["harmony_level"] = current + result["world_changes"]["harmony_level"]

            if result.get("whispers"):
                whisper_queue.extend(result["whispers"])

            if mechanics and result.get("mechanics_updates"):
                self._apply_mechanics(mechanics, agent_name, tick, result["mechanics_updates"])

        narratives = [r.get("consequence_summary", "") for r in agent_results]
        narrative = ". ".join(n for n in narratives if n)

        result = {
            "tick": tick,
            "agent_results": agent_results,
            "world_changes": world_changes,
            "narrative": narrative,
            "whispers": whisper_queue,
            "label": "SIMULATION_EVENT",
            "source_anchor": None,
            "simulation_note": "Generated world event — not grounded in source text.",
        }
        return result

    def _resolve_action(
        self, agent_name: str, action: str, thought: str, world: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve a single agent action into consequences + mechanics + whispers."""
        action_lower = action.lower()
        thought_lower = thought.lower() if thought else ""
        combined = f"{action_lower} {thought_lower}"
        world_changes: dict[str, Any] = {}
        consequence = f"{agent_name} acts."
        mechanics_updates: dict[str, Any] = {}
        whispers: list[dict[str, Any]] = []

        if any(kw in combined for kw in self._gather_keywords):
            world_changes["resources"] = {"food": 0.1, "materials": 0.05}
            mechanics_updates["skill"] = "gathering"
            consequence = f"{agent_name} gathers resources from the land."

        elif any(kw in combined for kw in self._build_keywords):
            world_changes["resources"] = {"materials": -0.1}
            world_changes["structure"] = {
                "name": f"{agent_name}'s structure",
                "type": "building",
                "tick": world.get("tick", 0),
            }
            mechanics_updates["skill"] = "building"
            mechanics_updates["building"] = {
                "name": f"{agent_name}'s shelter",
                "type": "shelter",
                "builder": agent_name,
            }
            consequence = f"{agent_name} builds something from the land's offering."

        elif any(kw in combined for kw in self._social_keywords):
            world_changes["harmony_level"] = 0.02
            mechanics_updates["relationship"] = {"trust_delta": 0.05, "cooperation_delta": 0.05}
            consequence = f"{agent_name} communicates with another."
            whispers = self._extract_whispers(agent_name, action)

        elif any(kw in combined for kw in self._explore_keywords):
            mechanics_updates["skill"] = "exploration"
            mechanics_updates["exploration_level"] = True
            consequence = f"{agent_name} ventures into unknown territory."

        elif any(kw in combined for kw in self._discovery_keywords):
            mechanics_updates["skill"] = "discovery"
            mechanics_updates["exploration_level"] = True
            consequence = f"{agent_name} discovers something new."

        elif any(kw in combined for kw in self._rest_keywords):
            consequence = f"{agent_name} rests and watches the world."

        else:
            mechanics_updates["skill"] = "observation"
            consequence = f"{agent_name} acts in the world."

        return {
            "agent": agent_name,
            "consequence_summary": consequence,
            "world_changes": world_changes,
            "mechanics_updates": mechanics_updates,
            "whispers": whispers,
            "label": "SIMULATION_EVENT",
        }

    def _extract_whispers(
        self, agent_name: str, action: str,
    ) -> list[dict[str, Any]]:
        """Extract inter-agent whispers from social actions."""
        whispers = []
        if "whisper" in action.lower() or "tell" in action.lower() or "share" in action.lower():
            whispers.append({
                "from": agent_name,
                "content": action[:200],
                "type": "social",
            })
        return whispers

    def _apply_mechanics(
        self, mechanics: Any, agent_name: str, tick: int, updates: dict[str, Any],
    ) -> None:
        """Apply mechanics updates from a consequence."""
        if "skill" in updates:
            mechanics.add_skill(agent_name, updates["skill"], tick, level=0.05)
        if "building" in updates:
            b = updates["building"]
            mechanics.add_building(b["name"], b["type"], b.get("builder", agent_name), tick)
        if "relationship" in updates:
            rel = updates["relationship"]
            for other_name in mechanics.relationships:
                for r in mechanics.relationships:
                    pair = (r.agent1, r.agent2)
                    if agent_name in pair:
                        other = r.agent2 if r.agent1 == agent_name else r.agent1
                        mechanics.update_relationship(
                            agent_name, other, tick,
                            trust_delta=rel.get("trust_delta", 0.0),
                            cooperation_delta=rel.get("cooperation_delta", 0.0),
                        )

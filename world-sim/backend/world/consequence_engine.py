"""
Consequence engine — resolves agent actions into world changes.
"""

from __future__ import annotations

from typing import Any


class ConsequenceEngine:
    """Deterministic consequence engine for the world simulation."""

    def resolve(
        self,
        agent_actions: list[dict[str, Any]],
        world_state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Resolve consequences from all agent actions.

        Returns a consequence dict with per-agent summaries and world changes.
        """
        tick = agent_actions[0].get("tick", 0) if agent_actions else 0
        world_changes: dict[str, Any] = {}

        # Process each agent's action
        agent_results = []
        for action in agent_actions:
            agent_name = action.get("agent", "Unknown")
            agent_action = action.get("action", "")
            result = self._resolve_action(agent_name, agent_action, world_state)
            agent_results.append(result)

            # Accumulate world changes
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

        # Build narrative
        narratives = [r.get("consequence_summary", "") for r in agent_results]
        narrative = ". ".join(n for n in narratives if n)

        return {
            "tick": tick,
            "agent_results": agent_results,
            "world_changes": world_changes,
            "narrative": narrative,
            "label": "SIMULATION_EVENT",
            "source_anchor": None,
            "simulation_note": "Generated world event — not grounded in source text.",
        }

    def _resolve_action(
        self, agent_name: str, action: str, world: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve a single agent action."""
        action_lower = action.lower()
        world_changes: dict[str, Any] = {}
        consequence = f"{agent_name} acts."

        # Resource changes
        if "gather" in action_lower or "harvest" in action_lower:
            world_changes["resources"] = {"food": 0.1, "materials": 0.05}
            consequence = f"{agent_name} gathers resources."

        elif "build" in action_lower or "construct" in action_lower:
            world_changes["resources"] = {"materials": -0.1}
            world_changes["structure"] = {
                "name": f"{agent_name}'s structure",
                "type": "building",
                "tick": world.get("tick", 0),
            }
            consequence = f"{agent_name} builds something."

        elif "tend" in action_lower or "farm" in action_lower:
            world_changes["resources"] = {"food": 0.05}
            consequence = f"{agent_name} tends the land."

        elif "speak" in action_lower or "talk" in action_lower:
            world_changes["harmony_level"] = 0.02
            consequence = f"{agent_name} speaks with others."

        elif "rest" in action_lower or "sleep" in action_lower:
            consequence = f"{agent_name} rests."

        return {
            "agent": agent_name,
            "consequence_summary": consequence,
            "world_changes": world_changes,
            "label": "SIMULATION_EVENT",
        }

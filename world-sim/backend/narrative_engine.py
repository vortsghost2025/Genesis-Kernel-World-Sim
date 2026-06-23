"""
Narrative engine — transforms simulation events into dramatic, cinematic narration.
"""

from __future__ import annotations

import random

class NarrativeEngine:
    """Generates dramatic, story-like narration from simulation events."""

    OPENINGS = [
        "In the beginning, when the world was still young...",
        "The day unfolds with quiet purpose across the ancient lands...",
        "As the light of the new cycle breaks across the horizon...",
        "A hush falls upon the world as history writes itself...",
        "The Creator's garden stirs with the breath of new life...",
        "In the silence between heartbeats, the world shifts...",
    ]

    TRANSITIONS = [
        "And so it is,",
        "Meanwhile,",
        "As the day deepens,",
        "Unseen by mortal eyes,",
        "In the grand tapestry of creation,",
        "The story continues,",
    ]

    WEATHER_NARRATIONS = {
        "gentle": [
            "A soft breeze carries the scent of blooming flowers across Eden.",
            "The sun shines warmly, golden rays filtering through ancient branches.",
            "All is calm. The world breathes gently under a benevolent sky.",
        ],
        "warm": [
            "Heat shimmers rise from the rich soil as the sun climbs higher.",
            "The air grows heavy and warm, testing the resolve of those who dwell here.",
            "A golden haze blankets the land. Nature hums with restless energy.",
        ],
        "cool": [
            "A refreshing coolness sweeps through the garden, dew clinging to every leaf.",
            "The sky softens to silver as evening draws near, the air crisp and clean.",
            "A gentle chill whispers across the earth, carrying the promise of rest.",
        ],
        "storm": [
            "Dark clouds gather above — lightning fractures the heavens, thunder shaking the very earth!",
            "The sky rages. Wind howls through the trees as rain lashes down in silver sheets.",
            "Nature's fury is unleashed. The ground trembles beneath the storm's wrath.",
        ],
    }

    ACTION_TEMPLATES = {
        "build": [
            "with deliberate hands and an unyielding will, {agent} sets to work shaping the raw materials of creation into something new.",
            "driven by the deep need for shelter and meaning, {agent} begins to build — transforming the garden itself through the power of making.",
        ],
        "explore": [
            "drawn by an ancient curiosity, {agent} steps beyond the familiar, eyes wide at the wonders that await.",
            "with each new horizon, {agent} pushes further into the unknown — mapping the edges of creation itself.",
        ],
        "gather": [
            "with patient hands, {agent} gathers the earth's bounty — each fruit, each branch, a gift from the garden.",
            "{agent} moves through the garden with purpose, collecting what the Creator has provided.",
        ],
        "observe": [
            "in quiet contemplation, {agent} observes the world — watching, learning, understanding the patterns of creation.",
            "a stillness settles over {agent} as the mind takes in the full scope of this wondrous world.",
        ],
        "rest": [
            "the weight of creation grows heavy, and {agent} finds rest beneath the sheltering branches of an ancient tree.",
            "as the light fades, {agent} settles into stillness — the garden a cradle, the sky a blanket of stars.",
        ],
        "social": [
            "connection blooms between {agent} and their companion — a bond forged in the shared experience of creation.",
            "through words and gestures, {agent} weaves the invisible threads of relationship, strengthening the fabric of their world.",
        ],
        "pray": [
            "looking upward with reverence, {agent} whispers a prayer to the heavens — a conversation between the created and the Creator.",
            "in a moment of profound humility, {agent} reaches toward the divine, seeking guidance in the vast silence.",
        ],
        "default": [
            "with purpose and determination, {agent} moves through their day, each action a verse in the unfolding epic of creation.",
            "the world watches as {agent} adds another chapter to the story of the first days.",
        ],
    }

    MEMORY_MILESTONES = [
        "As memories accumulate, {agent}'s mind grows richer — a tapestry of experience woven across time.",
        "The weight of lived experience shapes {agent}'s perspective, each memory a stone in the foundation of wisdom.",
        "Through remembering, {agent} grows — not just in knowledge, but in the depth of their understanding of this world.",
    ]

    DISCOVERY_TEMPLATE = (
        "A breathtaking moment in the history of the world — {discoverer} encounters {discovered} for the first time! "
        "The boundaries of the known world expand, and with it, the possibilities of all that is yet to come."
    )

    COMPARISON_TEMPLATE = (
        "In the {side1} Hemisphere, {agent1} {action1}. Meanwhile, in the {side2}, {agent2} {action2}. "
        "Two worlds, two stories, unfolding in parallel — each unique, each essential to the whole."
    )

    def __init__(self):
        self._used_openings = set()

    def generate_opening(self) -> str:
        """Generate a dramatic opening for a narration sequence."""
        available = [o for o in self.OPENINGS if o not in self._used_openings]
        if not available:
            self._used_openings.clear()
            available = list(self.OPENINGS)
        choice = random.choice(available)
        self._used_openings.add(choice)
        return choice

    def narrate_weather(self, weather: str) -> str:
        """Generate atmospheric narration based on weather."""
        options = self.WEATHER_NARRATIONS.get(weather, self.WEATHER_NARRATIONS["gentle"])
        return random.choice(options)

    def narrate_action(self, agent_name: str, action: str, thought: str = "") -> str:
        """Generate narration for an agent's action."""
        action_lower = action.lower()
        
        template = random.choice(self.ACTION_TEMPLATES.get("default", self.ACTION_TEMPLATES["default"]))
        
        if any(w in action_lower for w in ["build", "construct", "craft", "make", "create"]):
            template = random.choice(self.ACTION_TEMPLATES["build"])
        elif any(w in action_lower for w in ["explore", "discover", "wander", "walk", "search", "scout"]):
            template = random.choice(self.ACTION_TEMPLATES["explore"])
        elif any(w in action_lower for w in ["gather", "collect", "harvest", "pick"]):
            template = random.choice(self.ACTION_TEMPLATES["gather"])
        elif any(w in action_lower for w in ["observe", "watch", "study", "contemplate", "meditate"]):
            template = random.choice(self.ACTION_TEMPLATES["observe"])
        elif any(w in action_lower for w in ["rest", "sleep", "wait", "pause"]):
            template = random.choice(self.ACTION_TEMPLATES["rest"])
        elif any(w in action_lower for w in ["talk", "speak", "interact", "share", "greet"]):
            template = random.choice(self.ACTION_TEMPLATES["social"])
        elif any(w in action_lower for w in ["pray", "worship", "thank", "praise"]):
            template = random.choice(self.ACTION_TEMPLATES["pray"])
        
        return template.format(agent=agent_name)

    def narrate_discovery(self, discoverer: str, discovered: str) -> str:
        """Generate narration for a discovery event."""
        return self.DISCOVERY_TEMPLATE.format(
            discoverer=discoverer,
            discovered=discovered,
        )

    def narrate_memory_milestone(self, agent_name: str, memory_count: int) -> str:
        """Generate narration for a memory milestone."""
        template = random.choice(self.MEMORY_MILESTONES)
        return template.format(agent=agent_name)

    def narrate_comparison(self, east_agent: str, east_action: str, west_agent: str, west_action: str) -> str:
        """Generate a comparison narration between hemispheres."""
        return self.COMPARISON_TEMPLATE.format(
            side1="Eastern",
            agent1=east_agent,
            action1=east_action,
            side2="Western Frontier",
            agent2=west_agent,
            action2=west_action,
        )

    def narrate_event(self, event: dict) -> str:
        """Generate full narration for a simulation event."""
        label = event.get("label", "")
        agents = event.get("agents", {})
        narrative = event.get("narrative", "")
        hemisphere = event.get("hemisphere", "")

        parts = []

        # If it's a divine intervention, narrate it dramatically
        if "DIVINE" in label:
            parts.append(narrative)
            return " ".join(parts)

        # If it's a discovery event
        if "DISCOVERY" in label:
            parts.append(narrative)
            return " ".join(parts)

        # Weather narration
        world_changes = event.get("world_changes", {})
        if "weather" in world_changes:
            parts.append(self.narrate_weather(world_changes["weather"]))

        # Agent actions
        for name, data in agents.items():
            action = data.get("action", "")
            thought = data.get("thought", "")
            if action:
                parts.append(self.narrate_action(name, action, thought))

        if not parts:
            parts.append(narrative)

        return " ".join(parts)

    def narrate_cinematic_sequence(self, east_events: list, west_events: list) -> list[dict]:
        """Generate a cinematic sequence narration from recent events of both hemispheres."""
        narrations = []
        
        # Start with an opening
        narrations.append({
            "type": "opening",
            "text": self.generate_opening(),
        })

        # East hemisphere narration
        if east_events:
            latest_east = east_events[0] if east_events else None
            if latest_east:
                narration_text = self.narrate_event(latest_east)
                narrations.append({
                    "type": "event",
                    "hemisphere": "east",
                    "tick": latest_east.get("tick", 0),
                    "text": narration_text,
                })

        # West hemisphere narration
        if west_events:
            latest_west = west_events[0] if west_events else None
            if latest_west:
                narration_text = self.narrate_event(latest_west)
                narrations.append({
                    "type": "event",
                    "hemisphere": "west",
                    "tick": latest_west.get("tick", 0),
                    "text": narration_text,
                })

        # Cross-hemisphere comparison if both have events
        if east_events and west_events:
            east_latest = east_events[0]
            west_latest = west_events[0]
            east_agents = list(east_latest.get("agents", {}).keys())
            west_agents = list(west_latest.get("agents", {}).keys())
            
            if east_agents and west_agents:
                ea = east_latest["agents"][east_agents[0]]
                wa = west_latest["agents"][west_agents[0]]
                comp = self.narrate_comparison(
                    east_agents[0], ea.get("action", "acts"),
                    west_agents[0], wa.get("action", "acts"),
                )
                narrations.append({
                    "type": "comparison",
                    "text": comp,
                })

        return narrations

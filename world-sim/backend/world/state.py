"""
World state engine for the simulation.

Tracks resources, structures, time, and environment.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class WorldState:
    """The world/environment state for the simulation."""

    name: str = "Eden"
    day: int = 1
    tick: int = 0
    time_of_day: str = "morning"  # morning, midday, evening, night

    # Environment
    weather: str = "gentle"  # gentle, warm, cool, storm
    garden_condition: str = "pristine"  # pristine, tended, wild, developed

    # Resources
    resources: dict[str, float] = field(default_factory=lambda: {
        "food": 1.0,
        "water": 1.0,
        "materials": 0.8,
        "shelter": 0.0,
    })

    # Structures
    structures: list[dict[str, str]] = field(default_factory=list)

    # Relationships
    harmony_level: float = 1.0  # 0.0 to 1.0

    # Boundary
    boundary: str = "do not eat from the tree of knowledge of good and evil"
    boundary_respected: bool = True

    # Animals present
    animals_present: list[str] = field(default_factory=lambda: [
        "lion", "lamb", "eagle", "dove", "serpent",
    ])

    def observe(self) -> dict[str, Any]:
        """Return a snapshot of the world for agents to observe."""
        return {
            "day": self.day,
            "time_of_day": self.time_of_day,
            "weather": self.weather,
            "garden_condition": self.garden_condition,
            "resources": dict(self.resources),
            "structures": [s.get("name", "") for s in self.structures],
            "harmony_level": self.harmony_level,
            "boundary": self.boundary,
            "boundary_respected": self.boundary_respected,
            "animals_present": list(self.animals_present),
        }

    def advance_tick(self) -> None:
        """Advance the world clock by one tick."""
        self.tick += 1

        # Cycle time of day
        times = ["morning", "midday", "evening", "night"]
        self.time_of_day = times[self.tick % len(times)]

        # Advance day every 4 ticks
        if self.tick % 4 == 0:
            self.day += 1

        # Slowly deplete resources
        for key in self.resources:
            self.resources[key] = max(0.0, self.resources[key] - 0.005)

        # Weather shifts occasionally
        if self.tick % 8 == 0:
            weathers = ["gentle", "warm", "cool", "gentle"]
            self.weather = weathers[(self.tick // 8) % len(weathers)]

    def apply_changes(self, changes: dict[str, Any]) -> None:
        """Apply world changes from agent actions."""
        if "resources" in changes:
            for k, v in changes["resources"].items():
                self.resources[k] = max(0.0, min(1.0, self.resources.get(k, 0) + v))

        if "structure" in changes:
            self.structures.append(changes["structure"])

        if "harmony_level" in changes:
            self.harmony_level = max(0.0, min(1.0, changes["harmony_level"]))

        if "boundary_respected" in changes:
            self.boundary_respected = changes["boundary_respected"]

        if "garden_condition" in changes:
            self.garden_condition = changes["garden_condition"]

    def save_state(self, path: Path) -> None:
        """Persist world state to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "day": self.day,
            "tick": self.tick,
            "time_of_day": self.time_of_day,
            "weather": self.weather,
            "garden_condition": self.garden_condition,
            "resources": self.resources,
            "structures": self.structures,
            "harmony_level": self.harmony_level,
            "boundary": self.boundary,
            "boundary_respected": self.boundary_respected,
            "animals_present": self.animals_present,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_state(self, path: Path) -> None:
        """Restore world state from JSON."""
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self.name = data.get("name", self.name)
        self.day = data.get("day", self.day)
        self.tick = data.get("tick", self.tick)
        self.time_of_day = data.get("time_of_day", self.time_of_day)
        self.weather = data.get("weather", self.weather)
        self.garden_condition = data.get("garden_condition", self.garden_condition)
        self.resources = data.get("resources", self.resources)
        self.structures = data.get("structures", self.structures)
        self.harmony_level = data.get("harmony_level", self.harmony_level)
        self.boundary = data.get("boundary", self.boundary)
        self.boundary_respected = data.get("boundary_respected", self.boundary_respected)
        self.animals_present = data.get("animals_present", self.animals_present)

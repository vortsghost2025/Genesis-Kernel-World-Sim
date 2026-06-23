"""
World Mechanics System

Handles farming, building, crafting, resource management, and agent relationships.
Agents can discover, learn, and develop skills over time.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Resource:
    """A world resource."""
    name: str
    type: str  # food, water, wood, stone, metal, herb, etc.
    amount: float = 1.0
    max_amount: float = 1.0
    regen_rate: float = 0.01  # per tick
    discovered: bool = True


@dataclass
class Building:
    """A structure built by agents."""
    name: str
    type: str  # shelter, farm, workshop, storage, etc.
    builder: str
    tick_built: int
    durability: float = 1.0
    capacity: float = 1.0


@dataclass
class Skill:
    """A skill an agent has learned."""
    name: str
    level: float = 0.0  # 0.0 to 1.0
    tick_learned: int = 0


@dataclass
class Relationship:
    """Relationship between two agents."""
    agent1: str
    agent2: str
    trust: float = 0.5  # 0.0 to 1.0
    cooperation: float = 0.5  # 0.0 to 1.0
    last_interaction: int = 0


class WorldMechanics:
    """
    Manages world mechanics: resources, buildings, skills, relationships.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "world_mechanics.json"
        
        # Resources
        self.resources: list[Resource] = [
            Resource("fruit_trees", "food", 1.0, 1.0, 0.005),
            Resource("water_source", "water", 1.0, 1.0, 0.008),
            Resource("woodland", "wood", 0.8, 1.0, 0.003),
            Resource("stone_deposit", "stone", 0.5, 1.0, 0.001),
            Resource("herb_garden", "herb", 0.3, 1.0, 0.004),
        ]
        
        # Buildings
        self.buildings: list[Building] = []
        
        # Agent skills
        self.agent_skills: dict[str, list[Skill]] = {}
        
        # Relationships
        self.relationships: list[Relationship] = []
        
        # Load saved state
        self._load()

    def _load(self) -> None:
        """Load mechanics state from disk."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                
                # Load resources
                self.resources = [Resource(**r) for r in data.get("resources", [])]
                
                # Load buildings
                self.buildings = [Building(**b) for b in data.get("buildings", [])]
                
                # Load skills
                for agent, skills in data.get("agent_skills", {}).items():
                    self.agent_skills[agent] = [Skill(**s) for s in skills]
                
                # Load relationships
                self.relationships = [Relationship(**r) for r in data.get("relationships", [])]
            except Exception as e:
                print(f"Failed to load world mechanics: {e}")

    def _save(self) -> None:
        """Save mechanics state to disk."""
        data = {
            "resources": [
                {
                    "name": r.name,
                    "type": r.type,
                    "amount": r.amount,
                    "max_amount": r.max_amount,
                    "regen_rate": r.regen_rate,
                    "discovered": r.discovered,
                }
                for r in self.resources
            ],
            "buildings": [
                {
                    "name": b.name,
                    "type": b.type,
                    "builder": b.builder,
                    "tick_built": b.tick_built,
                    "durability": b.durability,
                    "capacity": b.capacity,
                }
                for b in self.buildings
            ],
            "agent_skills": {
                agent: [
                    {
                        "name": s.name,
                        "level": s.level,
                        "tick_learned": s.tick_learned,
                    }
                    for s in skills
                ]
                for agent, skills in self.agent_skills.items()
            },
            "relationships": [
                {
                    "agent1": r.agent1,
                    "agent2": r.agent2,
                    "trust": r.trust,
                    "cooperation": r.cooperation,
                    "last_interaction": r.last_interaction,
                }
                for r in self.relationships
            ],
        }
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def advance_tick(self, tick: int) -> dict[str, Any]:
        """Advance world mechanics by one tick."""
        changes = {"resources": {}, "buildings": [], "skills": [], "relationships": []}
        
        # Regenerate resources
        for resource in self.resources:
            if resource.discovered:
                old_amount = resource.amount
                resource.amount = min(resource.max_amount, resource.amount + resource.regen_rate)
                if resource.amount != old_amount:
                    changes["resources"][resource.name] = round(resource.amount, 3)
        
        # Decay buildings slowly
        for building in self.buildings:
            building.durability = max(0.0, building.durability - 0.001)
        
        # Save periodically
        if tick % 10 == 0:
            self._save()
        
        return changes

    def add_building(self, name: str, type: str, builder: str, tick: int) -> Building:
        """Add a new building."""
        building = Building(
            name=name,
            type=type,
            builder=builder,
            tick_built=tick,
        )
        self.buildings.append(building)
        self._save()
        return building

    def add_skill(self, agent: str, skill_name: str, tick: int, level: float = 0.1) -> Skill:
        """Add or improve a skill for an agent."""
        if agent not in self.agent_skills:
            self.agent_skills[agent] = []
        
        # Check if skill already exists
        for skill in self.agent_skills[agent]:
            if skill.name == skill_name:
                skill.level = min(1.0, skill.level + level)
                self._save()
                return skill
        
        # New skill
        skill = Skill(name=skill_name, level=level, tick_learned=tick)
        self.agent_skills[agent].append(skill)
        self._save()
        return skill

    def update_relationship(self, agent1: str, agent2: str, tick: int, 
                           trust_delta: float = 0.0, cooperation_delta: float = 0.0) -> Relationship:
        """Update relationship between two agents."""
        # Find existing relationship
        for rel in self.relationships:
            if (rel.agent1 == agent1 and rel.agent2 == agent2) or \
               (rel.agent1 == agent2 and rel.agent2 == agent1):
                rel.trust = max(0.0, min(1.0, rel.trust + trust_delta))
                rel.cooperation = max(0.0, min(1.0, rel.cooperation + cooperation_delta))
                rel.last_interaction = tick
                self._save()
                return rel
        
        # New relationship
        rel = Relationship(
            agent1=agent1,
            agent2=agent2,
            trust=0.5 + trust_delta,
            cooperation=0.5 + cooperation_delta,
            last_interaction=tick,
        )
        self.relationships.append(rel)
        self._save()
        return rel

    def get_resource(self, name: str) -> Resource | None:
        """Get a resource by name."""
        for resource in self.resources:
            if resource.name == name:
                return resource
        return None

    def get_agent_skills(self, agent: str) -> list[Skill]:
        """Get all skills for an agent."""
        return self.agent_skills.get(agent, [])

    def get_relationship(self, agent1: str, agent2: str) -> Relationship | None:
        """Get relationship between two agents."""
        for rel in self.relationships:
            if (rel.agent1 == agent1 and rel.agent2 == agent2) or \
               (rel.agent1 == agent2 and rel.agent2 == agent1):
                return rel
        return None

    def get_state(self) -> dict[str, Any]:
        """Get current mechanics state."""
        return {
            "resources": [
                {
                    "name": r.name,
                    "type": r.type,
                    "amount": round(r.amount, 3),
                    "max_amount": r.max_amount,
                    "discovered": r.discovered,
                }
                for r in self.resources
            ],
            "buildings": [
                {
                    "name": b.name,
                    "type": b.type,
                    "builder": b.builder,
                    "tick_built": b.tick_built,
                    "durability": round(b.durability, 3),
                }
                for b in self.buildings
            ],
            "agent_skills": {
                agent: [
                    {
                        "name": s.name,
                        "level": round(s.level, 3),
                        "tick_learned": s.tick_learned,
                    }
                    for s in skills
                ]
                for agent, skills in self.agent_skills.items()
            },
            "relationships": [
                {
                    "agent1": r.agent1,
                    "agent2": r.agent2,
                    "trust": round(r.trust, 3),
                    "cooperation": round(r.cooperation, 3),
                    "last_interaction": r.last_interaction,
                }
                for r in self.relationships
            ],
        }

    def clear(self) -> None:
        """Clear all mechanics state."""
        self.resources = [
            Resource("fruit_trees", "food", 1.0, 1.0, 0.005),
            Resource("water_source", "water", 1.0, 1.0, 0.008),
            Resource("woodland", "wood", 0.8, 1.0, 0.003),
            Resource("stone_deposit", "stone", 0.5, 1.0, 0.001),
            Resource("herb_garden", "herb", 0.3, 1.0, 0.004),
        ]
        self.buildings = []
        self.agent_skills = {}
        self.relationships = []
        self._save()

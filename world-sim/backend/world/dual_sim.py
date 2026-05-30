"""
Dual Hemisphere Simulation Engine.

Runs two independent simulation instances (East and West) in parallel.
Each hemisphere has its own agents, tick counter, and world state.
Agents can eventually discover each other through exploration.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.config import WorldSimConfig
from backend.agents.base import WorldAgent
from backend.agents.adam import create_adam
from backend.agents.eve import create_eve
from backend.world.state import WorldState
from backend.world.consequence_engine import ConsequenceEngine
from backend.memory.event_log import EventLog
from backend.memory.persistent_memory import PersistentMemory
from backend.providers.base import MockProvider, NvidiaNimProvider, call_log

logger = logging.getLogger("world.dual_sim")


@dataclass
class HemisphereSim:
    """A single hemisphere simulation instance."""
    
    name: str  # "east" or "west"
    world: WorldState
    agents: dict[str, WorldAgent]
    engine: ConsequenceEngine
    event_log: EventLog
    tick: int = 0
    enabled: bool = True
    exploration_level: int = 0  # 0-5, how far agents have explored

    def run_tick(self) -> dict[str, Any]:
        """Run one tick of simulation for this hemisphere."""
        if not self.enabled:
            return {"tick": self.tick, "status": "disabled"}

        self.tick += 1
        
        # World observes
        world_snapshot = self.world.observe()
        world_snapshot["hemisphere"] = self.name
        world_snapshot["exploration_level"] = self.exploration_level

        # Each agent decides
        agent_actions = []
        for name, agent in self.agents.items():
            if agent.enabled:
                action = agent.decide(world_snapshot)
                agent_actions.append(action)

        # Consequence engine resolves
        consequences = self.engine.resolve(agent_actions, world_snapshot)

        # Apply world changes
        self.world.apply_changes(consequences["world_changes"])
        self.world.advance_tick()

        # Agents remember consequences
        for name, agent in self.agents.items():
            agent_result = next(
                (r for r in consequences["agent_results"] if r["agent"] == name),
                None,
            )
            if agent_result:
                agent.remember_event(agent_result["consequence_summary"])

        # Log event
        event = {
            "tick": self.tick,
            "hemisphere": self.name,
            "label": consequences["label"],
            "narrative": consequences["narrative"],
            "agents": {
                name: {"thought": a.get("thought", ""), "action": a.get("action", "")}
                for a in agent_actions
            },
            "world_changes": consequences["world_changes"],
        }
        self.event_log.append(event)

        # Periodically consolidate memories
        if self.tick % 50 == 0:
            for agent in self.agents.values():
                agent.consolidate_memories()

        return {
            "tick": self.tick,
            "hemisphere": self.name,
            "status": "ok",
            "event": event,
        }

    def get_state(self) -> dict[str, Any]:
        """Get current state summary."""
        return {
            "name": self.name,
            "tick": self.tick,
            "enabled": self.enabled,
            "exploration_level": self.exploration_level,
            "world": {
                "day": self.world.day,
                "time_of_day": self.world.time_of_day,
                "weather": self.world.weather,
                "garden_condition": self.world.garden_condition,
                "harmony_level": self.world.harmony_level,
                "boundary_respected": self.world.boundary_respected,
            },
            "agents": {
                name: {
                    "tick": agent.tick,
                    "enabled": agent.enabled,
                    "current_thought": agent.current_thought[:100] if agent.current_thought else "",
                    "current_action": agent.current_action[:100] if agent.current_action else "",
                    "memory_count": len(agent.persistent_memory.memories),
                }
                for name, agent in self.agents.items()
            },
        }

    def save_state(self, data_dir: Path) -> None:
        """Save simulation state to disk."""
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Save world state
        self.world.save_state(data_dir / f"{self.name}_world_state.json")
        
        # Save agent states
        for name, agent in self.agents.items():
            agent.save_state(data_dir / f"{self.name}_{name.lower()}_state.json")

    def load_state(self, data_dir: Path) -> None:
        """Load simulation state from disk."""
        # Load world state
        world_path = data_dir / f"{self.name}_world_state.json"
        if world_path.exists():
            self.world.load_state(world_path)
        
        # Load agent states
        for name, agent in self.agents.items():
            agent_path = data_dir / f"{self.name}_{name.lower()}_state.json"
            if agent_path.exists():
                agent.load_state(agent_path)


class DualHemisphereSim:
    """
    Manages two independent hemisphere simulations.
    
    East and West run independently with their own agents, ticks, and memories.
    Eventually, exploration may lead to discovery between hemispheres.
    """

    def __init__(self, config: WorldSimConfig | None = None) -> None:
        self.config = config or WorldSimConfig.from_env()
        self.data_dir = Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create hemisphere simulations
        self.east = self._create_hemisphere("east")
        self.west = self._create_hemisphere("west")
        
        # Load saved state
        self.east.load_state(self.data_dir)
        self.west.load_state(self.data_dir)

    def _create_hemisphere(self, name: str) -> HemisphereSim:
        """Create a hemisphere simulation instance."""
        world = WorldState(name=f"{name.title()} Hemisphere")
        
        # Create agents for this hemisphere
        agents: dict[str, WorldAgent] = {}
        
        if name == "east":
            adam = create_adam()
            adam.region = "east"
            adam.persistent_memory = PersistentMemory("east_adam", self.data_dir / "memories")
            agents["Adam"] = adam
            
            eve = create_eve()
            eve.region = "east"
            eve.persistent_memory = PersistentMemory("east_eve", self.data_dir / "memories")
            agents["Eve"] = eve
        else:
            # West hemisphere - create new agents
            adam = create_adam()
            adam.name = "West Adam"
            adam.role = "first human of the West, explorer"
            adam.region = "west"
            adam.persistent_memory = PersistentMemory("west_adam", self.data_dir / "memories")
            agents["West Adam"] = adam
            
            eve = create_eve()
            eve.name = "West Eve"
            eve.role = "first woman of the West, discoverer"
            eve.region = "west"
            eve.persistent_memory = PersistentMemory("west_eve", self.data_dir / "memories")
            agents["West Eve"] = eve
        
        # Configure providers for each agent
        for agent_name, agent in agents.items():
            agent_cfg = self.config.agents.get(agent_name)
            if agent_cfg and agent_cfg.provider in ("nim-live", "nim-dry-run"):
                agent.set_provider(NvidiaNimProvider(
                    name=f"{agent_name.lower()}_nim",
                    api_key_env=agent_cfg.key_env,
                    model=agent_cfg.model,
                    mode=agent_cfg.provider,
                ))
            else:
                agent.set_provider(MockProvider(name=f"{agent_name.lower()}_mock"))
        
        engine = ConsequenceEngine()
        event_log = EventLog(log_path=self.data_dir / f"{name}_events.jsonl")
        event_log.load_all()
        
        return HemisphereSim(
            name=name,
            world=world,
            agents=agents,
            engine=engine,
            event_log=event_log,
        )

    def run_tick(self, hemisphere: str = "both") -> dict[str, Any]:
        """Run one tick for one or both hemispheres."""
        results = {}
        
        if hemisphere in ("east", "both"):
            results["east"] = self.east.run_tick()
        
        if hemisphere in ("west", "both"):
            results["west"] = self.west.run_tick()
        
        # Check for discovery between hemispheres
        if self._check_discovery():
            results["discovery"] = {
                "message": "The two hemispheres have discovered each other!",
                "tick_east": self.east.tick,
                "tick_west": self.west.tick,
            }
        
        # Save state periodically
        if self.east.tick % 10 == 0 or self.west.tick % 10 == 0:
            self.east.save_state(self.data_dir)
            self.west.save_state(self.data_dir)
        
        return results

    def _check_discovery(self) -> bool:
        """Check if the two hemispheres have discovered each other."""
        # Discovery happens when both hemispheres reach exploration level 5
        if self.east.exploration_level >= 5 and self.west.exploration_level >= 5:
            return True
        
        # Or after a certain number of ticks
        if self.east.tick >= 500 and self.west.tick >= 500:
            return True
        
        return False

    def get_state(self) -> dict[str, Any]:
        """Get combined state of both hemispheres."""
        return {
            "east": self.east.get_state(),
            "west": self.west.get_state(),
            "discovery": self._check_discovery(),
        }

    def add_agent(self, hemisphere: str, name: str, role: str = "", provider: str = "mock") -> bool:
        """Add a new agent to a hemisphere."""
        if hemisphere not in ("east", "west"):
            return False
        
        sim = self.east if hemisphere == "east" else self.west
        
        if name in sim.agents:
            return False
        
        agent = WorldAgent(
            name=name,
            role=role,
            region=hemisphere,
            enabled=True,
        )
        agent.persistent_memory = PersistentMemory(f"{hemisphere}_{name.lower()}", self.data_dir / "memories")
        
        if provider in ("nim-live", "nim-dry-run"):
            agent.set_provider(NvidiaNimProvider(
                name=f"{name.lower()}_nim",
                api_key_env=f"AGENT_{name.upper()}_NIM_KEY",
                mode=provider,
            ))
        else:
            agent.set_provider(MockProvider(name=f"{name.lower()}_mock"))
        
        sim.agents[name] = agent
        return True

    def remove_agent(self, hemisphere: str, name: str) -> bool:
        """Remove an agent from a hemisphere."""
        if hemisphere not in ("east", "west"):
            return False
        
        sim = self.east if hemisphere == "east" else self.west
        
        if name not in sim.agents:
            return False
        
        del sim.agents[name]
        return True

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
        
        # Configure providers for each agent using direct env vars
        provider_map = {
            "Adam": ("AGENT_EAST_ADAM_PROVIDER", "AGENT_EAST_ADAM_MODEL", "AGENT_EAST_ADAM_NIM_KEY"),
            "Eve": ("AGENT_EAST_EVE_PROVIDER", "AGENT_EAST_EVE_MODEL", "AGENT_EAST_EVE_NIM_KEY"),
            "West Adam": ("AGENT_WEST_ADAM_PROVIDER", "AGENT_WEST_ADAM_MODEL", "AGENT_WEST_ADAM_NIM_KEY"),
            "West Eve": ("AGENT_WEST_EVE_PROVIDER", "AGENT_WEST_EVE_MODEL", "AGENT_WEST_EVE_NIM_KEY"),
        }

        for agent_name, agent in agents.items():
            import os
            prov_env, model_env, key_env = provider_map.get(agent_name, (None, None, None))
            provider = os.environ.get(prov_env, "mock") if prov_env else "mock"
            model = os.environ.get(model_env, "meta/llama-3.1-8b-instruct") if model_env else "meta/llama-3.1-8b-instruct"

            if provider in ("nim-live", "nim-dry-run"):
                agent.set_provider(NvidiaNimProvider(
                    name=f"{agent_name.lower().replace(' ', '_')}_nim",
                    api_key_env=key_env or f"{prov_env.replace('_PROVIDER', '_NIM_KEY')}",
                    model=model,
                    mode=provider,
                ))
            else:
                agent.set_provider(MockProvider(name=f"{agent_name.lower().replace(' ', '_')}_mock"))
        
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

        # Update physical map positions & process landmark exploration
        self._update_map_positions(results)
        
        # Trigger Video Generation Pipeline if enabled
        try:
            from backend.providers.video_pipeline import video_pipeline
            if video_pipeline.cfg.enabled:
                narrative_parts = []
                if "east" in results and results["east"].get("status") == "ok":
                    narrative_parts.append(f"East: {results['east']['event']['narrative']}")
                if "west" in results and results["west"].get("status") == "ok":
                    narrative_parts.append(f"West: {results['west']['event']['narrative']}")
                if "discovery" in results:
                    narrative_parts.append(results["discovery"]["message"])
                
                if narrative_parts:
                    combined_narrative = " ".join(narrative_parts)
                    global_tick = self.east.tick
                    video_pipeline.process_tick(combined_narrative, global_tick)
        except Exception as video_err:
            logger.error("Video Pipeline failed during run_tick: %s", video_err)
        
        # Save state periodically
        if self.east.tick % 10 == 0 or self.west.tick % 10 == 0:
            self.east.save_state(self.data_dir)
            self.west.save_state(self.data_dir)
        
        return results

    def _update_map_positions(self, results: dict[str, Any]) -> None:
        """Update agent positions and discover landmarks on the map based on simulation results."""
        import json
        import random
        
        map_path = self.data_dir / "map_state.json"
        if not map_path.exists():
            return
            
        try:
            map_state = json.loads(map_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to load map state for update: %s", e)
            return

        # Create a mapping of agent keys to their action
        agent_actions = {}
        for hemis in ["east", "west"]:
            if hemis in results and results[hemis].get("status") == "ok":
                event = results[hemis].get("event", {})
                for name, data in event.get("agents", {}).items():
                    # Map e.g. "Adam" or "West Adam" -> "east_adam" or "west_adam"
                    clean_name = name.lower().replace("west ", "").replace("east ", "")
                    key = f"{hemis}_{clean_name}"
                    agent_actions[key] = data.get("action", "").lower()

        # Update coordinates and check discoveries
        for entity in map_state.get("entities", []):
            eid = entity.get("id")
            if eid in agent_actions:
                action = agent_actions[eid]
                x, y = entity.get("x", 0.5), entity.get("y", 0.5)
                
                # Check for exploration keywords
                is_exploring = any(w in action for w in ["explore", "discover", "wander", "walk", "travel", "climb", "search", "hunt", "go ", "move", "run", "seek", "survey", "scout"])
                
                if is_exploring:
                    dx = random.uniform(-0.06, 0.06)
                    dy = random.uniform(-0.06, 0.06)
                else:
                    # Minor drift
                    dx = random.uniform(-0.015, 0.015)
                    dy = random.uniform(-0.015, 0.015)
                    
                new_x = max(0.05, min(0.95, x + dx))
                new_y = max(0.05, min(0.95, y + dy))
                
                entity["x"] = round(new_x, 3)
                entity["y"] = round(new_y, 3)
                
                # Proximity to undiscovered locations in the same region
                for loc in map_state.get("entities", []):
                    if loc.get("region") == entity.get("region") and not loc.get("discovered") and loc.get("type") == "settlement":
                        lx, ly = loc.get("x", 0.5), loc.get("y", 0.5)
                        distance = ((new_x - lx) ** 2 + (new_y - ly) ** 2) ** 0.5
                        if distance < 0.15:  # Within discovery distance
                            loc["discovered"] = True
                            h_sim = self.east if entity.get("region") == "east" else self.west
                            loc["first_seen_tick"] = h_sim.tick
                            
                            # Increment exploration level
                            h_sim.exploration_level = min(5, h_sim.exploration_level + 1)
                            
                            # Log discovery event
                            discovery_msg = f"🌟 DISCOVERY: {entity.get('name')} has discovered {loc.get('name')}!"
                            h_sim.event_log.append({
                                "tick": h_sim.tick,
                                "hemisphere": h_sim.name,
                                "label": "DISCOVERY_EVENT",
                                "narrative": discovery_msg,
                                "agents": {},
                                "world_changes": {}
                            })
                            logger.info(discovery_msg)

        # Sync exploration level back to map_state regions
        if "regions" in map_state:
            if "east" in map_state["regions"]:
                map_state["regions"]["east"]["exploration_level"] = self.east.exploration_level
            if "west" in map_state["regions"]:
                map_state["regions"]["west"]["exploration_level"] = self.west.exploration_level

        # Save back
        try:
            map_path.write_text(json.dumps(map_state, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save updated map state: %s", e)

    def trigger_intervention(
        self,
        hemisphere: str,
        type: str,
        agent_name: str | None = None,
        details: str | None = None
    ) -> bool:
        """Trigger a divine creator intervention in one or both hemispheres."""
        hemispheres_to_affect = []
        if hemisphere == "both":
            hemispheres_to_affect = [self.east, self.west]
        elif hemisphere == "east":
            hemispheres_to_affect = [self.east]
        elif hemisphere == "west":
            hemispheres_to_affect = [self.west]
        else:
            return False

        for h_sim in hemispheres_to_affect:
            tick = h_sim.tick
            narrative = ""
            world_changes = {}
            label = "DIVINE_INTERVENTION"

            if type == "lightning":
                narrative = "⚡ A blazing bolt of lightning tears through the heavens! The sky darkens, thunder roars, and the earth trembles."
                world_changes = {
                    "weather": "storm",
                    "garden_condition": "wild",
                    "harmony_level": max(0.0, h_sim.world.harmony_level - 0.15)
                }
                # Apply directly
                h_sim.world.weather = "storm"
                h_sim.world.harmony_level = max(0.0, h_sim.world.harmony_level - 0.15)
                # Inject memories
                for agent in h_sim.agents.values():
                    agent.remember_event("⚡ [Divine Revelation] A powerful bolt of lightning struck nearby. The sky turned dark with thunderous clouds, leaving you in awe of the creator's power.")

            elif type == "rain":
                narrative = "🌧️ A gentle, life-giving rain begins to fall from the heavens, watering the soil and refreshing the garden."
                world_changes = {
                    "weather": "cool",
                    "garden_condition": "tended"
                }
                h_sim.world.weather = "cool"
                # Inject memories
                for agent in h_sim.agents.values():
                    agent.remember_event("🌧️ [Divine Blessing] A gentle, refreshing rain fell from the sky, feeding the plants and filling the water sources.")

            elif type == "blessing":
                narrative = "✨ A glorious golden light shines down from above. A feeling of divine peace, harmony, and abundance fills the atmosphere."
                world_changes = {
                    "harmony_level": min(1.0, h_sim.world.harmony_level + 0.2),
                    "garden_condition": "pristine"
                }
                h_sim.world.harmony_level = min(1.0, h_sim.world.harmony_level + 0.2)
                h_sim.world.garden_condition = "pristine"
                # Inject memories
                for agent in h_sim.agents.values():
                    agent.remember_event("✨ [Divine Blessing] You felt an overwhelming sense of warmth, peace, and abundance from the heavens. The land itself seems to glow with vitality.")

            elif type == "trial":
                narrative = "🔥 A severe trial is placed upon the land. Resources grow scarce, and the air grows hot and dry, testing the inhabitants' resilience."
                world_changes = {
                    "weather": "warm",
                    "garden_condition": "wild",
                }
                h_sim.world.weather = "warm"
                # Reduce resources
                for k in h_sim.world.resources:
                    h_sim.world.resources[k] = max(0.1, h_sim.world.resources[k] - 0.2)
                # Inject memories
                for agent in h_sim.agents.values():
                    agent.remember_event("🔥 [Divine Trial] The climate suddenly turned harsh, hot, and dry. Food and materials became harder to find. It is a time of testing.")

            elif type == "whisper":
                whisper_msg = details or "Walk uprightly and tend the garden."
                narrative = f"💭 A quiet, celestial whisper echoes directly into the mind."
                
                # If specific agent is specified
                if agent_name:
                    target_agent = None
                    for name, agent in h_sim.agents.items():
                        if name.lower() == agent_name.lower() or agent.name.lower() == agent_name.lower():
                            target_agent = agent
                            break
                    if target_agent:
                        target_agent.remember_event(f"💭 [Divine Whisper] You heard a soft, sacred voice whisper in your thoughts: '{whisper_msg}'")
                        narrative = f"💭 A quiet, celestial whisper from the Creator echoes in the mind of {target_agent.name}: '{whisper_msg}'"
                else:
                    # Whisper to everyone in the hemisphere
                    for agent in h_sim.agents.values():
                        agent.remember_event(f"💭 [Divine Whisper] You heard a soft, sacred voice whisper in your thoughts: '{whisper_msg}'")
                    narrative = f"💭 A quiet, celestial whisper echoes to all in the {h_sim.name.title()} Hemisphere: '{whisper_msg}'"

            # Log to event log
            event = {
                "tick": tick,
                "hemisphere": h_sim.name,
                "label": label,
                "narrative": narrative,
                "agents": {},
                "world_changes": world_changes,
            }
            h_sim.event_log.append(event)

        return True

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

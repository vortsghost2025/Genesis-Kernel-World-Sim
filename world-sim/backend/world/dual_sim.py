""" Dual Hemisphere Simulation Engine.

Runs two independent simulation instances (East and West) in parallel.
Each hemisphere has its own agents, tick counter, and world state.
Agents can eventually discover each other through exploration.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.config import WorldSimConfig
from backend.agents.base import WorldAgent
from backend.agents.adam import create_adam
from backend.agents.eve import create_eve
from backend.world.state import WorldState
from backend.world.consequence_engine import ConsequenceEngine
from backend.world.mechanics import WorldMechanics
from backend.memory.event_log import EventLog
from backend.memory.persistent_memory import PersistentMemory
from backend.providers.base import MockProvider, NvidiaNimProvider, call_log
from backend.providers.video_pipeline import VideoPipeline

logger = logging.getLogger("world.dual_sim")


@dataclass
class HemisphereSim:
    """A single hemisphere simulation instance."""

    name: str
    world: WorldState
    agents: dict[str, WorldAgent]
    engine: ConsequenceEngine
    event_log: EventLog
    mechanics: WorldMechanics
    tick: int = 0
    enabled: bool = True
    exploration_level: int = 0
    video_pipeline: VideoPipeline | None = None

    def run_tick(self) -> dict[str, Any]:
        if not self.enabled:
            return {"tick": self.tick, "status": "disabled"}
        self.tick += 1

        # Receive whispers before acting
        for agent in self.agents.values():
            if agent.enabled:
                agent.receive_whispers()

        world_snapshot = self.world.observe()
        world_snapshot["hemisphere"] = self.name
        world_snapshot["exploration_level"] = self.exploration_level
        agent_actions = []
        for name, agent in self.agents.items():
            if agent.enabled:
                action = agent.decide(world_snapshot)
                agent_actions.append(action)
        consequences = self.engine.resolve(
            agent_actions, world_snapshot,
            agents=self.agents, mechanics=self.mechanics,
        )
        self.world.apply_changes(consequences["world_changes"])
        self.world.advance_tick()
        mechanics_changes = self.mechanics.advance_tick(self.tick)

        # Deliver inter-agent whispers from consequence engine
        for w in consequences.get("whispers", []):
            from_name = w.get("from", "")
            content = w.get("content", "")
            for name, agent in self.agents.items():
                if name != from_name and agent.enabled:
                    agent.persistent_memory.add_whisper(
                        from_agent=from_name,
                        content=content,
                        tick=self.tick,
                        importance=0.7,
                    )

        for name, agent in self.agents.items():
            agent_result = next(
                (r for r in consequences["agent_results"] if r["agent"] == name), None,
            )
            if agent_result:
                agent.remember_event(agent_result["consequence_summary"])
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
            "mechanics_changes": mechanics_changes,
        }
        self.event_log.append(event)
        if self.video_pipeline and self.video_pipeline.enabled:
            try:
                self.video_pipeline.process_tick(
                    tick=self.tick,
                    hemisphere=self.name,
                    narrative=consequences.get("narrative", ""),
                    world_snapshot=world_snapshot,
                    agent_key=f"{self.name}_narrator",
                )
            except Exception as exc:
                logger.warning("video pipeline skipped tick=%d: %s", self.tick, exc)
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
                    "current_thought": agent.current_thought[:120] if agent.current_thought else "",
                    "current_action": agent.current_action[:120] if agent.current_action else "",
                    "current_goal": agent.current_goal,
                    "goals": agent.goals,
                    "relationships": agent.relationships,
                    "exploration_level": self.exploration_level,
                    "memory_count": len(agent.persistent_memory.memories),
                    "skills": [
                        {"name": s.name, "level": round(s.level, 3)}
                        for s in self.mechanics.get_agent_skills(name)
                    ],
                }
                for name, agent in self.agents.items()
            },
            "mechanics": self.mechanics.get_state(),
        }

    def save_state(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self.world.save_state(data_dir / f"{self.name}_world_state.json")
        for name, agent in self.agents.items():
            agent.save_state(data_dir / f"{self.name}_{name.lower()}_state.json")

    def load_state(self, data_dir: Path) -> None:
        world_path = data_dir / f"{self.name}_world_state.json"
        if world_path.exists():
            self.world.load_state(world_path)
        for name, agent in self.agents.items():
            agent_path = data_dir / f"{self.name}_{name.lower()}_state.json"
            if agent_path.exists():
                agent.load_state(agent_path)


class DualHemisphereSim:
    """Manages two independent hemisphere simulations."""

    def __init__(self, config: WorldSimConfig | None = None) -> None:
        self.config = config or WorldSimConfig.from_env()
        self.data_dir = Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Video pipeline (HLS streaming) — must come BEFORE hemisphere creation
        self.video_pipeline = VideoPipeline(self.config.video)
        self.east = self._create_hemisphere("east")
        self.west = self._create_hemisphere("west")
        self.east.load_state(self.data_dir)
        self.west.load_state(self.data_dir)
        self._init_map_state()
        # Restore exploration_level from map_state.json seed values
        self._restore_exploration_levels()

    def _init_map_state(self) -> None:
        import json
        map_path = self.data_dir / "map_state.json"
        if map_path.exists():
            return
        initial = {
            "entities": [
                {
                    "id": "east_adam",
                    "name": "Adam",
                    "type": "character",
                    "region": "east",
                    "x": 0.48, "y": 0.42,
                    "color": "#60a5fa",
                    "icon": "👤",
                    "discovered": True,
                    "description": "First human of the East. Tends the garden, names the creatures, seeks water.",
                    "first_seen_tick": 1,
                },
                {
                    "id": "east_eve",
                    "name": "Eve",
                    "type": "character",
                    "region": "east",
                    "x": 0.52, "y": 0.48,
                    "color": "#f87171",
                    "icon": "👤",
                    "discovered": True,
                    "description": "Companion of the East. Curious, relational, explores the garden boundaries.",
                    "first_seen_tick": 1,
                },
                {
                    "id": "west_adam",
                    "name": "West Adam",
                    "type": "character",
                    "region": "west",
                    "x": 0.52, "y": 0.42,
                    "color": "#ff8844",
                    "icon": "👤",
                    "discovered": False,
                    "description": "First human of the West. Explorer, builder, struggles against a harsh land.",
                    "first_seen_tick": None,
                },
                {
                    "id": "west_eve",
                    "name": "West Eve",
                    "type": "character",
                    "region": "west",
                    "x": 0.48, "y": 0.48,
                    "color": "#ff6644",
                    "icon": "👤",
                    "discovered": False,
                    "description": "Discoverer of the West. Watches the animals, reads the land for water.",
                    "first_seen_tick": None,
                },
                {
                    "id": "eden",
                    "name": "Eden",
                    "type": "landmark",
                    "region": "east",
                    "x": 0.50, "y": 0.45,
                    "color": "#4ade80",
                    "icon": "🌿",
                    "discovered": True,
                    "description": "The garden. Between two rivers. Tree of life and tree of knowledge grow here.",
                    "first_seen_tick": 1,
                },
                {
                    "id": "nod",
                    "name": "Nod",
                    "type": "settlement",
                    "region": "east",
                    "x": 0.62, "y": 0.50,
                    "color": "#d4a853",
                    "icon": "🏘️",
                    "discovered": True,
                    "description": "East of Eden. Where the first settlement rose outside the garden.",
                    "first_seen_tick": 1,
                },
                {
                    "id": "west_camp",
                    "name": "West Camp",
                    "type": "settlement",
                    "region": "west",
                    "x": 0.55, "y": 0.40,
                    "color": "#d4a853",
                    "icon": "🏕️",
                    "discovered": False,
                    "description": "A rough camp in the western wilderness. Built from whatever the land offered.",
                    "first_seen_tick": None,
                },
                {
                    "id": "mist_spring",
                    "name": "Mist Spring",
                    "type": "landmark",
                    "region": "west",
                    "x": 0.45, "y": 0.55,
                    "color": "#60a5fa",
                    "icon": "💧",
                    "discovered": False,
                    "description": "A hidden spring where mist collects at dawn. West Adam's hope.",
                    "first_seen_tick": None,
                },
            ],
            "regions": {
                "east": {"discovered": True, "exploration_level": 10, "name": "East Hemisphere"},
                "west": {"discovered": False, "exploration_level": 2, "name": "West Hemisphere"},
            },
            "disclaimer": "A world discovered through memory, choice, and consequence. Civilizations appear as agents explore, name, and build.",
        }
        map_path.write_text(json.dumps(initial, indent=2), encoding="utf-8")

    def _restore_exploration_levels(self) -> None:
        """Load exploration_level from map_state.json into hemisphere sims."""
        import json
        map_path = self.data_dir / "map_state.json"
        if not map_path.exists():
            return
        try:
            map_state = json.loads(map_path.read_text(encoding="utf-8"))
            regions = map_state.get("regions", {})
            if "east" in regions:
                self.east.exploration_level = regions["east"].get("exploration_level", 0)
            if "west" in regions:
                self.west.exploration_level = regions["west"].get("exploration_level", 0)
        except Exception:
            pass

    def _create_hemisphere(self, name: str) -> HemisphereSim:
        world = WorldState(name=f"{name.title()} Hemisphere")
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
        provider_map = {
            "Adam": ("AGENT_EAST_ADAM_PROVIDER", "AGENT_EAST_ADAM_MODEL", "AGENT_EAST_ADAM_NIM_KEY"),
            "Eve": ("AGENT_EAST_EVE_PROVIDER", "AGENT_EAST_EVE_MODEL", "AGENT_EAST_EVE_NIM_KEY"),
            "West Adam": ("AGENT_WEST_ADAM_PROVIDER", "AGENT_WEST_ADAM_MODEL", "AGENT_WEST_ADAM_NIM_KEY"),
            "West Eve": ("AGENT_WEST_EVE_PROVIDER", "AGENT_WEST_EVE_MODEL", "AGENT_WEST_EVE_NIM_KEY"),
        }
        for agent_name, agent in agents.items():
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
        mechanics = WorldMechanics(self.data_dir / "mechanics" / name)
        return HemisphereSim(
            name=name, world=world, agents=agents, engine=engine,
            event_log=event_log, mechanics=mechanics, video_pipeline=self.video_pipeline,
        )

    def run_tick(self, hemisphere: str = "both") -> dict[str, Any]:
        results = {}
        if hemisphere in ("east", "both"):
            results["east"] = self.east.run_tick()
        if hemisphere in ("west", "both"):
            results["west"] = self.west.run_tick()
        if self._check_discovery():
            results["discovery"] = {
                "message": "The two hemispheres have discovered each other!",
                "tick_east": self.east.tick,
                "tick_west": self.west.tick,
            }
        self._update_map_positions(results)
        if self.east.tick % 10 == 0 or self.west.tick % 10 == 0:
            self.east.save_state(self.data_dir)
            self.west.save_state(self.data_dir)
        return results

    def _update_map_positions(self, results: dict[str, Any]) -> None:
        import json
        import random
        map_path = self.data_dir / "map_state.json"
        if not map_path.exists():
            return
        try:
            map_state = json.loads(map_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to load map state: %s", e)
            return
        agent_actions = {}
        for hemis in ["east", "west"]:
            if hemis in results and results[hemis].get("status") == "ok":
                event = results[hemis].get("event", {})
                for name, data in event.get("agents", {}).items():
                    clean_name = name.lower().replace("west ", "").replace("east ", "")
                    key = f"{hemis}_{clean_name}"
                    agent_actions[key] = data.get("action", "").lower()
        for entity in map_state.get("entities", []):
            eid = entity.get("id")
            if eid in agent_actions:
                action = agent_actions[eid]
                x, y = entity.get("x", 0.5), entity.get("y", 0.5)
                is_exploring = any(w in action for w in ["explore", "discover", "wander", "walk", "travel", "climb", "search", "hunt", "go ", "move", "run", "seek", "survey", "scout"])
                dx = random.uniform(-0.06, 0.06) if is_exploring else random.uniform(-0.015, 0.015)
                dy = random.uniform(-0.06, 0.06) if is_exploring else random.uniform(-0.015, 0.015)
                new_x = max(0.05, min(0.95, x + dx))
                new_y = max(0.05, min(0.95, y + dy))
                entity["x"] = round(new_x, 3)
                entity["y"] = round(new_y, 3)
                for loc in map_state.get("entities", []):
                    if loc.get("region") == entity.get("region") and not loc.get("discovered") and loc.get("type") == "settlement":
                        lx, ly = loc.get("x", 0.5), loc.get("y", 0.5)
                        distance = ((new_x - lx) ** 2 + (new_y - ly) ** 2) ** 0.5
                        if distance < 0.15:
                            loc["discovered"] = True
                            h_sim = self.east if entity.get("region") == "east" else self.west
                            loc["first_seen_tick"] = h_sim.tick
                            h_sim.exploration_level = min(5, h_sim.exploration_level + 1)
                            discovery_msg = f"DISCOVERY: {entity.get('name')} discovered {loc.get('name')}!"
                            h_sim.event_log.append({
                                "tick": h_sim.tick,
                                "hemisphere": h_sim.name,
                                "label": "DISCOVERY_EVENT",
                                "narrative": discovery_msg,
                                "agents": {}, "world_changes": {},
                            })
                            logger.info(discovery_msg)
        if "regions" in map_state:
            if "east" in map_state["regions"]:
                stored = map_state["regions"]["east"].get("exploration_level", 0)
                map_state["regions"]["east"]["exploration_level"] = max(stored, self.east.exploration_level)
            if "west" in map_state["regions"]:
                stored = map_state["regions"]["west"].get("exploration_level", 0)
                map_state["regions"]["west"]["exploration_level"] = max(stored, self.west.exploration_level)
        try:
            map_path.write_text(json.dumps(map_state, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save map state: %s", e)

    def trigger_intervention(self, hemisphere, type, agent_name=None, details=None) -> bool:
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
            if type == "lightning":
                narrative = "A blazing bolt of lightning tears through the heavens!"
                world_changes = {"weather": "storm", "garden_condition": "wild"}
                h_sim.world.weather = "storm"
                h_sim.world.harmony_level = max(0.0, h_sim.world.harmony_level - 0.15)
                for agent in h_sim.agents.values():
                    agent.remember_event("Divine Revelation: Lightning struck nearby.")
            elif type == "rain":
                narrative = "A gentle, life-giving rain begins to fall from the heavens."
                world_changes = {"weather": "cool", "garden_condition": "tended"}
                h_sim.world.weather = "cool"
                for agent in h_sim.agents.values():
                    agent.remember_event("Divine Blessing: A gentle rain fell from the sky.")
            elif type == "blessing":
                narrative = "A glorious golden light shines down from above."
                world_changes = {"harmony_level": min(1.0, h_sim.world.harmony_level + 0.2), "garden_condition": "pristine"}
                h_sim.world.harmony_level = min(1.0, h_sim.world.harmony_level + 0.2)
                h_sim.world.garden_condition = "pristine"
                for agent in h_sim.agents.values():
                    agent.remember_event("Divine Blessing: Warmth and peace filled the atmosphere.")
            elif type == "trial":
                narrative = "A severe trial is placed upon the land."
                world_changes = {"weather": "warm", "garden_condition": "wild"}
                h_sim.world.weather = "warm"
                for k in h_sim.world.resources:
                    h_sim.world.resources[k] = max(0.1, h_sim.world.resources[k] - 0.2)
                for agent in h_sim.agents.values():
                    agent.remember_event("Divine Trial: The climate turned harsh and dry.")
            elif type == "whisper":
                whisper_msg = details or "Walk uprightly and tend the garden."
                narrative = f"A quiet, celestial whisper echoes into the mind: {whisper_msg}"
                if agent_name:
                    target_agent = None
                    for a in h_sim.agents.values():
                        if a.name.lower() == agent_name.lower() or a.name.lower().replace("west ", "") == agent_name.lower():
                            target_agent = a
                            break
                    if target_agent:
                        target_agent.remember_event(f"Divine Whisper: {whisper_msg}")
                else:
                    for agent in h_sim.agents.values():
                        agent.remember_event(f"Divine Whisper: {whisper_msg}")
            event = {"tick": tick, "hemisphere": h_sim.name, "label": "DIVINE_INTERVENTION", "narrative": narrative, "agents": {}, "world_changes": world_changes}
            h_sim.event_log.append(event)
        return True

    def _check_discovery(self) -> bool:
        if self.east.exploration_level >= 5 and self.west.exploration_level >= 5:
            return True
        if self.east.tick >= 500 and self.west.tick >= 500:
            return True
        return False

    def get_state(self) -> dict[str, Any]:
        return {"east": self.east.get_state(), "west": self.west.get_state(), "discovery": self._check_discovery()}

    def add_agent(self, hemisphere: str, name: str, role: str = "", provider: str = "mock") -> bool:
        if hemisphere not in ("east", "west"):
            return False
        sim = self.east if hemisphere == "east" else self.west
        if name in sim.agents:
            return False
        agent = WorldAgent(name=name, role=role, region=hemisphere, enabled=True)
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
        if hemisphere not in ("east", "west"):
            return False
        sim = self.east if hemisphere == "east" else self.west
        if name not in sim.agents:
            return False
        del sim.agents[name]
        return True

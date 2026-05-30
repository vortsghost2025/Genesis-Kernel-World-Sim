"""
World Sim — Main simulation loop.

Runs the observe → decide → act → consequence → memory loop.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import WorldSimConfig, config
from backend.agents.base import WorldAgent
from backend.agents.adam import create_adam
from backend.agents.eve import create_eve
from backend.world.state import WorldState
from backend.world.consequence_engine import ConsequenceEngine
from backend.memory.event_log import EventLog
from backend.providers.base import MockProvider, NvidiaNimProvider, call_log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("world.sim")


def setup_agents(cfg: WorldSimConfig) -> dict[str, WorldAgent]:
    """Create and configure agents based on config."""
    agents: dict[str, WorldAgent] = {}

    # Create default agents if not configured
    if "Adam" not in cfg.agents:
        agents["Adam"] = create_adam()
    if "Eve" not in cfg.agents:
        agents["Eve"] = create_eve()

    # Configure providers for each agent
    for name, agent in agents.items():
        agent_cfg = cfg.agents.get(name)
        if agent_cfg and agent_cfg.provider in ("nim-live", "nim-dry-run"):
            agent.set_provider(NvidiaNimProvider(
                name=f"{name.lower()}_nim",
                api_key_env=agent_cfg.key_env,
                model=agent_cfg.model,
                mode=agent_cfg.provider,
            ))
        else:
            agent.set_provider(MockProvider(name=f"{name.lower()}_mock"))

        # Apply traits from config
        if agent_cfg and agent_cfg.traits:
            agent.traits.update(agent_cfg.traits)

    return agents


def run_simulation(ticks: int = 10, interval_ms: int = 1000) -> None:
    """
    Run the world simulation.

    Each tick:
      1. World observes → world snapshot
      2. Each agent decides → thought + action
      3. Consequence engine resolves outcomes
      4. World state updates
      5. Agents remember consequences
      6. Event is logged
    """
    cfg = WorldSimConfig.from_env()
    warnings = cfg.validate()
    for w in warnings:
        logger.warning(w)

    world = WorldState()
    agents = setup_agents(cfg)
    engine = ConsequenceEngine()
    event_log = EventLog(log_path=PROJECT_ROOT / "data" / "events.jsonl")

    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Load saved state
    world.load_state(data_dir / "world_state.json")
    for name, agent in agents.items():
        agent.load_state(data_dir / f"{name.lower()}_state.json")
    event_log.load_all()

    start_tick = world.tick + 1
    logger.info("World Sim starting at tick %d, running %d ticks", start_tick, ticks)
    logger.info("Agents: %s", ", ".join(agents.keys()))

    for tick_num in range(start_tick, start_tick + ticks):
        # 1. World observes
        world_snapshot = world.observe()

        # 2. Each agent decides
        agent_actions = []
        for name, agent in agents.items():
            if agent.enabled:
                action = agent.decide(world_snapshot)
                agent_actions.append(action)

        # 3. Consequence engine resolves
        consequences = engine.resolve(agent_actions, world_snapshot)

        # 4. Apply world changes
        world.apply_changes(consequences["world_changes"])
        world.advance_tick()

        # 5. Agents remember
        for name, agent in agents.items():
            agent_result = next(
                (r for r in consequences["agent_results"] if r["agent"] == name),
                None,
            )
            if agent_result:
                agent.remember(agent_result)

        # 6. Log event
        event_log.append({
            "tick": tick_num,
            "label": consequences["label"],
            "narrative": consequences["narrative"],
            "agents": {
                name: {
                    "thought": a.get("thought", ""),
                    "action": a.get("action", ""),
                }
                for a in agent_actions
            },
            "world_changes": consequences["world_changes"],
        })

        # Print tick output
        logger.info(
            "Tick %d: %s",
            tick_num,
            consequences["narrative"][:100],
        )

        # Save state periodically
        if tick_num % cfg.save_interval == 0:
            world.save_state(data_dir / "world_state.json")
            for name, agent in agents.items():
                agent.save_state(data_dir / f"{name.lower()}_state.json")
            logger.info("State saved at tick %d", tick_num)

        # Wait between ticks
        if interval_ms > 0:
            time.sleep(interval_ms / 1000)

    # Final save
    world.save_state(data_dir / "world_state.json")
    for name, agent in agents.items():
        agent.save_state(data_dir / f"{name.lower()}_state.json")

    # Print summary
    summary = event_log.summary()
    provider_summary = call_log.summary()
    logger.info("Simulation complete.")
    logger.info("Total events: %d", summary["total_events"])
    logger.info("Provider calls: %d", provider_summary["total_calls"])


if __name__ == "__main__":
    ticks = 10
    interval = 1000
    if len(sys.argv) > 1:
        try:
            ticks = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python main.py [num_ticks] [interval_ms]")
            sys.exit(1)
    if len(sys.argv) > 2:
        try:
            interval = int(sys.argv[2])
        except ValueError:
            pass

    run_simulation(ticks=ticks, interval_ms=interval)

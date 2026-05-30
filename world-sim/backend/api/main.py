"""
FastAPI server — World Sim Creator Dashboard.

Endpoints:
  GET  /sim              — Creator dashboard UI
  GET  /api/state        — Current world state
  GET  /api/agents       — List all agents
  GET  /api/agents/<name> — Agent details
  POST /api/agents       — Add new agent
  DELETE /api/agents/<name> — Remove agent
  GET  /api/events       — Recent events
  GET  /api/timeline     — Full timeline
  POST /api/tick         — Advance one tick
  POST /api/run          — Run N ticks
  POST /api/reset        — Reset simulation
  GET  /api/providers    — Provider call log
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
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

# Load .env file
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ[_k.strip()] = _v.strip()

app = FastAPI(title="World Sim API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Singleton simulation state ---
data_dir = PROJECT_ROOT / "data"
data_dir.mkdir(parents=True, exist_ok=True)

cfg = WorldSimConfig.from_env()
world = WorldState()
agents: dict[str, WorldAgent] = {"Adam": create_adam(), "Eve": create_eve()}
engine = ConsequenceEngine()
event_log = EventLog(log_path=data_dir / "events.jsonl")

# Load saved state
world.load_state(data_dir / "world_state.json")
for name, agent in agents.items():
    agent.load_state(data_dir / f"{name.lower()}_state.json")
event_log.load_all()


def _setup_providers() -> None:
    """Configure providers for all agents."""
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


_setup_providers()


def _advance_one_tick() -> dict:
    """Run a single simulation tick."""
    world_snapshot = world.observe()

    agent_actions = []
    for name, agent in agents.items():
        if agent.enabled:
            action = agent.decide(world_snapshot)
            agent_actions.append(action)

    consequences = engine.resolve(agent_actions, world_snapshot)
    world.apply_changes(consequences["world_changes"])
    world.advance_tick()

    for name, agent in agents.items():
        agent_result = next(
            (r for r in consequences["agent_results"] if r["agent"] == name),
            None,
        )
        if agent_result:
            agent.remember(agent_result)

    event = {
        "tick": world.tick,
        "label": consequences["label"],
        "narrative": consequences["narrative"],
        "agents": {
            name: {"thought": a.get("thought", ""), "action": a.get("action", "")}
            for a in agent_actions
        },
        "world_changes": consequences["world_changes"],
    }
    event_log.append(event)

    # Persist
    world.save_state(data_dir / "world_state.json")
    for name, agent in agents.items():
        agent.save_state(data_dir / f"{name.lower()}_state.json")

    return event


# --- Pydantic models ---
class AddAgentRequest(BaseModel):
    name: str
    role: str = ""
    provider: str = "mock"
    model: str = "meta/llama-3.1-8b-instruct"
    key_env: str = ""
    traits: dict[str, float] = {}


# --- Routes ---

@app.get("/sim")
def serve_sim():
    """Serve the creator dashboard."""
    ui_path = PROJECT_ROOT / "frontend" / "sim.html"
    return FileResponse(ui_path)


@app.get("/map")
def serve_map():
    """Serve the ancient world map."""
    ui_path = PROJECT_ROOT / "frontend" / "map.html"
    return FileResponse(ui_path)


@app.get("/api/state")
def get_world_state():
    """Return current world state."""
    return {
        "tick": world.tick,
        "day": world.day,
        "time_of_day": world.time_of_day,
        "weather": world.weather,
        "garden_condition": world.garden_condition,
        "resources": world.resources,
        "structures": world.structures,
        "harmony_level": world.harmony_level,
        "boundary_respected": world.boundary_respected,
        "animals_present": world.animals_present,
    }


@app.get("/api/agents")
def get_agents():
    """Return all agents."""
    return {
        name: {
            "name": agent.name,
            "role": agent.role,
            "tick": agent.tick,
            "enabled": agent.enabled,
            "traits": agent.traits,
            "current_thought": agent.current_thought,
            "current_action": agent.current_action,
            "memory_count": len(agent.memory),
            "provider": agent.provider.name,
        }
        for name, agent in agents.items()
    }


@app.post("/api/agents")
def add_agent(req: AddAgentRequest):
    """Add a new agent to the simulation."""
    if req.name in agents:
        raise HTTPException(status_code=400, detail=f"Agent {req.name} already exists")

    agent = WorldAgent(
        name=req.name,
        role=req.role,
        traits=req.traits or {},
        enabled=True,
    )

    if req.provider in ("nim-live", "nim-dry-run"):
        agent.set_provider(NvidiaNimProvider(
            name=f"{req.name.lower()}_nim",
            api_key_env=req.key_env or f"AGENT_{req.name.upper()}_NIM_KEY",
            model=req.model,
            mode=req.provider,
        ))
    else:
        agent.set_provider(MockProvider(name=f"{req.name.lower()}_mock"))

    agents[req.name] = agent
    cfg.add_agent(req.name, req.role, req.model, req.key_env)

    return {"status": "ok", "agent": req.name}


@app.delete("/api/agents/{name}")
def remove_agent(name: str):
    """Remove an agent from the simulation."""
    if name not in agents:
        raise HTTPException(status_code=404, detail=f"Agent {name} not found")
    del agents[name]
    cfg.remove_agent(name)
    return {"status": "ok", "agent": name}


@app.get("/api/events")
def get_events(limit: int = 50):
    """Return recent events."""
    return event_log.recent(limit)


@app.get("/api/timeline")
def get_timeline():
    """Return full event timeline."""
    return event_log.events


@app.post("/api/tick")
def advance_tick():
    """Advance the simulation by one tick."""
    event = _advance_one_tick()
    return {"status": "ok", "event": event}


@app.post("/api/run")
def run_ticks(count: int = 5):
    """Run N ticks of simulation."""
    events = []
    for _ in range(count):
        event = _advance_one_tick()
        events.append(event)
    return {"status": "ok", "ticks_run": count, "events": events}


@app.post("/api/reset")
def reset_simulation():
    """Reset the simulation to initial state."""
    global world, agents, event_log

    world = WorldState()
    agents = {"Adam": create_adam(), "Eve": create_eve()}
    event_log = EventLog(log_path=data_dir / "events.jsonl")
    call_log.clear()

    # Clear saved state
    for f in data_dir.glob("*.json"):
        f.unlink()
    for f in data_dir.glob("*.jsonl"):
        f.unlink()

    _setup_providers()

    return {"status": "ok", "message": "Simulation reset"}


@app.get("/api/providers")
def get_providers():
    """Return provider call log summary."""
    return {
        "config": {
            "provider_mode": cfg.provider_mode,
            "tick_interval_ms": cfg.tick_interval_ms,
        },
        "call_log": call_log.summary(),
        "recent_calls": call_log.recent(20),
    }

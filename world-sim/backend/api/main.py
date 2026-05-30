"""
FastAPI server — World Sim Creator Dashboard (Dual Hemisphere).

Endpoints:
  GET  /sim              — Creator dashboard UI
  GET  /map              — World map
  GET  /api/state        — Combined world state
  GET  /api/state/east   — East hemisphere state
  GET  /api/state/west   — West hemisphere state
  GET  /api/agents       — List all agents
  GET  /api/agents/<name>/memory — Agent memories
  POST /api/agents       — Add new agent
  DELETE /api/agents/<name> — Remove agent
  GET  /api/events       — Recent events
  GET  /api/events/east  — East events
  GET  /api/events/west  — West events
  POST /api/tick         — Advance one tick (both hemispheres)
  POST /api/tick/east    — Advance east tick
  POST /api/tick/west    — Advance west tick
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
from backend.world.dual_sim import DualHemisphereSim
from backend.providers.base import call_log
from backend.key_management import save_keys, clear_keys, get_key_status, test_dry_run

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

app = FastAPI(title="World Sim API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dual hemisphere simulation ---
data_dir = PROJECT_ROOT / "data"
data_dir.mkdir(parents=True, exist_ok=True)

cfg = WorldSimConfig.from_env()
dual_sim = DualHemisphereSim(cfg)


# --- Pydantic models ---
class AddAgentRequest(BaseModel):
    name: str
    hemisphere: str = "east"
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
    """Serve the world map."""
    ui_path = PROJECT_ROOT / "frontend" / "map-v2.html"
    return FileResponse(ui_path)


@app.get("/data/base_map_clean.png")
def serve_base_map_clean():
    """Serve the clean Azgaar-generated base map (East) - no UI."""
    map_path = PROJECT_ROOT / "data" / "base_map_clean.png"
    if map_path.exists():
        return FileResponse(map_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Clean base map not found")


@app.get("/data/base_map_west_clean.png")
def serve_base_map_west_clean():
    """Serve the clean Azgaar-generated base map (West) - no UI."""
    map_path = PROJECT_ROOT / "data" / "base_map_west_clean.png"
    if map_path.exists():
        return FileResponse(map_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="West clean base map not found")


@app.get("/api/map-state")
def get_map_state():
    """Return map state JSON."""
    map_path = PROJECT_ROOT / "data" / "map_state.json"
    if map_path.exists():
        import json
        return json.loads(map_path.read_text(encoding="utf-8"))
    return {"entities": [], "disclaimer": "No map data available."}


# --- Key Management Endpoints ---

@app.get("/setup-keys")
def serve_setup_keys():
    """Serve the accessible key setup page."""
    ui_path = PROJECT_ROOT / "frontend" / "setup-keys.html"
    return FileResponse(ui_path)


@app.get("/api/setup-keys")
def get_setup_keys_status():
    """Return key presence status only — never key values."""
    return get_key_status()


@app.post("/api/setup-keys")
def post_setup_keys(body: dict):
    """Save keys to local .env only. Does NOT enable live mode."""
    return save_keys(body)


@app.post("/api/setup-keys/clear")
def post_clear_keys():
    """Clear keys from local .env and environment."""
    return clear_keys()


@app.get("/api/setup-keys/test")
def get_setup_keys_test():
    """Test dry-run for all agents."""
    return test_dry_run()


@app.get("/api/state")
def get_world_state():
    """Return combined state of both hemispheres."""
    return dual_sim.get_state()


@app.get("/api/state/east")
def get_east_state():
    """Return east hemisphere state."""
    return dual_sim.east.get_state()


@app.get("/api/state/west")
def get_west_state():
    """Return west hemisphere state."""
    return dual_sim.west.get_state()


@app.get("/api/agents")
def get_agents():
    """Return all agents from both hemispheres."""
    agents = {}
    for name, agent in dual_sim.east.agents.items():
        agents[f"east_{name}"] = {
            "name": agent.name,
            "hemisphere": "east",
            "role": agent.role,
            "tick": agent.tick,
            "enabled": agent.enabled,
            "traits": agent.traits,
            "current_thought": agent.current_thought,
            "current_action": agent.current_action,
            "memory_stats": agent.get_memory_stats(),
            "provider": agent.provider.name,
        }
    for name, agent in dual_sim.west.agents.items():
        agents[f"west_{name}"] = {
            "name": agent.name,
            "hemisphere": "west",
            "role": agent.role,
            "tick": agent.tick,
            "enabled": agent.enabled,
            "traits": agent.traits,
            "current_thought": agent.current_thought,
            "current_action": agent.current_action,
            "memory_stats": agent.get_memory_stats(),
            "provider": agent.provider.name,
        }
    return agents


@app.get("/api/agents/{agent_key}/memory")
def get_agent_memory(agent_key: str, limit: int = 20):
    """Return agent memories."""
    # Parse agent key (e.g., "east_Adam" or "west_Eve")
    if "_" not in agent_key:
        raise HTTPException(status_code=400, detail="Agent key must be in format 'hemisphere_name'")
    
    hemisphere, name = agent_key.split("_", 1)
    sim = dual_sim.east if hemisphere == "east" else dual_sim.west
    
    if name not in sim.agents:
        raise HTTPException(status_code=404, detail=f"Agent {name} not found in {hemisphere}")
    
    agent = sim.agents[name]
    memories = agent.persistent_memory.get_recent(limit)
    
    return {
        "agent": agent.name,
        "hemisphere": hemisphere,
        "memories": [m.to_dict() for m in memories],
        "stats": agent.get_memory_stats(),
    }


@app.post("/api/agents")
def add_agent(req: AddAgentRequest):
    """Add a new agent to a hemisphere."""
    if req.hemisphere not in ("east", "west"):
        raise HTTPException(status_code=400, detail="Hemisphere must be 'east' or 'west'")
    
    success = dual_sim.add_agent(req.hemisphere, req.name, req.role, req.provider)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to add agent {req.name}")
    
    return {"status": "ok", "agent": req.name, "hemisphere": req.hemisphere}


@app.delete("/api/agents/{agent_key}")
def remove_agent(agent_key: str):
    """Remove an agent from a hemisphere."""
    if "_" not in agent_key:
        raise HTTPException(status_code=400, detail="Agent key must be in format 'hemisphere_name'")
    
    hemisphere, name = agent_key.split("_", 1)
    success = dual_sim.remove_agent(hemisphere, name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent {name} not found in {hemisphere}")
    
    return {"status": "ok", "agent": name, "hemisphere": hemisphere}


@app.get("/api/events")
def get_events(hemisphere: str = "both", limit: int = 50):
    """Return recent events."""
    if hemisphere == "east":
        return dual_sim.east.event_log.recent(limit)
    elif hemisphere == "west":
        return dual_sim.west.event_log.recent(limit)
    else:
        # Combine both
        east_events = dual_sim.east.event_log.recent(limit // 2)
        west_events = dual_sim.west.event_log.recent(limit // 2)
        return east_events + west_events


@app.get("/api/events/east")
def get_east_events(limit: int = 50):
    """Return east hemisphere events."""
    return dual_sim.east.event_log.recent(limit)


@app.get("/api/events/west")
def get_west_events(limit: int = 50):
    """Return west hemisphere events."""
    return dual_sim.west.event_log.recent(limit)


@app.get("/api/timeline")
def get_timeline():
    """Return full event timeline from both hemispheres."""
    return {
        "east": dual_sim.east.event_log.events,
        "west": dual_sim.west.event_log.events,
    }


@app.post("/api/tick")
def advance_tick(hemisphere: str = "both"):
    """Advance one tick for one or both hemispheres."""
    results = dual_sim.run_tick(hemisphere)
    return {"status": "ok", "results": results}


@app.post("/api/tick/east")
def advance_east_tick():
    """Advance east hemisphere one tick."""
    return {"status": "ok", "results": {"east": dual_sim.run_tick("east")}}


@app.post("/api/tick/west")
def advance_west_tick():
    """Advance west hemisphere one tick."""
    return {"status": "ok", "results": {"west": dual_sim.run_tick("west")}}


@app.post("/api/run")
def run_ticks(count: int = 5, hemisphere: str = "both"):
    """Run N ticks."""
    results = []
    for _ in range(count):
        result = dual_sim.run_tick(hemisphere)
        results.append(result)
    return {"status": "ok", "ticks_run": count, "results": results}


@app.post("/api/reset")
def reset_simulation():
    """Reset the simulation."""
    global dual_sim
    dual_sim = DualHemisphereSim(cfg)
    call_log.clear()
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

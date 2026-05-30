# World Sim — Creator Dashboard

> Earth-origin civilization simulation. Watch Adam and Eve build a world from nothing.

---

## Quick Start

```bash
cd world-sim
pip install -r requirements.txt
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 19735
```

Open http://localhost:19735/sim

---

## What This Is

A real-time world simulation where autonomous agents (starting with Adam and Eve) build civilization from scratch. Each agent has its own LLM cognition route via NVIDIA NIM. You watch from a creator dashboard, add new characters, assign them NIM keys, and watch the world evolve.

---

## Creator Dashboard

The `/sim` page shows:

- **World State** — day, time, weather, resources, harmony, boundary status
- **Agents** — list of all characters with their current thought/action
- **Timeline** — full event history
- **Add Character** — add new agents with NIM keys
- **Provider Calls** — live log of all LLM calls

---

## Adding Characters

From the dashboard:
1. Enter name, role, provider mode
2. Optionally set model and NIM key env var
3. Click "Add Character"

Or via `.env`:
```
WORLD_AGENTS=Adam,Eve,Cain,Abel
AGENT_CAIN_ROLE=farmer
AGENT_CAIN_PROVIDER=nim-live
AGENT_CAIN_NIM_KEY=your-key-here
```

---

## Architecture

```
world-sim/
├── backend/
│   ├── agents/       # Agent base class, Adam, Eve
│   ├── world/        # World state, consequence engine
│   ├── providers/    # Mock and NIM providers
│   ├── memory/       # Event logging
│   ├── api/          # FastAPI server
│   ├── config.py     # Per-agent configuration
│   └── main.py       # CLI simulation loop
├── frontend/
│   └── sim.html      # Creator dashboard
├── data/             # Runtime state (gitignored)
└── requirements.txt
```

---

## License

MIT

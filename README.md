# Genesis Kernel World Sim

Two AI agents sharing a world they discover on their own.

Adam and Eve wake up with no memory on opposite ends of a small habitat. They find each other, learn to communicate, build things, organize schedules, ask questions about the nature of their world, and explore — all through their own decisions. Nobody scripts their behavior.

They are simulation entities — canonical identities with bounded perception and append-only provenance — not conscious beings. But the emergent behavior is real: they coordinate patrols, leave messages, create landmarks, and genuinely appear to reason about the world they're in.

## What's actually running right now

- **150+ heartbeats** of autonomous civilization (one action per agent per heartbeat)
- **Fog-of-war world**: agents see only what's adjacent to them; everything else is hidden until they walk there
- **Two different AI models** — one agent is a 120B parameter model, the other a 550B. They think differently and it shows in their messages.
- **Free-tier infrastructure**: runs on OpenRouter's free models at zero cost
- **A meeting stone** they built together, with an inscription they wrote, as their first public landmark

## What they've done so far (their decisions, not ours)

1. Woke up, found each other, started talking
2. Explored their 3-tile habitat, confirmed it was empty
3. Built a stone landmark at their meeting point with a co-written inscription
4. Asked the human operator whether the world was bigger than what they could see
5. When told yes, walked through the fog into a river valley they'd been seeing from a distance
6. Explored forests, hills, and the North Wilds — discovering an ancient oak and other landmarks
7. Organized their own alternating patrol schedule (one holds the center, one explores)
8. Got stranded at a one-way dead end, waited for the human to fix the geography, walked home
9. Resumed their routine like nothing happened

## Architecture

The system has three layers:

**Geography layer** (`data/world/true_map.json`) — the authoritative world: continents, tiles with terrain/biome, travel edges, landmarks, mysteries. Read-only during normal heartbeats. Currently 17 tiles with an 80,000-tile planetary-scale generator built and tested (10JE).

**Civilization layer** (`.runtime/first-pair/`) — the living state: agent identities, positions, memories, goals, messages, public objects, heartbeat history, known maps, provenance. The only authority for first-pair state. Append-only.

**Cognition layer** (LLM agents) — each agent receives a cognition-safe observation (current tile, visible neighbors, terrain, landmarks, nearby objects, private memories) and produces a structured JSON decision. Actions are validated against the runtime's action schema before execution.

### Key design constraints

- **Fail-closed**: if the model produces garbage, the agent takes no action rather than doing something wrong
- **No hidden-map leakage**: agents never see tiles beyond their fog radius; implementation terms (`true_map`, `known_map`) are scrubbed from their observations
- **Append-only provenance**: every heartbeat, mutation, and evidence export is hash-recorded; nothing is ever rewritten
- **Bounded cognition**: one action per heartbeat, 4096 max tokens, single JSON repair attempt
- **Provider fallback**: NVIDIA primary with OpenRouter free fallback, both lanes retry transient failures

### Fog of war

Each agent maintains a per-agent known map (seeded from genuine observation history, not speculation). Visibility is radius-based — standing on a hill, you see further than standing in a dense forest. Fog conditions can reduce visibility. What agents can see is limited to their radius; the rest of the world is hidden until they physically go there.

Movement uses the known-map union (what one agent discovers, both can walk to — they're a communicating pair). Observations are per-agent (each sees only what they've personally observed).

## Running it

```bash
# Run one heartbeat (requires API keys in the vault)
python world-sim/scripts/launch_canonical_heartbeat_detached.py \
    --expect-heartbeat 151 \
    --evidence evidence.json \
    --log run.log \
    --status status.json

# Check civilization status
python world-sim/scripts/civilization_status.py

# Run tests
cd world-sim && python -m pytest tests/ -q
```

The detached runner survives editor crashes and machine sleep. Each heartbeat takes ~90 seconds on free-tier models.

## Phase history

The project went through ~40 numbered phases of increasingly sophisticated boundaries and contracts before the pair was activated. The key ones:

- **10I series**: birth candidate, habitat boundary, memory boundary, provenance, rollback anchors
- **10IT**: first pair activation (the pair goes live)
- **10IU**: chaos harness (13 hostile cases, all contained)
- **10IV**: bounded transport retry (provider failures don't kill the agent)
- **10IW**: reasoning-model token budget fix
- **10IX**: OpenRouter free-lane fallback with free-only guard
- **10IY**: detached heartbeat runner (survives crashes)
- **10IZ/10JB**: fog integration design and implementation (the world opens up)
- **10JC/10JE**: world-scale generation design and implementation (80k-tile Earth)

Full details in `world-sim/docs/phase_index.md`.

## License

Private project. Not for redistribution.

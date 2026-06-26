# Phase 7 Fog Of War Scaffold

Phase 7 separates the world the engine knows from the world each agent knows.
The engine may hold a hidden true map. Agents only receive local observations
derived from their own position, visibility, and memory.

## Canon

Active first-pass canon:

- `east_adam` starts on Continent A.
- `east_eve` starts on Continent B.

Dormant-compatible scaffold:

- `west_adam` remains inactive but schema-compatible.
- `west_eve` remains inactive but schema-compatible.

The `east_` and `west_` prefixes are canonical ID namespaces only. Physical
location comes from `continent_id`, `region_id`, `tile_id`, and `coordinates`.

## Data Layers

Hidden true world, created only in a later gated phase:

```text
data/world/true_map.json
```

Per-agent known maps, created only in a later gated phase:

```text
data/agents/<agent_id>/known_map.json
data/agents/<agent_id>/world_position.json
```

The current 7C scaffold provides schemas, pure helpers, fixtures, and tests
only. It does not write active runtime data.

## Observation Radius

Initial observations use current tile plus a one-tile local ring. Dense forest,
caves, night, fog, and storms reduce visibility. Hills, coasts, open plains,
and clear visibility can increase it. Sounds, smoke, tracks, and other indirect
signals create hypotheses, not facts.

## Naming Rules

Engine landmark IDs remain stable and hidden. Agent names are stored in that
agent's known map. Two agents may name the same true landmark differently.
Renaming preserves previous names as history instead of rewriting memory.

## Contact Thresholds

Contact is evidence-based:

- Level 0: no evidence.
- Level 1: indirect anomaly.
- Level 2: repeated evidence.
- Level 3: intentional artifact or strong trace.
- Level 4: direct sighting or message.

Contact unlocks only at Level 4, or at Level 3 with explicit investigation.

## Migration Strategy

Future migration should treat `data/map_state.json` as a legacy UI projection,
not as the new source of truth. A compatibility bridge can project
`true_map + known_maps` back into `/api/map-state` while the frontend remains
unchanged.

## Future Gates

- 7D: migration script draft and dry-run report only.
- 7E: seed hidden true map in staging or fixtures, no runtime.
- 7F: no-provider observation probe on copied data only.
- 7G: canonical map migration with backup and audit, no provider.
- 7H: provider-capped local observation only, no movement.
- 7I: movement rules dry-run.
- 7J: contact evidence tests and UI projection review.

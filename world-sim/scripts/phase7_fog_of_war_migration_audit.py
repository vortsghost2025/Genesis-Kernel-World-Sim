"""Dry-run audit for future Phase 7 fog-of-war migration.

Reads current legacy map/registry inputs and reports what a later gated
migration would create. This script never writes canonical runtime data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    data_dir = project_root / "data"
    map_state = _read_json(data_dir / "map_state.json")
    registry = _read_json(data_dir / "agents" / "registry.json")

    registry_agents = {
        key: value
        for key, value in registry.items()
        if not key.startswith("$") and isinstance(value, dict)
    }
    active_canon = {"east_adam", "east_eve"}
    proposed_positions = []
    proposed_known_maps = []
    for entry in registry_agents.values():
        canonical_id = entry.get("canonical_id")
        proposed_known_maps.append(f"data/agents/{canonical_id}/known_map.json")
        proposed_positions.append({
            "agent_id": canonical_id,
            "path": f"data/agents/{canonical_id}/world_position.json",
            "active": canonical_id in active_canon,
        })

    return {
        "dry_run": True,
        "writes_performed": False,
        "map_state_shape": {
            "entities": len(map_state.get("entities", [])),
            "regions": sorted((map_state.get("regions") or {}).keys()),
            "has_disclaimer": "disclaimer" in map_state,
        },
        "agent_registry": {
            "count": len(registry_agents),
            "active_candidates": sorted(active_canon),
            "dormant_candidates": sorted(
                entry.get("canonical_id")
                for entry in registry_agents.values()
                if entry.get("canonical_id") not in active_canon
            ),
        },
        "would_create_later": {
            "true_map": "data/world/true_map.json",
            "known_maps": proposed_known_maps,
            "positions": proposed_positions,
        },
        "compatibility_risks": [
            "data/map_state.json uses global discovered flags, not per-agent known maps",
            "frontend /api/map-state consumers expect legacy entities/regions projection",
            "east_/west_ canonical IDs must not be interpreted as physical continent names",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 7 fog-of-war migration dry-run audit")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2))
        return
    print("Phase 7 fog-of-war migration audit (dry-run only)")
    print(f"Writes performed: {report['writes_performed']}")
    print(f"Map entities: {report['map_state_shape']['entities']}")
    print(f"Registry agents: {report['agent_registry']['count']}")
    print("Active candidates: " + ", ".join(report["agent_registry"]["active_candidates"]))
    print("Dormant candidates: " + ", ".join(report["agent_registry"]["dormant_candidates"]))
    print("Would create later:")
    print(f"- {report['would_create_later']['true_map']}")
    for path in report["would_create_later"]["known_maps"]:
        print(f"- {path}")


if __name__ == "__main__":
    main()

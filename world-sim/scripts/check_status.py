"""Quick status check for living pairs."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
WORLD_SIM = Path(__file__).resolve().parent.parent

for name, rel in [("east", ".runtime/first-pair"), ("west", ".runtime/first-pair-west")]:
    p = WORLD_SIM / rel / "world_state.json"
    if not p.is_file():
        continue
    data = json.loads(p.read_text(encoding="utf-8")).get("data", {})
    tick = data.get("tick")
    updated = data.get("updated_at_utc")
    agents = data.get("agents", {})
    occ = data.get("tile_occupancy", {})

    print(f"=== {name.upper()} PAIR (Tick {tick}) @ {updated} ===")
    for aref, pos in occ.items():
        astate = agents.get(aref, {})
        vitals = astate.get("vitals", {})
        downed = astate.get("downed", False)
        print(f"  {aref}: pos={pos} vitals={vitals} downed={downed}")

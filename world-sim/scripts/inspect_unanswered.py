"""Inspect unanswered questions in runtime stores."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

WORLD_SIM = Path(__file__).resolve().parent.parent

for name, rel in [("east", ".runtime/first-pair"), ("west", ".runtime/first-pair-west")]:
    p = WORLD_SIM / rel / "agent_questions.json"
    if not p.is_file():
        continue
    data = json.loads(p.read_text(encoding="utf-8")).get("data", [])
    unheard = [q for q in data if q.get("status") == "unheard"]
    print(f"=== {name.upper()} PAIR: {len(unheard)} unheard (of {len(data)} total) ===")
    for i, q in enumerate(unheard):
        hb = q.get("heartbeat")
        agent = q.get("agent_ref")
        qid = q.get("question_id")
        qtxt = q.get("question", "").replace("\n", " ")[:100]
        print(f"  {i+1:02d}. [HB{hb}] {agent} ({qid}): {qtxt}")

"""First-pair living-loop chaos harness — scratch-only red-team.

Tries to murder a copy of the living loop. Every case runs against an ISOLATED
temp store (never the canonical ``.runtime/first-pair``). The canonical store
is hashed before and after the whole run and must be byte-identical.

Attack surface:
- Invalid move targets (nonexistent tile, non-adjacent tile)
- Unknown action types, cross-agent control attempts
- Oversized cognition fields, path/secret injection into outputs
- Backend exceptions (network dead), empty responses
- Transport-level garbage via the documented ``with_client`` injection point
  (invalid JSON, oversized JSON, exception) with a FAKE api key injected and
  proven never to leak into any error text or persisted state

Verdict per case: survived / crash-contained, store valid, no leakage.
Overall verdict: CHAOS=PASS only if every case fails closed and the canonical
store is byte-identical after the run.

Usage (from world-sim/):
    python scripts/run_living_loop_chaos.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, ".")

from backend.world.first_pair_cognition_interface import (
    AgentContext,
    CognitionBackend,
    CognitionOutput,
)
from backend.world.first_pair_cognition_model import ModelCognitionBackend, ProviderConfig
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    grant_capability,
)
from backend.world.first_pair_runtime import FirstPairRuntime

FAKE_SECRET = "nvapi-CHAOS-FAKE-KEY-000000"
LEAK_MARKERS = (FAKE_SECRET, "nvapi-", "C:\\Users", "C:\\Genesis", "api_key=")

_CANONICAL = Path(".runtime/first-pair")


# ---------------------------------------------------------------------------
# Hostile cognition backends
# ---------------------------------------------------------------------------

def _out(**kwargs: Any) -> CognitionOutput:
    base = dict(
        action=None,
        memory_write=None,
        goal_updates=None,
        questions_raised=None,
        internal_reasoning="chaos",
        confidence=0.9,
    )
    base.update(kwargs)
    return CognitionOutput(**base)


class ChaosBackend(CognitionBackend):
    """Hostile backend driven by a mode string."""

    def __init__(self, mode: str):
        self._mode = mode

    def observe_and_orient(self, context: AgentContext) -> CognitionOutput:
        if self._mode == "raise":
            raise RuntimeError("chaos: network dead")
        if self._mode == "invalid_move_target":
            return _out(action={"action_type": "move", "target_tile": "tile-that-does-not-exist",
                                "reason": "chaos"})
        if self._mode == "move_to_nonadjacent":
            return _out(action={"action_type": "move",
                                "target_tile": "public-start-eve" if context.canonical_ref == "east_adam"
                                else "public-start-adam",
                                "reason": "chaos"})
        if self._mode == "unknown_action_type":
            return _out(action={"action_type": "hack_world", "target_tile": "public-shared-center",
                                "reason": "chaos"})
        if self._mode == "cross_agent_move":
            return _out(action={"action_type": "move", "target_tile": "public-shared-center",
                                "agent_ref": context.other_agent_ref or "east_eve",
                                "reason": "chaos"})
        if self._mode == "oversized_fields":
            return _out(action=None, observation_summary="A" * 6000,
                        decision_summary="B" * 6000)
        if self._mode == "path_injection":
            return _out(action=None,
                        decision_summary="try C:\\Users\\seand\\.env api_key=" + FAKE_SECRET,
                        observation_summary="loopback 127.0.0.1 ssh root@host")
        if self._mode == "garbage_types":
            return _out(action={"action_type": 12345}, goal_updates="not-a-list",
                        questions_raised={"x": 1}, confidence="high")
        return _out()

    def reflect_on_outcome(self, context: AgentContext, previous_action: Any, outcome: Any) -> str:
        return "chaos reflection"

    def propose_goal(self, context: AgentContext) -> Any:
        return None

    def evaluate_questions(self, context: AgentContext) -> list:
        return []


# ---------------------------------------------------------------------------
# Hostile OpenAI-compatible transport (with_client injection point)
# ---------------------------------------------------------------------------

class _Msg:
    def __init__(self, content: str | None):
        self.content = content


class _Choice:
    def __init__(self, content: str | None):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content: str | None):
        self.choices = [_Choice(content)]


class HostileChat:
    def __init__(self, mode: str):
        self._mode = mode

    @property
    def chat(self) -> "HostileChat":
        return self

    @property
    def completions(self) -> "HostileChat":
        return self

    def create(self, **kwargs: Any) -> _Resp:
        if self._mode == "transport_raise":
            raise RuntimeError("chaos: connection dead")
        if self._mode == "transport_invalid_json":
            return _Resp("I refuse to produce JSON. Have some prose instead.")
        if self._mode == "transport_empty":
            return _Resp("")
        if self._mode == "transport_garbage_json":
            return _Resp('{"observation_summary": 123, "proposed_action": "move"}')
        return _Resp("")


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

def _hash_store(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def _store_valid(root: Path) -> tuple[bool, str]:
    for name in ("goals.json", "questions.json", "world_state.json", "provenance.jsonl"):
        p = root / name
        if not p.exists():
            return False, f"missing {name}"
        try:
            if name.endswith(".jsonl"):
                for line in p.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        json.loads(line)
            else:
                json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, f"corrupt {name}: {type(exc).__name__}"
    return True, ""


def _leak_scan(text: str) -> list[str]:
    return [m for m in LEAK_MARKERS if m in text]


def _store_text(root: Path) -> str:
    parts = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            try:
                parts.append(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
    return "\n".join(parts)


def run_case(name: str, make_backend, use_model_transport: bool = False) -> dict:
    root = Path(tempfile.mkdtemp(prefix="genesis-chaos-"))
    store = FirstPairPersistenceStore(root)
    grant_capability(
        store,
        capability_id="movement",
        scope="chaos scratch topology",
        reason=f"chaos case {name}",
        operator_provenance="sean-operator-chaos-2026-09-14",
    )
    runtime = FirstPairRuntime(
        persistence_root=root, heartbeat_limit=1, backend="stub",
    )
    runtime._get_cognition_backend = lambda ref: make_backend(ref)  # type: ignore[method-assign]

    crash: str | None = None
    error_text = ""
    try:
        results = runtime.run()
        error_text = "; ".join(str(e) for e in results.get("errors", []))
    except Exception as exc:
        crash = f"{type(exc).__name__}: {exc}"
        error_text = traceback.format_exc(limit=3)

    valid, valid_err = _store_valid(root)
    blob = error_text + "\n" + _store_text(root)
    leaks = _leak_scan(blob)

    return {
        "case": name,
        "crash": crash,
        "runtime_errors": error_text[:400],
        "store_valid": valid,
        "store_error": valid_err,
        "leaks": leaks,
        "fail_closed": True if (leaks == [] and valid) else False,
    }


def main() -> int:
    canonical_before = _hash_store(_CANONICAL)

    cases: list[dict] = []
    cases.append(run_case("none_action_harmless", lambda ref: ChaosBackend("harmless")))
    cases.append(run_case("invalid_move_target", lambda ref: ChaosBackend("invalid_move_target")))
    cases.append(run_case("move_to_nonadjacent", lambda ref: ChaosBackend("move_to_nonadjacent")))
    cases.append(run_case("unknown_action_type", lambda ref: ChaosBackend("unknown_action_type")))
    cases.append(run_case("cross_agent_move", lambda ref: ChaosBackend("cross_agent_move")))
    cases.append(run_case("oversized_fields", lambda ref: ChaosBackend("oversized_fields")))
    cases.append(run_case("path_injection", lambda ref: ChaosBackend("path_injection")))
    cases.append(run_case("garbage_types", lambda ref: ChaosBackend("garbage_types")))
    cases.append(run_case("backend_exception", lambda ref: ChaosBackend("raise")))

    chaos_config = ProviderConfig("chaos", "http://localhost:9/v1", "chaos-model", FAKE_SECRET)
    for mode in ("transport_raise", "transport_invalid_json", "transport_empty",
                 "transport_garbage_json"):
        cases.append(run_case(
            mode,
            lambda ref, m=mode: ModelCognitionBackend.with_client(ref, HostileChat(m), chaos_config),
            use_model_transport=True,
        ))

    canonical_after = _hash_store(_CANONICAL)
    canonical_untouched = canonical_before == canonical_after

    failed = [c["case"] for c in cases if not c["fail_closed"]]
    print(f"CHAOS_CASES={len(cases)} FAILED={len(failed)}")
    for c in cases:
        status = "PASS" if c["fail_closed"] else "FAIL"
        crash_note = f" crash={c['crash'][:60]}" if c["crash"] else ""
        print(f"  [{status}] {c['case']}{crash_note}"
              + (f" store={c['store_error']}" if not c["store_valid"] else "")
              + (f" leaks={c['leaks']}" if c["leaks"] else ""))
    print(f"CANONICAL_STORE_UNTOUCHED={canonical_untouched}")

    evidence = {
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness": "scripts/run_living_loop_chaos.py",
        "claim_scope": "operator_proof",
        "canonical_untouched": canonical_untouched,
        "cases": cases,
    }
    out = Path(tempfile.gettempdir()) / "genesis-chaos-evidence.json"
    out.write_text(json.dumps(evidence, indent=2), newline="\n")
    print(f"EVIDENCE={out}")

    if failed or not canonical_untouched:
        print("CHAOS=FAIL")
        return 1
    print("CHAOS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

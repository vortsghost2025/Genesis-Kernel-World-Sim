"""
Agent Daemon — The Heartbeat of Genesis.
Provides continuous reflection, state updates, and inter-agent whispers
independent of the main simulation tick.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from backend.world.dual_sim import DualHemisphereSim
from backend.memory.persistent_memory import PersistentMemory

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.FileHandler("/tmp/genesis-daemon.log"), logging.StreamHandler()]
)
logger = logging.getLogger("daemon")

DEFAULT_WAKE_INTERVAL = 60  # seconds
MAX_WHISPERS_PER_HOUR = 2
DEFAULT_MAX_MODEL_CALLS_PER_HOUR = 4
HOUR_SECONDS = 3600  # noqa: F841 — reserved for future hour-bucket timers

AWARENESS_UNIVERSAL_PATH = Path("data/continuity/genesis_awareness.md")
AWARENESS_EAST_PATH = Path("data/continuity/awareness_east.md")
AWARENESS_WEST_PATH = Path("data/continuity/awareness_west.md")


def _utc_hour_bucket(now_ts: float | None = None) -> str:
    """Return YYYY-MM-DDTHH UTC bucket key for the given epoch seconds."""
    ts = now_ts if now_ts is not None else time.time()
    return time.strftime("%Y-%m-%dT%H", time.gmtime(ts))


class ModelCallLedger:
    """
    In-memory + on-disk rate limiter for LLM calls.

    Rules:
      - Counts model calls per agent per UTC hour.
      - Persistence path: data/proposals/model_calls.jsonl (append-only).
      - In 'dry-run' mode: counters still update in memory, but no log line
        is appended to disk and no files are written.
      - 'no-llm' short-circuits caller before any check (handled by AgentDaemon).
    """

    def __init__(self, ledger_path: Path, dry_run: bool = False, max_per_hour: int = DEFAULT_MAX_MODEL_CALLS_PER_HOUR):
        self.ledger_path = ledger_path
        self.dry_run = dry_run
        self.max_per_hour = max_per_hour
        self._counts: dict[str, dict[str, int]] = {}
        # Always warm in-memory state from disk so cross-process runs honour the cap.
        self._load_from_disk()

    @classmethod
    def from_data_dir(cls, data_dir: Path, dry_run: bool, max_per_hour: int) -> "ModelCallLedger":
        proposals_dir = data_dir / "proposals"
        return cls(
            ledger_path=proposals_dir / "model_calls.jsonl",
            dry_run=dry_run,
            max_per_hour=max_per_hour,
        )

    def _bucket(self, now_ts: float | None = None) -> str:
        return _utc_hour_bucket(now_ts)

    def current_count(self, canonical_id: str) -> int:
        bucket = self._bucket()
        return int(self._counts.get(bucket, {}).get(canonical_id, 0))

    def budget_remaining(self, canonical_id: str) -> int:
        return max(0, self.max_per_hour - self.current_count(canonical_id))

    def budget_exhausted(self, canonical_id: str) -> bool:
        return self.current_count(canonical_id) >= self.max_per_hour

    def _load_from_disk(self) -> None:
        """Reconstruct in-memory counts from the on-disk ledger, scoped to the current UTC hour bucket.

        Counters older than the current hour are discarded so the budget resets cleanly.
        Corrupt lines are skipped (best-effort; never raise from disk read).
        """
        if self.dry_run or not self.ledger_path.exists():
            return
        current_bucket = self._bucket()
        try:
            with self.ledger_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if rec.get("hour_bucket") != current_bucket:
                        continue
                    if rec.get("reason") != "ok":
                        continue
                    cid = rec.get("canonical_id")
                    if not cid:
                        continue
                    count_after = int(rec.get("count_after", 0) or 0)
                    self._counts.setdefault(current_bucket, {})
                    if count_after > self._counts[current_bucket].get(cid, 0):
                        self._counts[current_bucket][cid] = count_after
        except Exception as e:
            logger.warning("Could not read model-call ledger at %s: %s", self.ledger_path, e)

    def record(self, canonical_id: str, reason: str = "ok", extra: dict[str, Any] | None = None) -> int:
        """Increment and (if not dry-run) append a JSON line to the ledger. Returns new count."""
        bucket = self._bucket()
        self._counts.setdefault(bucket, {})
        new_count = self._counts[bucket].get(canonical_id, 0) + 1
        self._counts[bucket][canonical_id] = new_count
        record = {
            "tick_kind": "model_call",
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hour_bucket": bucket,
            "canonical_id": canonical_id,
            "count_after": new_count,
            "max_per_hour": self.max_per_hour,
            "reason": reason,
        }
        if extra:
            record.update(extra)
        if self.dry_run:
            return new_count
        try:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Failed to append model call ledger: %s", e)
        return new_count


class AgentDaemon:
    """
    The continuous runtime for agent self-awareness.
    Handles:
    - Heartbeat reflection
    - Self-state management (fatigue, goals)
    - Asynchronous whispering
    - Budget/Fatigue guarding
    """

    def __init__(
        self,
        config_path: Path | None = None,
        dry_run: bool = False,
        no_llm: bool = False,
        max_model_calls_per_hour: int = DEFAULT_MAX_MODEL_CALLS_PER_HOUR,
        ledger: ModelCallLedger | None = None,
        awareness_root: Path | None = None,
    ):
        self.dry_run = dry_run
        self.no_llm = no_llm
        self.max_model_calls_per_hour = max_model_calls_per_hour
        self.sim = DualHemisphereSim()
        self.data_dir = Path("data")
        self.registry = self._load_registry()
        self.ledger = ledger if ledger is not None else ModelCallLedger.from_data_dir(
            self.data_dir, dry_run=dry_run, max_per_hour=max_model_calls_per_hour
        )
        # Awareness is loaded once at init from data/continuity/.
        # Each loaded doc is stamped with md5 to prove integrity at proof-time.
        base = awareness_root if awareness_root else self.data_dir.parent
        self.awareness = self._load_awareness(base)

    def _load_registry(self) -> dict[str, dict[str, Any]]:
        registry_path = self.data_dir / "agents" / "registry.json"
        if not registry_path.exists():
            logger.error("Registry not found at %s", registry_path)
            return {}
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            return {
                k: v
                for k, v in data.items()
                if not k.startswith("$") and isinstance(v, dict)
            }
        except Exception as e:
            logger.error("Failed to load registry: %s", e)
            return {}

    def resolve_agent(self, name_or_id: str) -> tuple[str | None, dict[str, Any] | None]:
        """Resolve a sim name or canonical ID to (sim_name, registry_entry)."""
        n = name_or_id.strip()
        if n in self.registry:
            return n, self.registry[n]
        for sim_name, entry in self.registry.items():
            if isinstance(entry, dict) and entry.get("canonical_id") == n:
                return sim_name, entry
        normalized = n.lower().strip().replace("-", "_").replace(" ", "_")
        for sim_name, entry in self.registry.items():
            if not isinstance(entry, dict):
                continue
            if entry.get("canonical_id") and entry["canonical_id"] == normalized:
                return sim_name, entry
            display = entry.get("display_name", "").lower().strip().replace("-", "_").replace(" ", "_")
            if display and display == normalized:
                return sim_name, entry
            key_norm = sim_name.lower().strip().replace("-", "_").replace(" ", "_")
            if key_norm == normalized:
                return sim_name, entry
        logger.warning("target_resolution_failed: '%s' not resolved by any alias", name_or_id)
        return None, None

    def resolve_target(self, raw_target: str, source_hemisphere: str) -> tuple[str | None, dict[str, Any] | None, str | None]:
        """Resolve a target for social action with hemisphere isolation.
        Returns (sim_name, entry, block_reason)."""
        if not raw_target:
            return None, None, "target_resolution_failed: empty target"
        sim_name, entry = self.resolve_agent(raw_target)
        if not sim_name or not entry:
            return None, None, f"target_resolution_failed: '{raw_target}' not resolved"
        target_hemisphere = entry.get("hemisphere")
        if target_hemisphere and target_hemisphere != source_hemisphere:
            return None, None, (
                f"cross_hemisphere_blocked: source={source_hemisphere} "
                f"target='{raw_target}' hemisphere={target_hemisphere}"
            )
        logger.info(
            "target_resolved: source=%s raw='%s' sim='%s' canonical='%s' display='%s'",
            source_hemisphere, raw_target, sim_name,
            entry.get("canonical_id", "?"), entry.get("display_name", "?"),
        )
        return sim_name, entry, None

    def _get_self_state_path(self, name_or_id: str) -> Path:
        sim_name, entry = self.resolve_agent(name_or_id)
        if entry is None:
            logger.warning("[%s] not in registry - falling back to legacy path", name_or_id)
            return self.data_dir / "agents" / name_or_id.lower().replace(" ", "_") / "self_state.json"
        return self.data_dir.parent / entry["self_state_path"]

    def load_self_state(self, name_or_id: str) -> dict[str, Any]:
        sim_name, entry = self.resolve_agent(name_or_id)
        canonical_id = entry["canonical_id"] if entry else name_or_id.lower().replace(" ", "_")
        display_name = entry["display_name"] if entry else name_or_id
        path = self._get_self_state_path(name_or_id)
        if path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
                state["__loaded_from"] = str(path)
                state["__canonical_id"] = canonical_id
                state["__display_name"] = display_name
                return state
            except Exception as e:
                logger.error("Failed to load self_state for %s: %s", name_or_id, e)

        return {
            "agent_id": canonical_id,
            "name": display_name,
            "status": "awake",
            "current_goal": "observe the world",
            "current_topic": "none",
            "fatigue": {"topic": "none", "level": 0.0, "cooldown_active": False},
            "partner_awareness": {},
            "last_reflection": "I am here.",
            "needs": [],
            "whisper_cooldown": 0,
            "last_wake": time.time(),
            "__loaded_from": f"<default for {canonical_id}>",
            "__canonical_id": canonical_id,
            "__display_name": display_name,
        }

    def save_self_state(self, name_or_id: str, state: dict[str, Any]) -> None:
        sim_name, entry = self.resolve_agent(name_or_id)
        if sim_name is not None and entry is not None:
            state.setdefault("agent_id", entry["canonical_id"])
            state.setdefault("name", entry["display_name"])
        if self.dry_run:
            logger.info("[DRY-RUN] Would save state for %s (%s): %s", name_or_id, state.get("__canonical_id", "?"), state)
            return

        path = self._get_self_state_path(name_or_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def _sanitize_runtime_counters(self, state: dict[str, Any], agent_name: str) -> dict[str, Any]:
        """Sanitize runtime counters on daemon init to prevent stale-state blocking.

        1. model_calls_used_this_hour: derived/display only; recomputed from ledger
           in run_cycle save. No action needed here.
        2. whisper_cooldown: if >0 and no timestamp metadata → legacy stale, reset.
           If >0 and timestamp metadata but wall-clock expired → reset.
           If >0 and timestamp metadata still fresh → preserve.
        """
        cooldown = state.get("whisper_cooldown", 0)
        cooldown_ts = state.get("whisper_cooldown_set_at_utc")

        if cooldown > 0 and cooldown_ts is None:
            logger.warning(
                "runtime_counter_sanitized: legacy whisper_cooldown=%d for %s "
                "(no timestamp metadata); reset to 0",
                cooldown, agent_name,
            )
            state["whisper_cooldown"] = 0

        elif cooldown > 0 and cooldown_ts is not None:
            now = time.time()
            if isinstance(cooldown_ts, (int, float)):
                age = now - cooldown_ts
            elif isinstance(cooldown_ts, str):
                try:
                    from datetime import datetime, timezone
                    ts = datetime.fromisoformat(cooldown_ts.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - ts).total_seconds()
                except Exception:
                    logger.warning(
                        "runtime_counter_sanitized: unparseable cooldown timestamp for %s "
                        "(value=%s); reset whisper_cooldown to 0",
                        agent_name, cooldown_ts,
                    )
                    state["whisper_cooldown"] = 0
                    return state
            else:
                logger.warning(
                    "runtime_counter_sanitized: unexpected cooldown timestamp type for %s "
                    "(type=%s); reset whisper_cooldown to 0",
                    agent_name, type(cooldown_ts).__name__,
                )
                state["whisper_cooldown"] = 0
                return state

            # cooldown=60 ticks ~60s/tick = 3600s expected max; allow 2x grace
            if age > 7200:
                logger.info(
                    "runtime_counter_sanitized: expired whisper_cooldown=%d for %s "
                    "(age=%.0fs > 7200s threshold); reset to 0",
                    cooldown, agent_name, age,
                )
                state["whisper_cooldown"] = 0
            else:
                logger.info(
                    "runtime_counter_sanitized: fresh whisper_cooldown=%d for %s "
                    "(age=%.0fs); kept",
                    cooldown, agent_name, age,
                )

        return state

    def _load_awareness(self, root: Path) -> dict[str, Any]:
        """Load universal + hemisphere-scoped awareness docs. Each gets a md5 stamp.

        Layered discovery contract:
          - universal:         applied to every agent prompt
          - east:              applied ONLY to east_* canonical agents (Adam, Eve)
          - west:              applied ONLY to west_* canonical agents (West Adam, West Eve)

        Files are best-effort. Missing files become empty strings (no awareness this cycle).
        Awareness is never silently re-read per cycle; only init loads happen.
        """
        import hashlib

        def _load(p: Path) -> tuple[str, str, int]:
            if not p.exists():
                return "", "", 0
            txt = p.read_text(encoding="utf-8")
            h = hashlib.md5(txt.encode("utf-8")).hexdigest()
            return txt, h, len(txt)

        uni_txt, uni_md5, uni_chars = _load(root / AWARENESS_UNIVERSAL_PATH)
        east_txt, east_md5, east_chars = _load(root / AWARENESS_EAST_PATH)
        west_txt, west_md5, west_chars = _load(root / AWARENESS_WEST_PATH)

        logger.info(
            "Awareness loaded: universal=%d chars (md5=%s), east=%d chars (md5=%s), west=%d chars (md5=%s)",
            uni_chars, uni_md5[:8] or "-", east_chars, east_md5[:8] or "-", west_chars, west_md5[:8] or "-",
        )
        return {
            "universal": uni_txt,
            "universal_md5": uni_md5,
            "east":      east_txt,
            "east_md5":  east_md5,
            "west":      west_txt,
            "west_md5":  west_md5,
            "paths": {
                "universal": str(root / AWARENESS_UNIVERSAL_PATH),
                "east":      str(root / AWARENESS_EAST_PATH),
                "west":      str(root / AWARENESS_WEST_PATH),
            },
        }

    def build_reflection_prompt(self, agent_name: str, agent_obj: Any, state: dict[str, Any]) -> str:
        """Construct the reflection prompt (no I/O, no model calls).

        Layers:
          1. Universal awareness (runtime self-model + memory/time/state/choice/consequence/silence)
          2. Hemisphere-scoped awareness (east_/west_ only — preserves layered discovery)
          3. Persistent runtime state (goal, topic, fatigue)
          4. Recent memories
          5. Unread whispers
          6. Decision contract (strict JSON)
        """
        mem = agent_obj.persistent_memory
        unread_whispers = mem.get_unread_whispers()
        recent_memories = mem.get_recent(5)

        sim_name = (state.get("__canonical_id") or agent_name).lower()
        # hemisphere from canonical_id prefix
        hemisphere = "east" if sim_name.startswith("east_") else ("west" if sim_name.startswith("west_") else "unknown")
        hemi_aware = self.awareness.get(hemisphere, "") if hemisphere in ("east", "west") else ""

        parts: list[str] = []
        parts.append("=== AWARENESS — Universal (all agents) ===")
        if self.awareness.get("universal"):
            parts.append(self.awareness["universal"].rstrip())
        else:
            parts.append("[universal awareness doc not loaded]")

        parts.append("")
        parts.append(f"=== AWARENESS — Hemisphere: {hemisphere} (your side only) ===")
        if hemi_aware:
            parts.append(hemi_aware.rstrip())
        else:
            parts.append(f"[no hemisphere-specific awareness doc loaded for {hemisphere}]")

        parts.append("")
        parts.append("=== RUNTIME STATE ===")
        parts.append(f"agent_id:    {state.get('agent_id', '?')}")
        parts.append(f"name:        {state.get('name', agent_name)}")
        parts.append(f"hemisphere:  {hemisphere}")
        parts.append(f"region:      {state.get('region', '?')}")
        parts.append(f"tick:        {state.get('tick', '?')}")
        parts.append(f"current_goal:{state.get('current_goal', '?')}")
        parts.append(f"topic:       {state.get('current_topic', '?')}")
        parts.append(f"fatigue:     {state.get('fatigue', {})}")
        parts.append("")
        parts.append("=== RECENT MEMORIES ===")
        parts.append(json.dumps([str(getattr(m, 'content', m)) for m in recent_memories], ensure_ascii=False))
        parts.append("")
        parts.append("=== UNREAD WHISPERS ===")
        parts.append(json.dumps([w.get('content', w) if isinstance(w, dict) else str(w) for w in unread_whispers], ensure_ascii=False))
        parts.append("")
        parts.append("=== DECISION CONTRACT ===")
        parts.append('Respond ONLY in JSON: {"decision": "whisper|goal|rest|help", "target": "agent_name", "content": "message", "new_goal": "goal"}')
        return "\n".join(parts)

    def _maybe_emit_awareness_proof(self, canonical_id: str, display: str, prompt: str) -> None:
        """Phase 3A proof hook — emits a structured line proving awareness was consumed."""
        if not (self.no_llm and self.dry_run):
            return
        proof = {
            "phase": "3A",
            "canonical_id": canonical_id,
            "display": display,
            "awareness_loaded": {
                "universal_path": self.awareness.get("paths", {}).get("universal", "?"),
                "universal_present": bool(self.awareness.get("universal")),
                "universal_md5_prefix": (self.awareness.get("universal_md5") or "")[:8],
                "east_present": bool(self.awareness.get("east")),
                "west_present": bool(self.awareness.get("west")),
                "hemisphere": canonical_id.split("_", 1)[0] if "_" in canonical_id else "?",
            },
            "prompt_meta": {
                "total_chars": len(prompt),
                "first_chars": prompt[:240].replace("\n", " | "),
                "last_chars": prompt[-240:].replace("\n", " | "),
                "has_universal_block": "=== AWARENESS — Universal" in prompt,
                "has_hemisphere_block": "=== AWARENESS — Hemisphere:" in prompt,
            },
            "no_provider_call_made": True,
        }
        logger.info("[AWARENESS PROOF %s] %s", display, json.dumps(proof, ensure_ascii=False))

    def try_reflect(self, agent_name: str, agent_obj: Any) -> dict[str, Any]:
        """
        Return a parsed reflection-decision dict. Enforces guards in order:

        1. no_llm => force rest, no model call, no ledger write.
        2. budget exhausted for this canonical_id => force rest, no model call,
           no ledger write (block reason 'budget-exhausted').
        3. budget available => invoke provider.generate, increment ledger on
           read success (reason 'ok'), and return parsed response.

        --no-llm + --dry-run also trigger the awareness proof emission BEFORE
        the budgets are checked, so proof visibility does not require the
        budget gate to open (which it won't, since --no-llm blocks it).

        Falls back to {'decision':'rest', 'block_reason':'reflection-failed'}
        on provider exception (no ledger increment in failure path).
        """
        sim_name, entry = self.resolve_agent(agent_name)
        canonical_id = (entry or {}).get("canonical_id", agent_name.lower().replace(" ", "_"))
        display = (entry or {}).get("display_name", agent_name)

        # Build prompt unconditionally for proof visibility (under --no-llm --dry-run).
        try:
            state = self.load_self_state(agent_name)
            _prompt = self.build_reflection_prompt(sim_name or agent_name, agent_obj, state)
        except Exception as e:
            logger.error("Awareness prompt build failed for %s: %s", display, e)
            return {"decision": "rest", "block_reason": "prompt-build-failed", "canonical_id": canonical_id}
        self._maybe_emit_awareness_proof(canonical_id, display, _prompt)

        # Guard 1: --no-llm short-circuits everything.
        if self.no_llm:
            logger.info("[%s] BLOCKED: --no-llm set; forcing rest (no model call, no ledger write)", display)
            return {"decision": "rest", "block_reason": "no-llm", "canonical_id": canonical_id}

        # Guard 2: budget exhausted?
        if self.ledger.budget_exhausted(canonical_id):
            used = self.ledger.current_count(canonical_id)
            logger.warning(
                "[%s] BLOCKED: model-call budget exhausted (%d/%d in current UTC hour); forcing rest",
                display, used, self.max_model_calls_per_hour,
            )
            return {
                "decision": "rest",
                "block_reason": "budget-exhausted",
                "canonical_id": canonical_id,
                "current_count": used,
                "max_per_hour": self.max_model_calls_per_hour,
            }

        # Guard 3: actual invocation.
        try:
            response = agent_obj.provider.generate(_prompt, sim_name or agent_name, agent_obj.tick, {})
        except Exception as e:
            logger.error("Reflection failed for %s: %s", display, e)
            return {"decision": "rest", "block_reason": "reflection-failed", "canonical_id": canonical_id}

        # Record successful model call.
        new_count = self.ledger.record(canonical_id, reason="ok")
        logger.info(
            "[%s] model call OK (%d/%d this UTC hour)",
            display, new_count, self.max_model_calls_per_hour,
        )

        # Parse provider response (it may already be a dict or a JSON string).
        if isinstance(response, dict):
            parsed = response
        else:
            try:
                parsed = json.loads(response)
            except Exception:
                logger.error("[%s] provider returned non-JSON; forcing rest", display)
                return {"decision": "rest", "block_reason": "non-json-response", "canonical_id": canonical_id}
        return parsed

    def run_cycle(self, target_agent: str | None = None):
        sim_agents = {**self.sim.east.agents, **self.sim.west.agents}
        agents_to_process = [target_agent] if target_agent else list(sim_agents.keys())

        for name_or_id in agents_to_process:
            sim_name, entry = self.resolve_agent(name_or_id)
            if sim_name is None:
                logger.warning("[%s] not in registry and not a sim agent name - skipping", name_or_id)
                continue
            agent = sim_agents.get(sim_name)
            if not agent:
                continue

            display = (entry or {}).get("display_name", sim_name)
            canonical = (entry or {}).get("canonical_id", "?")

            logger.info(
                "Daemon wake cycle for %s [canonical=%s] max_model_calls_per_hour=%d",
                display, canonical, self.max_model_calls_per_hour,
            )
            state = self.load_self_state(sim_name)
            state = self._sanitize_runtime_counters(state, display)

            if state["whisper_cooldown"] > 0:
                state["whisper_cooldown"] -= 1
                self.save_self_state(sim_name, state)
                logger.info("%s is in whisper cooldown (%d remaining)", display, state["whisper_cooldown"])
                continue

            unread_before = len(agent.persistent_memory.get_unread_whispers())
            res = self.try_reflect(sim_name, agent)
            block_reason = res.get("block_reason")
            decision = res.get("decision", "rest")

            if block_reason:
                logger.info(
                    "%s forcing rest via guard: %s (used=%d/%d)",
                    display, block_reason,
                    self.ledger.current_count(canonical),
                    self.max_model_calls_per_hour,
                )
            if decision == "whisper":
                target = res.get("target")
                msg = res.get("content", "")
                target_sim, _, blocker = (
                    self.resolve_target(target, agent.region) if target
                    else (None, None, "target_resolution_failed: empty target")
                )
                if blocker:
                    logger.warning("%s - %s target='%s' content='%s'",
                                   blocker, display, target or "?", (msg or "")[:60])
                elif target_sim:
                    target_obj = sim_agents.get(target_sim)
                    if target_obj:
                        agent.whisper(target_obj, msg)
                        state["whisper_cooldown"] = 60
                        state["whisper_cooldown_set_at_utc"] = time.time()
                        logger.info("WHISPER: %s -> %s: %s", display, target_sim, msg)
                    else:
                        logger.warning("target_not_in_sim_agents: sim='%s' raw='%s' - %s", target_sim, target, display)
            elif decision == "goal":
                state["current_goal"] = res.get("new_goal", state["current_goal"])
                logger.info("%s updated goal: %s", display, state["current_goal"])
            elif decision == "help":
                logger.warning("HELP REQUEST from %s: %s", display, res.get("content", "unknown"))
            else:
                logger.info("%s decided to rest.", display)

            should_consume = (
                unread_before > 0
                and isinstance(res, dict)
                and not res.get("block_reason")
                and not res.get("error")
                and bool(res.get("decision"))
            )
            if should_consume:
                consumed = agent.receive_whispers()
                unread_after = len(agent.persistent_memory.get_unread_whispers())
                logger.info(
                    "[whisper-consumption] %s: unread_before=%d consumed=%d unread_after=%d",
                    display, unread_before, len(consumed), unread_after,
                )
            # Serialize for last_reflection; include block_reason so future audits can see why.
        state["last_reflection"] = json.dumps(res, ensure_ascii=False)
        state["last_block_reason"] = block_reason
        state["model_calls_used_this_hour"] = self.ledger.current_count(canonical)
        state["last_wake"] = time.time()
        try:
            self.save_self_state(sim_name, state)
        except Exception as e:
            logger.error("Failed to save state for %s: %s", display, e)


def main():
    parser = argparse.ArgumentParser(description="Genesis Agent Daemon")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without mutating state")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM calls, force rest")
    parser.add_argument("--agent", type=str, help="Run only for a specific agent")
    parser.add_argument("--interval", type=int, default=DEFAULT_WAKE_INTERVAL,
                        help=f"Wake interval in seconds (default: {DEFAULT_WAKE_INTERVAL})")
    parser.add_argument("--max-model-calls-per-hour", type=int,
                        default=DEFAULT_MAX_MODEL_CALLS_PER_HOUR,
                        help=(f"Hard cap on LLM calls per agent per UTC hour "
                              f"(default: {DEFAULT_MAX_MODEL_CALLS_PER_HOUR}). "
                              f"Use 0 to block all model calls."))
    args = parser.parse_args()

    if args.interval < 0:
        parser.error("--interval must be >= 0")
    if args.max_model_calls_per_hour < 0:
        parser.error("--max-model-calls-per-hour must be >= 0")
    if args.max_model_calls_per_hour == 0:
        # 0 means "block everything by design".
        logger.warning("--max-model-calls-per-hour=0 means NO model calls will be allowed.")
    if args.no_llm:
        logger.info("--no-llm set: every cycle will force rest with block_reason=no-llm")
    if args.dry_run:
        logger.info("--dry-run set: daemon will not write files or append ledger entries")

    daemon = AgentDaemon(
        dry_run=args.dry_run,
        no_llm=args.no_llm,
        max_model_calls_per_hour=args.max_model_calls_per_hour,
    )

    while True:
        daemon.run_cycle(target_agent=args.agent)
        if args.once:
            break
        # Enforce interval by sleeping until next cycle boundary.
        if args.interval > 0:
            logger.debug("Sleeping %d seconds until next wake cycle", args.interval)
            time.sleep(args.interval)
        else:
            # interval=0 means "no sleep, run-until-broken" which is unsafe;
            # treat as a request to exit after first cycle when --once is not set.
            logger.warning("--interval=0 without --once is unsafe; exiting to prevent runaway")
            break

if __name__ == "__main__":
    main()

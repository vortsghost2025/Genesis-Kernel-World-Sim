"""Phased memory-synthesis backfill runner.

`docs/memory_synthesis_spec.md` §5: synthesis never runs in the heartbeat
path. This script is the background cadence — plan oldest-uncovered-first
coverage, call the model once per group, validate, append. Fail-closed per
group, bounded per run.

Safety properties (all fail-closed, none advisory):

  * DRY-RUN BY DEFAULT. Without `--apply`, the script plans, prints, and
    exits. No model calls, no writes. An accidental invocation cannot mutate
    anything or spend anything.
  * FREE-ONLY PROOF FIRST. With `--apply`, the script runs the same
    resolution proof as the canonical heartbeat runner
    (`resolution_proof`: pinned primary model + pinned base URL + `:free`
    fallback) and exits non-zero before any model call if it fails.
  * VALIDATION BEFORE APPEND. Every rollup passes `build_synthesized_summary`
    + `append_summary`. A liar model, a crashed call, or an unparseable reply
    skips its group and is reported — the run continues, the store is
    untouched by that group.
  * BOUNDED. `--max-rollups` caps model calls per run. Default is 2.
  * ADDITIVE ONLY. This script appends summary records. It never edits raw
    memories, never advances the tick, never touches world state, goals,
    questions, or the charter. Selection prefers raw over synthesis, so a
    bad rollup degrades to dead weight, never to false evidence.

Usage:
    python world-sim/scripts/run_memory_synthesis.py --store <dir> --owner-ref east_adam --owner-id <canonical-id>
    python world-sim/scripts/run_memory_synthesis.py --pair east --owner-ref east_adam --apply --vault world-sim/.env --max-rollups 2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
REPO_ROOT = WORLD_SIM.parent
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    append_summary,
    build_synthesized_summary,
    load_memory,
    load_summaries,
    plan_synthesis_coverage,
)

STORES = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}
VAULT = WORLD_SIM / ".env"
SYNTH_MAX_TOKENS = 2048
SYNTH_TEMPERATURE = 0.0
REPORT_DIR = WORLD_SIM / ".scratch" / "synthesis"


class _EmptySynthesisResponse(Exception):
    """200 with no choices: the empty_response transient, retryable."""


def build_synthesis_prompt(covered: list[dict], owner_ref: str) -> str:
    """The rollup request. Sources in full, invention forbidden, JSON out."""
    lines = [
        f"You are compressing {owner_ref}'s own past into durable understanding.",
        "Your ENTIRE reply must be one JSON object and nothing else.",
        "Do not think out loud. Do not explain. Do not preamble.",
        "Below are memory entries (heartbeat, type, content). Write a short",
        "rollup of what happened and what was learned across them.",
        "RULES:",
        "- Name ONLY entities (tiles, resources, names) that appear verbatim",
        "  in the entries below. Inventing a specific is fabrication.",
        "- No emotions, beliefs, or intentions ascribed beyond what is written.",
        "- Keep the text under 800 characters.",
        "- Your ENTIRE reply must be the JSON object and nothing else.",
        "  Do not think out loud. Do not explain. Do not preamble.",
        "Reply with NOTHING but a JSON object of exactly this shape:",
        '{"text": "<rollup>", "salient_entities": ["<entity>", ...]}',
        "MEMORIES:",
    ]
    for mem in covered:
        lines.append(
            f"- hb {mem.get('heartbeat', '?')} "
            f"({mem.get('type', 'unknown')}): {mem.get('content', '')}"
        )
    return "\n".join(lines)


def parse_synthesis_response(text: str) -> tuple[dict | None, list[str]]:
    """Parse one model reply. Garbage is an error, never an exception.

    Repair ladder, strictest first: pristine JSON, then fenced, then the
    largest {...} block (models wrap replies in prose). Each step must still
    yield the exact shape; repair never invents keys, it only unwraps.
    """
    candidate = (text or "").strip()
    payload, errors = _try_parse_object(candidate)
    if not errors:
        return payload, []
    fenced = _strip_fences(candidate)
    if fenced != candidate:
        payload, errors = _try_parse_object(fenced)
        if not errors:
            return payload, []
    start, end = candidate.find("{"), candidate.rfind("}")
    if 0 <= start < end:
        payload, errors = _try_parse_object(candidate[start:end + 1])
        if not errors:
            return payload, []
    return None, ["synthesis reply is not JSON"]


def _strip_fences(candidate: str) -> str:
    text = candidate.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


def _try_parse_object(candidate: str) -> tuple[dict | None, list[str]]:
    try:
        payload = json.loads(candidate)
    except Exception:
        return None, ["not JSON"]
    if not isinstance(payload, dict):
        return None, ["synthesis reply is not an object"]
    if "text" not in payload or "salient_entities" not in payload:
        return None, ["synthesis reply must contain text and salient_entities"]
    if not isinstance(payload.get("text"), str):
        return None, ["synthesis reply has no text string"]
    entities = payload.get("salient_entities", [])
    if not isinstance(entities, list) or any(
        not isinstance(e, str) for e in entities
    ):
        return None, ["salient_entities must be a list of strings"]
    return {"text": payload["text"], "salient_entities": entities}, []


def free_lane_ok(primary_model: str, primary_url: str,
                 fallback_model: str) -> tuple[bool, str]:
    """Mirror of the heartbeat runner's free-only gate, as a pure predicate.

    Pinned primary model + pinned base URL (no silent lane hijack) and a
    `:free` fallback (no paid spend). Tested directly; enforced in main
    through the full resolution_proof before any model call.
    """
    from backend.world.canonical_heartbeat_runner import (
        PRIMARY_BASE_URL,
        PRIMARY_MODEL,
    )

    if primary_model != PRIMARY_MODEL:
        return False, (
            f"rejected: primary model {primary_model!r} is not the "
            f"configured {PRIMARY_MODEL!r}"
        )
    if primary_url != PRIMARY_BASE_URL:
        return False, (
            f"rejected: base url {primary_url!r} is not the configured "
            f"{PRIMARY_BASE_URL!r}"
        )
    if not fallback_model.endswith(":free"):
        return False, (
            f"rejected: fallback lane {fallback_model!r} is not a :free model"
        )
    return True, "free lane ok"


def _resolve_owner_id(store: FirstPairPersistenceStore,
                      owner_ref: str) -> str | None:
    data = store._read_json(store._path("identity.json"))
    if not data or data.get("type") != "identity_record":
        return None
    inner = data.get("data", {})
    if owner_ref == "east_adam":
        return inner.get("adam_agent_id")
    if owner_ref == "east_eve":
        return inner.get("eve_agent_id")
    return None


def run_synthesis_pass(
    store: FirstPairPersistenceStore,
    owner_ref: str,
    owner_id: str,
    synthesizer,
    max_rollups: int = 2,
    group_size: int = 8,
    newest_first_ratio: int = 0,
) -> dict:
    """One bounded pass: plan, synthesize, validate, append. Returns a report.

    `synthesizer(covered, owner_id)` returns {"text", "salient_entities"} or
    raises. Every failure mode — crash, garbage, grounding violation,
    append rejection — skips its group and is reported. The report is JSON
    serializable.
    """
    memories = load_memory(store).get(owner_ref, [])
    existing = [
        s for s in load_summaries(store) if s.owner_agent_id == owner_id
    ]
    already_covered: set[str] = set()
    for s in existing:
        already_covered.update(s.covered_memory_ids or [])
    from backend.world.first_pair_persistence import _ensure_memory_ids
    ensured_all = _ensure_memory_ids(
        [dict(m) for m in memories if isinstance(m, dict)], owner_id
    )
    report: dict = {
        "owner_ref": owner_ref,
        "groups_considered": 0,
        "appended": 0,
        "appended_ids": [],
        "skipped_covered": sum(
            1 for m in ensured_all if m.get("memory_id", "") in already_covered
        ),
        "failed": [],
    }
    groups = plan_synthesis_coverage(
        memories,
        [{"covered_memory_ids": set(s.covered_memory_ids)} for s in existing],
        owner_id,
        max_rollups=max_rollups,
        group_size=group_size,
        newest_first_ratio=newest_first_ratio,
    )
    report["groups_considered"] = len(groups)
    if not groups:
        uncovered_total = 0
        report["uncovered_remaining"] = uncovered_total
        return report
    for group in groups:
        hbs = sorted({m.get("heartbeat", 0) for m in group})
        try:
            draft = synthesizer(group, owner_id)
        except Exception as exc:
            # Record the message, not just the type: for unparseable replies
            # it carries the raw snippet, which is the only evidence of what
            # the model actually emitted. Truncated — reports are diagnostics,
            # not archives.
            report["failed"].append({
                "heartbeats": hbs,
                "errors": [f"synthesizer raised {type(exc).__name__}: "
                           f"{str(exc)[:400]}"],
            })
            continue
        if not isinstance(draft, dict):
            report["failed"].append({
                "heartbeats": sorted({m.get("heartbeat", 0) for m in group}),
                "errors": ["synthesizer must return a dict"],
            })
            continue
        rec, errors = build_synthesized_summary(group, owner_id,
                                                lambda c, o: draft)
        if errors or rec is None:
            report["failed"].append({
                "heartbeats": sorted({m.get("heartbeat", 0) for m in group}),
                "errors": errors,
            })
            continue
        result = append_summary(store, rec, memory_list=[
            m for m in load_memory(store).get(owner_ref, [])
        ])
        if result.get("ok"):
            report["appended"] += 1
            report["appended_ids"].append(rec.summary_id)
        else:
            report["failed"].append({
                "heartbeats": sorted({m.get("heartbeat", 0) for m in group}),
                "errors": result.get("errors", ["append rejected"]),
            })
    return report


def _live_synthesizer(client, model: str):
    from backend.world.first_pair_cognition_model import (
        _TRANSPORT_BACKOFF_SECONDS,
        _is_retryable_transport_error,
    )

    def call(covered: list[dict], owner_id: str) -> dict:
        prompt = build_synthesis_prompt(covered, owner_id)
        # Same transient-only retry policy as heartbeat transport (10IV):
        # 429/timeout/5xx back off bounded; auth/config errors fail fast.
        # Synthesis is background cadence, so a group that will not go
        # simply fails closed and is reported.
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system",
                         "content": "Compress the given memories. Reply with only the JSON object."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=SYNTH_TEMPERATURE,
                    max_tokens=SYNTH_MAX_TOKENS,
                )
                # Empty choices on a 200: the known empty_response transient
                # (the chain retries it per-pair). Not an exception, so it
                # is handled here rather than in the retry classifier.
                choices = getattr(response, "choices", None) or []
                if not choices or not getattr(choices[0].message, "content", ""):
                    raise _EmptySynthesisResponse("empty choices")
                text = choices[0].message.content or ""
                payload, errors = parse_synthesis_response(text)
                if errors or payload is None:
                    snippet = text.strip()[:300]
                    raise ValueError(
                        f"unparseable synthesis reply: {errors} raw:{snippet!r}"
                    )
                return payload
            except _EmptySynthesisResponse as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(_TRANSPORT_BACKOFF_SECONDS[
                        min(attempt, len(_TRANSPORT_BACKOFF_SECONDS) - 1)
                    ])
            except Exception as exc:
                last_error = exc
                if not _is_retryable_transport_error(exc):
                    break
                if attempt < 2:
                    time.sleep(_TRANSPORT_BACKOFF_SECONDS[
                        min(attempt, len(_TRANSPORT_BACKOFF_SECONDS) - 1)
                    ])
        raise last_error if last_error else RuntimeError("synthesis failed")

    return call


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pair", choices=("east", "west"), default=None)
    p.add_argument("--store", default=None)
    p.add_argument("--owner-ref", choices=("east_adam", "east_eve"),
                   default="east_adam")
    p.add_argument("--owner-id", default=None)
    p.add_argument("--max-rollups", type=int, default=2)
    p.add_argument("--group-size", type=int, default=8)
    p.add_argument("--newest-first-ratio", type=int, default=2,
                   help="interleave N newest groups per 1 oldest (0 = oldest-first)")
    p.add_argument("--vault", default=str(VAULT))
    p.add_argument("--apply", action="store_true",
                   help="perform the pass; without it, dry-run only")
    args = p.parse_args(argv)

    if args.store:
        store = FirstPairPersistenceStore(Path(args.store))
    elif args.pair:
        store = FirstPairPersistenceStore(STORES[args.pair])
    else:
        print("need --store or --pair", flush=True)
        return 2
    owner_id = args.owner_id or _resolve_owner_id(store, args.owner_ref)
    if not owner_id:
        print("cannot resolve owner id (no --owner-id and no identity record)",
              flush=True)
        return 2

    if not args.apply:
        memories = load_memory(store).get(args.owner_ref, [])
        existing = [
            s for s in load_summaries(store) if s.owner_agent_id == owner_id
        ]
        groups = plan_synthesis_coverage(
            memories,
            [{"covered_memory_ids": set(s.covered_memory_ids)}
             for s in existing],
            owner_id,
            max_rollups=args.max_rollups,
            group_size=args.group_size,
            newest_first_ratio=args.newest_first_ratio,
        )
        print(f"DRY-RUN {args.owner_ref}: {len(groups)} group(s) would be "
              f"synthesized, 0 model calls made, 0 writes performed.",
              flush=True)
        for group in groups:
            hbs = sorted(m.get("heartbeat", 0) for m in group)
            print(f"  group heartbeats {hbs[0]}-{hbs[-1]} "
                  f"({len(group)} memories)", flush=True)
        return 0

    # --- Live path: vault, proof, client. Fail closed before any call. ---
    from backend.world.canonical_heartbeat_runner import (
        build_clean_env,
        load_vault,
        resolution_proof,
    )
    from backend.world.first_pair_cognition_model import resolve_provider

    vault = load_vault(Path(args.vault))
    env = build_clean_env(Path(args.vault))
    ok, proof = resolution_proof(env, WORLD_SIM)
    print(proof, flush=True)
    if not ok:
        print(f"SYNTHESIS REFUSED: {proof}", flush=True)
        return 1
    # Apply the SAME clean env the proof child received: ambient hijack vars
    # stripped, pinned model vars set. A partial merge (fill-missing-only)
    # leaves ambient credentials without their pinned partners and fails
    # resolution in-process after passing it in the child. Measured.
    import os
    os.environ.update(env)

    config = resolve_provider()
    ok, reason = free_lane_ok(config.model, config.base_url,
                              _fallback_model_name(config))
    if not ok:
        print(f"SYNTHESIS REFUSED: {reason}", flush=True)
        return 1

    from openai import OpenAI

    from backend.world.first_pair_cognition_model import _client_api_key

    client = OpenAI(base_url=config.base_url,
                    api_key=_client_api_key(config), timeout=300.0)
    report = run_synthesis_pass(
        store, args.owner_ref, owner_id,
        _live_synthesizer(client, config.model),
        max_rollups=args.max_rollups,
        group_size=args.group_size,
        newest_first_ratio=args.newest_first_ratio,
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = (REPORT_DIR /
                   f"synthesis_{args.owner_ref}_{int(time.time())}.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8",
                           newline="\n")
    print(json.dumps(report, indent=2), flush=True)
    print(f"report: {report_path}", flush=True)
    return 0 if not report["failed"] else 1


def _fallback_model_name(config) -> str:
    from backend.world.first_pair_cognition_model import (
        resolve_fallback_provider,
    )

    fallback = resolve_fallback_provider(config)
    return fallback.model if fallback else "NONE"


if __name__ == "__main__":
    sys.exit(main())

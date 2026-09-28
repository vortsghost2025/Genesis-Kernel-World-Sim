"""Phase 10IY — Detached canonical heartbeat runner and launcher.

Implements the smallest reliable mechanism for running ONE explicitly
operator-authorized canonical heartbeat as an OS-level detached process
that survives an editor/UI crash. The launcher spawns the runner and
returns immediately; process durability belongs to the OS/runner layer —
never to another AI agent.

Boundaries:
- One heartbeat per invocation; no scheduler, no recurring mode, no
  automatic next heartbeat (Gate-7 stays closed — this is a bounded
  one-shot operator-launched process, not a daemon).
- Provider policy (see the constants below for the single source of truth):
  primary and fallback are BOTH ':free' models served through the
  OpenRouter-compatible endpoint. The free-only guard is ENFORCED at
  resolution: a non-':free' fallback, a primary that is not the configured
  model, or a base URL that is not the configured endpoint all fail closed
  before the loop launches. This sentence previously described a guard that
  only printed its verdict; see docs/heartbeat_runner_integrity_spec.md
  Defect A.
- Credentials are never printed, logged, or persisted by this module.
- CRITICAL NO-RERUN RULE: if the authoritative store already shows the
  authorized heartbeat persisted, the heartbeat is NEVER re-executed;
  recovery regenerates read-only state evidence, clearly labeled as
  recovered state evidence rather than original execution evidence.
- This module never calls a provider itself; it launches the existing
  operator-authorized loop script and the committed read-only state
  evidence exporter.

Durable status states: not-started -> running -> persisted ->
evidence-exported | failed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
CREATE_NO_WINDOW = 0x08000000

# Provider policy. These four constants are the single source of truth:
# build_clean_env() writes them and resolution_proof() asserts the resolver
# honored them, so the configured policy and the enforced policy cannot
# drift apart. The fallback MUST end in ':free' - the guard rejects anything
# else. Both lanes are free, so a provider failure degrades availability
# rather than cost.
PRIMARY_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
FALLBACK_MODEL = "z-ai/glm-5.2:free"
ADAM_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
EVE_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"

# Single source of truth for the lane endpoint. build_clean_env() writes this
# and resolution_proof() asserts the resolver honored it, so the configured
# policy and the enforced policy cannot drift apart.
PRIMARY_BASE_URL = "https://openrouter.ai/api/v1"

_STRIPPED_ENV_KEYS = (
    "GENESIS_FIRST_PAIR_BASE_URL",
    "GENESIS_FIRST_PAIR_API_KEY",
    "GENESIS_FIRST_PAIR_MODEL",
    "GENESIS_FIRST_PAIR_FALLBACK_MODEL",
    "GENESIS_FIRST_PAIR_MODEL_EAST_ADAM",
    "GENESIS_FIRST_PAIR_MODEL_EAST_EVE",
    "GENESIS_FIRST_PAIR_MODEL_WEST_ADAM",
    "GENESIS_FIRST_PAIR_MODEL_WEST_EVE",
    "NVIDIA_API_KEY",
    "OPENROUTER_API_KEY",
    "OLLAMA_HOST",
)

_RECOVERY_NOTE = (
    "regenerated read-only from the authoritative store after the "
    "original execution evidence was missing (interrupted run or crash); "
    "the heartbeat itself was never re-executed (no-rerun rule)"
)


class ProviderCredentialError(Exception):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_under(root: Path, path: str) -> Path:
    """Resolve a possibly-relative path against a known root.

    The loop and exporter subprocesses run with ``cwd=root``, so a relative
    path handed to them is resolved a SECOND time against that root. Passing
    the relative value through produced a doubled directory
    (``world-sim/world-sim/.scratch/...``) and a false failure report. Resolve
    once here; absolute inputs pass through untouched, which makes the
    operation idempotent.
    """
    p = Path(path)
    return p if p.is_absolute() else root / p


def _parse_proof(text: str) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines out of a resolution proof."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()
    return fields


def _write_status(status_path: Path, **fields) -> None:
    status: dict = {}
    if status_path.is_file():
        try:
            status = _read_json(status_path)
        except Exception:
            status = {}
    status["updated_at_utc"] = _utc_now()
    status.update(fields)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, indent=2), newline="\n")


def load_vault(path: Path) -> dict:
    vals: dict = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def build_clean_env(vault_path: Path) -> dict:
    """Build the clean child environment from the vault. Ambient provider
    variables are stripped so they can never hijack lane selection;
    credential values are never included in error text."""
    vault = load_vault(vault_path)
    nv = vault.get("NVIDIA_NIM_API_KEY", "").strip()
    ork = vault.get("OPENROUTER_API_KEY", "").strip()
    if not nv:
        raise ProviderCredentialError(
            "vault missing NVIDIA_NIM_API_KEY (required for the NVIDIA primary lane)"
        )
    if not ork:
        raise ProviderCredentialError(
            "vault missing OPENROUTER_API_KEY (required for the free fallback lane)"
        )
    env = dict(os.environ)
    for key in _STRIPPED_ENV_KEYS:
        env.pop(key, None)
    env["NVIDIA_API_KEY"] = nv
    env["OPENROUTER_API_KEY"] = ork
    env["GENESIS_FIRST_PAIR_BASE_URL"] = PRIMARY_BASE_URL
    env["GENESIS_FIRST_PAIR_API_KEY"] = ork
    env["GENESIS_FIRST_PAIR_MODEL"] = PRIMARY_MODEL
    env["GENESIS_FIRST_PAIR_FALLBACK_MODEL"] = FALLBACK_MODEL
    env["GENESIS_FIRST_PAIR_MODEL_EAST_ADAM"] = ADAM_MODEL
    env["GENESIS_FIRST_PAIR_MODEL_EAST_EVE"] = EVE_MODEL
    env["GENESIS_FIRST_PAIR_MODEL_WEST_ADAM"] = ADAM_MODEL
    env["GENESIS_FIRST_PAIR_MODEL_WEST_EVE"] = EVE_MODEL
    return env


def resolution_proof(env: dict, world_sim_root: Path) -> tuple[bool, str]:
    """Run the repo provider resolver in a clean child process and require
    a valid primary lane plus a valid fallback. The proof performs no
    network calls and never prints credential values."""
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "from backend.world.first_pair_cognition_model import ("
        "resolve_provider, resolve_fallback_provider); "
        "c = resolve_provider(); f = resolve_fallback_provider(c); "
        "print('RESOLUTION_PROVIDER=' + c.provider_type); "
        "print('RESOLUTION_BASE_URL=' + c.base_url); "
        "print('RESOLUTION_MODEL=' + c.model); "
        "print('RESOLUTION_KEY_SET=' + str(bool(c.api_key)).upper()); "
        "print('RESOLUTION_FALLBACK=' + ((f.provider_type + '/' + f.model) if f else 'NONE')); "
        "print('RESOLUTION_FALLBACK_FREE=' + str(bool(f and f.model.endswith(':free'))).upper())"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(world_sim_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception as exc:
        return False, f"resolution proof process failed: {type(exc).__name__}"
    text = proc.stdout.strip()
    if proc.returncode != 0:
        return False, text or f"resolution proof exited {proc.returncode}"
    fields = _parse_proof(text)
    if fields.get("RESOLUTION_KEY_SET") != "TRUE":
        return False, text + " (no primary credential resolved)"
    if fields.get("RESOLUTION_FALLBACK", "NONE") == "NONE":
        return False, text + " (no fallback lane)"

    # --- The free-only guard, actually enforced. -------------------------
    # Historically this function COMPUTED RESOLUTION_FALLBACK_FREE and never
    # asserted on it, so a paid fallback passed through while the docstring
    # and runbook both claimed the run fails closed. Measured on heartbeat
    # 941: RESOLUTION_FALLBACK_FREE=FALSE and the heartbeat launched anyway.
    if fields.get("RESOLUTION_FALLBACK_FREE") != "TRUE":
        return False, text + " (rejected: fallback lane is not a :free model)"

    # The remaining assertions stop a silent lane hijack: the resolver must
    # have honored the configured primary model and endpoint, not merely
    # returned *some* primary.
    resolved_model = fields.get("RESOLUTION_MODEL", "")
    if resolved_model != PRIMARY_MODEL:
        return False, (
            text + f" (rejected: primary model {resolved_model!r} is not the "
            f"configured {PRIMARY_MODEL!r})"
        )
    resolved_url = fields.get("RESOLUTION_BASE_URL", "")
    if resolved_url != PRIMARY_BASE_URL:
        return False, (
            text + f" (rejected: base url {resolved_url!r} is not the "
            f"configured {PRIMARY_BASE_URL!r})"
        )
    return True, text


def _store_counts(store_root: Path) -> tuple[int | None, int | None]:
    """Read (heartbeat record count, world tick) from the authoritative
    store; (None, None) when unparseable."""
    try:
        hb = _read_json(store_root / "heartbeat.json")
        count = len(hb.get("data", []))
    except Exception:
        return None, None
    try:
        ws = _read_json(store_root / "world_state.json")
        tick = ws.get("data", {}).get("tick")
    except Exception:
        return None, None
    return count, tick


def already_persisted(store_root: Path, expect: int) -> bool:
    count, tick = _store_counts(store_root)
    if count is None or tick is None:
        return False
    return count >= expect and tick >= expect


def preflight(store_root: Path, expect: int) -> tuple[bool, str]:
    count, tick = _store_counts(store_root)
    if count is None or tick is None:
        return False, "store parse failed (heartbeat.json/world_state.json)"
    if count != expect - 1:
        return False, f"record count {count} != expected {expect - 1} (expect-1)"
    if tick != expect - 1:
        return False, f"tick {tick} != expected {expect - 1} (expect-1)"
    return True, f"record count {count}, tick {tick}"


def export_state_evidence(
    export_script: Path, world_sim_root: Path, evidence_path: Path
) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [sys.executable, str(export_script), "--out", str(evidence_path)],
            cwd=str(world_sim_root),
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception as exc:
        return False, f"evidence export process failed: {type(exc).__name__}"
    if proc.returncode != 0 or not evidence_path.is_file():
        # Report the RESOLVED path. A bare returncode here is actively
        # misleading: heartbeat 941 exported successfully and this reported
        # "exited 0" as a failure, because the file had been written to a
        # doubled path the runner was not looking at.
        return False, (
            f"evidence export exited {proc.returncode}; expected file at "
            f"{evidence_path} (not found)"
        )
    return True, "evidence exported"


def _serving_provenance(store_root: Path) -> dict:
    """Summarise what actually served the heartbeat, from the store alone.

    The runbook's rule is "absence of error memories means single-attempt
    serves". This is a coarse proxy: it reads the persisted heartbeat record
    and reports an error path only when an agent's action outcome carries an
    error. It never invents a transport count it cannot see.
    """
    try:
        records = _read_json(store_root / "heartbeat.json").get("data", [])
        last = records[-1] if records else {}
    except Exception:
        return {"serving_provider_type": "unknown"}
    outcomes = last.get("action_outcomes") or {}
    errored = sorted(
        ref for ref, outcome in outcomes.items()
        if isinstance(outcome, dict) and outcome.get("error")
    )
    if errored:
        return {
            "serving_provider_type": "error_path_observed",
            "agents_with_errors": errored,
        }
    return {"serving_provider_type": "single_attempt_no_error_memories"}


def label_recovered_evidence(evidence_path: Path) -> None:
    ev = _read_json(evidence_path)
    ev["evidence_class"] = "recovered_state_evidence"
    ev["recovery_note"] = _RECOVERY_NOTE
    evidence_path.write_text(json.dumps(ev, indent=2, sort_keys=True), newline="\n")


def _runner_arg_parser() -> argparse.ArgumentParser:
    default_ws = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(
        description="Detached runner: ONE operator-authorized canonical heartbeat"
    )
    p.add_argument("--expect-heartbeat", type=int, required=True)
    p.add_argument("--evidence", type=str, required=True)
    p.add_argument("--status", type=str, required=True)
    p.add_argument("--vault", type=str, default=r"S:\kernel-lane\.env")
    p.add_argument("--store-root", type=str, default="")
    p.add_argument("--world-sim-root", type=str, default=str(default_ws))
    p.add_argument("--pair-id", type=str, default="east",
                   help="Pair identifier (east or west, default east)")
    p.add_argument(
        "--loop-script", type=str,
        default=str(Path(default_ws) / "scripts" / "run_first_pair_living_loop.py"),
    )
    p.add_argument(
        "--export-script", type=str,
        default=str(Path(default_ws) / "scripts" / "export_first_pair_state_evidence.py"),
    )
    return p


def runner_main(argv=None) -> int:
    args = _runner_arg_parser().parse_args(argv)
    if args.expect_heartbeat < 1:
        return 2
    world_sim_root = Path(args.world_sim_root)
    if args.store_root:
        store_root = Path(args.store_root)
    elif args.pair_id == "east":
        store_root = world_sim_root / ".runtime" / "first-pair"
    else:
        store_root = world_sim_root / ".runtime" / f"first-pair-{args.pair_id}"
    evidence = _resolve_under(world_sim_root, args.evidence)
    status_path = _resolve_under(world_sim_root, args.status)
    vault = Path(args.vault)
    loop_script = Path(args.loop_script)
    export_script = Path(args.export_script)
    expect = args.expect_heartbeat

    _write_status(
        status_path,
        status="running",
        expected_heartbeat=expect,
        pid=os.getpid(),
        started_at_utc=_utc_now(),
        store_root=str(store_root),
        evidence_path=str(evidence),
        detail="",
    )
    print(f"[runner] running: expect heartbeat {expect}, store {store_root}")

    try:
        env = build_clean_env(vault)
    except ProviderCredentialError as exc:
        _write_status(status_path, status="failed", detail=str(exc))
        return 1

    ok, text = resolution_proof(env, world_sim_root)
    print("[runner] " + text)
    if not ok:
        _write_status(
            status_path, status="failed",
            detail="provider resolution proof rejected (no paid fallback permitted)",
        )
        return 1

    # Defect D: the runbook requires provider provenance in the durable run
    # record. It used to exist only in this process's stdout. Persist both the
    # configured policy and what the resolver actually reported.
    proof_fields = _parse_proof(text)
    _write_status(
        status_path,
        primary_model=proof_fields.get("RESOLUTION_MODEL", PRIMARY_MODEL),
        fallback_model=proof_fields.get("RESOLUTION_FALLBACK", FALLBACK_MODEL),
        fallback_free=proof_fields.get("RESOLUTION_FALLBACK_FREE") == "TRUE",
        provider_base_url=proof_fields.get("RESOLUTION_BASE_URL", PRIMARY_BASE_URL),
        resolution_proof=text,
    )

    if already_persisted(store_root, expect):
        _write_status(
            status_path, status="persisted",
            detail=f"heartbeat {expect} already persisted; no rerun (recovery only)",
        )
        print(f"[runner] heartbeat {expect} already persisted; NOT re-executing")
    else:
        ok, detail = preflight(store_root, expect)
        if not ok:
            _write_status(status_path, status="failed", detail=f"preflight: {detail}")
            print(f"[runner] preflight failed: {detail}")
            return 1
        print(f"[runner] preflight ok: {detail}")
        print(f"[runner] launching ONE heartbeat: {loop_script} (pair: {args.pair_id})")
        proc = subprocess.run(
            [
                sys.executable, "-u", str(loop_script),
                "--heartbeats", "1",
                "--evidence", str(evidence),
                "--pair-id", args.pair_id,
                "--store-root", str(store_root),
            ],
            cwd=str(world_sim_root),
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
        if already_persisted(store_root, expect):
            _write_status(
                status_path, status="persisted",
                detail=f"heartbeat persisted (loop rc={proc.returncode})",
            )
            print(f"[runner] heartbeat {expect} persisted (loop rc={proc.returncode})")
        else:
            _write_status(
                status_path, status="failed",
                detail=f"loop did not persist heartbeat {expect} (rc={proc.returncode})",
            )
            print(f"[runner] FAILED: loop did not persist heartbeat {expect}")
            return 1

    serving = _serving_provenance(store_root)

    if evidence.is_file():
        _write_status(
            status_path, status="evidence-exported",
            evidence_class="original_execution_evidence",
            **serving,
        )
        print("[runner] original execution evidence present")
        return 0

    ok, detail = export_state_evidence(export_script, world_sim_root, evidence)
    if not ok:
        _write_status(
            status_path, status="failed",
            detail=f"recovery evidence: {detail}", **serving,
        )
        print(f"[runner] FAILED: recovery evidence export: {detail}")
        return 1
    label_recovered_evidence(evidence)
    _write_status(
        status_path, status="evidence-exported",
        evidence_class="recovered_state_evidence",
        detail=f"recovery evidence exported; heartbeat {expect} never re-executed",
        **serving,
    )
    print("[runner] recovered state evidence exported (labeled)")
    return 0


def _launcher_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Detached launcher: spawn the one-heartbeat runner and exit"
    )
    p.add_argument("--expect-heartbeat", type=int, required=True)
    p.add_argument("--evidence", type=str, required=True)
    p.add_argument("--log", type=str, required=True)
    p.add_argument("--status", type=str, required=True)
    p.add_argument("--vault", type=str, default=r"S:\kernel-lane\.env")
    p.add_argument("--store-root", type=str, default="")
    p.add_argument("--world-sim-root", type=str, default="")
    p.add_argument("--pair-id", type=str, default="east",
                   help="Pair identifier (east or west, default east)")
    p.add_argument("--loop-script", type=str, default="")
    p.add_argument("--export-script", type=str, default="")
    return p


def launcher_main(argv=None) -> int:
    args = _launcher_arg_parser().parse_args(argv)
    if args.expect_heartbeat < 1:
        return 2
    world_sim_root = Path(args.world_sim_root) if args.world_sim_root else (
        Path(__file__).resolve().parents[2]
    )
    store_root = args.store_root or str(
        world_sim_root / ".runtime" / "first-pair" if args.pair_id == "east"
        else world_sim_root / ".runtime" / f"first-pair-{args.pair_id}"
    )
    loop_script = args.loop_script or str(
        world_sim_root / "scripts" / "run_first_pair_living_loop.py"
    )
    export_script = args.export_script or str(
        world_sim_root / "scripts" / "export_first_pair_state_evidence.py"
    )
    runner_script = world_sim_root / "scripts" / "run_canonical_heartbeat_detached.py"
    status_path = Path(args.status)

    _write_status(
        status_path,
        status="not-started",
        expected_heartbeat=args.expect_heartbeat,
        pid=None,
        breakaway=None,
        store_root=store_root,
        evidence_path=args.evidence,
        detail="",
    )

    cmd = [
        sys.executable, "-u", str(runner_script),
        "--expect-heartbeat", str(args.expect_heartbeat),
        "--evidence", args.evidence,
        "--status", args.status,
        "--vault", args.vault,
        "--store-root", store_root,
        "--world-sim-root", str(world_sim_root),
        "--pair-id", args.pair_id,
        "--loop-script", loop_script,
        "--export-script", export_script,
    ]

    log_fh = open(args.log, "ab", buffering=0)
    flags = (
        DETACHED_PROCESS
        | CREATE_NEW_PROCESS_GROUP
        | CREATE_BREAKAWAY_FROM_JOB
        | CREATE_NO_WINDOW
    )
    try:
        proc = subprocess.Popen(
            cmd, stdout=log_fh, stderr=log_fh, creationflags=flags, close_fds=True
        )
        breakaway = True
    except (PermissionError, OSError):
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        proc = subprocess.Popen(
            cmd, stdout=log_fh, stderr=log_fh, creationflags=flags, close_fds=True
        )
        breakaway = False
    log_fh.close()

    _write_status(
        status_path,
        status="not-started",
        pid=proc.pid,
        breakaway=breakaway,
        detail="runner spawned; launcher exiting (runner owns durability)",
    )
    print(f"LAUNCHED pid={proc.pid} breakaway={breakaway}")
    print(f"STATUS={status_path}")
    print(f"LOG={args.log}")
    return 0

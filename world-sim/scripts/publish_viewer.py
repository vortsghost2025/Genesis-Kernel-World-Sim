"""Publish the built viewer, and move the public alias ONLY after verifying.

Why this exists
---------------
The public URL was being broken roughly daily by deployments that were never
verified: anything that put a new production deployment in front of
`genesis-civilization-observatory.vercel.app` became the face of the world,
including empty builds. On 2026-11-14 the operator and I traced the daily 404
to the project's Git integration: every push produced a production deployment
(the viewer cannot be built from git -- its 26 MB `viewer_data.js` is generated
locally and gitignored), and each one replaced the alias. The Git integration
was disconnected; this script is the other half of that fix.

The rule it enforces
--------------------
1. build the bundle locally (scripts/build_viewer_deploy.py);
2. deploy it as a PREVIEW -- production is not touched;
3. probe the preview: root 200, the viewer's own code markers present, the data
   file and at least one texture 200;
4. only if every probe passes, point the alias at that deployment;
5. confirm the alias actually serves the new build (Vercel edges cache briefly).

A failed build or a failed probe leaves the alias exactly where it was, so a
bad publish can never be the last thing the operator sees.

Usage
-----
    python publish_viewer.py                 # build, deploy, verify, alias
    python publish_viewer.py --dry-run       # build only, touch nothing
    python publish_viewer.py --verify-only URL
    python publish_viewer.py --no-build      # deploy the current bundle
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
BUNDLE = WORLD_SIM / "viewer" / "viewer-deploy"
BUILD_SCRIPT = WORLD_SIM / "scripts" / "build_viewer_deploy.py"
LOG = WORLD_SIM / ".runtime" / "viewer_publish.log"
LOCK = WORLD_SIM / ".runtime" / "viewer_publish.lock"

PROJECT = "genesis-civilization-observatory"
ALIAS = "genesis-civilization-observatory.vercel.app"
# The viewer's own code markers: if the served HTML lacks these, the deployment
# is not this viewer, whatever it is (an empty build, a stale build, a 404 page).
MARKERS = ("groundCoverKindFor", "floraKindFor", "interiorPropPlan")
PROBE_PATHS = ("assets/grass_tuft.webp", "viewer_data.js")
LOCK_STALE_SECONDS = 20 * 60
ANSI = re.compile(r"\x1b\[[0-9;]*m")
DEPLOY_URL = re.compile(
    r"https://" + re.escape(PROJECT) + r"-[a-z0-9]+\.vercel\.app")


def parse_deploy_url(cli_output: str) -> str | None:
    """The deployment URL from `vercel deploy` output, ANSI codes and all.

    Deliberately does NOT accept the bare project alias: this must return a
    specific deployment that can be probed before it is promoted.
    """
    text = ANSI.sub("", cli_output or "")
    for match in DEPLOY_URL.finditer(text):
        url = match.group(0)
        if url != f"https://{ALIAS}":
            return url
    return None


def assess(probes: dict, markers=MARKERS) -> tuple[bool, list[str]]:
    """Decide whether a deployed URL is fit to become the public viewer.

    probes: {"root": {...}, "paths": {path: {...}}, "html": str}
    """
    reasons: list[str] = []
    root = probes.get("root") or {}
    if root.get("status") != 200:
        reasons.append(f"root status {root.get('status')!r}")
    html = probes.get("html") or ""
    missing = [m for m in markers if m not in html]
    if missing:
        reasons.append("served HTML is missing " + ", ".join(missing))
    if len(html) < 50_000:
        reasons.append(f"served HTML is only {len(html)} bytes - not the viewer")
    for path, probe in (probes.get("paths") or {}).items():
        if probe.get("status") != 200:
            reasons.append(f"{path} status {probe.get('status')!r}")
        elif not probe.get("bytes"):
            reasons.append(f"{path} served no bytes")
    return (not reasons), reasons


def _http(url: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return {"status": resp.status, "bytes": len(body), "body": body}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "bytes": 0, "body": b""}
    except Exception as exc:  # noqa: BLE001 - any transport failure is a fail
        return {"status": None, "bytes": 0, "body": b"", "error": type(exc).__name__}


def probe(base: str) -> dict:
    root = _http(base + "/?publish-probe=" + str(int(time.time())))
    paths = {p: _http(f"{base}/{p}") for p in PROBE_PATHS}
    return {
        "root": {"status": root["status"], "bytes": root["bytes"]},
        "paths": {p: {"status": v["status"], "bytes": v["bytes"]}
                  for p, v in paths.items()},
        "html": root["body"].decode("utf-8", "replace"),
    }


def _log(line: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"[{stamp}] {line}\n")
    print(line)


def _vercel_cmd() -> list[str] | None:
    """Resolve the Vercel CLI without depending on the scheduler's PATH.

    On Windows the CLI is a `.cmd`, which CreateProcess will not launch on its
    own, so it is wrapped in `cmd /c` -- the scheduled task runs with a minimal
    environment and must not be the place this fails.
    """
    found = shutil.which("vercel")
    if found:
        if found.lower().endswith((".cmd", ".bat")):
            return ["cmd", "/c", found]
        return [found]
    for cand in (Path(os.environ.get("APPDATA", "")) / "npm" / "vercel.cmd",
                 Path(os.environ.get("APPDATA", "")) / "npm" / "vercel"):
        if cand.is_file():
            if cand.suffix.lower() in (".cmd", ".bat"):
                return ["cmd", "/c", str(cand)]
            return [str(cand)]
    if shutil.which("npx"):
        return ["npx", "--yes", "vercel"]
    return None


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 900):
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, timeout=timeout)


def _deploy_dir() -> Path:
    """Stage the bundle OUTSIDE the repo before deploying.

    Vercel's CLI walks up to the enclosing git root, and this repo's root is not
    the viewer: deploying from inside the tree uploaded the wrong thing (that is
    how an empty build reached production). A copy in the OS temp dir has no
    repository above it.
    """
    dest = Path(os.environ.get("TEMP", "/tmp")) / "genesis-viewer-publish"
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(BUNDLE, dest)
    return dest


def _lock_is_stale() -> bool:
    if not LOCK.is_file():
        return True
    try:
        return (time.time() - LOCK.stat().st_mtime) > LOCK_STALE_SECONDS
    except OSError:
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="build only; deploy nothing")
    parser.add_argument("--no-build", action="store_true",
                        help="use the existing bundle instead of rebuilding")
    parser.add_argument("--verify-only", metavar="URL",
                        help="probe a URL and report; change nothing")
    args = parser.parse_args()

    if args.verify_only:
        probes = probe(args.verify_only.rstrip("/"))
        ok, reasons = assess(probes)
        _log(f"verify-only {args.verify_only}: {'OK' if ok else 'FAIL ' + '; '.join(reasons)}")
        return 0 if ok else 1

    if not _lock_is_stale():
        _log("another publish appears to be running; skipping this tick")
        return 0

    vercel = _vercel_cmd()
    if vercel is None:
        _log("ABORT: no vercel CLI found (checked PATH and %APPDATA%\\npm)")
        return 1

    # The lock is taken BEFORE the build, not after it. silent_launch.vbs starts
    # this process detached and returns immediately, so the scheduler's
    # MultipleInstances=IgnoreNew cannot prevent two runs overlapping -- only
    # this file can, and it must cover the build too (that is the slow part).
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    try:
        return _publish(args, vercel)
    finally:
        LOCK.unlink(missing_ok=True)


def _publish(args, vercel: list[str]) -> int:
    if not args.no_build:
        build = _run([sys.executable, str(BUILD_SCRIPT)], cwd=WORLD_SIM, timeout=1800)
        if build.returncode != 0 or not (BUNDLE / "index.html").is_file():
            _log(f"ABORT: build failed (rc={build.returncode}); alias untouched")
            return 1
        if "MISS" in (build.stdout or "") or "Traceback" in (build.stderr or ""):
            _log("ABORT: build reported a missing file or traceback; alias untouched")
            return 1

    if args.dry_run:
        _log("dry run: build complete, nothing deployed")
        return 0

    if not (BUNDLE / "index.html").is_file():
        _log("ABORT: no bundle to deploy; alias untouched")
        return 1

    staging = _deploy_dir()
    # A deploy that returns nothing readable is retried once before giving up.
    # Measured 2026-11-15 10:21: the scheduled run logged "could not read a
    # deployment URL (rc=1)" and nothing else, so there was no way to tell a
    # transient CLI failure from a real problem. Now the output tail is logged
    # too, and one retry covers the transient case.
    url = ""
    tail = ""
    for attempt in (1, 2):
        dep = _run(vercel + ["deploy", "--yes", "--project", PROJECT], cwd=staging)
        output = (dep.stdout or "") + (dep.stderr or "")
        url = parse_deploy_url(output) or ""
        if url:
            break
        tail = " | ".join(line.strip() for line in output.strip().splitlines()[-4:])
        _log(f"deploy attempt {attempt} produced no URL (rc={dep.returncode}): "
             f"{tail[:400]}")
        if attempt == 1:
            time.sleep(15)
    if not url:
        _log("ABORT: could not read a deployment URL after 2 attempts; "
             "alias untouched")
        return 1

    probes = probe(url)
    ok, reasons = assess(probes)
    if not ok:
        _log(f"ABORT: preview {url} failed verification ({'; '.join(reasons)}); "
             "alias untouched")
        return 1

    alias = _run(vercel + ["alias", "set", url, ALIAS])
    if alias.returncode != 0:
        _log(f"ABORT: alias set failed (rc={alias.returncode}); "
             f"previous deployment still live")
        return 1

    # The edge caches the old index.html briefly; confirm it really flipped.
    live_reasons: list[str] = []
    for attempt in range(1, 7):
        time.sleep(4)
        live = probe(f"https://{ALIAS}")
        live_ok, live_reasons = assess(live)
        if live_ok:
            _log(f"published {url} -> {ALIAS} (confirmed after {attempt} probe(s))")
            return 0
    _log(f"published {url} -> {ALIAS}, but the alias still served the old "
         f"build after 6 probes ({'; '.join(live_reasons)})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

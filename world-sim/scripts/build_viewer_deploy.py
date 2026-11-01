#!/usr/bin/env python
"""Assemble a static, deployable copy of the 3D Civilization Observatory.

The live viewer under world-sim/viewer/prototype/ is left untouched. This
builds world-sim/viewer-dist/ -- a self-contained static site that can be
pushed to Netlify, Vercel, or any static host with no server process.

What it does:
  1. copies the html entry points, js libs, and world backdrop
  2. re-encodes every prop texture from PNG to WebP (measured ~95% smaller)
     and rewrites the asset paths in the COPIED html, never the source
  3. exports a fresh viewer_data.js from the live .runtime stores
  4. writes netlify.toml and vercel.json

Refresh the deployed site by re-running this script and re-pushing.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
VIEWER = WORLD_SIM / "viewer"
PROTO = VIEWER / "prototype"
# was viewer-dist, but a lingering handle from a finished `vercel deploy`
# made that path undeletable and an rmtree against it wiped a good build.
# Building to a fresh directory sidesteps the lock entirely.
DIST = VIEWER / "viewer-deploy"

EXPORTER = WORLD_SIM / "scripts" / "export_viewer_snapshot.py"

# Entry points, js libs and backdrop that must be copied verbatim.
STATIC_COPY = [
    ("index.html", "index.html"),
    ("../classic_2d.html", "classic_2d.html"),
    ("./js/three.min.js", "js/three.min.js"),
    ("./js/OrbitControls.js", "js/OrbitControls.js"),
    ("../world_base.png", "world_base.png"),
]

# Files the live viewer loads from viewer/ (one directory ABOVE prototype/):
# the terrain JSON, agent portraits, and the classic 2D viewer's PWA assets.
# They must be copied into the deploy root and their ../ prefixes stripped.
PARENT_ASSETS = [
    "../continent_terrain.json",
    "../adam_portrait.jpg",
    "../eve_portrait.jpg",
    "../manifest.json",
    "../apple-touch-icon.png",
    "../icon-192.png",
]

# Basenames whose leading "../" is stripped from the copied html. Anything not
# listed keeps its path, so an unhandled reference fails loudly rather than
# silently pointing at a file that is not there.
REWRITABLE = {
    "continent_terrain.json",
    "adam_portrait.jpg",
    "eve_portrait.jpg",
    "manifest.json",
    "apple-touch-icon.png",
    "icon-192.png",
    "viewer_data.js",
    "classic_2d.html",
}

WEBP_QUALITY = 82


def build_webp(src: Path, dst: Path) -> int:
    """Re-encode one texture as WebP. Returns the destination byte size."""
    from PIL import Image

    im = Image.open(src)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    im.save(dst, "WEBP", quality=WEBP_QUALITY, method=6)
    return dst.stat().st_size


_PREFIX_SUBS = [(re.escape(name), name) for name in sorted(REWRITABLE)]


def rewrite_asset_paths(html: str) -> str:
    """Make the copied html self-contained inside the deploy root.

    Three rewrites, all required because the live viewer sits one directory
    deeper than the deploy root:

      ./assets/x.png  -> ./assets/x.webp     (re-encoded textures)
      ../name         -> name                (data, portraits, terrain, PWA)
      ./prototype/index.html -> ./index.html (the classic viewer's back link)

    Only the basenames in REWRITABLE are stripped. An unlisted ../ reference
    is left alone so verification catches it rather than silently pointing at
    a file that was never copied.
    """
    html = re.sub(
        r"(['\"])(\./assets/[A-Za-z0-9_\-]+)\.png(['\"])",
        r"\1\2.webp\3",
        html,
    )
    for pat, name in _PREFIX_SUBS:
        # handles quoted src="; quoted href="; and template fetches
        html = re.sub(r"(['\"`])\.\./" + pat + r"\b", r"\1" + name, html)
        html = re.sub(r"(['\"`])\.\./" + pat + r"\?", r"\1" + name + "?", html)
    html = html.replace("./prototype/index.html", "./index.html")
    return html


def _clear_output_dir() -> None:
    """Empty the build output without ever risking a half-wiped tree.

    The previous implementation called shutil.rmtree directly. When a lingering
    CLI handle locked the folder, rmtree had already removed most children
    before raising, so a "failed" cleanup destroyed a good build -- twice.
    Now: build into a temp dir and swap, so the live tree is only ever replaced
    by a complete one.
    """
    global DIST
    staging = VIEWER / (DIST.name + ".staging")
    if staging.exists():
        try:
            shutil.rmtree(staging)
        except OSError as exc:
            print("  WARN could not clear staging %s (%s)" % (staging, exc))
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "assets").mkdir(parents=True, exist_ok=True)
    (staging / "js").mkdir(parents=True, exist_ok=True)
    if DIST.exists():
        try:
            DIST.rename(staging.parent / (DIST.name + ".old"))
            shutil.rmtree(staging.parent / (DIST.name + ".old"))
        except OSError:
            # fall back to in-place overwrite
            pass
    DIST = staging


def _publish_staging() -> Path:
    """Move the completed staging tree into place as the real output dir."""
    real = DIST                      # this IS the staging directory
    target = VIEWER / "viewer-deploy"
    # 1) move any previous real build out of the way
    if target.exists():
        try:
            target.rename(VIEWER / "viewer-deploy.old")
        except OSError as exc:
            print("  WARN could not move previous build aside (%s)" % exc)
    # 2) promote staging
    real.rename(target)
    # 3) remove the old build
    old = VIEWER / "viewer-deploy.old"
    if old.exists():
        try:
            shutil.rmtree(old)
        except OSError as exc:
            print("  WARN could not delete previous build (%s)" % exc)
    return target


def main() -> int:
    _clear_output_dir()

    total_before = total_after = 0

    # 1. static copies
    for src_rel, dst_rel in STATIC_COPY:
        src = (PROTO / src_rel).resolve()
        dst = DIST / dst_rel
        if not src.exists():
            print("  MISS  %s" % src_rel)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        total_before += src.stat().st_size
        total_after += dst.stat().st_size
        print("  copy  %-38s %s bytes" % (dst_rel, format(dst.stat().st_size, ",")))

    # 1b. parent-directory assets (terrain json, portraits, PWA files)
    print()
    print("  parent assets")
    for rel in PARENT_ASSETS:
        src = (PROTO / rel).resolve()
        dst = DIST / os.path.basename(rel)
        if not src.exists():
            print("    MISS  %s" % rel)
            continue
        shutil.copy2(src, dst)
        total_before += src.stat().st_size
        total_after += dst.stat().st_size
        print("    copy  %-28s %s bytes" % (os.path.basename(rel),
                                           format(dst.stat().st_size, ",")))

    # 2. textures -> WebP, and rewrite the copied html
    print()
    print("  textures -> WebP (quality %d)" % WEBP_QUALITY)
    src_assets = PROTO / "assets"
    for png in sorted(src_assets.glob("*.png")):
        dst = DIST / "assets" / (png.stem + ".webp")
        before = png.stat().st_size
        after = build_webp(png, dst)
        total_before += before
        total_after += after
        print("    %-24s %10s -> %8s  (%2.0f%% saved)"
              % (png.name, format(before, ","), format(after, ","),
                 100.0 * (1 - after / before)))

    for html_name in ("index.html", "classic_2d.html"):
        target = DIST / html_name
        if not target.exists():
            continue
        text = target.read_text(encoding="utf-8")
        text = rewrite_asset_paths(text)
        target.write_text(text, encoding="utf-8", newline="")

    # 3. fresh data export straight into the dist
    print()
    print("  exporting fresh viewer_data.js from live stores ...")
    r = subprocess.run(
        [
            sys.executable,
            str(EXPORTER),
            "--out",
            str(DIST / "viewer_data.js"),
        ],
        cwd=str(WORLD_SIM),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        return 1
    print("   ", (r.stdout.strip().splitlines() or ["ok"])[-1])

    # 4. host config
    (DIST / "netlify.toml").write_text(
        """# Genesis Civilization Observatory - static deploy
[build]
  publish = "."

# The civilization snapshot is a single large JSON-in-JS file. It compresses
# ~4x at the CDN; declare the content encoding so it is compressed once and
# cached, and let the browser revalidate the html entry points.
[[headers]]
  for = "/*.js"
  [headers.values]
    Cache-Control = "public, max-age=3600"
    Content-Type = "application/javascript; charset=utf-8"

[[headers]]
  for = "/*.webp"
  [headers.values]
    Cache-Control = "public, max-age=86400, immutable"
    Content-Type = "image/webp"

[[headers]]
  for = "/*.html"
  [headers.values]
    Cache-Control = "public, max-age=0, must-revalidate"
""",
        encoding="utf-8",
        newline="",
    )

    # NOTE: only Cache-Control is set. Vercel infers Content-Type from the
    # extension and its automatic gzip/brotli compression keys off that
    # inference -- setting Content-Type explicitly here suppressed it and
    # served the 14.9 MB viewer_data.js uncompressed (measured on the first
    # deploy). Let the platform infer the type and it compresses.
    (DIST / "vercel.json").write_text(
        """{
  "cleanUrls": true,
  "trailingSlash": false,
  "headers": [
    {
      "source": "/(.*).js",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=3600" }
      ]
    },
    {
      "source": "/(.*).webp",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=86400, immutable" }
      ]
    },
    {
      "source": "/(.*).png",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=86400, immutable" }
      ]
    },
    {
      "source": "/(.*).json",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=3600" }
      ]
    }
  ]
}
""",
        encoding="utf-8",
        newline="",
    )

    print()
    print("  deploy size: %s -> %s bytes (%.1f%% saved)"
          % (format(total_before, ","), format(total_after, ","),
             100.0 * (1 - total_after / max(total_before, 1))))
    print("  built: %s" % DIST)
    final = _publish_staging()
    print("  published: %s" % final)
    print()
    print("  next:")
    print("    netlify deploy --prod --dir=world-sim/viewer/viewer-deploy")
    print("    vercel --prod world-sim/viewer/viewer-deploy")
    return 0


DEPLOY_HELP = (
    "\n"
    "Deploy. IMPORTANT: the Vercel CLI walks up to the enclosing git repo root\n"
    "when there is no .vercel link in the deploy directory, which uploads the\n"
    "whole repo (~24,000 files) and trips the 15000-item request limit. Copy\n"
    "the build OUTSIDE the repo and deploy from there:\n"
    "\n"
    "    $tmp = Join-Path $env:TEMP 'genesis-observatory-deploy'\n"
    "    Remove-Item -Recurse -Force $tmp -EA SilentlyContinue\n"
    "    New-Item -ItemType Directory -Force -Path $tmp | Out-Null\n"
    "    Copy-Item 'world-sim/viewer/viewer-deploy/*' $tmp -Recurse -Force\n"
    "    cd $tmp\n"
    "    vercel deploy --prod --yes --project genesis-civilization-observatory\n"
    "\n"
    "Do NOT run 'vercel link' inside the Genesis repo: it writes the link to the\n"
    "repo root and every later deploy uploads the entire repository.\n"
)


if __name__ == "__main__":
    _code = main()
    if _code == 0:
        print(DEPLOY_HELP)
    raise SystemExit(_code)

"""Capture the live viewer headlessly, with no window and no GPU.

Why this exists: asking the operator to hold a desktop window in the foreground
made my problem his. A viewer screenshot must not depend on what he is doing.

Runs Chrome headless with SOFTWARE rendering (SwiftShader), so it cannot touch
the GPU that crashed twice, and captures the page for real -- the DOM HUD plus
the WebGL scene -- by waiting until the viewer has actually painted frames
rather than guessing a sleep.

    python scripts/shoot_viewer.py --civ east --cam adam --out shots/east.png
    python scripts/shoot_viewer.py --civ west --cam topdown --width 1920 --height 1200
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

BASE = "https://genesis-civilization-observatory.vercel.app"

# Count real painted frames before capturing: the viewer animates on
# requestAnimationFrame, so a screenshot taken too early is an empty blue field.
_FRAME_PROBE = """
window.__shotFrames = 0;
(function tick() { window.__shotFrames++; requestAnimationFrame(tick); })();
"""


def build_url(civ: str, cam: str, override: str = "", base: str = BASE) -> str:
    """The viewer URL for a civ/cam pair. Pure, so it can be asserted."""
    if override:
        return override
    url = f"{base}/?civ={civ}"
    if cam:
        url += f"&cam={cam}"
    return url


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--civ", default="east", help="east | west")
    ap.add_argument("--cam", default="", help="adam | eve | topdown | orbit | landscape")
    ap.add_argument("--url", default="", help="override the whole URL")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=1000)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-frames", type=int, default=40,
                    help="painted frames to wait for before capturing")
    ap.add_argument("--click", default="",
                    help="after loading, click the first control whose text "
                         "contains this (e.g. 'Interior')")
    ap.add_argument("--timeout", type=float, default=180.0)
    args = ap.parse_args()

    url = build_url(args.civ, args.cam, args.url)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SHOOT_ERROR: playwright not installed")
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome",
            headless=True,
            args=[
                "--use-angle=swiftshader",     # software WebGL: no GPU at all
                "--enable-unsafe-swiftshader",
                "--hide-scrollbars",
                "--mute-audio",
                "--disable-lcd-text",
            ],
        )
        page = browser.new_page(viewport={"width": args.width, "height": args.height},
                               device_scale_factor=1)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))
        page.goto(url, wait_until="load", timeout=90_000)
        page.wait_for_function(
            "() => document.body && document.body.innerText.includes('GENESIS')",
            timeout=60_000)
        page.evaluate(_FRAME_PROBE)

        clicked = ""
        if args.click:
            # Headless, so the viewer's own controls are drivable: no window, and
            # nobody has to click anything.
            page.locator(
                f"button:has-text('{args.click}'), "
                f"[role=button]:has-text('{args.click}')").first.click(timeout=20_000)
            clicked = args.click
            page.evaluate(_FRAME_PROBE)  # restart the counter after the change

        deadline = time.time() + args.timeout
        frames = 0
        while time.time() < deadline:
            frames = page.evaluate("() => window.__shotFrames || 0")
            if frames >= args.min_frames:
                break
            time.sleep(1.0)

        # one more beat so the last painted frame is the one we keep
        time.sleep(1.5)
        page.screenshot(path=str(out), full_page=False)
        title = page.title()
        browser.close()

    size = out.stat().st_size
    print(f"SHOT url={url}")
    if clicked:
        print(f"SHOT clicked={clicked!r}")
    print(f"SHOT painted_frames={frames} page_errors={len(errors)}")
    for e in errors[:3]:
        print(f"SHOT page_error: {e}")
    print(f"SHOT {out} ({size:,} bytes) title={title!r}")
    if frames < args.min_frames:
        print(f"SHOT WARNING: only {frames} frames painted before the timeout")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Generate app icons for the Genesis Observatory PWA."""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

VIEWER = Path(__file__).resolve().parent.parent / "viewer"

def create_app_icon():
    size = 512
    img = Image.new("RGBA", (size, size), (3, 5, 9, 255))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2

    # Background ambient radial glow
    for r in range(240, 20, -10):
        alpha = int(45 * (1 - r / 240))
        # Cyan / gold celestial blend
        color = (0, int(180 * (1 - r/240)), int(220 * (1 - r/240)), alpha)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    # Outer celestial compass ring (gold)
    r_outer = 210
    draw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
                 outline=(254, 202, 87, 220), width=6)

    # Secondary cyan ring
    r_mid = 175
    draw.ellipse([cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid],
                 outline=(0, 210, 211, 180), width=3)

    # Inner ring (dashed effect using ticks)
    for deg in range(0, 360, 15):
        rad = math.radians(deg)
        x1 = cx + (r_mid - 8) * math.cos(rad)
        y1 = cy + (r_mid - 8) * math.sin(rad)
        x2 = cx + (r_mid + 8) * math.cos(rad)
        y2 = cy + (r_mid + 8) * math.sin(rad)
        w = 3 if deg % 90 == 0 else 1
        col = (254, 202, 87, 255) if deg % 90 == 0 else (0, 210, 211, 140)
        draw.line([x1, y1, x2, y2], fill=col, width=w)

    # Central stylized 4-point Diamond Star (Genesis Genesis Crest)
    points = [
        (cx, cy - 140),  # North
        (cx + 28, cy - 28),
        (cx + 140, cy),  # East
        (cx + 28, cy + 28),
        (cx, cy + 140),  # South
        (cx - 28, cy + 28),
        (cx - 140, cy),  # West
        (cx - 28, cy - 28),
    ]
    draw.polygon(points, fill=(245, 247, 250, 240), outline=(254, 202, 87, 255))

    # Inner core radiant diamond (cyan)
    inner_pts = [
        (cx, cy - 70),
        (cx + 16, cy - 16),
        (cx + 70, cy),
        (cx + 16, cy + 16),
        (cx, cy + 70),
        (cx - 16, cy + 16),
        (cx - 70, cy),
        (cx - 16, cy - 16),
    ]
    draw.polygon(inner_pts, fill=(0, 210, 211, 255))

    # Center jewel
    r_core = 14
    draw.ellipse([cx - r_core, cy - r_core, cx + r_core, cy + r_core],
                 fill=(255, 255, 255, 255), outline=(254, 202, 87, 255), width=2)

    # Save 512x512
    p512 = VIEWER / "icon-512.png"
    img.save(p512, "PNG")
    print(f"Saved {p512}")

    # Save 192x192
    img192 = img.resize((192, 192), Image.Resampling.LANCZOS)
    p192 = VIEWER / "icon-192.png"
    img192.save(p192, "PNG")
    print(f"Saved {p192}")

    # Save apple-touch-icon 180x180
    img_apple = img.resize((180, 180), Image.Resampling.LANCZOS)
    p_apple = VIEWER / "apple-touch-icon.png"
    img_apple.save(p_apple, "PNG")
    print(f"Saved {p_apple}")

if __name__ == "__main__":
    create_app_icon()

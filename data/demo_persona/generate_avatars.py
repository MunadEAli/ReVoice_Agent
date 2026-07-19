"""
Generate simple colored-circle initials avatars for the demo persona using Pillow.
Saves PNGs to data/demo_persona/avatars/ and optionally uploads to OSS.

Personas: Lily (L), David (D), Carol (C), Margaret (M - the user)
"""
from __future__ import annotations

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

AVATARS_DIR = Path(__file__).parent / "avatars"

PERSONA_COLORS = {
    "lily":     ("#F4A261", "#FFFFFF"),   # warm orange, white text
    "david":    ("#457B9D", "#FFFFFF"),   # steel blue, white text
    "carol":    ("#6D6875", "#FFFFFF"),   # muted purple, white text
    "margaret": ("#2D6A4F", "#FFFFFF"),   # forest green, white text
}

SIZE = 256


def _draw_avatar(initial: str, bg_color: str, fg_color: str) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), bg_color)
    draw = ImageDraw.Draw(img)

    # Draw circle background
    draw.ellipse([0, 0, SIZE - 1, SIZE - 1], fill=bg_color)

    # Try to use a bold font; fall back to default
    font = None
    font_size = 120
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/ariblk.ttf", font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

    # Center text
    bbox = draw.textbbox((0, 0), initial, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (SIZE - tw) // 2 - bbox[0]
    y = (SIZE - th) // 2 - bbox[1]
    draw.text((x, y), initial, fill=fg_color, font=font)

    return img


def generate_all(upload: bool = False) -> dict[str, str]:
    """Generate all avatars, upload if `upload=True`, return {name: url} map."""
    AVATARS_DIR.mkdir(parents=True, exist_ok=True)

    urls = {}
    for name, (bg, fg) in PERSONA_COLORS.items():
        initial = name[0].upper()
        img = _draw_avatar(initial, bg, fg)
        path = AVATARS_DIR / f"{name}.png"
        img.save(str(path))
        print(f"Saved avatar: {path}")

        if upload:
            from services.storage.oss_client import upload_file
            object_key = f"avatars/{name}.png"
            url = upload_file(str(path), object_key)
            print(f"Uploaded {name}: {url}")
            urls[name] = url
        else:
            urls[name] = f"file://{path.as_posix()}"

    return urls


if __name__ == "__main__":
    import sys
    should_upload = "--upload" in sys.argv
    result = generate_all(upload=should_upload)
    print("\nAvatar URLs:")
    for name, url in result.items():
        print(f"  {name}: {url}")

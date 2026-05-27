"""
modules/thumbnail.py
Generates YouTube thumbnails using Pillow (free).
Finance style: dark gradient bg + bold white text + accent bar.
Food style: bright warm bg + large text + food emoji accent.
"""

import os
import textwrap
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests

from config import (
    ChannelConfig, THUMB_WIDTH, THUMB_HEIGHT,
    OPENAI_API_KEY,
)

FONT_PATH = "assets/fonts/Roboto-Bold.ttf"
FONT_PATH_REG = "assets/fonts/Roboto-Regular.ttf"


def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    path = FONT_PATH if bold else FONT_PATH_REG
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _download_bg_image(query: str, output_path: str) -> Optional[str]:
    """Grab a Pexels photo for the background (optional enhancement)."""
    from config import PEXELS_API_KEY
    if not PEXELS_API_KEY:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            timeout=10,
        )
        photos = r.json().get("photos", [])
        if not photos:
            return None
        img_url = photos[0]["src"]["large2x"]
        img_r = requests.get(img_url, timeout=20)
        with open(output_path, "wb") as f:
            f.write(img_r.content)
        return output_path
    except Exception:
        return None


def generate_finance_thumbnail(
    channel: ChannelConfig,
    text: str,
    output_path: str,
    bg_query: Optional[str] = None,
) -> str:
    """
    Finance/AI style thumbnail:
    Dark semi-transparent overlay + bold white title + green accent bar.
    """
    accent = _hex_to_rgb(channel.primary_color)
    img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (15, 15, 25))

    # try to get a background photo
    if bg_query:
        bg_tmp = output_path.replace(".jpg", "_bg.jpg")
        bg_path = _download_bg_image(bg_query, bg_tmp)
        if bg_path:
            try:
                bg = Image.open(bg_path).convert("RGB")
                bg = bg.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.LANCZOS)
                bg = bg.filter(ImageFilter.GaussianBlur(radius=2))
                # dark overlay
                overlay = Image.new("RGBA", (THUMB_WIDTH, THUMB_HEIGHT), (0, 0, 0, 160))
                img = bg.copy()
                img.paste(Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (0, 0, 0)),
                          mask=overlay.split()[3])
                os.remove(bg_path)
            except Exception:
                pass

    draw = ImageDraw.Draw(img)

    # accent bar on left
    bar_width = 12
    draw.rectangle([(40, 80), (40 + bar_width, THUMB_HEIGHT - 80)], fill=accent)

    # wrap and draw title text
    font_large = _load_font(90)
    font_small = _load_font(50)

    words = text.upper().split()
    lines = textwrap.wrap(text.upper(), width=14)
    y = 120

    for line in lines[:3]:
        draw.text((80, y), line, font=font_large, fill=(255, 255, 255))
        bbox = draw.textbbox((80, y), line, font=font_large)
        y = bbox[3] + 20

    # bottom accent strip
    draw.rectangle(
        [(0, THUMB_HEIGHT - 70), (THUMB_WIDTH, THUMB_HEIGHT)],
        fill=(*accent, 200)
    )
    draw.text(
        (40, THUMB_HEIGHT - 55),
        channel.name.upper(),
        font=_load_font(36),
        fill=(255, 255, 255),
    )

    os.makedirs(Path(output_path).parent, exist_ok=True)
    img.save(output_path, "JPEG", quality=95)
    print(f"  [thumb] Finance thumbnail saved: {Path(output_path).name}")
    return output_path


def generate_food_thumbnail(
    channel: ChannelConfig,
    text: str,
    output_path: str,
    bg_query: Optional[str] = None,
) -> str:
    """
    Food style thumbnail:
    Warm background photo + bold orange text + white stroke.
    """
    accent = _hex_to_rgb(channel.primary_color)
    img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (255, 240, 220))

    if bg_query:
        bg_tmp = output_path.replace(".jpg", "_bg.jpg")
        bg_path = _download_bg_image(bg_query + " food", bg_tmp)
        if bg_path:
            try:
                bg = Image.open(bg_path).convert("RGB")
                bg = bg.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.LANCZOS)
                img = bg
                os.remove(bg_path)
            except Exception:
                pass

    draw = ImageDraw.Draw(img)

    # semi-transparent dark band at top for text readability
    band = Image.new("RGBA", (THUMB_WIDTH, 320), (0, 0, 0, 140))
    img.paste(Image.new("RGB", (THUMB_WIDTH, 320), (0, 0, 0)),
              (0, 0), mask=band.split()[3])

    font_large = _load_font(96)

    lines = textwrap.wrap(text.upper(), width=12)
    y = 50
    for line in lines[:2]:
        # white outline effect
        for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3)]:
            draw.text((40+dx, y+dy), line, font=font_large, fill=(0,0,0))
        draw.text((40, y), line, font=font_large, fill=(255, 255, 255))
        bbox = draw.textbbox((40, y), line, font=font_large)
        y = bbox[3] + 15

    # accent bottom bar
    draw.rectangle(
        [(0, THUMB_HEIGHT - 80), (THUMB_WIDTH, THUMB_HEIGHT)],
        fill=(*accent, 230)
    )
    draw.text(
        (40, THUMB_HEIGHT - 62),
        channel.name,
        font=_load_font(40),
        fill=(255, 255, 255),
    )

    os.makedirs(Path(output_path).parent, exist_ok=True)
    img.save(output_path, "JPEG", quality=95)
    print(f"  [thumb] Food thumbnail saved: {Path(output_path).name}")
    return output_path


def generate_thumbnail(
    channel: ChannelConfig,
    thumbnail_text: str,
    output_path: str,
    bg_query: Optional[str] = None,
) -> str:
    """Route to the correct thumbnail style for the channel."""
    if channel.thumbnail_style == "food":
        return generate_food_thumbnail(channel, thumbnail_text, output_path, bg_query)
    else:
        return generate_finance_thumbnail(channel, thumbnail_text, output_path, bg_query)


if __name__ == "__main__":
    from config import CHANNEL_A, CHANNEL_B
    generate_thumbnail(CHANNEL_A, "Save $1000 Fast", "temp/thumb_a.jpg", "money investment")
    generate_thumbnail(CHANNEL_B, "5 Ingredient Meals", "temp/thumb_b.jpg", "healthy food")
    print("Thumbnails generated in temp/")

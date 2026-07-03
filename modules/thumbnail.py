"""
modules/thumbnail.py
Generates YouTube thumbnails.
Channel A (finance): VidIQ AI generation via Anthropic MCP → Pillow fallback
Channel B (horror): GPT Image cinematic horror style
"""

import os
import math
import textwrap
import requests
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from config import (
    ChannelConfig, THUMB_WIDTH, THUMB_HEIGHT,
    OPENAI_API_KEY, PEXELS_API_KEY,
)

FONT_PATH     = "assets/fonts/Roboto-Bold.ttf"
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


def _generate_dalle_background(prompt: str, output_path: str, quality: str = "medium") -> Optional[str]:
    """Generate a background using GPT Image models."""
    if not OPENAI_API_KEY:
        return None
    try:
        import base64
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        print(f"  [thumb] GPT Image generating background ({quality})...")
        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1536x1024",
            quality=quality,
            n=1,
        )
        b64_data = response.data[0].b64_json
        img_data = base64.b64decode(b64_data)
        img = Image.open(BytesIO(img_data)).convert("RGB")
        img = img.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.LANCZOS)
        img.save(output_path, "JPEG", quality=95)
        print(f"  [thumb] Background saved")
        return output_path
    except Exception as e:
        print(f"  [thumb] GPT Image error: {e} — falling back to Pexels")
        return None


def _fetch_pexels_background(query: str, output_path: str) -> Optional[str]:
    """Fallback: grab a Pexels photo as background."""
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
        img = Image.open(BytesIO(img_r.content)).convert("RGB")
        img = img.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.LANCZOS)
        img.save(output_path, "JPEG", quality=95)
        return output_path
    except Exception as e:
        print(f"  [thumb] Pexels bg error: {e}")
        return None


def _get_background(dalle_prompt: str, pexels_query: str, bg_path: str, quality: str = "medium") -> Optional[Image.Image]:
    bg = _generate_dalle_background(dalle_prompt, bg_path, quality=quality)
    if not bg:
        bg = _fetch_pexels_background(pexels_query, bg_path)
    if bg and os.path.exists(bg):
        return Image.open(bg).convert("RGB")
    return None


def _draw_text_with_shadow(
    draw: ImageDraw.Draw,
    text: str,
    position: Tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: Tuple = (255, 255, 255),
    shadow_color: Tuple = (0, 0, 0),
    shadow_offset: int = 4,
) -> int:
    x, y = position
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)
    bbox = draw.textbbox((x, y), text, font=font)
    return bbox[3]


def _apply_vignette(img: Image.Image, strength: float = 0.7) -> Image.Image:
    width, height = img.size
    cx, cy = width // 2, height // 2
    max_dist = math.sqrt(cx**2 + cy**2)
    vignette = Image.new("L", (width, height), 255)
    pixels = vignette.load()
    for y in range(height):
        for x in range(width):
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            normalized = dist / max_dist
            factor = max(0, 1 - (normalized * strength * 1.4) ** 1.5)
            pixels[x, y] = int(255 * factor)
    vignette_rgb = Image.merge("RGB", [vignette, vignette, vignette])
    result = Image.new("RGB", img.size)
    img_data = list(img.getdata())
    vig_data = list(vignette_rgb.getdata())
    result_data = [
        (int(ip[0]*vp[0]/255), int(ip[1]*vp[1]/255), int(ip[2]*vp[2]/255))
        for ip, vp in zip(img_data, vig_data)
    ]
    result.putdata(result_data)
    return result


def _apply_horror_grading(img: Image.Image) -> Image.Image:
    img = ImageEnhance.Color(img).enhance(0.65)
    img = ImageEnhance.Contrast(img).enhance(1.35)
    img = ImageEnhance.Brightness(img).enhance(0.8)
    img = _apply_vignette(img, strength=0.8)
    return img


# ── Finance thumbnail ──────────────────────────────────────────────────────────

def generate_finance_thumbnail(
    channel: ChannelConfig,
    text: str,
    output_path: str,
    bg_query: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Finance thumbnail — tries VidIQ first, falls back to Pillow vertical split.
    VidIQ produces professional quality matching top performers.
    Pillow fallback: vertical split red/center/green with bold text.
    """
    # ── VidIQ thumbnail disabled — using manual VidIQ web interface instead ───
    # try:
    #     from modules.thumbnail_vidiq import generate_via_anthropic_mcp
    #     title = kwargs.get("title", text)
    #     result = generate_via_anthropic_mcp(title, text, output_path)
    #     if result:
    #         return result
    #     print("  [thumb] VidIQ failed — using Pillow fallback")
    # except Exception as e:
    #     print(f"  [thumb] VidIQ unavailable: {e} — using Pillow")

    # ── Pillow fallback: vertical split ───────────────────────────────────────
    accent = _hex_to_rgb(channel.primary_color)
    bg_path = output_path.replace(".jpg", "_bg.jpg")

    dalle_prompt = (
        f"Cinematic dark finance YouTube thumbnail background, "
        f"{'about ' + bg_query if bg_query else 'stock market trading'}, "
        f"dramatic red and green stock chart arrows, dark moody atmosphere, "
        f"professional financial imagery, smartphone app screens, "
        f"deep dark blue and black tones, 4K quality, no text, photorealistic"
    )

    bg_img = _get_background(dalle_prompt, bg_query or "stock market red green", bg_path, quality="medium")

    img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (8, 10, 20))
    if bg_img:
        darkened = ImageEnhance.Brightness(bg_img).enhance(0.7)
        img.paste(darkened, (0, 0))

    draw = ImageDraw.Draw(img)

    # split text
    words = text.upper().split()
    mid = len(words) // 2
    left_text = " ".join(words[:mid]) if mid > 0 else words[0]
    right_text = " ".join(words[mid:]) if mid < len(words) else ""

    full = text.upper()
    if "?" in full and full.count("?") == 1:
        parts = full.split("?")
        left_text = parts[0].strip() + "?"
        right_text = parts[1].strip() if parts[1].strip() else right_text
    elif ":" in full:
        parts = full.split(":", 1)
        left_text = parts[0].strip()
        right_text = parts[1].strip()

    # left red panel
    left_overlay = Image.new("RGBA", (THUMB_WIDTH // 3, THUMB_HEIGHT), (180, 20, 20, 180))
    img.paste(Image.new("RGB", (THUMB_WIDTH // 3, THUMB_HEIGHT), (180, 20, 20)),
              (0, 0), mask=left_overlay.split()[3])
    draw.polygon([(60, 80), (160, 80), (110, 160)], fill=(255, 50, 50))

    # right green panel
    right_overlay = Image.new("RGBA", (THUMB_WIDTH // 3, THUMB_HEIGHT), (20, 160, 70, 180))
    img.paste(Image.new("RGB", (THUMB_WIDTH // 3, THUMB_HEIGHT), (20, 160, 70)),
              (THUMB_WIDTH * 2 // 3, 0), mask=right_overlay.split()[3])
    draw.polygon([
        (THUMB_WIDTH * 2 // 3 + 60, 160),
        (THUMB_WIDTH * 2 // 3 + 160, 160),
        (THUMB_WIDTH * 2 // 3 + 110, 80)
    ], fill=(50, 255, 100))

    max_chars = max(len(left_text), len(right_text)) if right_text else len(left_text)
    if max_chars <= 5:
        font_size = 150
    elif max_chars <= 8:
        font_size = 125
    elif max_chars <= 12:
        font_size = 100
    else:
        font_size = 80

    font_large = _load_font(font_size)

    def draw_panel_text(panel_text: str, panel_x: int, panel_w: int):
        lines = textwrap.wrap(panel_text, width=8)[:2]
        total_h = len(lines) * (font_size + 15)
        start_y = (THUMB_HEIGHT - total_h) // 2
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_large)
            text_w = bbox[2] - bbox[0]
            x = panel_x + (panel_w - text_w) // 2
            y = start_y + i * (font_size + 15)
            for dx in range(-5, 6, 2):
                for dy in range(-5, 6, 2):
                    draw.text((x + dx, y + dy), line, font=font_large, fill=(0, 0, 0))
            draw.text((x, y), line, font=font_large, fill=(255, 255, 255))

    draw_panel_text(left_text, 0, THUMB_WIDTH // 3)
    if right_text:
        draw_panel_text(right_text, THUMB_WIDTH * 2 // 3, THUMB_WIDTH // 3)

    # divider lines
    draw.rectangle([(THUMB_WIDTH // 3 - 2, 0), (THUMB_WIDTH // 3 + 2, THUMB_HEIGHT)], fill=(255, 255, 255, 60))
    draw.rectangle([(THUMB_WIDTH * 2 // 3 - 2, 0), (THUMB_WIDTH * 2 // 3 + 2, THUMB_HEIGHT)], fill=(255, 255, 255, 60))

    try:
        if os.path.exists(bg_path):
            os.remove(bg_path)
    except Exception:
        pass

    os.makedirs(Path(output_path).parent, exist_ok=True)
    img.save(output_path, "JPEG", quality=97)
    print(f"  [thumb] Finance thumbnail saved (Pillow): {Path(output_path).name}")
    return output_path


# ── Food thumbnail ─────────────────────────────────────────────────────────────

def generate_food_thumbnail(
    channel: ChannelConfig,
    text: str,
    output_path: str,
    bg_query: Optional[str] = None,
    **kwargs,
) -> str:
    accent = _hex_to_rgb(channel.primary_color)
    bg_path = output_path.replace(".jpg", "_bg.jpg")

    dalle_prompt = (
        f"Stunning food photography for a YouTube thumbnail, "
        f"{'featuring ' + bg_query if bg_query else 'delicious home cooked meal'}, "
        f"warm appetising lighting, shallow depth of field, "
        f"vibrant colours, professional food photography, "
        f"no text, top-down or 45-degree angle, 4K quality"
    )

    bg_img = _get_background(dalle_prompt, bg_query or "delicious food cooking", bg_path)

    if bg_img:
        img = ImageEnhance.Brightness(bg_img).enhance(0.75)
    else:
        img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (255, 240, 220))

    draw = ImageDraw.Draw(img)
    band_h = 280
    band = Image.new("RGBA", (THUMB_WIDTH, band_h), (0, 0, 0, 170))
    img.paste(Image.new("RGB", (THUMB_WIDTH, band_h), (0, 0, 0)), (0, 0), mask=band.split()[3])

    font_large = _load_font(96)
    font_small = _load_font(44)

    lines = textwrap.wrap(text.upper(), width=12)[:2]
    y = 40
    for line in lines:
        y = _draw_text_with_shadow(draw, line, (45, y), font_large,
                                    fill=(255, 255, 255), shadow_color=(*accent, 255), shadow_offset=3) + 12

    draw.rectangle([(0, THUMB_HEIGHT - 75), (THUMB_WIDTH, THUMB_HEIGHT)], fill=(*accent, 230))
    draw.text((45, THUMB_HEIGHT - 57), channel.name, font=font_small, fill=(255, 255, 255))

    try:
        if os.path.exists(bg_path):
            os.remove(bg_path)
    except Exception:
        pass

    os.makedirs(Path(output_path).parent, exist_ok=True)
    img.save(output_path, "JPEG", quality=95)
    print(f"  [thumb] Food thumbnail saved: {Path(output_path).name}")
    return output_path


# ── Dark History thumbnail ─────────────────────────────────────────────────────

def generate_dark_history_thumbnail(
    channel: ChannelConfig,
    text: str,
    output_path: str,
    bg_query: Optional[str] = None,
    **kwargs,
) -> str:
    accent = _hex_to_rgb(channel.primary_color)
    bg_path = output_path.replace(".jpg", "_bg.jpg")

    dalle_prompt = (
        f"Cinematic dark mysterious YouTube thumbnail background, "
        f"{'ancient ' + bg_query if bg_query else 'ancient ruins mysterious'}, "
        f"dramatic dark atmosphere, deep shadows, ominous dark red and black tones, "
        f"fog or mist, ancient stone textures, dramatic underlighting, "
        f"no text, no faces, photorealistic, 4K quality"
    )

    bg_img = _get_background(dalle_prompt, bg_query or "ancient dark mystery ruins", bg_path)

    if bg_img:
        img = ImageEnhance.Brightness(bg_img).enhance(0.35)
        img = img.filter(ImageFilter.GaussianBlur(radius=1))
    else:
        img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (10, 0, 0))

    draw = ImageDraw.Draw(img)
    draw.rectangle([(45, 70), (59, THUMB_HEIGHT - 70)], fill=(*accent, 255))

    font_large = _load_font(96)
    font_small = _load_font(40)

    lines = textwrap.wrap(text.upper(), width=13)[:3]
    y = 90
    for line in lines:
        y = _draw_text_with_shadow(draw, line, (80, y), font_large,
                                    fill=(255, 255, 255), shadow_color=(*accent, 255), shadow_offset=4) + 16

    draw.rectangle([(0, THUMB_HEIGHT - 75), (THUMB_WIDTH, THUMB_HEIGHT)], fill=(*accent, 240))
    draw.text((45, THUMB_HEIGHT - 57), "💀 CHUCKY'S UNTOLD STORIES", font=font_small, fill=(255, 255, 255))

    try:
        if os.path.exists(bg_path):
            os.remove(bg_path)
    except Exception:
        pass

    os.makedirs(Path(output_path).parent, exist_ok=True)
    img.save(output_path, "JPEG", quality=95)
    print(f"  [thumb] Dark history thumbnail saved: {Path(output_path).name}")
    return output_path


# ── Horror Fiction thumbnail ───────────────────────────────────────────────────

def generate_horror_fiction_thumbnail(
    channel: ChannelConfig,
    text: str,
    output_path: str,
    bg_query: Optional[str] = None,
    story_hook: str = "",
    **kwargs,
) -> str:
    """
    Horror fiction thumbnail — cinematic doll style matching Chucky's Untold Stories.
    Pure AI art, no text overlay, only small watermark.
    6 rotating scene compositions for visual variety.
    """
    import random
    bg_path = output_path.replace(".jpg", "_bg.jpg")
    scene_context = bg_query or "Victorian room rocking chair"

    scenes = [
        f"Extreme close-up of a weathered porcelain doll face, cracked pale skin, glass eyes reflecting a single candle flame, dark Victorian room background, story: {text}",
        f"Wide cinematic shot of a small porcelain doll sitting alone in an abandoned Victorian room, moonlight through broken window, long shadows, dusty floor, story: {text}",
        f"Porcelain doll perched at top of dark wooden staircase, single lamp below casting eerie upward light, peeling wallpaper, cobwebs, story: {text}",
        f"Creepy porcelain doll sitting at a rain-streaked window at night, backlit by cold blue moonlight, dark silhouette, story: {text}",
        f"Antique rocking chair with porcelain doll, motion blur suggesting recent movement, candlelight from fireplace, Victorian parlour, story: {text}",
        f"Three-quarter view of cracked porcelain doll, one eye reflecting candlelight one eye in shadow, dusty attic setting, cobwebs, story: {text}",
    ]

    dalle_prompt = (
        f"Hyper-realistic horror movie poster art, cinematic photography style, 8K quality. "
        f"SCENE: {random.choice(scenes)}. "
        f"COLOR PALETTE: Deep sepia and black base, warm amber candlelight, cold blue moonlight. "
        f"STYLE: Film grain texture, heavy vignette corners, atmospheric fog, dust particles. "
        f"MOOD: Suffocating dread, uncanny valley, something deeply wrong. "
        f"ABSOLUTELY NO: text, watermarks, modern objects, bright colors, people's faces, nature landscapes, icicles."
    )

    print(f"  [thumb] Generating story-specific horror thumbnail...")
    bg_img = _get_background(dalle_prompt, "creepy doll Victorian dark room candle", bg_path, quality="high")

    if bg_img:
        img = _apply_horror_grading(bg_img)
    else:
        img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (8, 0, 0))

    draw = ImageDraw.Draw(img)

    # subtle watermark only
    font_small = _load_font(26)
    watermark = "💀 Chucky's Untold Stories"
    bbox = draw.textbbox((0, 0), watermark, font=font_small)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = THUMB_WIDTH - w - 15
    y = THUMB_HEIGHT - h - 15
    padding = 5
    draw.rectangle([x - padding, y - padding, x + w + padding, y + h + padding], fill=(0, 0, 0, 140))
    draw.text((x, y), watermark, font=font_small, fill=(160, 160, 160))

    try:
        if os.path.exists(bg_path):
            os.remove(bg_path)
    except Exception:
        pass

    os.makedirs(Path(output_path).parent, exist_ok=True)
    img.save(output_path, "JPEG", quality=97)
    print(f"  [thumb] Horror fiction thumbnail saved: {Path(output_path).name}")
    return output_path


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_thumbnail(
    channel: ChannelConfig,
    thumbnail_text: str,
    output_path: str,
    bg_query: Optional[str] = None,
    story_hook: str = "",
    **kwargs,
) -> str:
    """Route to the correct thumbnail style for the channel."""
    if channel.thumbnail_style == "food":
        return generate_food_thumbnail(channel, thumbnail_text, output_path, bg_query)
    elif channel.thumbnail_style == "dark_history":
        return generate_dark_history_thumbnail(channel, thumbnail_text, output_path, bg_query)
    elif channel.thumbnail_style == "horror_fiction":
        return generate_horror_fiction_thumbnail(channel, thumbnail_text, output_path, bg_query, story_hook)
    else:
        return generate_finance_thumbnail(channel, thumbnail_text, output_path, bg_query, **kwargs)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    from config import CHANNEL_A, CHANNEL_B

    # test finance (VidIQ → Pillow fallback)
    generate_thumbnail(CHANNEL_A, "AI RISK? BIG REWARD?", "temp/thumb_finance_test.jpg", "AI investing")
    print("Finance: temp/thumb_finance_test.jpg")

    # test horror
    generate_thumbnail(CHANNEL_B, "The Cursed Doll", "temp/thumb_horror_test.jpg",
                      story_hook="A doll that moves on its own.")
    print("Horror: temp/thumb_horror_test.jpg")

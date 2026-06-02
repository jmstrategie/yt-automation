"""
modules/thumbnail.py
Generates YouTube thumbnails using Pillow + DALL-E 3 backgrounds.
Supports four styles: finance, food, dark_history, horror_fiction.
Horror fiction uses story-specific DALL-E HD prompts with cinematic grading.
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


def _generate_dalle_background(prompt: str, output_path: str, quality: str = "standard") -> Optional[str]:
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
        # gpt-image-1 returns base64, not URL
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


def _get_background(dalle_prompt: str, pexels_query: str, bg_path: str, quality: str = "standard") -> Optional[Image.Image]:
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
    """Apply smooth radial vignette — darkens corners dramatically."""
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
    """Cinematic horror color grading: desaturate, contrast boost, darken, vignette."""
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
    accent = _hex_to_rgb(channel.primary_color)
    bg_path = output_path.replace(".jpg", "_bg.jpg")

    dalle_prompt = (
        f"Cinematic wide shot for a YouTube finance thumbnail, "
        f"dark moody atmosphere, professional financial theme, "
        f"{'about ' + bg_query if bg_query else 'stock market and technology'}, "
        f"dramatic lighting, deep blue and dark tones, 4K quality, "
        f"no text, no people's faces, photorealistic"
    )

    bg_img = _get_background(dalle_prompt, bg_query or "finance technology", bg_path)

    if bg_img:
        img = ImageEnhance.Brightness(bg_img).enhance(0.45)
        img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
    else:
        img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (10, 12, 28))

    draw = ImageDraw.Draw(img)
    draw.rectangle([(45, 70), (59, THUMB_HEIGHT - 70)], fill=(*accent, 255))

    lines = textwrap.wrap(text.upper(), width=13)[:3]
    font_large = _load_font(100)
    font_small = _load_font(44)

    y = 100
    for line in lines:
        y = _draw_text_with_shadow(draw, line, (80, y), font_large) + 18

    bar_height = 80
    draw.rectangle([(0, THUMB_HEIGHT - bar_height), (THUMB_WIDTH, THUMB_HEIGHT)], fill=(*accent, 210))
    draw.text((45, THUMB_HEIGHT - bar_height + 22), f"🐋 {channel.name.upper()}", font=font_small, fill=(255, 255, 255))

    try:
        if os.path.exists(bg_path):
            os.remove(bg_path)
    except Exception:
        pass

    os.makedirs(Path(output_path).parent, exist_ok=True)
    img.save(output_path, "JPEG", quality=95)
    print(f"  [thumb] Finance thumbnail saved: {Path(output_path).name}")
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
        y = _draw_text_with_shadow(draw, line, (45, y), font_large, fill=(255, 255, 255), shadow_color=(*accent, 255), shadow_offset=3) + 12

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
        y = _draw_text_with_shadow(draw, line, (80, y), font_large, fill=(255, 255, 255), shadow_color=(*accent, 255), shadow_offset=4) + 16

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


# ── Horror Fiction thumbnail (Chucky's Untold Stories style) ───────────────────

def generate_horror_fiction_thumbnail(
    channel: ChannelConfig,
    text: str,
    output_path: str,
    bg_query: Optional[str] = None,
    story_hook: str = "",
    **kwargs,
) -> str:
    """
    Matches the Chucky's Untold Stories visual style exactly:
    - Pure cinematic AI art — NO text overlay
    - Creepy porcelain doll as centerpiece
    - Victorian/abandoned interior, single candle or moonlight
    - Deep sepia/black palette with amber candlelight
    - Heavy vignette, film grain, desaturated horror grading
    - Only a small subtle watermark in the corner
    Uses HD DALL-E 3 for maximum quality.
    """
    bg_path = output_path.replace(".jpg", "_bg.jpg")

    # build story-specific scene from title and hook
    scene_context = bg_query or "Victorian room rocking chair"
    hook_excerpt = story_hook[:150] if story_hook else text

    import random

    # randomize scene type for visual variety across videos
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
        # apply cinematic horror grading
        img = _apply_horror_grading(bg_img)
    else:
        # fallback: pure black with subtle red gradient
        img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (8, 0, 0))

    draw = ImageDraw.Draw(img)

    # subtle watermark only — bottom right, semi-transparent
    font_small = _load_font(26)
    watermark = "💀 Chucky's Untold Stories"
    bbox = draw.textbbox((0, 0), watermark, font=font_small)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = THUMB_WIDTH - w - 15
    y = THUMB_HEIGHT - h - 15

    # dark pill background for watermark
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
) -> str:
    """Route to the correct thumbnail style for the channel."""
    if channel.thumbnail_style == "food":
        return generate_food_thumbnail(channel, thumbnail_text, output_path, bg_query)
    elif channel.thumbnail_style == "dark_history":
        return generate_dark_history_thumbnail(channel, thumbnail_text, output_path, bg_query)
    elif channel.thumbnail_style == "horror_fiction":
        return generate_horror_fiction_thumbnail(channel, thumbnail_text, output_path, bg_query, story_hook)
    else:
        return generate_finance_thumbnail(channel, thumbnail_text, output_path, bg_query)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    from config import CHANNEL_A, CHANNEL_B

    # test finance
    generate_thumbnail(CHANNEL_A, "EVERY DOLLAR GETS A JOB", "temp/thumb_finance_test.jpg", "budgeting money")
    print("Finance thumbnail: temp/thumb_finance_test.jpg")

    # test horror
    generate_thumbnail(
        CHANNEL_B,
        "The Doll That Blinks When You Look Away",
        "temp/thumb_horror_test.jpg",
        "rocking chair dark Victorian room",
        story_hook="On March 14th, 2019, at exactly 3:47 in the morning, I woke to find the doll sitting upright on my dresser.",
    )
    print("Horror thumbnail: temp/thumb_horror_test.jpg")

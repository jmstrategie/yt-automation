"""
Horror Fiction Thumbnail Generator — Standalone module
Generates cinematic horror thumbnails matching the Chucky's Untold Stories style:
- Pure AI art, no text overlay
- Creepy doll as centerpiece
- Victorian/abandoned interior settings
- Dramatic single-source lighting
- Heavy vignette, desaturated palette
- Small watermark only
"""

import os
import requests
import textwrap
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps


FONT_PATH = "assets/fonts/Roboto-Bold.ttf"


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def _generate_story_thumbnail(
    story_title: str,
    story_hook: str,
    output_path: str,
    openai_api_key: str,
) -> Optional[str]:
    """
    Generate a hyper-specific horror thumbnail based on the actual story content.
    Extracts the key horror element from the title/hook and builds a cinematic scene around it.
    """
    from openai import OpenAI
    client = OpenAI(api_key=openai_api_key)

    # extract the core horror element for the scene
    horror_element = story_title.lower()

    # build a highly specific DALL-E prompt
    dalle_prompt = f"""Hyper-realistic horror movie poster art, cinematic photography style.

SCENE: A porcelain doll with cracked pale face, glass eyes catching candlelight, positioned in a Victorian interior.
The doll relates to: {story_title}

COMPOSITION:
- Extreme close-up OR dramatic three-quarter view of the doll
- Doll positioned slightly off-center, eyes facing viewer directly
- Setting: dark Victorian room, dusty wooden floor, aged wallpaper with faded floral pattern
- Single light source: one flickering candle OR moonlight through a broken window casting long shadows
- Foreground: out-of-focus dust particles, cobwebs in corners

COLOR PALETTE:
- Deep sepia and black as base
- Warm amber/orange from candlelight on doll's face
- Cold blue-grey moonlight from background window
- Heavy vignette darkening all four corners
- Slight film grain texture overlay

QUALITY: 8K photorealistic, cinematic depth of field, horror movie production quality
ABSOLUTELY NO: text, watermarks, logos, people's faces, modern objects, bright colors
MOOD: suffocating dread, uncanny valley, something is deeply wrong"""

    print(f"  [thumb] DALL-E 3 generating story-specific horror thumbnail...")

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=dalle_prompt,
            size="1792x1024",
            quality="hd",  # use HD for thumbnails
            n=1,
        )
        img_url = response.data[0].url
        r = requests.get(img_url, timeout=30)
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img = img.resize((1280, 720), Image.LANCZOS)

        # post-processing to enhance horror aesthetic
        img = _apply_horror_grading(img)

        # add minimal watermark only
        img = _add_watermark(img)

        os.makedirs(Path(output_path).parent, exist_ok=True)
        img.save(output_path, "JPEG", quality=97)
        print(f"  [thumb] Horror thumbnail saved: {Path(output_path).name}")
        return output_path

    except Exception as e:
        print(f"  [thumb] DALL-E error: {e}")
        return None


def _apply_horror_grading(img: Image.Image) -> Image.Image:
    """Apply cinematic horror color grading to the image."""

    # 1. Slight desaturation — not black and white, but muted
    from PIL import ImageEnhance
    img = ImageEnhance.Color(img).enhance(0.7)

    # 2. Increase contrast for dramatic look
    img = ImageEnhance.Contrast(img).enhance(1.3)

    # 3. Slightly darken overall
    img = ImageEnhance.Brightness(img).enhance(0.85)

    # 4. Heavy vignette effect
    img = _apply_vignette(img, strength=0.75)

    return img


def _apply_vignette(img: Image.Image, strength: float = 0.7) -> Image.Image:
    """Apply a smooth radial vignette effect."""
    import math

    width, height = img.size
    vignette = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(vignette)

    # create smooth radial gradient
    cx, cy = width // 2, height // 2
    max_dist = math.sqrt(cx**2 + cy**2)

    pixels = vignette.load()
    for y in range(height):
        for x in range(width):
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            normalized = dist / max_dist
            # smooth falloff — darkens corners more aggressively
            factor = max(0, 1 - (normalized * strength * 1.4)**1.5)
            pixels[x, y] = int(255 * factor)

    # apply vignette as multiply blend
    img_array = img.convert("RGB")
    vignette_rgb = Image.merge("RGB", [vignette, vignette, vignette])

    result = Image.new("RGB", img.size)
    for i, (ip, vp) in enumerate(zip(img_array.getdata(), vignette_rgb.getdata())):
        r = int(ip[0] * vp[0] / 255)
        g = int(ip[1] * vp[1] / 255)
        b = int(ip[2] * vp[2] / 255)
        result.putpixel((i % width, i // width), (r, g, b))

    return result


def _add_watermark(img: Image.Image) -> Image.Image:
    """Add a subtle channel watermark in the bottom right corner only."""
    draw = ImageDraw.Draw(img)
    font = _load_font(24)

    watermark = "💀 Chucky's Untold Stories"
    bbox = draw.textbbox((0, 0), watermark, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    x = img.width - w - 15
    y = img.height - h - 15

    # semi-transparent dark background pill
    padding = 6
    draw.rectangle(
        [x - padding, y - padding, x + w + padding, y + h + padding],
        fill=(0, 0, 0, 120)
    )
    draw.text((x, y), watermark, font=font, fill=(180, 180, 180))

    return img


def _fallback_horror_thumbnail(
    channel,
    text: str,
    output_path: str,
) -> str:
    """Solid color fallback if DALL-E fails."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1280, 720), (8, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_font(80)

    lines = textwrap.wrap(text.upper(), width=14)[:3]
    y = 200
    for line in lines:
        draw.text((80, y), line, font=font, fill=(200, 200, 200))
        bbox = draw.textbbox((80, y), line, font=font)
        y = bbox[3] + 20

    os.makedirs(Path(output_path).parent, exist_ok=True)
    img.save(output_path, "JPEG", quality=95)
    return output_path


def generate_horror_fiction_thumbnail(
    channel,
    thumbnail_text: str,
    output_path: str,
    bg_query: Optional[str] = None,
    story_hook: str = "",
) -> str:
    """
    Main entry point for horror fiction thumbnails.
    Uses story title and hook to generate a scene-specific cinematic image.
    """
    from config import OPENAI_API_KEY

    if OPENAI_API_KEY:
        result = _generate_story_thumbnail(
            story_title=thumbnail_text,
            story_hook=story_hook[:200] if story_hook else thumbnail_text,
            output_path=output_path,
            openai_api_key=OPENAI_API_KEY,
        )
        if result:
            return result

    print(f"  [thumb] Using fallback horror thumbnail")
    return _fallback_horror_thumbnail(channel, thumbnail_text, output_path)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    from config import CHANNEL_B

    result = generate_horror_fiction_thumbnail(
        channel=CHANNEL_B,
        thumbnail_text="The Doll That Blinks When You Look Away",
        output_path="temp/thumb_horror_test.jpg",
        story_hook="On March 14th, 2019, at exactly 3:47 in the morning, I woke to find the doll sitting upright on my dresser.",
    )
    print(f"Saved: {result}")
    print("Open temp/thumb_horror_test.jpg to review")

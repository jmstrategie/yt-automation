"""
modules/thumbnail_vidiq.py
VidIQ-powered thumbnail generation for Channel A (Wealth Whale).
Uses VidIQ MCP through Anthropic API to generate professional finance thumbnails.
Refine loop commented out — enable after first 3 videos.
"""

import os
import re
import requests
from pathlib import Path
from typing import Optional


def download_thumbnail_from_url(url: str, output_path: str) -> Optional[str]:
    """Download a thumbnail from URL to local disk."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        os.makedirs(Path(output_path).parent, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(r.content)
        size_kb = os.path.getsize(output_path) // 1024
        print(f"  [thumb] Downloaded VidIQ thumbnail ({size_kb}KB)")
        return output_path
    except Exception as e:
        print(f"  [thumb] Download error: {e}")
        return None


def generate_via_anthropic_mcp(
    title: str,
    thumbnail_text: str,
    output_path: str,
) -> Optional[str]:
    """
    Generate thumbnail by calling VidIQ MCP through Anthropic API.
    VidIQ uses MCP not REST — this is the correct integration approach.
    """
    import anthropic
    from config import ANTHROPIC_API_KEY

    # smart text split for left/right panels
    words = thumbnail_text.upper().split()
    mid = len(words) // 2
    left_text = " ".join(words[:mid]) if mid > 0 else thumbnail_text.upper()
    right_text = " ".join(words[mid:]) if len(words) > 1 else ""

    # natural split at ? or :
    if "?" in thumbnail_text.upper():
        parts = thumbnail_text.upper().split("?", 1)
        left_text = parts[0].strip() + "?"
        right_text = parts[1].strip() if parts[1].strip() else right_text
    elif ":" in thumbnail_text.upper():
        parts = thumbnail_text.upper().split(":", 1)
        left_text = parts[0].strip()
        right_text = parts[1].strip() if parts[1].strip() else right_text

    user_query = (
        f"Vertical split thumbnail. "
        f"Left panel dark red background with bold white text '{left_text}' and red down arrow and bearish stock chart. "
        f"Center panel: smartphone showing investment portfolio app with green performance chart. "
        f"Right panel dark green background with bold white text '{right_text}' and green up arrow and gold bull statue. "
        f"Professional dramatic finance YouTube aesthetic. High contrast. No branding or watermarks."
    )

    print(f"  [thumb] Generating via Anthropic+VidIQ MCP...")

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            mcp_servers=[{
                "type": "url",
                "url": "https://mcp.vidiq.com/mcp",
                "name": "vidiq",
            }],
            messages=[{
                "role": "user",
                "content": (
                    f"Use the vidiq_generate_thumbnail tool to generate a YouTube thumbnail. "
                    f"Parameters: title='{title}', userQuery='{user_query}'. "
                    f"Return ONLY the imageUrl value from the response, nothing else."
                )
            }],
        )

        # extract image URL from all response blocks
        for block in response.content:
            text_content = ""
            if hasattr(block, "text") and block.text:
                text_content = block.text
            elif hasattr(block, "content"):
                text_content = str(block.content)

            if text_content:
                urls = re.findall(
                    r'https://[^\s\'"<>\)]+\.(?:png|jpg|jpeg)',
                    text_content
                )
                if urls:
                    print(f"  [thumb] VidIQ image URL found")
                    return download_thumbnail_from_url(urls[0], output_path)

    except Exception as e:
        print(f"  [thumb] Anthropic+VidIQ error: {e}")

    return None


# ── Score + Refine (COMMENTED OUT — enable after first 3 videos) ──────────────

# def score_and_refine(
#     thumbnail_url: str,
#     title: str,
#     output_path: str,
#     score_threshold: int = 55,
# ) -> Optional[str]:
#     """
#     Score a VidIQ thumbnail and refine if score < threshold.
#     Cost: 5 credits to score + 22 to refine = 27 credits max.
#     Enable after reviewing first 3 videos.
#
#     To enable:
#     1. Uncomment this function
#     2. In generate_finance_thumbnail_vidiq(), uncomment the score_and_refine call
#     """
#     import anthropic
#     from config import ANTHROPIC_API_KEY
#
#     client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
#
#     # Step 1: Score
#     score_response = client.messages.create(
#         model="claude-sonnet-4-5",
#         max_tokens=300,
#         mcp_servers=[{"type": "url", "url": "https://mcp.vidiq.com/mcp", "name": "vidiq"}],
#         messages=[{"role": "user", "content":
#             f"Use vidiq_score_thumbnail. videoId='', title='{title}', image='{thumbnail_url}'. "
#             f"Return only the score number."
#         }],
#     )
#     score = 0
#     for block in score_response.content:
#         if hasattr(block, "text"):
#             numbers = re.findall(r'\b(\d{1,3})\b', block.text)
#             if numbers:
#                 score = int(numbers[0])
#                 break
#
#     print(f"  [thumb] VidIQ score: {score}/100")
#
#     if score >= score_threshold:
#         return download_thumbnail_from_url(thumbnail_url, output_path)
#
#     # Step 2: Refine if score too low
#     print(f"  [thumb] Score {score} < {score_threshold} — refining...")
#     refine_response = client.messages.create(
#         model="claude-sonnet-4-5",
#         max_tokens=300,
#         mcp_servers=[{"type": "url", "url": "https://mcp.vidiq.com/mcp", "name": "vidiq"}],
#         messages=[{"role": "user", "content":
#             f"Use vidiq_refine_thumbnail. sourceThumbnail='{thumbnail_url}', "
#             f"instructions='Make text larger and bolder. Sharpen red/green split. "
#             f"Add directional arrow center. Increase contrast.', "
#             f"originalConcept='Finance vertical split thumbnail for: {title}'. "
#             f"Return only the imageUrl."
#         }],
#     )
#     for block in refine_response.content:
#         if hasattr(block, "text") and block.text:
#             urls = re.findall(r'https://[^\s\'"<>\)]+\.(?:png|jpg|jpeg)', block.text)
#             if urls:
#                 print(f"  [thumb] Refined thumbnail ready")
#                 return download_thumbnail_from_url(urls[0], output_path)
#
#     return download_thumbnail_from_url(thumbnail_url, output_path)


def generate_finance_thumbnail_vidiq(
    title: str,
    thumbnail_text: str,
    output_path: str,
) -> Optional[str]:
    """
    Main entry: generate VidIQ thumbnail for finance channel.
    Score + refine loop disabled — enable after first 3 videos.
    """
    result = generate_via_anthropic_mcp(title, thumbnail_text, output_path)

    # ── Enable after first 3 videos ──────────────────────────────────────────
    # if result:
    #     refined = score_and_refine(result_url, title, output_path)
    #     return refined or result

    return result


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    result = generate_finance_thumbnail_vidiq(
        title="How AI Saves Me $500/Month (Frugal Living in 2026)",
        thumbnail_text="AI SAVES $500/MONTH",
        output_path="temp/thumb_vidiq_test.jpg",
    )
    print(f"Result: {result}")
    if result:
        print("Open temp/thumb_vidiq_test.jpg to review")

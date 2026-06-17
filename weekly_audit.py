"""
weekly_audit.py
Runs every Sunday via GitHub Actions.
Pulls VidIQ keyword data for both channels and updates the VIDIQ_KEYWORDS
dict in modules/trends.py automatically based on fresh search volume + competition data.

This closes the loop: VidIQ data -> keyword file -> next week's topic selection.
"""

import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def update_keywords_file(niche: str, keywords: list):
    """
    Update the VIDIQ_KEYWORDS dict in modules/trends.py for a given niche.
    keywords: list of (keyword, monthly_search, competition) tuples
    """
    trends_path = "modules/trends.py"

    with open(trends_path, "r") as f:
        content = f.read()

    # build new keyword block
    lines = [f'    "{niche}": [']
    for kw, vol, comp in keywords:
        lines.append(f'        ("{kw}", {int(vol)}, {int(comp)}),')
    lines.append("    ],")
    new_block = "\n".join(lines)

    # find and replace the existing block for this niche
    pattern = rf'    "{niche}": \[.*?\n    \],'
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, new_block, content, flags=re.DOTALL)
        print(f"  Updated existing '{niche}' keyword block")
    else:
        # insert before the closing brace of VIDIQ_KEYWORDS dict
        insertion_point = content.find("}\n\n\ndef fetch_rss_headlines")
        if insertion_point == -1:
            insertion_point = content.find("def fetch_rss_headlines")
        content = content[:insertion_point] + new_block + "\n" + content[insertion_point:]
        print(f"  Added new '{niche}' keyword block")

    with open(trends_path, "w") as f:
        f.write(content)


def get_finance_keywords():
    """
    Returns updated finance keyword data.
    In production this calls VidIQ via the Anthropic MCP connection.
    For now, uses the latest known-good data from manual research.
    Update this function's return value each week based on /youtube audit + VidIQ findings.
    """
    return [
        ("budgeting", 183312, 20),
        ("budgeting for beginners", 142756, 34),
        ("personal finance apps", 12531, 17),
        ("best money management apps", 4606, 15),
        ("budgeting apps for beginners", 5056, 26),
        ("monarch money review", 38804, 29),
        ("how to budget", 50361, 49),
        ("personal finance", 1516126, 53),
        ("save money", 105667, 48),
        ("rocket money", 19673, 38),
        ("copilot money review", 3302, 30),
        ("best budgeting app", 16306, 35),
    ]


def get_horror_keywords():
    """
    Returns updated horror fiction keyword data.
    Update weekly based on VidIQ research.
    """
    return [
        ("horror stories", 1872291, 71),
        ("scary stories", 715473, 72),
        ("true horror stories", 362030, 70),
        ("paranormal investigation", 74718, 47),
        ("robert the doll", 50361, 41),
        ("haunted doll", 7661, 58),
        ("ghost hunting", 185659, 61),
        ("haunted", 188001, 61),
        ("cursed doll", 5000, 35),
        ("creepy story", 300000, 38),
    ]


def run_weekly_audit():
    """Main weekly audit routine."""
    print(f"\n{'='*60}")
    print(f"WEEKLY AUDIT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    print("📊 Updating Channel A (Wealth Whale) keywords...")
    finance_kw = get_finance_keywords()
    update_keywords_file("personal_finance_ai", finance_kw)

    print("\n💀 Updating Channel B (Chucky's) keywords...")
    horror_kw = get_horror_keywords()
    update_keywords_file("horror_fiction", horror_kw)

    # log the run
    log_entry = {
        "date": datetime.now().isoformat(),
        "finance_keywords_count": len(finance_kw),
        "horror_keywords_count": len(horror_kw),
        "top_finance_opportunity": min(finance_kw, key=lambda x: x[2])[0],
        "top_horror_opportunity": min(horror_kw, key=lambda x: x[2])[0],
    }

    os.makedirs("output", exist_ok=True)
    log_path = "output/weekly_audit_log.json"
    history = []
    if os.path.exists(log_path):
        with open(log_path) as f:
            history = json.load(f)
    history.append(log_entry)
    with open(log_path, "w") as f:
        json.dump(history[-12:], f, indent=2)  # keep last 12 weeks

    print(f"\n✅ Weekly audit complete")
    print(f"   Top finance opportunity: {log_entry['top_finance_opportunity']}")
    print(f"   Top horror opportunity: {log_entry['top_horror_opportunity']}")
    print(f"\nNext: commit and push modules/trends.py changes")


if __name__ == "__main__":
    run_weekly_audit()

#!/usr/bin/env python3
"""
setup.py — first-time setup wizard.
Run this once before your first pipeline run.
"""

import os
import sys
import subprocess
import urllib.request
from pathlib import Path


def check(label, cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    ok = result.returncode == 0
    print(f"  {'✓' if ok else '✗'} {label}")
    if not ok:
        print(f"    → {result.stderr.strip()[:100]}")
    return ok


def download_fonts():
    os.makedirs("assets/fonts", exist_ok=True)
    fonts = {
        "Roboto-Bold.ttf": "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf",
        "Roboto-Regular.ttf": "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf",
    }
    for name, url in fonts.items():
        path = f"assets/fonts/{name}"
        if not os.path.exists(path):
            print(f"  Downloading {name}...")
            urllib.request.urlretrieve(url, path)
            print(f"  ✓ {name}")
        else:
            print(f"  ✓ {name} (already exists)")


def create_env():
    if os.path.exists(".env"):
        print("  ✓ .env already exists")
        return
    with open(".env.example") as f:
        template = f.read()
    with open(".env", "w") as f:
        f.write(template)
    print("  ✓ Created .env — open it and add your API keys")


def check_secrets():
    os.makedirs("secrets", exist_ok=True)
    for name in ["client_secrets_channelA.json", "client_secrets_channelB.json"]:
        path = f"secrets/{name}"
        if os.path.exists(path):
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name} — download from Google Cloud Console and place in secrets/")


def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


print("\n🔧 YouTube Automation Setup\n")

print("1. Checking system dependencies...")
check("Python 3.9+", ["python3", "--version"])
check("FFmpeg", ["ffmpeg", "-version"])
check("Git", ["git", "--version"])

print("\n2. Installing Python packages...")
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"])
print("  ✓ Packages installed")

print("\n3. Downloading fonts...")
download_fonts()

print("\n4. Creating .env file...")
create_env()

print("\n5. Checking secrets folder...")
check_secrets()

print("\n6. Loading environment...")
load_env()

print("\n7. Testing Anthropic API key...")
api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if api_key.startswith("sk-ant-"):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{"role": "user", "content": "Say OK"}]
        )
        print(f"  ✓ API key works — response: {resp.content[0].text.strip()}")
    except Exception as e:
        print(f"  ✗ API key error: {e}")
else:
    print("  ✗ ANTHROPIC_API_KEY not set — edit .env first")

print("\n" + "="*50)
print("Setup complete!")
print("\nNext steps:")
print("  1. Edit .env and add your ANTHROPIC_API_KEY")
print("  2. Place client_secrets_channelA.json in secrets/")
print("  3. Get a free Pexels API key at pexels.com/api and add to .env")
print("  4. Test the pipeline:")
print("     python pipeline.py --channel A --dry-run")
print("  5. First real run (triggers YouTube OAuth in browser):")
print("     python pipeline.py --channel A")
print("="*50 + "\n")

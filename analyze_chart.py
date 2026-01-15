#!/usr/bin/env python3
"""
ICT Chart Analyzer - Vision-Based Trading Analysis

Simply screenshot your chart and this tool will analyze it for ICT setups.

Usage:
    python analyze_chart.py path/to/chart.png
    python analyze_chart.py --watch ~/Desktop  # Watch folder for new screenshots
"""

import argparse
import base64
import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Try OpenAI first, fall back to Anthropic
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


ICT_ANALYSIS_PROMPT = """You are an expert ICT (Inner Circle Trader) analyst. Analyze this trading chart and identify:

## MARKET STRUCTURE
- Current trend direction (bullish/bearish/ranging)
- Recent Break of Structure (BOS) or Change of Character (ChoCH)
- Higher highs/higher lows OR lower highs/lower lows

## KEY LEVELS (mark approximate prices if visible)
- Swing highs and swing lows
- Equal highs/lows (liquidity pools)
- Previous day/week/month highs and lows if identifiable

## ICT CONCEPTS PRESENT
- Fair Value Gaps (FVG) - unfilled gaps between candles
- Order Blocks (OB) - last opposite candle before a move
- Breaker Blocks - failed order blocks
- Liquidity sweeps - wicks taking out obvious levels
- Premium/Discount zones relative to recent range

## CURRENT SETUP ASSESSMENT
Based on what you see, is there a valid ICT trade setup RIGHT NOW?

If YES, provide:
- Direction: LONG or SHORT
- Entry zone: price area or description
- Stop loss: where to place it
- Target: first take-profit level
- Confluence score: 1-10 (how many ICT concepts align)
- Confidence: LOW / MEDIUM / HIGH

If NO valid setup:
- Explain what's missing
- What would you need to see for a trade

## MODELS TO CHECK
- Silver Bullet (10:00-11:00 or 14:00-15:00 NY time setups)
- Judas Swing (fake move at session open)
- OTE Retracement (entry at 62-79% fib of impulse)
- Power of Three (accumulation → manipulation → distribution)

Be specific about what you SEE in this chart. Reference candle patterns, price levels, and time if visible."""


def encode_image(image_path: str) -> str:
    """Encode image to base64 for API."""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def get_image_media_type(path: str) -> str:
    """Determine image media type from extension."""
    ext = Path(path).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/png")


def analyze_with_openai(image_path: str, api_key: str) -> str:
    """Analyze chart using OpenAI GPT-4 Vision."""
    client = OpenAI(api_key=api_key)
    
    base64_image = encode_image(image_path)
    media_type = get_image_media_type(image_path)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ICT_ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
        max_tokens=2000,
    )
    
    return response.choices[0].message.content


def analyze_with_anthropic(image_path: str, api_key: str) -> str:
    """Analyze chart using Claude Vision."""
    client = anthropic.Anthropic(api_key=api_key)
    
    base64_image = encode_image(image_path)
    media_type = get_image_media_type(image_path)
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_image,
                        },
                    },
                    {"type": "text", "text": ICT_ANALYSIS_PROMPT},
                ],
            }
        ],
    )
    
    return response.content[0].text


def analyze_chart(image_path: str) -> str:
    """Analyze a chart image for ICT setups."""
    path = Path(image_path)
    if not path.exists():
        return f"Error: File not found: {image_path}"
    
    if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        return f"Error: Unsupported image format: {path.suffix}"
    
    # Check for API keys
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if openai_key and HAS_OPENAI:
        print("Using OpenAI GPT-4o for analysis...")
        return analyze_with_openai(image_path, openai_key)
    elif anthropic_key and HAS_ANTHROPIC:
        print("Using Claude for analysis...")
        return analyze_with_anthropic(image_path, anthropic_key)
    else:
        return """Error: No AI API key found.

Set one of these environment variables:
    export OPENAI_API_KEY="sk-..."
    export ANTHROPIC_API_KEY="sk-ant-..."

Then install the corresponding package:
    pip install openai
    pip install anthropic
"""


def watch_folder(folder: str, interval: float = 2.0):
    """Watch a folder for new chart images and analyze them."""
    folder = Path(folder)
    if not folder.is_dir():
        print(f"Error: Not a directory: {folder}")
        return
    
    print(f"Watching {folder} for new chart images...")
    print("Take a screenshot and save it there. Press Ctrl+C to stop.\n")
    
    seen = set(f.name for f in folder.glob("*") if f.is_file())
    
    try:
        while True:
            time.sleep(interval)
            current = set(f.name for f in folder.glob("*") if f.is_file())
            new_files = current - seen
            
            for name in new_files:
                path = folder / name
                if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                    print(f"\n{'='*60}")
                    print(f"New chart detected: {name}")
                    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print("="*60 + "\n")
                    
                    result = analyze_chart(str(path))
                    print(result)
                    print("\n" + "="*60 + "\n")
            
            seen = current
    except KeyboardInterrupt:
        print("\nStopped watching.")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze trading charts for ICT setups using AI vision"
    )
    parser.add_argument(
        "image",
        nargs="?",
        help="Path to chart image (PNG, JPG, etc.)",
    )
    parser.add_argument(
        "--watch",
        metavar="FOLDER",
        help="Watch a folder for new screenshots and analyze them",
    )
    
    args = parser.parse_args()
    
    if args.watch:
        watch_folder(args.watch)
    elif args.image:
        print(f"Analyzing: {args.image}\n")
        result = analyze_chart(args.image)
        print(result)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python analyze_chart.py ~/Desktop/chart.png")
        print("  python analyze_chart.py --watch ~/Desktop")


if __name__ == "__main__":
    main()

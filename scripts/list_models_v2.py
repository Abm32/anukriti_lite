#!/usr/bin/env python3
"""
Query the actual list of available models from the API
"""

import os
import sys

# Load API key
api_key = None
try:
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("GOOGLE_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
            elif line.startswith("GEMINI_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
except FileNotFoundError:
    pass

if not api_key:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GOOGLE_API_KEY or GEMINI_API_KEY not set")
    sys.exit(1)

print("=" * 80)
print("Querying Available Models from API:")
print("=" * 80)
print(f"API Key: {api_key[:10]}...{api_key[-4:]}\n")

try:
    from google import genai

    client = genai.Client(api_key=api_key)

    print("Fetching models list...\n")
    models = client.models.list()

    print(f"Found {len(models)} total models:\n")

    # Group by support for generateContent
    generate_content_models = []
    other_models = []

    for model in models:
        model_info = {
            "name": model.name,
            "display_name": getattr(model, "display_name", "N/A"),
            "description": getattr(model, "description", "N/A"),
        }

        # Check if it supports generateContent
        if hasattr(model, "supported_generation_methods"):
            if "generateContent" in model.supported_generation_methods:
                generate_content_models.append(model_info)
            else:
                other_models.append(model_info)
        else:
            other_models.append(model_info)

    if generate_content_models:
        print("=" * 80)
        print("MODELS SUPPORTING generateContent (USE THESE):")
        print("=" * 80)
        for model in generate_content_models:
            print(f"\n  ✓ {model['name']}")
            if model["display_name"] != "N/A":
                print(f"    Display: {model['display_name']}")
            if model["description"] != "N/A":
                print(f"    Description: {model['description'][:100]}...")

    if other_models:
        print("\n" + "=" * 80)
        print("OTHER MODELS (may not support generateContent):")
        print("=" * 80)
        for model in other_models[:10]:  # Show first 10
            print(f"  - {model['name']}")
        if len(other_models) > 10:
            print(f"  ... and {len(other_models) - 10} more")

    # Also try to get model names directly
    print("\n" + "=" * 80)
    print("MODEL NAMES (extracted):")
    print("=" * 80)
    model_names = [m.name for m in models]
    for name in sorted(model_names):
        print(f"  - {name}")

except ImportError:
    print("ERROR: google-genai package not installed")
    print("Install it with: pip install google-genai")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback

    traceback.print_exc()

    # Fallback: The 429 error suggests gemini-2.0-flash-exp might work
    print("\n" + "=" * 80)
    print("NOTE: gemini-2.0-flash-exp returned 429 (rate limit), not 404")
    print("This suggests it EXISTS but has quota issues.")
    print("Try using: gemini-2.0-flash-exp")
    print("=" * 80)

#!/usr/bin/env python3
"""
Quick script to test available Gemini models
"""

import os
import sys

# Try to load from .env file manually
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

# Fallback to environment variable
if not api_key:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GOOGLE_API_KEY or GEMINI_API_KEY not set")
    print("Please set it in .env file or environment variable")
    sys.exit(1)

print("=" * 80)
print("Testing Gemini Models:")
print("=" * 80)
print(f"API Key found: {api_key[:10]}...{api_key[-4:]}\n")

# Common model names to test (based on actual API results)
models_to_test = [
    "gemini-2.5-flash",  # Newest, fastest
    "gemini-2.5-pro",  # Newest, most capable
    "gemini-2.0-flash",  # Stable version
    "gemini-2.0-flash-exp",  # Experimental
    "gemini-2.0-flash-001",  # Versioned
]

try:
    from langchain_google_genai import ChatGoogleGenerativeAI

    print("Testing each model...\n")

    working_models = []
    failed_models = []

    for model_name in models_to_test:
        print(f"Testing: {model_name}...", end=" ")
        try:
            llm = ChatGoogleGenerativeAI(
                model=model_name, temperature=0.2, api_key=api_key
            )
            # Try a simple test
            response = llm.invoke("Say 'test'")
            if response:
                print("✓ WORKS")
                working_models.append(model_name)
            else:
                print("✗ No response")
                failed_models.append((model_name, "No response"))
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "NOT_FOUND" in error_msg:
                print("✗ NOT FOUND")
                failed_models.append((model_name, "404 NOT_FOUND"))
            else:
                print(f"✗ ERROR: {error_msg[:50]}")
                failed_models.append((model_name, error_msg[:100]))

    print("\n" + "=" * 80)
    print("RESULTS:")
    print("=" * 80)

    if working_models:
        print("\n✓ WORKING MODELS (use these):")
        for model in working_models:
            print(f"  - {model}")
    else:
        print("\n✗ No working models found")

    if failed_models:
        print("\n✗ FAILED MODELS:")
        for model, error in failed_models:
            print(f"  - {model}: {error}")

except ImportError:
    print("ERROR: langchain-google-genai not installed")
    print("Install it with: pip install langchain-google-genai")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback

    traceback.print_exc()

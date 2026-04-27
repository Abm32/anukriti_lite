#!/usr/bin/env python3
"""
Smoke-test Amazon Nova Lite / Pro via Bedrock Converse (local dev).

Usage (from repo root, with conda env and .env loaded):

  python scripts/test_bedrock_nova.py

Requires: AWS credentials (env or ~/.aws/credentials), Bedrock model access
for Nova in BEDROCK_REGION, and boto3 installed.
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.chdir(_REPO_ROOT)

from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    try:
        import boto3
    except ImportError:
        print("ERROR: pip install boto3")
        return 1

    from src.config import config, resolve_nova_model_id
    from src.llm_bedrock import _extract_converse_output_text

    region = config.BEDROCK_REGION
    print(f"Region: {region}")
    print(f"NOVA_LITE_MODEL: {config.NOVA_LITE_MODEL}")
    print(f"NOVA_PRO_MODEL: {config.NOVA_PRO_MODEL}")
    print()

    client = boto3.client("bedrock-runtime", region_name=region)

    for label, variant in (("Nova Lite", "lite"), ("Nova Pro", "pro")):
        model_id = resolve_nova_model_id(variant)
        print(f"--- {label} ({model_id}) ---")
        try:
            resp = client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": "Reply with exactly: OK"}],
                    }
                ],
                inferenceConfig={"maxTokens": 64, "temperature": 0.0},
            )
            text = _extract_converse_output_text(resp)
            print(f"OK — model replied: {text[:200]!r}")
        except Exception as e:
            print(f"FAILED: {type(e).__name__}: {e}")
        print()

    print("Tip: enable Nova models in AWS Console → Bedrock → Model access.")
    print("Tip: wrong region or model ID → ValidationException or AccessDenied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

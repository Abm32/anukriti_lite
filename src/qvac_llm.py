"""
QVAC local LLM bridge for Anukriti.

The Python API keeps the deterministic PGx pipeline, retrieval, and Solana
attestations in-process. This module shells out to a tiny Node.js bridge that
uses @qvac/sdk for the optional local explanation model.
"""

import json
import subprocess  # nosec B404 - fixed argv, no shell
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import config
from src.exceptions import LLMError


def generate_pgx_response_qvac(
    context: str,
    query: str,
    pgx_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate a PGx explanation using the local QVAC JS SDK bridge.

    Raises:
        LLMError: if Node, the bridge, or @qvac/sdk is unavailable.
    """
    if not config.QVAC_ENABLED:
        raise LLMError("QVAC backend is disabled. Set QVAC_ENABLED=true.", model="qvac")

    script_path = Path(config.QVAC_SCRIPT_PATH)
    if not script_path.exists():
        raise LLMError(
            f"QVAC bridge script not found at {script_path}",
            model="qvac",
        )

    payload = {
        "context": context,
        "query": query,
        "pgx_data": pgx_data or None,
    }

    try:
        proc = subprocess.run(  # nosec B603 - fixed argv bridge, no shell
            [config.QVAC_NODE_BIN, str(script_path)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=config.QVAC_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise LLMError(
            "Node.js was not found. QVAC requires Node.js >=22.17 and npm >=10.9.",
            model="qvac",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise LLMError(
            f"QVAC local model timed out after {config.QVAC_TIMEOUT_SECONDS}s.",
            model="qvac",
        ) from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if "@qvac/sdk" in detail or "ERR_MODULE_NOT_FOUND" in detail:
            detail = (
                "QVAC SDK is not installed. Run `cd qvac && npm install` "
                "or `npm install @qvac/sdk` in the configured bridge workspace."
            )
        raise LLMError(f"QVAC bridge failed: {detail}", model="qvac")

    raw = proc.stdout.strip()
    if not raw:
        raise LLMError("QVAC bridge returned an empty response.", model="qvac")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if data.get("error"):
        raise LLMError(f"QVAC bridge failed: {data['error']}", model="qvac")

    text = str(data.get("text", "")).strip()
    if not text:
        raise LLMError("QVAC bridge returned no explanation text.", model="qvac")
    return text

"""Privacy-preserving Solana attestation helpers for trial exports."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess  # nosec B404 - optional fixed-argument Solana CLI wrapper
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping

ATTESTATION_SCHEMA_VERSION = "anukriti.trial_export_attestation.v1"
SIMULATION_ATTESTATION_SCHEMA_VERSION = "anukriti.simulation_result_attestation.v1"
SOLANA_MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
SOLANA_DEVNET_EXPLORER_BASE = "https://explorer.solana.com/tx"
SOLANA_DEVNET_RPC_URL = "https://api.devnet.solana.com"
SOLANA_MAINNET_RPC_URL = "https://api.mainnet-beta.solana.com"


def resolve_solana_rpc_url(network: str = "devnet", rpc_url: str | None = None) -> str:
    """
    Resolve the Solana RPC URL for proof submission/lookup.

    Set SOLANA_RPC_URL to a sponsor/provider endpoint such as Helius for reliable
    hackathon demos. The public devnet endpoint remains the fallback.
    """

    if rpc_url:
        return rpc_url
    configured = os.getenv("SOLANA_RPC_URL", "").strip()
    if configured:
        return configured
    if network == "mainnet-beta":
        return SOLANA_MAINNET_RPC_URL
    if network.startswith("http://") or network.startswith("https://"):
        return network
    return SOLANA_DEVNET_RPC_URL


def canonicalize_attestation_payload(payload: Mapping[str, Any]) -> str:
    """Return deterministic JSON for hashing while excluding attestation metadata."""

    sanitized = dict(payload)
    sanitized.pop("attestation", None)
    return json.dumps(
        sanitized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def hash_attestation_payload(payload: Mapping[str, Any]) -> str:
    """Compute a stable SHA-256 hash for any Anukriti proof payload."""

    canonical = canonicalize_attestation_payload(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hash_trial_export_payload(payload: Mapping[str, Any]) -> str:
    """Compute the stable SHA-256 hash for a trial export payload."""

    return hash_attestation_payload(payload)


def build_solana_memo(
    payload_hash: str, *, schema_version: str = ATTESTATION_SCHEMA_VERSION
) -> str:
    """Build the compact memo string intended for a Solana devnet transaction."""

    return f"anukriti:{schema_version}:{payload_hash}"


def build_anukriti_attestation(
    payload: Mapping[str, Any],
    *,
    schema_version: str,
    network: str = "devnet",
    generated_at: str | None = None,
    proof_status: str = "prepared_not_submitted",
    signature: str | None = None,
    privacy_model: str | None = None,
) -> Dict[str, Any]:
    """Create an off-chain Anukriti attestation artifact."""

    payload_hash = hash_attestation_payload(payload)
    memo = build_solana_memo(payload_hash, schema_version=schema_version)
    issued_at = generated_at or datetime.now(timezone.utc).isoformat()
    explorer_url = (
        f"{SOLANA_DEVNET_EXPLORER_BASE}/{signature}?cluster={network}"
        if signature
        else None
    )
    return {
        "schema_version": schema_version,
        "network": network,
        "hash_algorithm": "sha256",
        "payload_hash": payload_hash,
        "canonicalization": "json.dumps(sort_keys=True, separators=(',', ':')); attestation field excluded",
        "privacy_model": privacy_model
        or "Only the payload hash/memo is intended for Solana; sensitive Anukriti data remains off-chain.",
        "solana": {
            "cluster": network,
            "memo_program_id": SOLANA_MEMO_PROGRAM_ID,
            "memo": memo,
            "devnet_proof_status": proof_status,
            "signature": signature,
            "explorer_url": explorer_url,
            "submit_hint": (
                "Submit the memo with a devnet wallet transaction, then store the "
                "signature beside this attestation artifact."
            ),
        },
        "generated_at": issued_at,
    }


def build_trial_export_attestation(
    payload: Mapping[str, Any],
    *,
    network: str = "devnet",
    generated_at: str | None = None,
    proof_status: str = "prepared_not_submitted",
    signature: str | None = None,
) -> Dict[str, Any]:
    """
    Create an off-chain attestation artifact for a trial export.

    The full PGx export stays off-chain. Only this hash/memo should be anchored on
    Solana, preserving cohort privacy while making later tampering detectable.
    """

    return build_anukriti_attestation(
        payload,
        schema_version=ATTESTATION_SCHEMA_VERSION,
        network=network,
        generated_at=generated_at,
        proof_status=proof_status,
        signature=signature,
        privacy_model=(
            "Only the payload hash/memo is intended for Solana; sample-level PGx "
            "rows remain off-chain."
        ),
    )


def build_simulation_result_attestation(
    payload: Mapping[str, Any],
    *,
    network: str = "devnet",
    generated_at: str | None = None,
    proof_status: str = "prepared_not_submitted",
    signature: str | None = None,
) -> Dict[str, Any]:
    """
    Create an off-chain attestation artifact for a single simulation result.

    This proves the exact AI-engine output artifact without placing patient profile
    text, genetics, or explanation content directly on-chain.
    """

    return build_anukriti_attestation(
        payload,
        schema_version=SIMULATION_ATTESTATION_SCHEMA_VERSION,
        network=network,
        generated_at=generated_at,
        proof_status=proof_status,
        signature=signature,
        privacy_model=(
            "Only the simulation result hash/memo is intended for Solana; patient "
            "profile text, genetics, PGx output, and AI explanation remain off-chain."
        ),
    )


def verify_trial_export_attestation(
    payload: Mapping[str, Any], attestation: Mapping[str, Any]
) -> bool:
    """Return True when the attestation hash matches the export payload."""

    return bool(hash_attestation_payload(payload) == attestation.get("payload_hash"))


def verify_trial_export_attestation_detail(
    payload: Mapping[str, Any], attestation: Mapping[str, Any]
) -> Dict[str, Any]:
    """Return a structured verification result for UI and API consumers."""

    computed_hash = hash_trial_export_payload(payload)
    expected_hash = str(attestation.get("payload_hash", ""))
    memo = str((attestation.get("solana") or {}).get("memo", ""))
    memo_matches_hash = memo.endswith(expected_hash) if expected_hash else False
    valid = computed_hash == expected_hash and memo_matches_hash
    return {
        "valid": valid,
        "computed_hash": computed_hash,
        "expected_hash": expected_hash,
        "hash_matches": computed_hash == expected_hash,
        "memo_matches_hash": memo_matches_hash,
        "schema_version": attestation.get("schema_version"),
        "network": attestation.get("network"),
        "proof_status": (attestation.get("solana") or {}).get("devnet_proof_status"),
        "signature": (attestation.get("solana") or {}).get("signature"),
        "explorer_url": (attestation.get("solana") or {}).get("explorer_url"),
    }


def _rpc_request(
    method: str,
    params: List[Any],
    *,
    network: str = "devnet",
    rpc_url: str | None = None,
    timeout_s: int = 20,
) -> Dict[str, Any]:
    url = resolve_solana_rpc_url(network=network, rpc_url=rpc_url)
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "anukriti-proof",
            "method": method,
            "params": params,
        }
    ).encode("utf-8")
    request = urllib.request.Request(  # nosec B310 - user-configured Solana RPC URL
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "rpc_url": url,
            "error": str(exc),
        }
    if data.get("error"):
        return {
            "ok": False,
            "rpc_url": url,
            "error": data["error"],
        }
    return {
        "ok": True,
        "rpc_url": url,
        "result": data.get("result"),
    }


def fetch_solana_transaction(
    signature: str,
    *,
    network: str = "devnet",
    rpc_url: str | None = None,
    timeout_s: int = 20,
) -> Dict[str, Any]:
    """Fetch a parsed Solana transaction for memo proof lookup."""

    return _rpc_request(
        "getTransaction",
        [
            signature,
            {
                "encoding": "jsonParsed",
                "commitment": "confirmed",
                "maxSupportedTransactionVersion": 0,
            },
        ],
        network=network,
        rpc_url=rpc_url,
        timeout_s=timeout_s,
    )


def extract_anukriti_memos(transaction: Mapping[str, Any]) -> List[str]:
    """Extract Anukriti memo strings from parsed transaction JSON/logs."""

    memos: List[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, str):
            if "anukriti:" in value:
                start = value.find("anukriti:")
                memo = value[start:].strip().strip('"').strip("'")
                if memo and memo not in memos:
                    memos.append(memo)
        elif isinstance(value, Mapping):
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(transaction)
    return memos


def verify_solana_memo_proof(
    signature: str,
    expected_memo: str,
    *,
    network: str = "devnet",
    rpc_url: str | None = None,
    timeout_s: int = 20,
) -> Dict[str, Any]:
    """Verify that a Solana transaction contains the expected Anukriti memo."""

    tx = fetch_solana_transaction(
        signature,
        network=network,
        rpc_url=rpc_url,
        timeout_s=timeout_s,
    )
    if not tx.get("ok"):
        return {
            "valid": False,
            "status": "rpc_error",
            "signature": signature,
            "network": network,
            "rpc_url": tx.get("rpc_url"),
            "error": tx.get("error"),
            "expected_memo": expected_memo,
            "memos": [],
        }
    result = tx.get("result")
    if not result:
        return {
            "valid": False,
            "status": "transaction_not_found",
            "signature": signature,
            "network": network,
            "rpc_url": tx.get("rpc_url"),
            "expected_memo": expected_memo,
            "memos": [],
        }
    memos = extract_anukriti_memos(result)
    memo_matches = expected_memo in memos
    return {
        "valid": memo_matches,
        "status": "verified" if memo_matches else "memo_mismatch",
        "signature": signature,
        "network": network,
        "rpc_url": tx.get("rpc_url"),
        "expected_memo": expected_memo,
        "memos": memos,
        "slot": result.get("slot"),
        "block_time": result.get("blockTime"),
        "explorer_url": f"{SOLANA_DEVNET_EXPLORER_BASE}/{signature}?cluster={network}",
    }


def submit_memo_with_solana_cli(
    memo: str,
    *,
    network: str = "devnet",
    keypair_path: str | None = None,
    rpc_url: str | None = None,
    timeout_s: int = 45,
) -> Dict[str, Any]:
    """
    Submit a memo-only devnet proof using the local Solana CLI when configured.

    The command sends 0 SOL from the configured wallet to itself with the memo
    attached. It is intentionally optional: production deployments can replace
    this with a custodial signer, user wallet, or server-side transaction builder.
    """

    solana_bin = shutil.which("solana")
    if not solana_bin:
        return {
            "submitted": False,
            "status": "cli_missing",
            "message": "Solana CLI is not installed on this host.",
        }

    url = resolve_solana_rpc_url(network=network, rpc_url=rpc_url)
    address_cmd = [solana_bin, "address", "--url", url]
    if keypair_path:
        address_cmd.extend(["--keypair", keypair_path])

    try:
        address_result = subprocess.run(  # nosec B603
            address_cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        wallet_address = address_result.stdout.strip()
        if not wallet_address:
            raise RuntimeError("Solana CLI returned an empty wallet address")

        transfer_cmd = [
            solana_bin,
            "transfer",
            "--url",
            url,
            "--allow-unfunded-recipient",
            "--with-memo",
            memo,
            wallet_address,
            "0",
        ]
        if keypair_path:
            transfer_cmd.extend(["--keypair", keypair_path])

        transfer_result = subprocess.run(  # nosec B603
            transfer_cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        RuntimeError,
    ) as e:
        return {
            "submitted": False,
            "status": "submission_failed",
            "message": str(e),
        }

    signature = ""
    for line in transfer_result.stdout.splitlines():
        line = line.strip()
        if line.startswith("Signature:"):
            signature = line.split("Signature:", 1)[1].strip()
            break
    if not signature:
        signature = transfer_result.stdout.strip().splitlines()[-1].strip()

    return {
        "submitted": True,
        "status": "submitted",
        "signature": signature,
        "rpc_url": url,
        "explorer_url": f"{SOLANA_DEVNET_EXPLORER_BASE}/{signature}?cluster=devnet",
    }

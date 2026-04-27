"""Privacy-preserving Solana attestation helpers for trial exports."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess  # nosec B404 - optional fixed-argument Solana CLI wrapper
from datetime import datetime, timezone
from typing import Any, Dict, Mapping

ATTESTATION_SCHEMA_VERSION = "anukriti.trial_export_attestation.v1"
SIMULATION_ATTESTATION_SCHEMA_VERSION = "anukriti.simulation_result_attestation.v1"
SOLANA_MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
SOLANA_DEVNET_EXPLORER_BASE = "https://explorer.solana.com/tx"


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


def submit_memo_with_solana_cli(
    memo: str,
    *,
    network: str = "devnet",
    keypair_path: str | None = None,
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

    url = "https://api.devnet.solana.com" if network == "devnet" else network
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
        "explorer_url": f"{SOLANA_DEVNET_EXPLORER_BASE}/{signature}?cluster=devnet",
    }

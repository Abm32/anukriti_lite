"""Tests for Solana-ready trial export attestations."""

from __future__ import annotations

from src.solana_attestation import (
    ATTESTATION_SCHEMA_VERSION,
    SIMULATION_ATTESTATION_SCHEMA_VERSION,
    build_simulation_result_attestation,
    build_trial_export_attestation,
    extract_anukriti_memos,
    hash_trial_export_payload,
    resolve_solana_rpc_url,
    verify_trial_export_attestation,
    verify_solana_memo_proof,
    verify_trial_export_attestation_detail,
)


def _trial_export_payload() -> dict:
    return {
        "workflow": "clopidogrel_cyp2c19",
        "drug_name": "Clopidogrel",
        "genes": ["CYP2C19"],
        "source": "local",
        "dataset_id": None,
        "requested_samples": 1,
        "summary": {"called": 1, "cannot_call": 0, "insufficient_data": 0},
        "rows": [
            {
                "sample_id": "NA12878",
                "workflow": "clopidogrel_cyp2c19",
                "drug_name": "Clopidogrel",
                "gene": "CYP2C19",
                "diplotype_or_genotype": "*1/*2",
                "phenotype": "Intermediate Metabolizer",
                "recommendation_category": "consider_alternative_antiplatelet",
                "recommendation_text": "Consider alternative antiplatelet strategy.",
                "call_state": "called",
                "call_reason": "Deterministic call from PharmVar + CPIC tables",
            }
        ],
    }


def test_hash_is_stable_regardless_of_key_order():
    payload = _trial_export_payload()
    reordered = {
        "rows": payload["rows"],
        "summary": payload["summary"],
        "requested_samples": payload["requested_samples"],
        "dataset_id": payload["dataset_id"],
        "source": payload["source"],
        "genes": payload["genes"],
        "drug_name": payload["drug_name"],
        "workflow": payload["workflow"],
    }

    assert hash_trial_export_payload(payload) == hash_trial_export_payload(reordered)


def test_attestation_ignores_existing_attestation_field():
    payload = _trial_export_payload()
    attestation = build_trial_export_attestation(
        payload, generated_at="2026-04-17T00:00:00+00:00"
    )
    payload_with_attestation = dict(payload, attestation=attestation)

    assert hash_trial_export_payload(payload) == hash_trial_export_payload(
        payload_with_attestation
    )


def test_attestation_contains_solana_devnet_memo():
    payload = _trial_export_payload()
    attestation = build_trial_export_attestation(
        payload, generated_at="2026-04-17T00:00:00+00:00"
    )

    assert attestation["schema_version"] == ATTESTATION_SCHEMA_VERSION
    assert attestation["network"] == "devnet"
    assert attestation["hash_algorithm"] == "sha256"
    assert attestation["solana"]["memo"].endswith(attestation["payload_hash"])
    assert attestation["solana"]["devnet_proof_status"] == "prepared_not_submitted"
    assert verify_trial_export_attestation(payload, attestation)


def test_tampered_payload_fails_verification():
    payload = _trial_export_payload()
    attestation = build_trial_export_attestation(
        payload, generated_at="2026-04-17T00:00:00+00:00"
    )
    tampered = _trial_export_payload()
    tampered["rows"][0]["phenotype"] = "Poor Metabolizer"

    assert not verify_trial_export_attestation(tampered, attestation)


def test_verification_detail_explains_tamper_failure():
    payload = _trial_export_payload()
    attestation = build_trial_export_attestation(
        payload, generated_at="2026-04-17T00:00:00+00:00"
    )
    tampered = _trial_export_payload()
    tampered["summary"]["called"] = 0

    detail = verify_trial_export_attestation_detail(tampered, attestation)

    assert detail["valid"] is False
    assert detail["hash_matches"] is False
    assert detail["memo_matches_hash"] is True
    assert detail["expected_hash"] == attestation["payload_hash"]


def test_simulation_attestation_uses_simulation_schema_and_detects_tamper():
    payload = {
        "drug_name": "Clopidogrel",
        "risk_level": "Medium",
        "result": "RISK LEVEL: Medium",
        "pgx_structured": {
            "gene": "CYP2C19",
            "phenotype": "Intermediate Metabolizer",
        },
        "audit": {"backend": "nova", "model": "amazon.nova-lite-v1:0"},
    }
    attestation = build_simulation_result_attestation(
        payload, generated_at="2026-04-27T00:00:00+00:00"
    )
    tampered = dict(payload, risk_level="Low")

    assert attestation["schema_version"] == SIMULATION_ATTESTATION_SCHEMA_VERSION
    assert (
        f"anukriti:{SIMULATION_ATTESTATION_SCHEMA_VERSION}:"
        in attestation["solana"]["memo"]
    )
    assert verify_trial_export_attestation_detail(payload, attestation)["valid"] is True
    assert (
        verify_trial_export_attestation_detail(tampered, attestation)["valid"] is False
    )


def test_resolve_solana_rpc_url_prefers_configured_provider(monkeypatch):
    monkeypatch.setenv("SOLANA_RPC_URL", "https://example-helius-rpc.invalid")

    assert resolve_solana_rpc_url("devnet") == "https://example-helius-rpc.invalid"


def test_extract_anukriti_memos_from_parsed_transaction():
    memo = "anukriti:anukriti.trial_export_attestation.v1:abc123"
    transaction = {
        "transaction": {
            "message": {
                "instructions": [
                    {
                        "programId": "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
                        "parsed": memo,
                    }
                ]
            }
        },
        "meta": {
            "logMessages": [
                'Program log: Memo (len 52): "anukriti:other"',
            ]
        },
    }

    assert memo in extract_anukriti_memos(transaction)
    assert "anukriti:other" in extract_anukriti_memos(transaction)


def test_verify_solana_memo_proof_uses_rpc_result(monkeypatch):
    memo = "anukriti:anukriti.trial_export_attestation.v1:abc123"

    def fake_fetch(signature, *, network, rpc_url, timeout_s):
        return {
            "ok": True,
            "rpc_url": "https://example-helius-rpc.invalid",
            "result": {
                "slot": 123,
                "blockTime": 456,
                "transaction": {
                    "message": {
                        "instructions": [
                            {
                                "programId": "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
                                "parsed": memo,
                            }
                        ]
                    }
                },
            },
        }

    monkeypatch.setattr("src.solana_attestation.fetch_solana_transaction", fake_fetch)

    result = verify_solana_memo_proof(
        "fake-signature",
        memo,
        rpc_url="https://example-helius-rpc.invalid",
    )

    assert result["valid"] is True
    assert result["status"] == "verified"
    assert result["memos"] == [memo]

#!/usr/bin/env python3
"""
Anukriti AI Pharmacogenomics API
FastAPI wrapper for Anukriti backend

Exposes REST API endpoints for pharmacogenomics risk simulation.
"""

import hashlib
import json
import logging
import os
import subprocess  # nosec B404 - tabix invocation; fixed args
import tempfile
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    _SLOWAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SLOWAPI_AVAILABLE = False

from src.agent_engine import extract_risk_level, run_simulation
from src.allele_caller import call_gene_from_variants
from src.citation_grounding import compute_explanation_grounding
from src.confidence_tiering import classify_confidence_tier
from src.config import config, resolve_nova_model_id
from src.cyp1a2_caller import interpret_cyp1a2
from src.cyp2b6_caller import interpret_cyp2b6
from src.cyp3a_caller import interpret_cyp3a4, interpret_cyp3a5
from src.dpyd_caller import interpret_dpyd
from src.exceptions import ConfigurationError, LLMError
from src.gst_caller import interpret_gst_combined
from src.hla_caller import (
    interpret_hla_b1502_anticonvulsant,
    interpret_hla_b5701_abacavir,
)
from src.input_processor import get_drug_fingerprint
from src.llm_bedrock import generate_pgx_response, generate_pgx_response_nova
from src.logging_config import get_request_id, new_request_id, setup_logging
from src.nat2_caller import interpret_nat2
from src.novel_drug_inference import PGX_GENE_SET, infer_novel_drug_hypothesis
from src.pgx_structured import format_novel_drug_output, format_output
from src.qvac_llm import generate_pgx_response_qvac
from src.rag.retriever import (
    get_retriever_status,
    retrieve,
    retrieve_docs,
    retrieve_docs_scored,
)
from src.rag_bedrock import run_bedrock_rag, run_nova_rag
from src.security import (
    MAX_VCF_BYTES,
    RequestSizeLimitMiddleware,
    validate_vcf_upload,
    verify_api_key,
)
from src.slco1b1_caller import interpret_slco1b1
from src.solana_attestation import (
    SIMULATION_ATTESTATION_SCHEMA_VERSION,
    build_simulation_result_attestation,
    build_trial_export_attestation,
    resolve_solana_rpc_url,
    submit_memo_with_solana_cli,
    verify_solana_memo_proof,
    verify_trial_export_attestation_detail,
)
from src.tpmt_caller import interpret_tpmt
from src.vcf_processor import (
    discover_local_vcf_paths,
    discover_vcf_paths,
    download_s3_vcf_if_needed,
    extract_variants_with_tabix,
    generate_patient_profile_from_vcf,
    get_sample_ids_from_vcf,
)
from src.vector_search import find_similar_drugs, get_vector_backend_status
from src.warfarin_caller import interpret_warfarin_from_vcf

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter (slowapi) — graceful no-op when not installed
# ---------------------------------------------------------------------------
if _SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = None  # type: ignore[assignment]

# Initialize FastAPI app
app = FastAPI(
    title="Anukriti AI Pharmacogenomics Engine",
    description="AI-powered pharmacogenomics risk simulation using CPIC guidelines",
    version="0.4.0",
)

if _SLOWAPI_AVAILABLE and limiter is not None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request size guard (must be added before CORS)
app.add_middleware(RequestSizeLimitMiddleware)

# CORS — restrict origins in production via ALLOWED_ORIGINS env var
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()] if _raw_origins else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=_raw_origins
    != "",  # only send credentials when origins are restricted
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request-ID middleware — injects a correlation ID into every request
# ---------------------------------------------------------------------------
@app.middleware("http")
async def _request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or new_request_id()
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


def _is_mock_drug_result(similar_drugs: Optional[List[str]]) -> bool:
    drugs = similar_drugs or []
    if not drugs:
        return False
    return all((d or "").startswith("Mock Drug") for d in drugs)


def _vector_context(similar_drugs: Optional[List[str]]) -> Dict[str, Any]:
    if _is_mock_drug_result(similar_drugs):
        return {
            "backend": "mock",
            "context_sources": "Mock data (vector fallback)",
            "used_pinecone": False,
            "mock_fallback": True,
        }
    status = get_vector_backend_status()
    active = status.get("active", "unknown")
    if active == "opensearch":
        return {
            "backend": "opensearch",
            "context_sources": "AWS OpenSearch vector search",
            "used_pinecone": False,
            "mock_fallback": False,
        }
    if active == "pinecone":
        return {
            "backend": "pinecone",
            "context_sources": "ChEMBL (via Pinecone)",
            "used_pinecone": True,
            "mock_fallback": False,
        }
    if active == "mock":
        return {
            "backend": "mock",
            "context_sources": "Mock data (vector fallback)",
            "used_pinecone": False,
            "mock_fallback": True,
        }
    return {
        "backend": active,
        "context_sources": "Vector search",
        "used_pinecone": False,
        "mock_fallback": False,
    }


def _deterministic_coverage(candidate_genes: List[str]) -> Dict[str, Any]:
    supported = sorted(PGX_GENE_SET)
    inferred = sorted(set(candidate_genes or []))
    callable_genes = sorted(set(inferred).intersection(set(supported)))
    missing = sorted(set(inferred) - set(callable_genes))
    ratio = (len(callable_genes) / len(inferred)) if inferred else 0.0
    return {
        "inferred_genes": inferred,
        "supported_genes": supported,
        "callable_genes": callable_genes,
        "missing_genes": missing,
        "coverage_ratio": round(ratio, 2),
    }


def _normalize_nova_variant(raw: Optional[str]) -> Optional[str]:
    """Accept lite|pro aliases; invalid values return None so server default applies."""
    if raw is None:
        return None
    v = str(raw).strip().lower()
    if v in ("lite", "nova-lite", "nova_lite"):
        return "lite"
    if v in ("pro", "nova-pro", "nova_pro"):
        return "pro"
    return None


def _bedrock_failure_hint(exc: BaseException) -> str:
    """
    Map boto3 Bedrock errors to a short user-facing hint (no raw AWS messages).
    """
    msg = str(exc)
    low = msg.lower()
    if "unrecognizedclient" in low or ("security token" in low and "invalid" in low):
        return (
            "AWS credentials are invalid or expired. Update AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY (or use ~/.aws/credentials) and restart the API."
        )
    if "quarantine" in low or "compromised" in low:
        return (
            "AWS marked these access keys as compromised (quarantine). Create new "
            "IAM keys in the console, attach Bedrock permissions, and rotate .env."
        )
    if "accessdenied" in low or "not authorized" in low:
        return (
            "Bedrock access denied. Enable the model in Bedrock → Model access and "
            "ensure IAM allows bedrock:InvokeModel for this foundation model."
        )
    if "throttl" in low or "too many requests" in low:
        return "Bedrock is throttling requests. Retry in a few minutes."
    return "Bedrock request failed. See API server logs for the full error."


def _qvac_failure_hint(exc: BaseException) -> str:
    msg = str(exc)
    if "@qvac/sdk" in msg or "QVAC SDK is not installed" in msg:
        return "Install the QVAC bridge dependencies with `cd qvac && npm install`."
    if "Node.js was not found" in msg:
        return "Install Node.js >=22.17 and ensure QVAC_NODE_BIN points to it."
    return "Check QVAC local model setup, Node.js version, and qvac/package.json dependencies."


def _model_id_for_backend(backend: str, nova_variant: Optional[str] = None) -> str:
    if backend == "gemini":
        return config.GEMINI_MODEL
    if backend == "nova":
        return resolve_nova_model_id(_normalize_nova_variant(nova_variant))
    if backend == "qvac":
        return config.QVAC_MODEL_LABEL
    return config.CLAUDE_MODEL


def _normalize_runtime_backend(raw_backend: Optional[str]) -> str:
    backend = (raw_backend or config.LLM_BACKEND).lower()
    if backend in {"gemini", "claude"}:
        logger.info(
            "Backend '%s' requested but credits exhausted; routing to nova", backend
        )
        return "nova"
    if backend not in {"bedrock", "nova", "qvac"}:
        return "nova"
    return backend


def _validation_gate(
    *,
    confidence_tier: str,
    deterministic_coverage: Dict[str, Any],
    vector_ctx: Dict[str, Any],
) -> Dict[str, Any]:
    decision_grade = (
        confidence_tier == "high"
        and bool(deterministic_coverage.get("callable_genes"))
        and not bool(vector_ctx.get("mock_fallback"))
    )
    if decision_grade:
        reason = (
            "High confidence tier with deterministic coverage and real vector context."
        )
    else:
        reason = (
            "Not decision-grade: requires high confidence, deterministic coverage, "
            "and non-mock retrieval context."
        )
    return {
        "decision_grade": decision_grade,
        "reason": reason,
        "required_conditions": [
            "confidence_tier == high",
            "deterministic_coverage.callable_genes not empty",
            "vector_mock_fallback == false",
        ],
    }


def _load_validation_artifact_summary() -> Dict[str, Any]:
    """
    Lightweight reproducible validation artifact summary from local benchmark sets.
    """
    app_root = os.path.dirname(os.path.abspath(__file__))
    cpic_path = os.path.join(app_root, "cpic_examples.json")
    warf_path = os.path.join(app_root, "warfarin_examples.json")
    summary: Dict[str, Any] = {
        "cpic_examples_count": 0,
        "warfarin_examples_count": 0,
        "artifact_ready": False,
        "notes": [],
    }
    try:
        import json

        if os.path.isfile(cpic_path):
            with open(cpic_path, "r", encoding="utf-8") as f:
                cpic = json.load(f)
            summary["cpic_examples_count"] = len(cpic) if isinstance(cpic, list) else 0
        else:
            summary["notes"].append("cpic_examples.json missing")

        if os.path.isfile(warf_path):
            with open(warf_path, "r", encoding="utf-8") as f:
                warf = json.load(f)
            summary["warfarin_examples_count"] = (
                len(warf) if isinstance(warf, list) else 0
            )
        else:
            summary["notes"].append("warfarin_examples.json missing")
    except Exception as e:
        summary["notes"].append(f"Failed to read benchmark files: {e}")

    summary["artifact_ready"] = (
        summary["cpic_examples_count"] > 0 and summary["warfarin_examples_count"] > 0
    )
    return summary


# Request/Response Models
class AnalyzeRequest(BaseModel):
    """Request model for drug analysis"""

    drug_name: str = Field(
        ..., min_length=1, max_length=200, description="Name of the drug to analyze"
    )
    patient_profile: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="Patient profile including genetics and conditions",
    )
    drug_smiles: Optional[str] = Field(
        None, max_length=2000, description="SMILES string of the drug (optional)"
    )
    similar_drugs: Optional[List[str]] = Field(
        None, description="Pre-computed similar drugs (optional)"
    )
    llm_backend: Optional[str] = Field(
        default=None,
        description=(
            "Override for LLM backend per request. "
            "Allowed values: 'gemini', 'bedrock', 'nova', 'claude', 'qvac'. "
            "If omitted, server default from configuration is used."
        ),
    )
    nova_variant: Optional[str] = Field(
        default=None,
        description=(
            "When llm_backend is 'nova': 'lite' or 'pro' for Amazon Nova Lite vs "
            "Nova Pro on Bedrock. If omitted, uses NOVA_DEFAULT_VARIANT from server config."
        ),
    )

    @field_validator("drug_smiles")
    @classmethod
    def validate_smiles(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        # Basic structural check: must contain at least one letter (atom symbol)
        # and only SMILES-legal characters. Rejects obvious injections.
        import re

        if not re.search(r"[A-Za-z]", v):
            raise ValueError("SMILES string must contain at least one atom symbol.")
        illegal = re.search(r"[^\w\s\(\)\[\]\.\+\-=#@\\\/\%\:\*]", v)
        if illegal:
            raise ValueError(f"SMILES contains illegal character: {illegal.group()!r}")
        return v

    @field_validator("llm_backend")
    @classmethod
    def validate_backend(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"gemini", "bedrock", "nova", "claude", "qvac"}
        if v.lower() not in allowed:
            raise ValueError(f"llm_backend must be one of {sorted(allowed)}, got {v!r}")
        return v.lower()


class AnalyzeResponse(BaseModel):
    """Response model for drug analysis"""

    result: str = Field(..., description="AI-generated pharmacogenomics prediction")
    risk_level: Optional[str] = Field(
        None, description="Extracted risk level (Low/Medium/High)"
    )
    drug_name: str = Field(..., description="Name of the analyzed drug")
    status: str = Field(default="success", description="Request status")
    # RAG context (transparent reasoning)
    similar_drugs_used: Optional[List[str]] = Field(
        None, description="Retrieved similar drugs used for prediction"
    )
    genetics_summary: Optional[str] = Field(
        None,
        description="Genetic variants / metabolizer status used (e.g. CYP2D6 poor metabolizer)",
    )
    context_sources: Optional[str] = Field(
        None,
        description="Source of similar drugs (e.g. ChEMBL via Pinecone, Mock data)",
    )
    pgx_structured: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Deterministic PGx result + AI explanation, when available.",
    )
    audit: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Non-sensitive audit metadata (timestamps, backend/model, cache hints).",
    )
    ehr_bundle: Optional[Dict[str, Any]] = Field(
        default=None,
        description="FHIR-like JSON bundle suitable for EHR-style export.",
    )
    attestation: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Privacy-preserving hash proof for this simulation result. "
            "The Solana memo contains only schema label + payload hash."
        ),
    )


class NovelDrugAnalyzeRequest(BaseModel):
    """Request model for explicit novel-drug analysis."""

    drug_name: str = Field(
        ..., min_length=1, max_length=200, description="Candidate or novel drug name"
    )
    drug_smiles: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="SMILES string for the novel compound",
    )
    patient_profile: str = Field(
        ..., min_length=1, max_length=20000, description="Patient profile text"
    )
    targets: Optional[List[str]] = Field(
        default=None, description="Known/assumed targets (optional)"
    )
    metabolism_enzymes: Optional[List[str]] = Field(
        default=None, description="Known/assumed metabolism enzymes (optional)"
    )
    transporters: Optional[List[str]] = Field(
        default=None, description="Known/assumed transporter genes (optional)"
    )
    evidence_notes: Optional[str] = Field(
        default=None, description="Free-text preclinical/literature evidence notes"
    )
    llm_backend: Optional[str] = Field(
        default=None, description="Optional LLM backend override"
    )
    nova_variant: Optional[str] = Field(
        default=None,
        description="When using Nova backend: 'lite' or 'pro'",
    )
    include_population_summary: bool = Field(
        default=True, description="Include ancestry-aware population summary"
    )
    cohort_size: int = Field(
        default=300,
        ge=50,
        le=2000,
        description="Synthetic cohort size for novel-drug population summary",
    )


class HealthResponse(BaseModel):
    """Response model for health check"""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    model: str = Field(..., description="LLM model being used")


# API Endpoints
@app.get("/", response_model=HealthResponse)
async def health_check():
    """
    Fast health check endpoint - no external service checks
    Returns basic service status and configuration quickly
    """
    logger.info("Health check requested - using fast implementation")

    if config.LLM_BACKEND == "gemini":
        llm_model = config.GEMINI_MODEL
    elif config.LLM_BACKEND == "nova":
        llm_model = resolve_nova_model_id(None)
    else:
        llm_model = config.CLAUDE_MODEL

    return HealthResponse(
        status="Anukriti AI Engine Online",
        version="0.2.0",
        model=f"{config.LLM_BACKEND}:{llm_model}",
    )


@app.get("/demo")
async def demo_examples():
    """
    Get demo examples for testing and competition presentation
    Returns pre-configured examples that showcase different risk levels
    """
    return {
        "examples": [
            {
                "drug_name": "Warfarin",
                "patient_profile": "ID: DEMO-001\nAge: 45\nGenetics: CYP2C9 Poor Metabolizer\nConditions: Atrial Fibrillation\nLifestyle: Non-smoker",
                "expected_risk": "High",
                "description": "Anticoagulant with genetic contraindication",
            },
            {
                "drug_name": "Codeine",
                "patient_profile": "ID: DEMO-002\nAge: 32\nGenetics: CYP2D6 Poor Metabolizer\nConditions: Chronic Pain\nLifestyle: Non-smoker",
                "expected_risk": "High",
                "description": "Opioid prodrug requiring CYP2D6 activation",
            },
            {
                "drug_name": "Clopidogrel",
                "patient_profile": "ID: DEMO-003\nAge: 58\nGenetics: CYP2C19 Poor Metabolizer\nConditions: Coronary Artery Disease\nLifestyle: Former smoker",
                "expected_risk": "High",
                "description": "Antiplatelet requiring CYP2C19 activation",
            },
            {
                "drug_name": "Ibuprofen",
                "patient_profile": "ID: DEMO-004\nAge: 28\nGenetics: CYP2C9 Normal Metabolizer\nConditions: Headache\nLifestyle: Active, non-smoker",
                "expected_risk": "Low",
                "description": "NSAID with normal metabolism",
            },
            {
                "drug_name": "Metoprolol",
                "patient_profile": "ID: DEMO-005\nAge: 52\nGenetics: CYP2D6 Extensive Metabolizer\nConditions: Hypertension\nLifestyle: Regular exercise",
                "expected_risk": "Low",
                "description": "Beta-blocker with normal CYP2D6 function",
            },
        ],
        "competition_info": {
            "platform": "Anukriti AI Pharmacogenomics Engine",
            "version": "0.2.0",
            "features": [
                "Real-time AI risk assessment",
                "CPIC guideline compliance",
                "Multi-enzyme genetic analysis",
                "Cloud-agnostic deployment",
                "Enterprise-ready API",
            ],
        },
    }


@app.get("/metrics")
async def get_metrics():
    """
    In-process operational metrics.

    Returns vector search backend usage, fallback rates, and LLM call stats.
    Use this to detect when Pinecone/OpenSearch is silently failing and mock
    data is being served to users.
    """
    from src.metrics import snapshot

    return snapshot()


@app.get("/health-fast")
async def fast_health_check():
    """
    Ultra-fast health check without external service checks
    Used by Streamlit UI for quick connectivity testing
    """
    logger.info("Fast health check requested")

    try:
        # Test basic configuration without external calls
        if config.LLM_BACKEND == "gemini":
            llm_model = config.GEMINI_MODEL
        elif config.LLM_BACKEND == "nova":
            llm_model = resolve_nova_model_id(None)
        else:
            llm_model = config.CLAUDE_MODEL

        return {
            "status": "healthy",
            "timestamp": "2026-03-06T00:00:00Z",
            "version": "0.4.0",
            "environment": "production",
            "services": {
                "api": "online",
                "llm_backend": config.LLM_BACKEND,
                "model": llm_model,
            },
            "response_time_ms": "< 1000",
        }
    except Exception as e:
        logger.error(f"Fast health check failed: {e}")
        return {"status": "error", "error": str(e), "timestamp": "2026-03-06T00:00:00Z"}


@app.get("/health/llm-status")
async def llm_status():
    """
    Return the current active LLM backend and full fallback chain status.

    Shows which backend is currently primary (Nova, Claude, Gemini, Ollama,
    or deterministic CPIC). The fallback chain ensures the demo is resilient
    to Bedrock quota limits, network issues, or missing API keys.

    Ollama provides a fully local fallback: install https://ollama.ai and
    run 'ollama pull llama3' to enable. No cloud credentials required.
    """
    from src.multi_backend_llm import multi_backend_llm

    status = multi_backend_llm.get_backend_status()
    return {
        "active_backend": status["active_backend"],
        "active_backend_display": status["active_backend_display"],
        "fallback_chain": status["fallback_chain"],
        "backend_availability": status["backend_availability"],
        "ollama": {
            "available": status["backend_availability"].get("ollama", False),
            "model": status.get("ollama_model"),
            "base_url": status.get("ollama_base_url"),
            "setup_hint": "Install from https://ollama.ai then run: ollama pull llama3",
        },
        "demo_safe": status["demo_safe"],
        "note": (
            "Fallback order: AWS Bedrock Nova → Bedrock Claude → Google Gemini → "
            "Anthropic Claude → Local Ollama → Deterministic CPIC (always available)."
        ),
    }


@app.get("/health")
async def detailed_health():
    """
    Detailed health check for monitoring and competition demo
    Includes AWS integration status and capabilities with async checks
    """
    logger.info("Detailed health check requested")

    try:
        # Test configuration
        is_valid, missing_keys = config.validate_required()

        if config.LLM_BACKEND == "gemini":
            llm_model = config.GEMINI_MODEL
        elif config.LLM_BACKEND == "nova":
            llm_model = resolve_nova_model_id(None)
        else:
            llm_model = config.CLAUDE_MODEL

        # Check AWS integration status with timeouts and async patterns
        aws_services_status = {}

        # Use shorter timeouts and better error handling
        aws_timeout = int(os.getenv("AWS_SERVICE_CHECK_TIMEOUT", "5"))

        try:
            # S3 Status - with timeout
            from src.aws.s3_genomic_manager import S3GenomicDataManager

            bucket_name = os.getenv("AWS_S3_BUCKET_GENOMIC", "synthatrial-genomic-data")
            if bucket_name and os.getenv("AWS_ACCESS_KEY_ID"):
                try:
                    s3_manager = S3GenomicDataManager(bucket_name)
                    # Quick check - just verify client exists, don't make actual calls
                    aws_services_status["s3_genomic"] = (
                        "connected" if s3_manager.s3_client else "disconnected"
                    )
                except Exception as e:
                    logger.warning(f"S3 status check failed: {e}")
                    aws_services_status["s3_genomic"] = "disconnected"
            else:
                aws_services_status["s3_genomic"] = "not_configured"

            # Lambda Status - with timeout and no actual function calls
            lambda_function = os.getenv(
                "AWS_LAMBDA_FUNCTION_NAME", "synthatrial-batch-processor"
            )
            if os.getenv("AWS_ACCESS_KEY_ID") and lambda_function:
                try:
                    import boto3

                    # Just create client, don't make actual calls that can hang
                    lambda_client = boto3.client(
                        "lambda",
                        region_name=os.getenv("AWS_LAMBDA_REGION", "us-east-1"),
                    )
                    aws_services_status["lambda"] = "configured"
                except Exception as e:
                    logger.warning(f"Lambda client creation failed: {e}")
                    aws_services_status["lambda"] = "disconnected"
            else:
                aws_services_status["lambda"] = "not_configured"

            # Step Functions Status - with timeout and no actual calls
            state_machine_arn = os.getenv("AWS_STEP_FUNCTIONS_STATE_MACHINE")
            if os.getenv("AWS_ACCESS_KEY_ID") and state_machine_arn:
                try:
                    import boto3

                    # Just create client, don't make actual calls that can hang
                    sf_client = boto3.client(
                        "stepfunctions",
                        region_name=os.getenv("AWS_STEP_FUNCTIONS_REGION", "us-east-1"),
                    )
                    aws_services_status["step_functions"] = "configured"
                except Exception as e:
                    logger.warning(f"Step Functions client creation failed: {e}")
                    aws_services_status["step_functions"] = "disconnected"
            else:
                aws_services_status["step_functions"] = "not_configured"

        except Exception as e:
            logger.warning(f"AWS services status check failed: {e}")
            aws_services_status = {"error": str(e)}

        vector_status = get_vector_backend_status()
        return {
            "status": "healthy",
            "timestamp": "2026-03-06T00:00:00Z",
            "version": "0.4.0",
            "environment": "production",
            "services": {
                "api": "online",
                "llm": "connected" if is_valid else "configuration_error",
                "vector_db": get_vector_backend_status().get("active", "mock"),
                "aws_integration": aws_services_status,
            },
            "configuration": {
                "backend": config.LLM_BACKEND,
                "model": llm_model,
                "temperature": config.GEMINI_TEMPERATURE,
                "missing_keys": missing_keys if not is_valid else [],
                "aws_account_id": os.getenv("AWS_ACCOUNT_ID", "403732031470"),
                "aws_region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            },
            "capabilities": {
                "pharmacogenomics_engines": [
                    "CYP2D6",
                    "CYP2C19",
                    "CYP2C9",
                    "UGT1A1",
                    "SLCO1B1",
                ],
                "population_simulation": {
                    "max_cohort_size": int(
                        os.getenv("POPULATION_SIMULATOR_MAX_COHORT_SIZE", "10000")
                    ),
                    "aws_lambda_scaling": os.getenv(
                        "POPULATION_SIMULATOR_ENABLE_LAMBDA", "false"
                    ).lower()
                    == "true",
                    "supported_populations": ["AFR", "EUR", "EAS", "SAS", "AMR"],
                },
                "aws_services": {
                    "s3_genomic_data": aws_services_status.get("s3_genomic")
                    == "connected",
                    "lambda_batch_processing": aws_services_status.get("lambda")
                    == "configured",
                    "step_functions_orchestration": aws_services_status.get(
                        "step_functions"
                    )
                    == "configured",
                },
            },
            "endpoints": [
                {"path": "/", "method": "GET", "description": "Fast health check"},
                {
                    "path": "/health-fast",
                    "method": "GET",
                    "description": "Ultra-fast health check",
                },
                {
                    "path": "/health",
                    "method": "GET",
                    "description": "Detailed health with AWS status",
                },
                {
                    "path": "/aws-status",
                    "method": "GET",
                    "description": "AWS integration status",
                },
                {
                    "path": "/population-simulate",
                    "method": "GET",
                    "description": "Population simulation demo",
                },
                {
                    "path": "/architecture-diagram",
                    "method": "GET",
                    "description": "Generate architecture diagram",
                },
                {
                    "path": "/data-status",
                    "method": "GET",
                    "description": "Pinecone vs mock, VCF chromosomes, ChEMBL presence, S3 status",
                },
                {
                    "path": "/analyze",
                    "method": "POST",
                    "description": "Drug risk analysis",
                },
                {"path": "/demo", "method": "GET", "description": "Demo examples"},
                {"path": "/docs", "method": "GET", "description": "API documentation"},
            ],
        }
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {"status": "error", "error": str(e), "timestamp": "2026-03-06T00:00:00Z"}


_AWS_STATUS_CACHE: Dict[str, Any] = {}
_AWS_STATUS_CACHE_TS: float = 0.0


@app.get("/regulatory/classification")
async def regulatory_classification():
    """
    Machine-readable regulatory classification metadata for SynthaTrial.

    Returns the CDS classification under 21st Century Cures Act §520(o)(1)(E),
    current validation stage, data ethics statement, and clinical validation
    roadmap milestones. Intended for EHR/integration partners and regulatory review.
    """
    return {
        "tool": "SynthaTrial Pharmacogenomics Engine",
        "version": "0.5.0",
        "regulatory_status": {
            "classification": "Non-device Clinical Decision Support (CDS)",
            "authority": "21st Century Cures Act §520(o)(1)(E)",
            "fda_regulated": False,
            "rationale": (
                "SynthaTrial meets all four factors for non-device CDS: "
                "(1) does not acquire/process medical images; "
                "(2) not intended for immediately life-threatening conditions; "
                "(3) intended for use by clinicians who can independently review the basis; "
                "(4) not intended to replace clinical judgment."
            ),
            "reference": "docs/regulatory/FDA_CDS_COMPLIANCE.md",
        },
        "validation_stage": {
            "current_stage": 0,
            "stage_label": "Research Prototype",
            "description": "CPIC-aligned fixture testing; Coriell concordance; no prospective clinical validation.",
            "next_stage": "Stage 1 — Prospective concordance study with CLIA lab partner (target: Q3-Q4 2026)",
            "roadmap_reference": "docs/regulatory/CLINICAL_VALIDATION_ROADMAP.md",
        },
        "data_ethics": {
            "patient_data_stored": False,
            "patient_data_transmitted": False,
            "genomic_data_source": "1000 Genomes Project Phase 3 (de-identified, publicly released)",
            "data_access": "AWS Open Data Program — s3://1000genomes (no egress charges)",
            "irb_status": "Data sourced from IRB-approved international consortium; no new patient data collected.",
            "hipaa_note": "Tool does not process Protected Health Information (PHI). VCF data held in memory only during request lifecycle.",
        },
        "gene_panel": {
            "tier_1_genes": [
                "CYP2D6",
                "CYP2C19",
                "CYP2C9",
                "CYP3A4",
                "CYP3A5",
                "CYP1A2",
                "CYP2B6",
                "NAT2",
                "UGT1A1",
                "SLCO1B1",
                "VKORC1",
                "TPMT",
                "DPYD",
                "GSTM1",
                "GSTT1",
                "HLA_B5701",
            ],
            "cpic_level_a_genes": [
                "CYP2D6",
                "CYP2C19",
                "CYP2C9",
                "CYP3A5",
                "CYP2B6",
                "NAT2",
                "UGT1A1",
                "SLCO1B1",
                "VKORC1",
                "TPMT",
                "DPYD",
                "HLA_B5701",
            ],
            "cpic_level_b_genes": ["CYP3A4", "CYP1A2", "GSTM1", "GSTT1"],
            "total_genes": 16,
            "note": "Full comprehensive pharmacogenome (50+ genes) requires additional CPIC guideline expansion.",
        },
        "clinical_notes": {
            "use_case": "Research, drug development simulation, pharmacogenomics education",
            "not_for": "Direct patient care, prescription decisions, clinical diagnosis",
            "output_framing": "All outputs include CPIC citation, confidence tier, and independent clinical review guidance",
        },
    }


@app.get("/aws-status")
async def aws_integration_status(deep: bool = False):
    """
    AWS Integration Status endpoint
    Returns status of AWS services integration (S3, Lambda, Step Functions)
    """
    global _AWS_STATUS_CACHE, _AWS_STATUS_CACHE_TS
    cache_ttl = int(os.getenv("AWS_STATUS_CACHE_TTL", "30"))
    now = time.time()
    if _AWS_STATUS_CACHE and (now - _AWS_STATUS_CACHE_TS) < cache_ttl and not deep:
        return _AWS_STATUS_CACHE

    try:
        # Check S3 Genomic Data Manager - non-blocking approach
        s3_genomic_connected = False
        vcf_files_count = 0
        s3_bucket_info = {}

        try:
            from src.aws.s3_genomic_manager import S3GenomicDataManager

            bucket_name = os.getenv("AWS_S3_BUCKET_GENOMIC", "synthatrial-genomic-data")
            if bucket_name and os.getenv("AWS_ACCESS_KEY_ID"):
                try:
                    s3_manager = S3GenomicDataManager(bucket_name)
                    if s3_manager.s3_client:
                        s3_genomic_connected = True
                        if deep:
                            # Optional: may take longer; S3 client has strict timeouts.
                            try:
                                vcf_files = s3_manager.list_vcf_files()
                                vcf_files_count = len(vcf_files)
                                s3_bucket_info = s3_manager.get_bucket_info()
                            except Exception as e:
                                logger.warning(f"S3 deep status failed: {e}")
                except Exception as e:
                    logger.warning(f"S3 manager creation failed: {e}")
            else:
                logger.info(
                    "S3 not configured - missing bucket name or AWS credentials"
                )
        except Exception as e:
            logger.warning(f"S3 status check failed: {e}")

        # Check Lambda availability - non-blocking approach
        lambda_available = False
        lambda_function_name = os.getenv(
            "AWS_LAMBDA_FUNCTION_NAME", "synthatrial-batch-processor"
        )
        try:
            import boto3

            if os.getenv("AWS_ACCESS_KEY_ID") and lambda_function_name:
                # Just create client, don't make actual calls that can hang
                lambda_client = boto3.client(
                    "lambda", region_name=os.getenv("AWS_LAMBDA_REGION", "us-east-1")
                )
                lambda_available = True  # Client creation successful = configured
        except Exception as e:
            logger.warning(f"Lambda client creation failed: {e}")

        # Check Step Functions availability - non-blocking approach
        step_functions_available = False
        state_machine_arn = os.getenv("AWS_STEP_FUNCTIONS_STATE_MACHINE")
        try:
            import boto3

            if os.getenv("AWS_ACCESS_KEY_ID") and state_machine_arn:
                # Just create client, don't make actual calls that can hang
                sf_client = boto3.client(
                    "stepfunctions",
                    region_name=os.getenv("AWS_STEP_FUNCTIONS_REGION", "us-east-1"),
                )
                step_functions_available = (
                    True  # Client creation successful = configured
                )
        except Exception as e:
            logger.warning(f"Step Functions client creation failed: {e}")

        out = {
            "aws_integration": {
                "s3_genomic_connected": s3_genomic_connected,
                "vcf_files_count": vcf_files_count,
                "s3_bucket_info": s3_bucket_info,
                "lambda_available": lambda_available,
                "lambda_function_name": lambda_function_name,
                "step_functions_available": step_functions_available,
                "state_machine_arn": state_machine_arn,
            },
            "aws_account_id": os.getenv("AWS_ACCOUNT_ID", "403732031470"),
            "aws_region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            "status": (
                "live"
                if (
                    s3_genomic_connected or lambda_available or step_functions_available
                )
                else "local"
            ),
        }
        if not deep:
            _AWS_STATUS_CACHE = out
            _AWS_STATUS_CACHE_TS = now
        return out

    except Exception as e:
        logger.error(f"AWS status check failed: {e}")
        return {
            "aws_integration": {
                "s3_genomic_connected": False,
                "vcf_files_count": 0,
                "lambda_available": False,
                "step_functions_available": False,
            },
            "status": "error",
            "error": str(e),
        }


class PopulationSimulateRequest(BaseModel):
    """Request model for cohort-based population simulation"""

    cohort_size: int = Field(
        default=100,
        ge=10,
        le=10000,
        description="Number of patients in the cohort",
    )
    drug: str = Field(default="Warfarin", description="Drug to simulate")
    population_mix: Optional[Dict[str, float]] = Field(
        default=None,
        description="Population distribution (AFR, EUR, EAS, SAS, AMR). Default: balanced.",
    )
    candidate_genes: Optional[List[str]] = Field(
        default=None,
        description="Optional inferred genes for novel-drug simulation mode.",
    )
    confidence_tier: Optional[str] = Field(
        default=None,
        description="Optional global confidence tier for novel-drug simulation mode.",
    )


def _run_population_simulation(
    cohort_size: int,
    drug: str,
    population_mix: Dict[str, float],
    candidate_genes: Optional[List[str]] = None,
    confidence_tier: Optional[str] = None,
) -> Dict[str, Any]:
    """Shared logic for population simulation."""
    from src.population_simulator import PopulationSimulator

    simulator = PopulationSimulator(
        cohort_size=cohort_size,
        population_mix=population_mix,
    )
    if candidate_genes:
        novel_out = simulator.run_novel_drug_simulation(
            drug_name=drug,
            candidate_genes=candidate_genes,
            confidence_tier=(confidence_tier or "exploratory"),
            parallel=True,
        )
        return {
            "demo_simulation": novel_out,
            "capabilities": {
                "max_cohort_size": 10000,
                "supported_populations": ["AFR", "EUR", "EAS", "SAS", "AMR"],
                "ancestry_aware_confidence": True,
                "novel_drug_mode": True,
            },
            "status": "success",
        }

    results = simulator.run_simulation(drug=drug, parallel=True)
    perf = results.performance_metrics
    aws_lambda_used = False
    step_functions_used = False

    # Optionally invoke Lambda when available
    lambda_fn = os.getenv("AWS_LAMBDA_FUNCTION_NAME", "synthatrial-batch-processor")
    if os.getenv("AWS_ACCESS_KEY_ID") and lambda_fn:
        try:
            from src.aws.lambda_batch_processor import LambdaBatchProcessor

            processor = LambdaBatchProcessor(
                function_name=lambda_fn,
                region=os.getenv("AWS_LAMBDA_REGION", "us-east-1"),
            )
            if processor.lambda_client:
                demo_sim = PopulationSimulator(5, population_mix)
                demo_cohort = demo_sim.generate_cohort()
                demo_patients = [p.to_dict() for p in demo_cohort]
                out = processor.invoke_batch_simulation(
                    drug=drug,
                    patient_batch=demo_patients,
                    invocation_type="RequestResponse",
                )
                aws_lambda_used = out is not None
        except Exception as e:
            logger.debug(f"Lambda invocation skipped: {e}")

    # Optionally start Step Functions when available
    state_machine = os.getenv("AWS_STEP_FUNCTIONS_STATE_MACHINE")
    if os.getenv("AWS_ACCESS_KEY_ID") and state_machine:
        try:
            from src.aws.step_functions_orchestrator import StepFunctionsOrchestrator

            orchestrator = StepFunctionsOrchestrator(
                state_machine_arn=state_machine,
                region=os.getenv("AWS_STEP_FUNCTIONS_REGION", "us-east-1"),
            )
            if orchestrator.stepfunctions_client:
                exec_arn = orchestrator.start_clinical_trial_simulation(
                    trial_name="demo_sim",
                    drug=drug,
                    cohort_size=cohort_size,
                    population_mix=population_mix,
                )
                step_functions_used = exec_arn is not None
        except Exception as e:
            logger.debug(f"Step Functions start skipped: {e}")

    return {
        "demo_simulation": {
            "drug": drug,
            "cohort_size": cohort_size,
            "population_diversity": results.population_breakdown,
            "population_breakdown": results.population_breakdown,
            "risk_summary": results.response_distribution,
            "risk_distribution": results.response_distribution,
            "gene_phenotype_distribution": getattr(
                results, "gene_phenotype_distribution", None
            ),
            "gene_genotype_distribution": getattr(
                results, "gene_genotype_distribution", None
            ),
            "performance_metrics": {
                "total_time_seconds": perf.total_time_seconds,
                "throughput_patients_per_minute": perf.throughput_patients_per_minute,
                "average_latency_ms": perf.average_latency_ms,
                "patients_per_second": (
                    cohort_size / perf.total_time_seconds
                    if perf.total_time_seconds > 0
                    else 0
                ),
                "cost_per_patient": (
                    perf.aws_cost_estimate / cohort_size if cohort_size > 0 else 0
                ),
            },
            "performance": {
                "total_time_seconds": perf.total_time_seconds,
                "throughput_patients_per_minute": perf.throughput_patients_per_minute,
                "average_latency_ms": perf.average_latency_ms,
                "patients_per_second": (
                    cohort_size / perf.total_time_seconds
                    if perf.total_time_seconds > 0
                    else 0
                ),
                "cost_per_patient": (
                    perf.aws_cost_estimate / cohort_size if cohort_size > 0 else 0
                ),
            },
            "aws_lambda_used": aws_lambda_used,
            "step_functions_used": step_functions_used,
        },
        "capabilities": {
            "max_cohort_size": 10000,
            "supported_populations": ["AFR", "EUR", "EAS", "SAS", "AMR"],
            "aws_lambda_scaling": True,
            "real_time_metrics": True,
        },
        "status": "success",
    }


@app.post("/population-simulate")
async def population_simulate_post(body: PopulationSimulateRequest):
    """
    Cohort-based population simulation with custom parameters.
    Use this for Batch Mode and custom cohort configurations.
    """
    try:
        population_mix = body.population_mix or {
            "AFR": 0.25,
            "EUR": 0.40,
            "EAS": 0.20,
            "SAS": 0.10,
            "AMR": 0.05,
        }
        return _run_population_simulation(
            cohort_size=body.cohort_size,
            drug=body.drug,
            population_mix=population_mix,
            candidate_genes=body.candidate_genes,
            confidence_tier=body.confidence_tier,
        )
    except Exception as e:
        logger.error(f"Population simulation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/population-simulate")
async def population_simulation_demo():
    """
    Population Simulation Demo endpoint (default params).
    Use POST /population-simulate for custom cohort size, drug, and population mix.
    """
    try:
        population_mix = {
            "AFR": 0.25,
            "EUR": 0.40,
            "EAS": 0.20,
            "SAS": 0.10,
            "AMR": 0.05,
        }
        return _run_population_simulation(
            cohort_size=100,
            drug="Warfarin",
            population_mix=population_mix,
        )
    except Exception as e:
        logger.error(f"Population simulation demo failed: {e}")
        return {
            "demo_simulation": None,
            "status": "error",
            "error": str(e),
            "fallback": "Population simulation requires full AWS integration",
        }


@app.get("/architecture-diagram")
async def generate_architecture_diagram():
    """
    Generate Architecture Diagram endpoint
    Creates professional architecture diagrams for competition presentation
    """
    try:
        from src.diagram_generator import ArchitectureDiagramGenerator

        generator = ArchitectureDiagramGenerator()

        # Generate competition-ready diagram
        diagram_info = generator.generate_competition_diagram(
            output_format="svg",
            include_aws_services=True,
            include_performance_metrics=True,
        )

        return {
            "architecture_diagram": {
                "generated": True,
                "output_path": diagram_info.get("output_path"),
                "format": "svg",
                "aws_services_included": [
                    "S3 (Genomic Data)",
                    "Lambda (Batch Processing)",
                    "Step Functions (Orchestration)",
                    "CloudWatch (Monitoring)",
                ],
                "diagram_url": f"/static/architecture.svg",  # If serving static files
            },
            "competition_features": {
                "professional_styling": True,
                "aws_service_icons": True,
                "performance_annotations": True,
                "scalability_indicators": True,
            },
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Architecture diagram generation failed: {e}")
        return {
            "architecture_diagram": {"generated": False, "error": str(e)},
            "status": "error",
        }


@app.get("/validation/concordance-summary")
async def validation_concordance_summary():
    """
    Return current PGx validation concordance metrics for all 15 Tier-1 genes.

    Reports fixture-based concordance (deterministic caller tests) and
    documents the status of reference sample validation against Coriell and
    GIAB NA12878 (HG001). See docs/regulatory/CLINICAL_VALIDATION_ROADMAP.md
    for the prospective validation roadmap.
    """
    from tests.test_expanded_validation import CONCORDANCE_METRICS, GIAB_NA12878_TRUTH

    return {
        "concordance_metrics": CONCORDANCE_METRICS,
        "giab_na12878_truth_genotypes": GIAB_NA12878_TRUTH,
        "gene_panel": {
            "tier_1_genes": [
                "CYP2D6",
                "CYP2C19",
                "CYP2C9",
                "CYP3A4",
                "CYP3A5",
                "CYP1A2",
                "CYP2B6",
                "NAT2",
                "UGT1A1",
                "SLCO1B1",
                "VKORC1",
                "TPMT",
                "DPYD",
                "GSTM1",
                "GSTT1",
                "HLA_B5701",
            ],
            "total": 16,
        },
        "references": {
            "coriell": "https://www.coriell.org/",
            "giab": "https://www.nist.gov/programs-projects/genome-bottle",
            "pharmcat": "docs/validation/PHARMCAT_COMPARISON.md",
            "cpic": "https://cpicpgx.org",
            "pharmvar": "https://www.pharmvar.org",
        },
    }


@app.get("/data-status")
async def data_status(source: str = "auto"):
    """
    Report whether the app is using real data (Pinecone/ChEMBL, VCF) or mock.
    Now includes S3 genomic data status.

    - vector_db: active vector backend ("opensearch", "pinecone", or "mock").
    - vcf_chromosomes: chromosomes found (S3 or local data/genomes).
    - vcf_source: "s3" or "local" indicating data source.
    - chembl_db_present: True if ChEMBL SQLite exists.
    - s3_genomic_status: S3 bucket information if available.
    """
    app_root = os.path.dirname(os.path.abspath(__file__))
    genomes_dir = os.path.join(app_root, "data", "genomes")
    chembl_paths = [
        os.path.join(app_root, "data", "chembl", "chembl_34_sqlite", "chembl_34.db"),
        os.path.join(app_root, "data", "chembl", "chembl_34.db"),
    ]

    # Discover VCF paths according to requested source mode.
    vcf_found = _discover_paths_by_source(genomes_dir, source)
    chembl_present = any(os.path.isfile(p) for p in chembl_paths)

    # Determine VCF source
    vcf_source = "local"
    s3_genomic_status = None

    # Check if any VCF paths are S3 URLs
    if vcf_found and any(path.startswith("s3://") for path in vcf_found.values()):
        vcf_source = "s3"

        # Get S3 bucket information
        try:
            from src.aws.s3_genomic_manager import S3GenomicDataManager

            bucket_name = os.getenv("AWS_S3_BUCKET_GENOMIC", "synthatrial-genomic-data")
            if bucket_name and os.getenv("AWS_ACCESS_KEY_ID"):
                s3_manager = S3GenomicDataManager(bucket_name)
                if s3_manager.s3_client:
                    s3_genomic_status = s3_manager.get_bucket_info()
        except Exception as e:
            logger.warning(f"S3 status check failed: {e}")

    vector_status = get_vector_backend_status()
    return {
        "vector_db": vector_status.get("active", "mock"),
        "vector_db_configured": vector_status.get("configured", "pinecone"),
        "vcf_chromosomes": list(vcf_found.keys()) if vcf_found else [],
        "vcf_paths": vcf_found,
        "vcf_source": vcf_source,
        "vcf_files_count": len(vcf_found),
        "chembl_db_present": chembl_present,
        "s3_genomic_status": s3_genomic_status,
        "aws_integration": {
            "s3_genomic_data": vcf_source == "s3",
            "bucket_name": os.getenv(
                "AWS_S3_BUCKET_GENOMIC", "synthatrial-genomic-data"
            ),
            "aws_account_id": os.getenv("AWS_ACCOUNT_ID", "403732031470"),
            "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        },
    }


class VcfProfileRequest(BaseModel):
    """Request model for VCF-based patient profile generation"""

    drug_name: str = Field(..., description="Drug name for drug-triggered PGx")
    sample_id: str = Field(..., description="Sample ID from VCF file")


class VcfUploadProfileRequest(BaseModel):
    """Request model for uploaded VCF-based patient profile generation."""

    upload_id: str = Field(..., description="Upload session identifier")
    drug_name: str = Field(..., description="Drug name for drug-triggered PGx")
    sample_id: str = Field(..., description="Sample ID from uploaded VCF")


_VCF_UPLOADS: Dict[str, Dict[str, Any]] = {}

# VCF upload TTL: sessions older than this (seconds) are auto-cleaned.
_VCF_UPLOAD_TTL: int = int(os.getenv("VCF_UPLOAD_TTL_SECONDS", str(24 * 3600)))


# ---------------------------------------------------------------------------
# FHIR EHR Integration Endpoints
# ---------------------------------------------------------------------------


class FhirPushRequest(BaseModel):
    """Request model for pushing a FHIR bundle to an external FHIR R4 server."""

    fhir_server_url: str = Field(
        ...,
        description="Base URL of the target FHIR R4 server (e.g. http://hapi.fhir.org/baseR4)",
    )
    bundle: Dict[str, Any] = Field(
        ..., description="FHIR Bundle resource (JSON) to POST"
    )
    auth_token: Optional[str] = Field(
        None, description="Bearer token for FHIR server authentication"
    )


@app.post("/fhir/push")
async def fhir_push(req: FhirPushRequest) -> Dict[str, Any]:
    """
    Push a FHIR Bundle to an external FHIR R4 server.

    Accepts the bundle built by the PGx engine (via src/fhir_genomics.py)
    and POSTs it to the specified FHIR server. Returns the server's response
    including any OperationOutcome.
    """
    try:
        import httpx
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="httpx is required for FHIR push. Install with: pip install httpx",
        )

    headers: Dict[str, str] = {
        "Content-Type": "application/fhir+json",
        "Accept": "application/fhir+json",
    }
    if req.auth_token:
        headers["Authorization"] = f"Bearer {req.auth_token}"

    target_url = req.fhir_server_url.rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                target_url,
                json=req.bundle,
                headers=headers,
            )

        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:2000]}

        return {
            "status": "success" if resp.is_success else "error",
            "http_status": resp.status_code,
            "fhir_server_url": target_url,
            "response": body,
        }
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail=f"FHIR server at {target_url} timed out",
        )
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to FHIR server at {target_url}: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"FHIR push failed: {exc}",
        )


@app.get("/fhir/capability")
async def fhir_capability() -> Dict[str, Any]:
    """
    Return a FHIR R4 CapabilityStatement describing Anukriti's FHIR-producing
    capabilities. Required by the FHIR specification for server registration
    and interoperability negotiation.
    """
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": "2026-04-16",
        "kind": "instance",
        "fhirVersion": "4.0.1",
        "format": ["json"],
        "software": {
            "name": "Anukriti PGx Engine",
            "version": "0.2.0",
        },
        "implementation": {
            "description": (
                "Anukriti virtual phase-0 pharmacogenomics safety simulation. "
                "Produces FHIR GenomicReport, Observation, and MedicationStatement "
                "resources from deterministic PGx calling."
            ),
        },
        "rest": [
            {
                "mode": "server",
                "resource": [
                    {
                        "type": "Bundle",
                        "interaction": [{"code": "create"}],
                        "profile": "http://hl7.org/fhir/StructureDefinition/Bundle",
                    },
                    {
                        "type": "DiagnosticReport",
                        "interaction": [{"code": "read"}, {"code": "search-type"}],
                        "profile": "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/genomic-report",
                    },
                    {
                        "type": "Observation",
                        "interaction": [{"code": "read"}],
                        "profile": "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/therapeutic-implication",
                    },
                ],
            }
        ],
    }


class ZervehackRetrieveRequest(BaseModel):
    query: str = Field(
        ..., description="Natural language query to retrieve evidence for."
    )
    top_k: int = Field(5, ge=1, le=20, description="Number of evidence rows to return.")
    min_confidence: float = Field(
        0.2,
        ge=0.0,
        le=1.0,
        description="Minimum top-score required to return evidence (safety gate).",
    )
    enforce_gating: bool = Field(
        True, description="If true, refuse to return evidence when confidence is low."
    )


@app.get("/zervehack/status")
async def zervehack_status() -> Dict[str, Any]:
    """
    ZerveHack-friendly status endpoint: shows retrieval backend mode + operational metrics.
    """
    from src.metrics import snapshot

    return {
        "retriever": get_retriever_status(),
        "vector": get_vector_backend_status(),
        "metrics": snapshot(),
    }


@app.post("/zervehack/retrieve")
async def zervehack_retrieve(req: ZervehackRetrieveRequest) -> Dict[str, Any]:
    """
    Retrieve CPIC-aligned evidence rows for a query and return both ids + content.
    """
    scored = retrieve_docs_scored(req.query, top_k=int(req.top_k))
    top_score = float(scored[0][1]) if scored else 0.0
    decision = "allow"
    message = "Evidence retrieved."
    if bool(req.enforce_gating) and top_score < float(req.min_confidence):
        decision = "refuse"
        message = (
            "Low evidence confidence: refusing to present evidence for this query. "
            "Try adding the drug/gene or a more specific question."
        )
        scored = []
    return {
        "query": req.query,
        "top_k": int(req.top_k),
        "retriever": get_retriever_status(),
        "confidence": {
            "decision": decision,
            "top_score": round(top_score, 4),
            "min_confidence": float(req.min_confidence),
        },
        "message": message,
        "docs": [
            {
                "doc_id": d.doc_id,
                "source": d.source,
                "key": d.key,
                "text": d.text,
                "score": round(float(score), 6),
            }
            for d, score in scored
        ],
    }


async def _cleanup_stale_uploads() -> None:
    """Background task: remove VCF upload sessions older than _VCF_UPLOAD_TTL."""
    import asyncio
    import shutil

    while True:
        await asyncio.sleep(3600)  # run every hour
        cutoff = time.time() - _VCF_UPLOAD_TTL
        stale = [
            uid
            for uid, info in list(_VCF_UPLOADS.items())
            if info.get("created_at", 0) < cutoff
        ]
        for uid in stale:
            info = _VCF_UPLOADS.pop(uid, None)
            if info:
                tmp_dir = os.path.dirname(info.get("vcf_path", ""))
                if tmp_dir and os.path.isdir(tmp_dir):
                    try:
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                    except Exception as exc:
                        logger.warning(
                            "Failed to cleanup stale upload dir %s: %s", tmp_dir, exc
                        )
        if stale:
            logger.info(f"Cleaned up {len(stale)} stale VCF upload session(s)")


@app.on_event("startup")
async def _start_background_tasks() -> None:
    import asyncio

    asyncio.create_task(_cleanup_stale_uploads())


# -----------------------------
# Simple in-memory job system
# -----------------------------
_JOBS: Dict[str, Dict[str, Any]] = {}

# TTL caches (in-memory)
_SAMPLES_CACHE: Dict[str, Dict[str, Any]] = {}
_PROFILE_CACHE: Dict[str, Dict[str, Any]] = {}
_EXPLANATION_CACHE: Dict[str, Dict[str, Any]] = {}


def _cache_get(
    cache: Dict[str, Dict[str, Any]], key: str, ttl_seconds: int
) -> Optional[Any]:
    item = cache.get(key)
    if not item:
        return None
    ts = float(item.get("ts", 0))
    if (time.time() - ts) > ttl_seconds:
        cache.pop(key, None)
        return None
    return item.get("val")


def _cache_set(cache: Dict[str, Dict[str, Any]], key: str, val: Any) -> None:
    cache[key] = {"ts": time.time(), "val": val}


@contextmanager
def _with_vcf_source_mode(mode: str):
    """
    Temporarily force vcf_processor discovery mode.
    Useful when request-level source should override process-level env.
    """
    prev = os.getenv("VCF_SOURCE_MODE")
    if mode:
        os.environ["VCF_SOURCE_MODE"] = mode
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("VCF_SOURCE_MODE", None)
        else:
            os.environ["VCF_SOURCE_MODE"] = prev


def _discover_paths_by_source(genomes_dir: str, source: str) -> Dict[str, str]:
    """
    Discover VCF paths according to a request-level source selector:
    - local: local filesystem only
    - s3: s3 discovery only
    - auto: local first, then s3 fallback
    """
    src = (source or "auto").strip().lower()
    if src == "local":
        return discover_local_vcf_paths(genomes_dir)
    if src == "s3":
        with _with_vcf_source_mode("s3"):
            return discover_vcf_paths(genomes_dir)
    # auto
    local = discover_local_vcf_paths(genomes_dir)
    if local:
        return local
    with _with_vcf_source_mode("s3"):
        return discover_vcf_paths(genomes_dir)


def _job_gc() -> None:
    """Garbage-collect old jobs to bound memory."""
    ttl = int(os.getenv("JOB_TTL_SECONDS", "900"))
    now = time.time()
    to_del = [
        jid for jid, j in _JOBS.items() if (now - float(j.get("created", now))) > ttl
    ]
    for jid in to_del:
        _JOBS.pop(jid, None)


class VcfProfileJobRequest(BaseModel):
    drug_name: str
    sample_id: str
    source: str = "auto"  # local | s3 | auto
    dataset_id: Optional[str] = None


def _generate_profile_sync(req: VcfProfileJobRequest) -> str:
    """
    Generate patient profile synchronously (shared by /vcf-profile and job runner).
    """
    ttl = int(os.getenv("VCF_PROFILE_CACHE_TTL", "900"))
    cache_key = f"profile:{req.source}:{req.dataset_id}:{req.sample_id}:{(req.drug_name or '').strip().lower()}"
    cached = _cache_get(_PROFILE_CACHE, cache_key, ttl)
    if isinstance(cached, str) and cached:
        return cached

    # dataset_id path: local/s3/upload
    if req.dataset_id:
        parsed = _parse_dataset_id(req.dataset_id)
        if not parsed:
            raise ValueError("Invalid dataset_id")
        src = parsed["source"]
        ref = parsed["ref"]
        if src == "upload":
            info = _VCF_UPLOADS.get(ref)
            if not info:
                raise ValueError("Upload session not found")
            vcf_path = info["vcf_path"]
            chrom = info.get("chrom", "chr22")
            vcf_paths_by_chrom = {chrom: vcf_path}
            profile = generate_patient_profile_from_vcf(
                vcf_path=vcf_path,
                sample_id=req.sample_id,
                drug_name=req.drug_name,
                vcf_paths_by_chrom=vcf_paths_by_chrom,
            )
            _cache_set(_PROFILE_CACHE, cache_key, profile)
            return profile
        if src in ("remote_all", "open_data_all"):
            _pgx_chroms = [
                "chr1",
                "chr2",
                "chr6",
                "chr7",
                "chr8",
                "chr10",
                "chr12",
                "chr15",
                "chr16",
                "chr19",
                "chr22",
            ]
            url_fn = (
                _aws_open_data_1000g_s3_url
                if src == "open_data_all"
                else _igsr_1000g_vcf_url
            )
            vcf_paths_by_chrom = {ch: url_fn(ch) for ch in _pgx_chroms}
            primary_vcf = vcf_paths_by_chrom["chr22"]
            profile = generate_patient_profile_from_vcf(
                vcf_path=primary_vcf,
                sample_id=req.sample_id,
                drug_name=req.drug_name,
                vcf_paths_by_chrom=vcf_paths_by_chrom,
            )
            _cache_set(_PROFILE_CACHE, cache_key, profile)
            return profile
        if src == "remote":
            chrom = _guess_chrom_from_name(ref)
            vcf_paths_by_chrom = {chrom: ref}
            profile = generate_patient_profile_from_vcf(
                vcf_path=ref,
                sample_id=req.sample_id,
                drug_name=req.drug_name,
                vcf_paths_by_chrom=vcf_paths_by_chrom,
            )
            _cache_set(_PROFILE_CACHE, cache_key, profile)
            return profile
        chrom = _guess_chrom_from_name(ref)
        vcf_paths_by_chrom = {chrom: ref}
        profile = generate_patient_profile_from_vcf(
            vcf_path=ref,
            sample_id=req.sample_id,
            drug_name=req.drug_name,
            vcf_paths_by_chrom=vcf_paths_by_chrom,
        )
        _cache_set(_PROFILE_CACHE, cache_key, profile)
        return profile

    # default discovery path
    app_root = os.path.dirname(os.path.abspath(__file__))
    genomes_dir = os.path.join(app_root, "data", "genomes")
    src = (req.source or "auto").strip().lower()
    vcf_paths = _discover_paths_by_source(genomes_dir, src)
    if not vcf_paths:
        raise ValueError("No VCF files found")
    primary_vcf = vcf_paths.get("chr22") or next(iter(vcf_paths.values()))
    profile = generate_patient_profile_from_vcf(
        vcf_path=primary_vcf,
        sample_id=req.sample_id,
        drug_name=req.drug_name,
        vcf_paths_by_chrom=vcf_paths,
    )
    _cache_set(_PROFILE_CACHE, cache_key, profile)
    return profile


def _run_vcf_profile_job(job_id: str, req: VcfProfileJobRequest) -> None:
    job = _JOBS.get(job_id)
    if not job:
        return
    job["status"] = "running"
    job["updated"] = time.time()
    job["message"] = "Generating patient profile"
    try:
        profile = _generate_profile_sync(req)
        job["status"] = "succeeded"
        job["result"] = {"patient_profile": profile, "sample_id": req.sample_id}
        job["message"] = "Done"
    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        job["message"] = "Failed"
    finally:
        job["updated"] = time.time()


@app.post("/jobs/vcf-profile")
async def create_vcf_profile_job(
    body: VcfProfileJobRequest, background: BackgroundTasks
):
    _job_gc()
    job_id = uuid.uuid4().hex
    _JOBS[job_id] = {
        "id": job_id,
        "type": "vcf-profile",
        "status": "queued",
        "created": time.time(),
        "updated": time.time(),
        "message": "Queued",
    }
    background.add_task(_run_vcf_profile_job, job_id, body)
    return {"job_id": job_id, "status": "queued"}


class PopulationSimJobRequest(BaseModel):
    cohort_size: int = Field(default=100, ge=10, le=10000)
    drug: str = Field(default="Warfarin")
    population_mix: Optional[Dict[str, float]] = None


def _run_population_sim_job(job_id: str, req: PopulationSimJobRequest) -> None:
    job = _JOBS.get(job_id)
    if not job:
        return
    job["status"] = "running"
    job["updated"] = time.time()
    job["message"] = "Simulating cohort"
    try:
        population_mix = req.population_mix or {
            "AFR": 0.25,
            "EUR": 0.40,
            "EAS": 0.20,
            "SAS": 0.10,
            "AMR": 0.05,
        }
        out = _run_population_simulation(
            cohort_size=req.cohort_size,
            drug=req.drug,
            population_mix=population_mix,
        )
        job["status"] = "succeeded"
        job["result"] = out
        job["message"] = "Done"
    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        job["message"] = "Failed"
    finally:
        job["updated"] = time.time()


@app.post("/jobs/population-simulate")
async def create_population_sim_job(
    body: PopulationSimJobRequest, background: BackgroundTasks
):
    _job_gc()
    job_id = uuid.uuid4().hex
    _JOBS[job_id] = {
        "id": job_id,
        "type": "population-simulate",
        "status": "queued",
        "created": time.time(),
        "updated": time.time(),
        "message": "Queued",
    }
    background.add_task(_run_population_sim_job, job_id, body)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    _job_gc()
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _guess_chrom_from_name(name: str) -> str:
    """Infer chromosome key from a filename or URL. Longer suffixes first to avoid
    'chr1' matching 'chr10' etc."""
    chrom_guess = "chr22"
    for c in (
        "chr22",
        "chr19",
        "chr16",
        "chr15",
        "chr12",
        "chr11",
        "chr10",
        "chr8",
        "chr7",
        "chr6",
        "chr2",
        "chr1",
    ):
        if c in (name or ""):
            return c
    return chrom_guess


def _dataset_id(source: str, ref: str) -> str:
    # Not used for security; just a stable short identifier for UI dataset selection.
    h = hashlib.sha1(  # nosec B324 - not used for security
        f"{source}|{ref}".encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()[:16]
    return f"{source}|{h}|{ref}"


def _parse_dataset_id(dataset_id: str) -> Optional[Dict[str, str]]:
    """
    Parse dataset_id created by _dataset_id(source, ref).
    Returns dict with source and ref (path/s3-url/upload-id).
    """
    if not dataset_id:
        return None
    parts = dataset_id.split("|", 2)
    if len(parts) != 3:
        return None
    source, _h, ref = parts
    return {"source": source, "ref": ref}


def _igsr_1000g_vcf_url(chrom: str) -> str:
    """
    Remote 1000 Genomes Phase 3 VCF URL (IGSR) for streaming via tabix HTTP range requests.
    """
    # Phase 3 integrated callset filenames
    base = os.getenv(
        "IGSR_1000G_BASE_URL",
        "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502",
    ).rstrip("/")
    c = chrom.lower().replace("chr", "")
    return f"{base}/ALL.chr{c}.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz"


def _aws_open_data_1000g_s3_url(chrom: str) -> str:
    """
    AWS Open Data 1000 Genomes bucket path (public, us-east-1).
    Uses the same Phase 3 integrated callset filenames.
    """
    prefix = (
        os.getenv("AWS_1000G_RELEASE_PREFIX", "release/20130502").strip().strip("/")
    )
    c = chrom.lower().replace("chr", "")
    key = f"{prefix}/ALL.chr{c}.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz"
    # Use HTTPS endpoint so tabix can stream via HTTP range requests (no full download).
    return f"https://1000genomes.s3.amazonaws.com/{key}"


@app.get("/vcf-datasets")
async def vcf_datasets(source: str = "auto"):
    """
    List available VCF datasets for selection in the UI.

    source=local: enumerate data/genomes/*.vcf.gz
    source=s3: enumerate S3 genomes keys (may be slower)
    source=auto: local first, fallback to s3
    """
    app_root = os.path.dirname(os.path.abspath(__file__))
    genomes_dir = os.path.join(app_root, "data", "genomes")
    src = (source or "auto").strip().lower()

    out: List[Dict[str, Any]] = []

    def _add_local():
        if not os.path.isdir(genomes_dir):
            return
        for name in os.listdir(genomes_dir):
            if not name.endswith(".vcf.gz"):
                continue
            path = os.path.join(genomes_dir, name)
            if not os.path.isfile(path):
                continue
            chrom = _guess_chrom_from_name(name)
            out.append(
                {
                    "dataset_id": _dataset_id("local", os.path.abspath(path)),
                    "source": "local",
                    "chrom": chrom,
                    "label": name,
                }
            )

    def _add_s3():
        try:
            from src.aws.s3_genomic_manager import S3GenomicDataManager

            bucket_name = os.getenv("AWS_S3_BUCKET_GENOMIC", "synthatrial-genomic-data")
            if not (bucket_name and os.getenv("AWS_ACCESS_KEY_ID")):
                return
            s3_manager = S3GenomicDataManager(bucket_name)
            if not s3_manager.s3_client:
                return
            files = s3_manager.list_vcf_files()
            for fi in files:
                key = fi.get("key", "")
                chrom = _guess_chrom_from_name(key)
                s3_url = f"s3://{bucket_name}/{key}"
                out.append(
                    {
                        "dataset_id": _dataset_id("s3", s3_url),
                        "source": "s3",
                        "chrom": chrom,
                        "label": key,
                    }
                )
        except Exception as e:
            logger.warning(f"S3 dataset listing failed: {e}")

    _PGX_CHROMS = [
        "chr1",
        "chr2",
        "chr6",
        "chr7",
        "chr8",
        "chr10",
        "chr12",
        "chr15",
        "chr16",
        "chr19",
        "chr22",
    ]

    def _add_remote():
        # Remote 1000G via IGSR (streamed with tabix; no full downloads)
        out.append(
            {
                "dataset_id": _dataset_id("remote_all", "all_pgx"),
                "source": "remote_all",
                "chrom": "all_pgx",
                "label": "IGSR 1000G Phase3 — All PGx Chromosomes (16 genes)",
            }
        )
        for ch in _PGX_CHROMS:
            url = _igsr_1000g_vcf_url(ch)
            out.append(
                {
                    "dataset_id": _dataset_id("remote", url),
                    "source": "remote",
                    "chrom": ch,
                    "label": f"IGSR 1000G Phase3 {ch}",
                }
            )

    def _add_open_data():
        # AWS Open Data (public S3 bucket: s3://1000genomes)
        out.append(
            {
                "dataset_id": _dataset_id("open_data_all", "all_pgx"),
                "source": "open_data_all",
                "chrom": "all_pgx",
                "label": "AWS Open Data 1000G Phase3 — All PGx Chromosomes (16 genes)",
            }
        )
        for ch in _PGX_CHROMS:
            url = _aws_open_data_1000g_s3_url(ch)
            out.append(
                {
                    "dataset_id": _dataset_id("open_data", url),
                    "source": "open_data",
                    "chrom": ch,
                    "label": f"AWS Open Data 1000G Phase3 {ch}",
                }
            )

    if src == "local":
        _add_local()
    elif src == "s3":
        _add_s3()
    elif src in {"remote", "igsr"}:
        _add_remote()
    elif src in {"open_data", "aws_open_data", "aws"}:
        _add_open_data()
    else:
        _add_local()
        if not out:
            _add_s3()
        # Always include remote datasets as a fallback option
        _add_remote()
        _add_open_data()

    # Also include active upload sessions (best-effort)
    for upload_id, info in list(_VCF_UPLOADS.items()):
        out.append(
            {
                "dataset_id": _dataset_id("upload", upload_id),
                "source": "upload",
                "chrom": info.get("chrom", "chr22"),
                "label": os.path.basename(info.get("vcf_path", "upload.vcf.gz")),
            }
        )

    return {"datasets": out}


@app.get("/vcf-datasets/streaming-status")
async def vcf_streaming_status():
    """
    Probe the 1000 Genomes AWS Open Data HTTPS endpoint.

    Returns live latency and availability for HTTPS tabix streaming.
    No local download is required — tabix streams via HTTP range requests.
    The 1000 Genomes dataset is part of the AWS Open Data Program (zero egress
    charges in us-east-1). This endpoint is used by the demo UI to show the
    live streaming banner.
    """
    from src.vcf_processor import (
        get_1000genomes_streaming_paths,
        probe_1000genomes_streaming,
    )

    probe = probe_1000genomes_streaming(timeout=8)
    streaming_paths = get_1000genomes_streaming_paths()
    return {
        "streaming_available": probe.get("available", False),
        "latency_ms": probe.get("latency_ms"),
        "probe_url": probe.get("url"),
        "error": probe.get("error"),
        "source": "AWS Open Data Program — 1000 Genomes Phase 3",
        "cost": "$0 — no egress charges (AWS Open Data)",
        "mode": "HTTPS tabix range requests — no local download required",
        "chromosomes_available": list(streaming_paths.keys()),
        "genes_covered": [
            "CYP2D6 (chr22)",
            "GSTT1 (chr22)",
            "CYP2C19 (chr10)",
            "CYP2C9 (chr10)",
            "CYP3A4 (chr7)",
            "CYP3A5 (chr7)",
            "CYP1A2 (chr15)",
            "CYP2B6 (chr19)",
            "NAT2 (chr8)",
            "UGT1A1 (chr2)",
            "SLCO1B1 (chr12)",
            "VKORC1 (chr16)",
            "TPMT (chr6)",
            "HLA-B*5701 (chr6)",
            "DPYD (chr1)",
            "GSTM1 (chr1)",
        ],
    }


def _ensure_tabix_index(vcf_path: str) -> None:
    """
    Ensure a .tbi index exists for a bgzipped VCF.
    Uses `tabix -p vcf` to create the index if missing.
    """
    tbi_path = vcf_path + ".tbi"
    if os.path.exists(tbi_path):
        return
    try:
        subprocess.run(  # nosec B603 B607
            ["tabix", "-f", "-p", "vcf", vcf_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail="tabix is required on the server to index uploaded VCFs.",
        ) from e
    except subprocess.TimeoutExpired as e:
        raise HTTPException(
            status_code=500,
            detail="Indexing timed out while running tabix on uploaded VCF.",
        ) from e
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or "").strip()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to index VCF with tabix. Ensure it is bgzipped and sorted. {msg}",
        ) from e


@app.get("/vcf-samples")
async def vcf_samples(
    source: str = "auto", chrom: str = "chr22", dataset_id: Optional[str] = None
):
    """
    Get sample IDs from available VCF files.

    Query params:
    - source: local | s3 | auto (default auto)
    - chrom: which chromosome VCF to use when present (default chr22)
    """
    if dataset_id:
        ttl = int(os.getenv("VCF_SAMPLES_CACHE_TTL", "300"))
        cache_key = f"dataset:{dataset_id}:samples"
        cached = _cache_get(_SAMPLES_CACHE, cache_key, ttl)
        if cached:
            return cached
        parsed = _parse_dataset_id(dataset_id)
        if not parsed:
            raise HTTPException(status_code=400, detail="Invalid dataset_id")
        src = parsed["source"]
        ref = parsed["ref"]
        if src == "upload":
            info = _VCF_UPLOADS.get(ref)
            if not info:
                raise HTTPException(status_code=404, detail="Upload session not found")
            vcf_path = info["vcf_path"]
            samples = get_sample_ids_from_vcf(vcf_path, limit=50)
            out = {
                "samples": samples,
                "vcf_available": True,
                "vcf_source": "upload",
                "chromosomes": [info.get("chrom", "chr22")],
            }
            _cache_set(_SAMPLES_CACHE, cache_key, out)
            return out
        if src in ("remote_all", "open_data_all"):
            _PGX_CHROMS_LIST = [
                "chr1",
                "chr2",
                "chr6",
                "chr7",
                "chr8",
                "chr10",
                "chr12",
                "chr15",
                "chr16",
                "chr19",
                "chr22",
            ]
            probe_url = (
                _aws_open_data_1000g_s3_url("chr22")
                if src == "open_data_all"
                else _igsr_1000g_vcf_url("chr22")
            )
            samples = get_sample_ids_from_vcf(probe_url, limit=50)
            out = {
                "samples": samples,
                "vcf_available": bool(samples),
                "vcf_source": src,
                "chromosomes": _PGX_CHROMS_LIST,
            }
            _cache_set(_SAMPLES_CACHE, cache_key, out)
            return out
        if src == "remote":
            # Stream header/sample IDs via tabix -H over HTTPS URL
            samples = get_sample_ids_from_vcf(ref, limit=50)
            out = {
                "samples": samples,
                "vcf_available": True,
                "vcf_source": "remote",
                "chromosomes": [_guess_chrom_from_name(ref)],
            }
            _cache_set(_SAMPLES_CACHE, cache_key, out)
            return out
        vcf_path = ref
        samples = get_sample_ids_from_vcf(vcf_path, limit=50)
        out = {
            "samples": samples,
            "vcf_available": True,
            "vcf_source": src,
            "chromosomes": [_guess_chrom_from_name(ref)],
        }
        _cache_set(_SAMPLES_CACHE, cache_key, out)
        return out

    app_root = os.path.dirname(os.path.abspath(__file__))
    genomes_dir = os.path.join(app_root, "data", "genomes")
    ttl = int(os.getenv("VCF_SAMPLES_CACHE_TTL", "300"))
    cache_key = f"src:{source}:chrom:{chrom}"
    cached = _cache_get(_SAMPLES_CACHE, cache_key, ttl)
    if cached:
        return cached
    src = (source or "auto").strip().lower()
    vcf_source = "local"
    vcf_paths = _discover_paths_by_source(genomes_dir, src)
    vcf_source = (
        "s3" if any(p.startswith("s3://") for p in vcf_paths.values()) else "local"
    )
    if not vcf_paths:
        # Fallback: try remote 1000 Genomes via tabix HTTP range request
        try:
            from src.remote_vcf import get_remote_sample_ids

            remote_samples = get_remote_sample_ids("chr22", limit=50)
            if remote_samples:
                return {
                    "samples": remote_samples,
                    "vcf_available": True,
                    "vcf_source": "remote_1000genomes",
                    "chromosomes": ["chr22"],
                }
        except Exception as e:
            logger.warning(f"Remote sample fetch failed: {e}")
        return {"samples": [], "vcf_available": False, "message": "No VCF files found"}
    chrom_key = chrom if chrom.startswith("chr") else f"chr{chrom}"
    vcf_path = (
        vcf_paths.get(chrom_key)
        or vcf_paths.get("chr22")
        or next(iter(vcf_paths.values()))
    )
    try:
        samples = get_sample_ids_from_vcf(vcf_path, limit=50)
        out = {
            "samples": samples,
            "vcf_available": True,
            "vcf_source": vcf_source,
            "chromosomes": list(vcf_paths.keys()),
        }
        _cache_set(_SAMPLES_CACHE, cache_key, out)
        return out
    except Exception as e:
        logger.error(f"Failed to get VCF samples: {e}")
        return {"samples": [], "vcf_available": True, "error": str(e)}


@app.post("/vcf-profile")
async def vcf_profile(
    body: VcfProfileRequest, source: str = "auto", dataset_id: Optional[str] = None
):
    """
    Generate patient profile from VCF data.

    Query params:
    - source: local | s3 | auto (default auto)
    """
    try:
        profile = _generate_profile_sync(
            VcfProfileJobRequest(
                drug_name=body.drug_name,
                sample_id=body.sample_id,
                source=source,
                dataset_id=dataset_id,
            )
        )
        return {"patient_profile": profile, "sample_id": body.sample_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"VCF profile generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vcf-upload-samples")
async def vcf_upload_samples(
    vcf: UploadFile = File(...),
    tbi: UploadFile = File(...),
    _auth: None = Depends(verify_api_key),
):
    """
    Upload a bgzipped VCF (.vcf.gz) plus its tabix index (.tbi), then return sample IDs.
    Intended for Streamlit VCF upload workflows.
    """
    upload_id = uuid.uuid4().hex
    tmp_dir = os.path.join(tempfile.gettempdir(), f"anukriti_upload_{upload_id}")
    os.makedirs(tmp_dir, exist_ok=True)

    vcf_name = os.path.basename(vcf.filename or "upload.vcf.gz")

    # Read first bytes for magic-byte check before writing to disk
    first_chunk = await vcf.read(2)
    validate_vcf_upload(vcf_name, first_chunk, vcf.size)
    remaining = await vcf.read()
    vcf_bytes = first_chunk + remaining

    if len(vcf_bytes) > MAX_VCF_BYTES:
        raise HTTPException(
            status_code=413, detail="VCF file exceeds maximum allowed size."
        )

    vcf_path = os.path.join(tmp_dir, vcf_name)
    tbi_path = vcf_path + ".tbi"

    try:
        with open(vcf_path, "wb") as f:
            f.write(vcf_bytes)
        with open(tbi_path, "wb") as f:
            f.write(await tbi.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

    chrom_guess = "chr22"
    for c in ("chr22", "chr10", "chr2", "chr12", "chr16", "chr6", "chr11", "chr19"):
        if c in vcf_name:
            chrom_guess = c
            break

    _VCF_UPLOADS[upload_id] = {
        "vcf_path": vcf_path,
        "chrom": chrom_guess,
        "created_at": time.time(),
    }
    try:
        samples = get_sample_ids_from_vcf(vcf_path, limit=50)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Could not read sample IDs from VCF: {e}"
        )

    return {
        "upload_id": upload_id,
        "chrom": chrom_guess,
        "samples": samples,
        "vcf_filename": vcf_name,
    }


@app.post("/vcf-upload")
async def vcf_upload(
    vcf: UploadFile = File(...), _auth: None = Depends(verify_api_key)
):
    """
    Upload a bgzipped VCF (.vcf.gz) and build its tabix index server-side.
    Returns upload_id + sample IDs.
    """
    upload_id = uuid.uuid4().hex
    tmp_dir = os.path.join(tempfile.gettempdir(), f"anukriti_upload_{upload_id}")
    os.makedirs(tmp_dir, exist_ok=True)

    vcf_name = os.path.basename(vcf.filename or "upload.vcf.gz")

    # Read first bytes for magic-byte check before writing to disk
    first_chunk = await vcf.read(2)
    validate_vcf_upload(vcf_name, first_chunk, vcf.size)
    remaining = await vcf.read()
    vcf_bytes = first_chunk + remaining

    if len(vcf_bytes) > MAX_VCF_BYTES:
        raise HTTPException(
            status_code=413, detail="VCF file exceeds maximum allowed size."
        )
    vcf_path = os.path.join(tmp_dir, vcf_name)

    try:
        with open(vcf_path, "wb") as f:
            f.write(vcf_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

    _ensure_tabix_index(vcf_path)

    chrom_guess = "chr22"
    for c in ("chr22", "chr10", "chr2", "chr12", "chr16", "chr6", "chr11", "chr19"):
        if c in vcf_name:
            chrom_guess = c
            break

    _VCF_UPLOADS[upload_id] = {
        "vcf_path": vcf_path,
        "chrom": chrom_guess,
        "created_at": time.time(),
    }
    try:
        samples = get_sample_ids_from_vcf(vcf_path, limit=50)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Could not read sample IDs from VCF: {e}"
        )

    return {
        "upload_id": upload_id,
        "chrom": chrom_guess,
        "samples": samples,
        "vcf_filename": vcf_name,
        "indexed": True,
    }


@app.delete("/vcf-upload/{upload_id}")
async def delete_vcf_upload(upload_id: str):
    """Delete an uploaded VCF session from server temp storage."""
    info = _VCF_UPLOADS.pop(upload_id, None)
    if not info:
        raise HTTPException(status_code=404, detail="Upload session not found")
    vcf_path = info.get("vcf_path")
    if vcf_path:
        tmp_dir = os.path.dirname(vcf_path)
        # Best-effort cleanup
        for p in (vcf_path, vcf_path + ".tbi"):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except OSError as e:
                logger.debug(f"Failed to remove upload file {p}: {e}")
        try:
            if tmp_dir and os.path.isdir(tmp_dir):
                os.rmdir(tmp_dir)
        except OSError as e:
            logger.debug(f"Failed to remove upload temp dir {tmp_dir}: {e}")
    return {"status": "deleted", "upload_id": upload_id}


@app.post("/vcf-upload-profile")
async def vcf_upload_profile(body: VcfUploadProfileRequest):
    """Generate patient profile from an uploaded VCF session."""
    info = _VCF_UPLOADS.get(body.upload_id)
    if not info:
        raise HTTPException(
            status_code=404, detail="Upload session not found. Re-upload VCF."
        )

    vcf_path = info["vcf_path"]
    chrom = info.get("chrom", "chr22")
    vcf_paths_by_chrom = {chrom: vcf_path}
    try:
        profile = generate_patient_profile_from_vcf(
            vcf_path=vcf_path,
            sample_id=body.sample_id,
            drug_name=body.drug_name,
            vcf_paths_by_chrom=vcf_paths_by_chrom,
        )
        return {"patient_profile": profile, "sample_id": body.sample_id, "chrom": chrom}
    except Exception as e:
        logger.error(f"Uploaded VCF profile generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_ehr_bundle(
    *,
    drug_name: str,
    patient_profile: str,
    risk_level: Optional[str],
    pgx_structured: Optional[Dict[str, Any]],
    backend: str,
    model_id: str,
) -> Dict[str, Any]:
    """
    Build a small FHIR-like Bundle for export (not a strict FHIR implementation).
    Intended for hackathon/demo EHR-style portability.
    """
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    patient_id = None
    for ln in (patient_profile or "").splitlines():
        if ln.strip().lower().startswith("id:"):
            patient_id = ln.split(":", 1)[-1].strip()
            break
    patient_id = patient_id or "UNKNOWN"

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": now_iso,
        "entry": [
            {"resource": {"resourceType": "Patient", "id": patient_id}},
            {
                "resource": {
                    "resourceType": "Medication",
                    "id": f"med-{drug_name.lower().replace(' ', '-')}",
                    "code": {"text": drug_name},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": f"pgx-risk-{patient_id}",
                    "status": "final",
                    "category": [{"text": "pharmacogenomics"}],
                    "code": {"text": "PGx risk summary"},
                    "valueString": risk_level or "Unknown",
                    "note": [
                        {
                            "text": "Research prototype output. Deterministic PGx engine decides; LLM explains."
                        }
                    ],
                }
            },
            {
                "resource": {
                    "resourceType": "DiagnosticReport",
                    "id": f"pgx-report-{patient_id}",
                    "status": "final",
                    "code": {"text": "Pharmacogenomics report"},
                    "conclusion": risk_level or "Unknown",
                    "presentedForm": [
                        {
                            "contentType": "application/json",
                            "data": {
                                "patient_profile": patient_profile,
                                "pgx_structured": pgx_structured,
                                "backend": backend,
                                "model": model_id,
                            },
                        }
                    ],
                }
            },
        ],
    }


def _build_analysis_proof_payload(
    *,
    result: str,
    risk_level: Optional[str],
    drug_name: str,
    status: str,
    similar_drugs_used: Optional[List[str]],
    genetics_summary: Optional[str],
    context_sources: Optional[str],
    pgx_structured: Optional[Dict[str, Any]],
    audit: Optional[Dict[str, Any]],
    ehr_bundle: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the exact single-simulation artifact we attest.

    This is intentionally the same public response surface minus the attestation
    block itself. If a downstream reviewer changes the risk, explanation,
    structured PGx, model metadata, or export bundle, verification fails.
    """

    return {
        "result": result,
        "risk_level": risk_level,
        "drug_name": drug_name,
        "status": status,
        "similar_drugs_used": similar_drugs_used,
        "genetics_summary": genetics_summary,
        "context_sources": context_sources,
        "pgx_structured": pgx_structured,
        "audit": audit,
        "ehr_bundle": ehr_bundle,
    }


def _build_analysis_attestation(**payload_kwargs: Any) -> Dict[str, Any]:
    """Build a simulation-result attestation from AnalyzeResponse fields."""

    return build_simulation_result_attestation(
        _build_analysis_proof_payload(**payload_kwargs)
    )


def _risk_level_with_pgx_fallback(
    result_text: str, pgx_structured: Optional[Dict[str, Any]]
) -> Optional[str]:
    """Prefer deterministic PGx risk; fall back to LLM text only if absent."""
    if pgx_structured:
        dr = pgx_structured.get("risk_level")
        if dr is not None and str(dr).strip():
            parsed = extract_risk_level(f"RISK LEVEL: {dr}")
            if parsed:
                return parsed
    rl = extract_risk_level(result_text)
    if rl:
        return rl
    return None


def _is_hla_proxy_positive(phen: Optional[str]) -> bool:
    if not phen:
        return False
    return "positive" in phen.lower()


def _apply_explanation_grounding(
    pgx_structured: Optional[Dict[str, Any]],
    explanation: str,
    retrieved_docs: List[str],
) -> Optional[Dict[str, Any]]:
    """Agent 5: overlap of explanation sentences vs retrieved CPIC/RAG chunks (no extra LLM)."""
    if pgx_structured is None:
        return None
    out = dict(pgx_structured)
    out["grounding"] = compute_explanation_grounding(explanation, retrieved_docs)
    return out


def _ensure_deterministic_risk_preamble(
    result_text: str, pgx_structured: Optional[Dict[str, Any]]
) -> str:
    """Prepend RISK LEVEL from engine when LLM text omits it (Gemini/Claude paths)."""
    if not pgx_structured:
        return result_text
    dr = pgx_structured.get("risk_level")
    if dr is None or not str(dr).strip():
        return result_text
    if os.getenv("SYNTHATRIAL_PIN_DETERMINISTIC_HEADER", "true").lower() not in (
        "1",
        "true",
        "yes",
    ):
        return result_text
    t = (result_text or "").strip()
    if t.upper().startswith("RISK LEVEL:"):
        return result_text
    return f"RISK LEVEL: {dr}\n\n{result_text}"


def _run_single_simulation(
    request: AnalyzeRequest, similar_drugs: List[str], backend: str
) -> tuple[str, Optional[str], Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Run a single drug-patient simulation. Respects LLM_BACKEND (bedrock vs gemini).
    Returns (result, risk_level, pgx_structured, genetics_summary, llm_failure_hint).
    llm_failure_hint is set when Bedrock/Nova returned a fallback instead of an LLM explanation.
    """
    nv = _normalize_nova_variant(getattr(request, "nova_variant", None))
    llm_failure_hint: Optional[str] = None
    genetics_summary = None
    for line in (request.patient_profile or "").splitlines():
        line = line.strip()
        if line.lower().startswith("genetics:"):
            genetics_summary = line.replace("Genetics:", "").strip()
            break

    def _slco_pheno_from_profile(profile: str) -> Optional[str]:
        for ln in (profile or "").splitlines():
            ln_clean = ln.strip()
            if "SLCO1B1:" in ln_clean:
                return ln_clean.split("SLCO1B1:")[-1].strip()
        return None

    def _map_pheno_to_genotype(pheno: str) -> str:
        p = (pheno or "").lower()
        if "poor" in p:
            return "CC"
        if "decreased" in p:
            return "TC"
        return "TT"

    def _extract_gene_pheno(profile: str, gene: str) -> Optional[str]:
        for ln in (profile or "").splitlines():
            ln_clean = ln.strip()
            if f"{gene}:" in ln_clean:
                return ln_clean.split(f"{gene}:")[-1].strip()
        return None

    def _pheno_to_tpmt_variants(pheno: str) -> Dict[str, str]:
        p = (pheno or "").lower()
        if "poor" in p:
            return {"rs1800460": "C", "rs1142345": "C"}
        if "intermediate" in p:
            return {"rs1800460": "C"}
        return {}

    def _pheno_to_dpyd_variants(pheno: str) -> Dict[str, str]:
        p = (pheno or "").lower()
        if "poor" in p:
            return {"rs3918290": "T"}
        if "intermediate" in p:
            return {"rs67376798": "T"}
        return {}

    drug_lower = (request.drug_name or "").strip().lower()

    hla_b1502_result: Optional[Dict[str, Any]] = None
    if drug_lower in {"carbamazepine", "oxcarbazepine", "phenytoin"}:
        _hp = _extract_gene_pheno(request.patient_profile, "HLA_B1502")
        if _hp:
            hla_b1502_result = interpret_hla_b1502_anticonvulsant(
                _is_hla_proxy_positive(_hp), drug_lower
            )

    hla_b5701_result: Optional[Dict[str, Any]] = None
    if drug_lower == "abacavir":
        _hb = _extract_gene_pheno(request.patient_profile, "HLA_B5701")
        if _hb:
            hla_b5701_result = interpret_hla_b5701_abacavir(_is_hla_proxy_positive(_hb))

    slco_pheno = _slco_pheno_from_profile(request.patient_profile)
    slco_result: Optional[Dict[str, Any]] = None
    if drug_lower in {"simvastatin", "atorvastatin", "rosuvastatin"} and slco_pheno:
        slco_geno = _map_pheno_to_genotype(slco_pheno)
        slco_result = interpret_slco1b1(slco_geno, request.drug_name)

    # TPMT PGx for thiopurines
    tpmt_result: Optional[Dict[str, Any]] = None
    if drug_lower in {"azathioprine", "mercaptopurine", "thioguanine"}:
        tpmt_pheno = _extract_gene_pheno(request.patient_profile, "TPMT")
        if tpmt_pheno:
            tpmt_variants = _pheno_to_tpmt_variants(tpmt_pheno)
            tpmt_result = interpret_tpmt(tpmt_variants, drug_name=drug_lower)

    # DPYD PGx for fluoropyrimidines
    dpyd_result: Optional[Dict[str, Any]] = None
    if drug_lower in {"fluorouracil", "capecitabine", "tegafur"}:
        dpyd_pheno = _extract_gene_pheno(request.patient_profile, "DPYD")
        if dpyd_pheno:
            dpyd_variants = _pheno_to_dpyd_variants(dpyd_pheno)
            dpyd_result = interpret_dpyd(dpyd_variants, drug_name=drug_lower)

    # CYP3A5 PGx for tacrolimus/calcineurin inhibitors (CPIC Level A)
    cyp3a5_result: Optional[Dict[str, Any]] = None
    if drug_lower in {"tacrolimus", "cyclosporine", "midazolam", "fentanyl"}:
        cyp3a5_result = interpret_cyp3a5({}, drug_name=drug_lower)

    # CYP3A4 PGx for broader substrate list
    cyp3a4_result: Optional[Dict[str, Any]] = None
    if drug_lower in {"simvastatin", "atorvastatin", "lovastatin", "alprazolam"}:
        cyp3a4_result = interpret_cyp3a4({}, drug_name=drug_lower)

    # CYP1A2 PGx for antipsychotics and xanthines (CPIC Level B)
    cyp1a2_result: Optional[Dict[str, Any]] = None
    if drug_lower in {
        "clozapine",
        "olanzapine",
        "theophylline",
        "caffeine",
        "tizanidine",
        "duloxetine",
    }:
        cyp1a2_result = interpret_cyp1a2({}, drug_name=drug_lower)

    # CYP2B6 PGx for efavirenz and antidepressants (CPIC Level A)
    cyp2b6_result: Optional[Dict[str, Any]] = None
    if drug_lower in {"efavirenz", "bupropion", "methadone", "nevirapine"}:
        cyp2b6_result = interpret_cyp2b6({}, drug_name=drug_lower)

    # NAT2 PGx for isoniazid and sulfonamides (CPIC Level A)
    nat2_result: Optional[Dict[str, Any]] = None
    if drug_lower in {
        "isoniazid",
        "sulfamethoxazole",
        "hydralazine",
        "procainamide",
        "dapsone",
    }:
        nat2_result = interpret_nat2({}, drug_name=drug_lower)

    # Use the most specific PGx result available — HLA hypersensitivity first, then CPIC callers
    specific_pgx = (
        hla_b1502_result
        or hla_b5701_result
        or slco_result
        or tpmt_result
        or dpyd_result
        or cyp3a5_result
        or cyp2b6_result
        or nat2_result
        or cyp1a2_result
        or cyp3a4_result
    )

    pgx_structured: Optional[Dict[str, Any]] = None
    if backend == "bedrock" and specific_pgx:
        # ---------- Explanation cache (long-lived, app-level) ----------
        cache_ttl = int(os.getenv("EXPLANATION_CACHE_TTL", "3600"))
        model_id = config.CLAUDE_MODEL
        cache_key = _safe_cache_key = "|".join(
            [
                "pgx-expl",
                backend,
                model_id,
                str(specific_pgx.get("gene", "")),
                str(specific_pgx.get("genotype", "")),
                str(specific_pgx.get("phenotype", "")),
                str(specific_pgx.get("risk", "")),
                str(specific_pgx.get("recommendation", "")),
            ]
        )
        cached = _cache_get(_EXPLANATION_CACHE, _safe_cache_key, cache_ttl)
        if cached:
            # Cache hit: reuse explanation + structured PGx without another Bedrock call
            return (
                cached["result"],
                cached["risk_level"],
                cached["pgx_structured"],
                genetics_summary,
                None,
            )

        query = f"{specific_pgx.get('gene', '')} {request.drug_name} pharmacogenomics"
        docs = retrieve(query, top_k=3)
        context = (
            "\n\n".join(docs)
            if docs
            else (
                f"{specific_pgx.get('gene', 'PGx')} background; use only conservative, "
                "guideline-aligned reasoning."
            )
        )
        try:
            explanation = generate_pgx_response(
                context=context, query=query, pgx_data=specific_pgx
            )
            pgx_structured = _apply_explanation_grounding(
                format_output(specific_pgx, explanation),
                explanation,
                docs,
            )
            result = explanation
        except Exception as e:
            # Resilience: if Bedrock is throttled/unavailable, still return deterministic PGx
            logger.warning(
                f"Bedrock explanation failed; returning deterministic-only: {e}"
            )
            llm_failure_hint = _bedrock_failure_hint(e)
            expl_fb = f"LLM explanation unavailable. {llm_failure_hint}"
            pgx_structured = _apply_explanation_grounding(
                format_output(specific_pgx, expl_fb),
                expl_fb,
                docs,
            )
            result = (
                f"RISK LEVEL: {specific_pgx.get('risk','Unknown')}\n\n"
                f"PREDICTED REACTION:\nDeterministic PGx signal for {specific_pgx.get('gene','PGx')}. "
                f"{llm_failure_hint}\n\n"
                f"BIOLOGICAL MECHANISM:\nLLM explanation unavailable.\n\n"
                f"DOSING IMPLICATION:\n{specific_pgx.get('recommendation','See deterministic recommendation.')}\n"
            )
        # Store in explanation cache (best-effort)
        try:
            _cache_set(
                _EXPLANATION_CACHE,
                _safe_cache_key,
                {
                    "result": result,
                    "risk_level": _risk_level_with_pgx_fallback(result, pgx_structured),
                    "pgx_structured": pgx_structured,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to store explanation cache entry: {e}")
    elif backend == "nova" and specific_pgx:
        # ---------- Nova Core: explicit Amazon Nova model call via Bedrock ----------
        cache_ttl = int(os.getenv("EXPLANATION_CACHE_TTL", "3600"))
        model_id = resolve_nova_model_id(nv)
        _safe_cache_key = "|".join(
            [
                "pgx-expl",
                backend,
                model_id,
                str(specific_pgx.get("gene", "")),
                str(specific_pgx.get("genotype", "")),
                str(specific_pgx.get("phenotype", "")),
                str(specific_pgx.get("risk", "")),
                str(specific_pgx.get("recommendation", "")),
            ]
        )
        cached = _cache_get(_EXPLANATION_CACHE, _safe_cache_key, cache_ttl)
        if cached:
            return (
                cached["result"],
                cached["risk_level"],
                cached["pgx_structured"],
                genetics_summary,
                None,
            )
        query = f"{specific_pgx.get('gene', '')} {request.drug_name} pharmacogenomics"
        docs = retrieve(query, top_k=3)
        context = (
            "\n\n".join(docs)
            if docs
            else (
                f"{specific_pgx.get('gene', 'PGx')} background; use only conservative, "
                "guideline-aligned reasoning."
            )
        )
        try:
            explanation = generate_pgx_response_nova(
                context=context,
                query=query,
                pgx_data=specific_pgx,
                nova_variant=nv,
            )
            pgx_structured = _apply_explanation_grounding(
                format_output(specific_pgx, explanation),
                explanation,
                docs,
            )
            result = explanation
        except Exception as e:
            logger.warning(
                f"Nova explanation failed; returning deterministic-only: {e}"
            )
            llm_failure_hint = _bedrock_failure_hint(e)
            expl_fb = f"LLM explanation unavailable. {llm_failure_hint}"
            pgx_structured = _apply_explanation_grounding(
                format_output(specific_pgx, expl_fb),
                expl_fb,
                docs,
            )
            result = (
                f"RISK LEVEL: {specific_pgx.get('risk','Unknown')}\n\n"
                f"PREDICTED REACTION:\nDeterministic PGx signal for {specific_pgx.get('gene','PGx')}. "
                f"{llm_failure_hint}\n\n"
                f"BIOLOGICAL MECHANISM:\nLLM explanation unavailable.\n\n"
                f"DOSING IMPLICATION:\n{specific_pgx.get('recommendation','See deterministic recommendation.')}\n"
            )
        try:
            _cache_set(
                _EXPLANATION_CACHE,
                _safe_cache_key,
                {
                    "result": result,
                    "risk_level": _risk_level_with_pgx_fallback(result, pgx_structured),
                    "pgx_structured": pgx_structured,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to store explanation cache entry: {e}")
    elif backend == "qvac" and specific_pgx:
        cache_ttl = int(os.getenv("EXPLANATION_CACHE_TTL", "3600"))
        model_id = config.QVAC_MODEL_LABEL
        _safe_cache_key = "|".join(
            [
                "pgx-expl",
                backend,
                model_id,
                str(specific_pgx.get("gene", "")),
                str(specific_pgx.get("genotype", "")),
                str(specific_pgx.get("phenotype", "")),
                str(specific_pgx.get("risk", "")),
                str(specific_pgx.get("recommendation", "")),
            ]
        )
        cached = _cache_get(_EXPLANATION_CACHE, _safe_cache_key, cache_ttl)
        if cached:
            return (
                cached["result"],
                cached["risk_level"],
                cached["pgx_structured"],
                genetics_summary,
                None,
            )
        query = f"{specific_pgx.get('gene', '')} {request.drug_name} pharmacogenomics"
        docs = retrieve(query, top_k=3)
        context = (
            "\n\n".join(docs)
            if docs
            else (
                f"{specific_pgx.get('gene', 'PGx')} background; use only conservative, "
                "guideline-aligned reasoning."
            )
        )
        try:
            explanation = generate_pgx_response_qvac(
                context=context,
                query=query,
                pgx_data=specific_pgx,
            )
            pgx_structured = _apply_explanation_grounding(
                format_output(specific_pgx, explanation),
                explanation,
                docs,
            )
            result = explanation
        except Exception as e:
            logger.warning(
                "QVAC explanation failed; returning deterministic-only: %s",
                e,
                exc_info=True,
            )
            llm_failure_hint = _qvac_failure_hint(e)
            expl_fb = f"LLM explanation unavailable. {llm_failure_hint}"
            pgx_structured = _apply_explanation_grounding(
                format_output(specific_pgx, expl_fb),
                expl_fb,
                docs,
            )
            result = (
                f"RISK LEVEL: {specific_pgx.get('risk','Unknown')}\n\n"
                f"PREDICTED REACTION:\nDeterministic PGx signal for {specific_pgx.get('gene','PGx')}. "
                f"{llm_failure_hint}\n\n"
                "BIOLOGICAL MECHANISM:\nQVAC local explanation unavailable.\n\n"
                f"DOSING IMPLICATION:\n{specific_pgx.get('recommendation','See deterministic recommendation.')}\n"
            )
        try:
            _cache_set(
                _EXPLANATION_CACHE,
                _safe_cache_key,
                {
                    "result": result,
                    "risk_level": _risk_level_with_pgx_fallback(result, pgx_structured),
                    "pgx_structured": pgx_structured,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to store explanation cache entry: {e}")
    elif backend == "bedrock":
        try:
            result = run_bedrock_rag(
                drug_name=request.drug_name,
                patient_profile=request.patient_profile,
                drug_smiles=request.drug_smiles,
                similar_drugs=similar_drugs,
            )
        except Exception as e:
            logger.warning(f"Bedrock RAG failed; returning deterministic-only: {e}")
            llm_failure_hint = _bedrock_failure_hint(e)
            result = (
                "RISK LEVEL: Unknown\n\n"
                f"PREDICTED REACTION:\n{llm_failure_hint}\n\n"
                "BIOLOGICAL MECHANISM:\nDeterministic engine ran, but no Bedrock explanation was generated.\n\n"
                "DOSING IMPLICATION:\nUse deterministic PGx outputs if available.\n"
            )
    elif backend == "nova":
        try:
            result = run_nova_rag(
                drug_name=request.drug_name,
                patient_profile=request.patient_profile,
                drug_smiles=request.drug_smiles,
                similar_drugs=similar_drugs,
                nova_variant=nv,
            )
        except Exception as e:
            logger.warning(
                "Nova RAG failed; returning deterministic-only: %s", e, exc_info=True
            )
            llm_failure_hint = _bedrock_failure_hint(e)
            result = (
                "RISK LEVEL: Unknown\n\n"
                f"PREDICTED REACTION:\n{llm_failure_hint}\n\n"
                "BIOLOGICAL MECHANISM:\nDeterministic engine ran, but no Nova explanation was generated.\n\n"
                "DOSING IMPLICATION:\nUse deterministic PGx outputs if available.\n"
            )
    elif backend == "qvac":
        query = f"{request.drug_name} pharmacogenomics {request.patient_profile[:500]}"
        docs = retrieve(query, top_k=3)
        context = (
            "\n\n".join(docs)
            if docs
            else "Use conservative pharmacogenomics reasoning."
        )
        try:
            explanation = generate_pgx_response_qvac(
                context=context,
                query=query,
                pgx_data=None,
            )
            result = explanation
        except Exception as e:
            logger.warning(
                "QVAC RAG failed; returning deterministic-only: %s", e, exc_info=True
            )
            llm_failure_hint = _qvac_failure_hint(e)
            result = (
                "RISK LEVEL: Unknown\n\n"
                f"PREDICTED REACTION:\n{llm_failure_hint}\n\n"
                "BIOLOGICAL MECHANISM:\nDeterministic engine ran, but no QVAC explanation was generated.\n\n"
                "DOSING IMPLICATION:\nUse deterministic PGx outputs if available.\n"
            )
    elif backend == "claude":
        result = run_simulation(
            drug_name=request.drug_name,
            similar_drugs=similar_drugs,
            patient_profile=request.patient_profile,
            drug_smiles=request.drug_smiles,
            backend="claude",
        )
        if specific_pgx:
            pgx_structured = format_output(
                specific_pgx,
                "",
            )
            result = _ensure_deterministic_risk_preamble(result, pgx_structured)
    else:
        result = run_simulation(
            drug_name=request.drug_name,
            similar_drugs=similar_drugs,
            patient_profile=request.patient_profile,
            drug_smiles=request.drug_smiles,
        )
        if specific_pgx:
            pgx_structured = format_output(
                specific_pgx,
                "",
            )
            result = _ensure_deterministic_risk_preamble(result, pgx_structured)

    risk_level = _risk_level_with_pgx_fallback(result, pgx_structured)
    return result, risk_level, pgx_structured, genetics_summary, llm_failure_hint


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_drug(
    request: AnalyzeRequest, req: Request, _auth: None = Depends(verify_api_key)
):
    """
    Analyze drug-patient interaction and predict pharmacogenomics risk

    This endpoint:
    1. Processes the drug SMILES (if provided) to generate molecular fingerprint
    2. Finds similar drugs using vector similarity search (if not provided)
    3. Runs AI simulation using patient profile and drug information
    4. Returns risk assessment following CPIC guidelines

    Args:
        request: AnalyzeRequest containing drug info and patient profile

    Returns:
        AnalyzeResponse with AI-generated risk prediction

    Raises:
        HTTPException: If configuration is invalid or simulation fails
    """
    logger.info(f"Received analysis request for drug: {request.drug_name}")

    try:
        # Validate configuration
        is_valid, missing_keys = config.validate_required()
        if not is_valid:
            logger.error(f"Configuration error: Missing keys {missing_keys}")
            raise HTTPException(
                status_code=500,
                detail=f"Server configuration error: Missing {', '.join(missing_keys)}. "
                "Please contact administrator.",
            )

        # Get similar drugs if not provided
        similar_drugs = request.similar_drugs
        if not similar_drugs:
            logger.info("Computing similar drugs via vector search")
            try:
                drug_smiles = request.drug_smiles or "CC(=O)Nc1ccc(O)cc1"
                vector = get_drug_fingerprint(drug_smiles)
                similar_drugs = find_similar_drugs(vector)
                logger.info(f"Found {len(similar_drugs)} similar drugs")
            except Exception as e:
                logger.warning(f"Vector search failed: {e}, using empty list")
                similar_drugs = []

        # Decide backend: request override wins over global default.
        backend = _normalize_runtime_backend(request.llm_backend)

        # Run AI simulation (respects backend: bedrock, nova, qvac)
        logger.info("Running pharmacogenomics simulation")
        (
            result,
            risk_level,
            pgx_structured,
            genetics_summary,
            llm_failure_hint,
        ) = _run_single_simulation(request, similar_drugs, backend)
        vector_ctx = _vector_context(similar_drugs)
        context_sources = vector_ctx["context_sources"]
        similar_names = [
            s.split("|")[0].strip() if "|" in s else s for s in similar_drugs
        ]

        logger.info(f"Simulation completed successfully. Risk level: {risk_level}")

        model_id = _model_id_for_backend(backend, request.nova_variant)
        audit = {
            "ts": time.time(),
            "backend": backend,
            "model": model_id,
            "context_sources": (context_sources),
            "used_pinecone": vector_ctx["used_pinecone"],
            "vector_backend": vector_ctx["backend"],
            "vector_mock_fallback": vector_ctx["mock_fallback"],
        }
        if backend == "nova":
            audit["nova_variant"] = _normalize_nova_variant(request.nova_variant) or (
                "pro" if config.NOVA_DEFAULT_VARIANT == "pro" else "lite"
            )
        if llm_failure_hint:
            audit["llm_failure_hint"] = llm_failure_hint
        ehr_bundle = _build_ehr_bundle(
            drug_name=request.drug_name,
            patient_profile=request.patient_profile,
            risk_level=risk_level,
            pgx_structured=pgx_structured,
            backend=backend,
            model_id=model_id,
        )
        response_fields = {
            "result": result,
            "risk_level": risk_level,
            "drug_name": request.drug_name,
            "status": "success",
            "similar_drugs_used": similar_names or similar_drugs,
            "genetics_summary": genetics_summary,
            "context_sources": context_sources,
            "pgx_structured": pgx_structured,
            "audit": audit,
            "ehr_bundle": ehr_bundle,
        }
        attestation = _build_analysis_attestation(**response_fields)

        return AnalyzeResponse(
            **response_fields,
            attestation=attestation,
        )

    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Server configuration error: {str(e)}",
        )

    except LLMError as e:
        logger.error(f"LLM error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"AI simulation service unavailable: {str(e)}",
        )

    except Exception as e:
        logger.error(f"Unexpected error during analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@app.post("/analyze/novel-drug")
async def analyze_novel_drug(request: NovelDrugAnalyzeRequest):
    """
    Explicit novel-drug analysis:
    - structure retrieval via vector search,
    - evidence-based candidate gene inference,
    - confidence-tiered output,
    - optional ancestry-aware population summary.
    """
    try:
        is_valid, missing_keys = config.validate_required()
        if not is_valid:
            raise HTTPException(
                status_code=500,
                detail=f"Server configuration error: Missing {', '.join(missing_keys)}",
            )

        vector = get_drug_fingerprint(request.drug_smiles)
        similar_drugs = find_similar_drugs(vector)
        vector_ctx = _vector_context(similar_drugs)

        inference = infer_novel_drug_hypothesis(
            drug_name=request.drug_name,
            similar_drugs=similar_drugs,
            targets=request.targets or [],
            metabolism_enzymes=request.metabolism_enzymes or [],
            transporters=request.transporters or [],
            evidence_notes=request.evidence_notes,
        )

        coverage = _deterministic_coverage(inference.get("candidate_genes", []))
        tier_info = classify_confidence_tier(
            inference_confidence=float(inference.get("inference_confidence", 0.0)),
            candidate_genes=inference.get("candidate_genes", []),
            deterministic_callable_genes=coverage.get("callable_genes", []),
            evidence_items=inference.get("evidence_items", []),
        )

        backend = _normalize_runtime_backend(request.llm_backend)

        sim_req = AnalyzeRequest(
            drug_name=request.drug_name,
            patient_profile=request.patient_profile,
            drug_smiles=request.drug_smiles,
            similar_drugs=similar_drugs,
            llm_backend=backend,
            nova_variant=request.nova_variant,
        )
        (
            result,
            risk_level,
            pgx_structured,
            genetics_summary,
            llm_failure_hint,
        ) = _run_single_simulation(sim_req, similar_drugs, backend)

        novel_meta = {
            "novel_drug_mode": True,
            "targets": request.targets or [],
            "metabolism_enzymes": request.metabolism_enzymes or [],
            "transporters": request.transporters or [],
            "inference": inference,
            "deterministic_coverage": coverage,
            "confidence_tier": tier_info["confidence_tier"],
            "confidence_rationale": tier_info["rationale"],
        }
        pgx_structured_novel = format_novel_drug_output(
            base_pgx=pgx_structured or {},
            explanation=result,
            novel_metadata=novel_meta,
        )

        population_summary = None
        if request.include_population_summary:
            from src.population_simulator import PopulationSimulator

            population_mix = {
                "AFR": 0.25,
                "EUR": 0.40,
                "EAS": 0.20,
                "SAS": 0.10,
                "AMR": 0.05,
            }
            sim = PopulationSimulator(
                cohort_size=request.cohort_size,
                population_mix=population_mix,
            )
            population_summary = sim.run_novel_drug_simulation(
                drug_name=request.drug_name,
                candidate_genes=inference.get("candidate_genes", []),
                confidence_tier=tier_info["confidence_tier"],
                parallel=True,
            )

        validation_gate = _validation_gate(
            confidence_tier=tier_info["confidence_tier"],
            deterministic_coverage=coverage,
            vector_ctx=vector_ctx,
        )
        validation_artifact = _load_validation_artifact_summary()
        audit = {
            "ts": time.time(),
            "backend": backend,
            "model": _model_id_for_backend(backend, request.nova_variant),
            **(
                {
                    "nova_variant": _normalize_nova_variant(request.nova_variant)
                    or ("pro" if config.NOVA_DEFAULT_VARIANT == "pro" else "lite")
                }
                if backend == "nova"
                else {}
            ),
            "vector_backend": vector_ctx.get("backend"),
            "vector_mock_fallback": vector_ctx.get("mock_fallback"),
            "used_pinecone": vector_ctx.get("used_pinecone"),
            "novel_drug_mode": True,
            "confidence_tier": tier_info["confidence_tier"],
            **({"llm_failure_hint": llm_failure_hint} if llm_failure_hint else {}),
        }

        response_payload = {
            "status": "success",
            "drug_name": request.drug_name,
            "risk_level": risk_level,
            "result": result,
            "context_sources": vector_ctx.get("context_sources"),
            "similar_drugs_used": [
                s.split("|")[0].strip() if "|" in s else s for s in similar_drugs
            ],
            "genetics_summary": genetics_summary,
            "pgx_structured": pgx_structured_novel,
            "audit": audit,
            "novel_drug": {
                "confidence_tier": tier_info["confidence_tier"],
                "inference_confidence": tier_info["inference_confidence"],
                "inference_rationale": tier_info["rationale"],
                "candidate_genes": inference.get("candidate_genes", []),
                "evidence_items": inference.get("evidence_items", []),
                "deterministic_coverage": coverage,
                "validation_gate": validation_gate,
                "validation_artifact": validation_artifact,
                "population_summary": population_summary,
            },
        }
        response_payload["attestation"] = build_simulation_result_attestation(
            response_payload
        )
        return response_payload
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Novel-drug analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/novel-drug/validation-artifact")
async def novel_drug_validation_artifact():
    """Return reproducible benchmark-summary artifact for novel-drug gating."""
    return {
        "status": "success",
        "artifact": _load_validation_artifact_summary(),
        "gate_policy": _validation_gate(
            confidence_tier="exploratory",
            deterministic_coverage={"callable_genes": []},
            vector_ctx={"mock_fallback": True},
        ),
    }


# Example usage for testing
class BatchAnalyzeRequest(BaseModel):
    """Request model for batch analysis"""

    requests: List[AnalyzeRequest] = Field(..., description="List of analysis requests")


class TrialExportRequest(BaseModel):
    """
    Deterministic trial-facing cohort export request.
    Focused MVP workflows only:
    - clopidogrel_cyp2c19
    - warfarin_cyp2c9_vkorc1
    """

    workflow: str = Field(
        ...,
        description="Workflow identifier: clopidogrel_cyp2c19 | warfarin_cyp2c9_vkorc1",
    )
    sample_ids: List[str] = Field(
        ...,
        min_length=1,
        description="Sample IDs to process from selected VCF dataset/source.",
    )
    source: str = Field(
        default="auto", description="VCF source mode: local | s3 | auto"
    )
    dataset_id: Optional[str] = Field(
        default=None,
        description="Optional dataset ID from /vcf-datasets for explicit source selection.",
    )


class AttestationVerifyRequest(BaseModel):
    """Verify that a local export payload still matches its attestation."""

    payload: Dict[str, Any] = Field(..., description="Trial export payload to verify.")
    attestation: Dict[str, Any] = Field(
        ..., description="Attestation block returned by Anukriti."
    )


class AttestationSubmitRequest(BaseModel):
    """Submit an already prepared attestation memo with the local Solana CLI."""

    attestation: Dict[str, Any] = Field(..., description="Prepared attestation block.")
    keypair_path: Optional[str] = Field(
        default=None,
        description="Optional Solana keypair path. Defaults to the Solana CLI config.",
    )
    rpc_url: Optional[str] = Field(
        default=None,
        description="Optional Solana RPC URL. Use a provider endpoint such as Helius for reliable demos.",
    )


class AttestationLookupRequest(BaseModel):
    """Look up a Solana transaction and verify the expected Anukriti memo."""

    signature: str = Field(..., min_length=20, description="Solana transaction signature.")
    attestation: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Prepared attestation block. If provided, its solana.memo is verified.",
    )
    expected_memo: Optional[str] = Field(
        default=None,
        description="Expected memo string. Used when attestation is not provided.",
    )
    network: str = Field(default="devnet", description="Solana cluster or RPC URL label.")
    rpc_url: Optional[str] = Field(
        default=None,
        description="Optional Solana RPC URL, e.g. a Helius devnet/mainnet endpoint.",
    )


class AnukritiLiteDemoRequest(BaseModel):
    """Generate a self-contained Anukriti Lite proof demo."""

    workflow: str = Field(default="clopidogrel_cyp2c19")
    submit_to_devnet: bool = Field(
        default=False,
        description="If true, submit the memo with the local Solana CLI.",
    )
    keypair_path: Optional[str] = Field(default=None)
    rpc_url: Optional[str] = Field(default=None)


TRIAL_WORKFLOWS: Dict[str, Dict[str, Any]] = {
    "clopidogrel_cyp2c19": {
        "drug_name": "Clopidogrel",
        "genes": ["CYP2C19"],
    },
    "warfarin_cyp2c9_vkorc1": {
        "drug_name": "Warfarin",
        "genes": ["CYP2C9", "VKORC1"],
    },
}


def _trial_recommendation_for_cyp2c19(phenotype_normalized: str) -> Tuple[str, str]:
    phen = (phenotype_normalized or "").strip().lower()
    if phen == "poor_metabolizer":
        return (
            "consider_alternative_antiplatelet",
            "Reduced clopidogrel activation expected; consider prasugrel or ticagrelor per CPIC guidance.",
        )
    if phen == "intermediate_metabolizer":
        return (
            "consider_alternative_antiplatelet",
            "Intermediate clopidogrel activation; consider alternative antiplatelet strategy per CPIC guidance.",
        )
    if phen == "ultra_rapid_metabolizer":
        return (
            "use_with_monitoring",
            "Increased activation potential; use standard therapy with routine clinical monitoring.",
        )
    if phen == "extensive_metabolizer":
        return (
            "standard_therapy",
            "Expected normal activation; standard clopidogrel therapy is generally appropriate.",
        )
    return (
        "manual_review",
        "Could not classify CYP2C19 phenotype for clopidogrel. Manual PGx review required.",
    )


def _trial_gene_chrom(gene: str) -> str:
    mapping = {
        "CYP2C19": "chr10",
        "CYP2C9": "chr10",
        "VKORC1": "chr16",
    }
    return mapping.get(gene, "chr22")


def _vcf_paths_for_trial(source: str, dataset_id: Optional[str]) -> Dict[str, str]:
    if dataset_id:
        parsed = _parse_dataset_id(dataset_id)
        if not parsed:
            raise ValueError("Invalid dataset_id")
        src = parsed["source"]
        ref = parsed["ref"]
        if src == "upload":
            info = _VCF_UPLOADS.get(ref)
            if not info:
                raise ValueError("Upload session not found")
            chrom = info.get("chrom", "chr22")
            return {chrom: info["vcf_path"]}
        if src == "remote":
            return {_guess_chrom_from_name(ref): ref}
        return {_guess_chrom_from_name(ref): ref}

    app_root = os.path.dirname(os.path.abspath(__file__))
    genomes_dir = os.path.join(app_root, "data", "genomes")
    return _discover_paths_by_source(genomes_dir, source)


def _build_variant_map(
    variants: List[Dict[str, Any]], sample_id: str
) -> Dict[str, Tuple[str, str, str]]:
    out: Dict[str, Tuple[str, str, str]] = {}
    for v in variants:
        rsid = str(v.get("id", "")).strip()
        if not rsid or rsid == ".":
            continue
        samples = v.get("samples", {}) or {}
        gt = samples.get(sample_id)
        if not gt or gt in (".", "./.", ".|."):
            continue
        ref = str(v.get("ref", ""))
        alt = str(v.get("alt", ""))
        if "," in alt:
            alt = alt.split(",")[0]
        out[rsid] = (ref, alt, str(gt))
    return out


def _sample_exists_in_any_vcf(sample_id: str, vcf_paths: Dict[str, str]) -> bool:
    for path in vcf_paths.values():
        try:
            samples = get_sample_ids_from_vcf(path, limit=None)
        except Exception as e:
            logger.debug(f"Sample existence check failed for {path}: {e}")
            samples = []
        if sample_id in samples:
            return True
    return False


def _extract_trial_gene_variant_map(
    sample_id: str, gene: str, vcf_paths: Dict[str, str]
) -> Tuple[Dict[str, Tuple[str, str, str]], str]:
    chrom = _trial_gene_chrom(gene)
    vcf_path = vcf_paths.get(chrom)
    if not vcf_path:
        return {}, f"Missing {chrom} VCF required for {gene}"
    try:
        local_vcf = (
            download_s3_vcf_if_needed(vcf_path)
            if vcf_path.startswith("s3://")
            else vcf_path
        )
        variants = extract_variants_with_tabix(local_vcf, gene)
        var_map = _build_variant_map(variants, sample_id)
        return var_map, ""
    except Exception as e:
        return {}, f"Failed to extract {gene} variants: {e}"


def _trial_row_cyp2c19(sample_id: str, vcf_paths: Dict[str, str]) -> Dict[str, Any]:
    row = {
        "sample_id": sample_id,
        "workflow": "clopidogrel_cyp2c19",
        "drug_name": "Clopidogrel",
        "gene": "CYP2C19",
        "diplotype_or_genotype": None,
        "phenotype": None,
        "recommendation_category": None,
        "recommendation_text": None,
        "call_state": "cannot_call",
        "call_reason": None,
    }
    var_map, err = _extract_trial_gene_variant_map(sample_id, "CYP2C19", vcf_paths)
    if err:
        row["call_state"] = "insufficient_data"
        row["call_reason"] = err
        return row

    cpic_result = call_gene_from_variants("CYP2C19", var_map)
    if not cpic_result:
        row["call_reason"] = "Curated CYP2C19 PharmVar/CPIC data unavailable"
        return row

    row["diplotype_or_genotype"] = cpic_result.get("diplotype")
    row["phenotype"] = cpic_result.get("phenotype_display")
    row["call_state"] = "called"
    row["call_reason"] = "Deterministic call from PharmVar + CPIC tables"
    rec_category, rec_text = _trial_recommendation_for_cyp2c19(
        cpic_result.get("phenotype_normalized", "")
    )
    row["recommendation_category"] = rec_category
    row["recommendation_text"] = rec_text
    return row


def _trial_row_warfarin(sample_id: str, vcf_paths: Dict[str, str]) -> Dict[str, Any]:
    row = {
        "sample_id": sample_id,
        "workflow": "warfarin_cyp2c9_vkorc1",
        "drug_name": "Warfarin",
        "gene": "CYP2C9+VKORC1",
        "diplotype_or_genotype": None,
        "phenotype": None,
        "recommendation_category": None,
        "recommendation_text": None,
        "call_state": "cannot_call",
        "call_reason": None,
    }
    cyp_map, cyp_err = _extract_trial_gene_variant_map(sample_id, "CYP2C9", vcf_paths)
    vk_map, vk_err = _extract_trial_gene_variant_map(sample_id, "VKORC1", vcf_paths)

    if cyp_err or vk_err:
        row["call_state"] = "insufficient_data"
        reasons = [r for r in (cyp_err, vk_err) if r]
        row["call_reason"] = "; ".join(reasons)
        return row

    cyp_result = call_gene_from_variants("CYP2C9", cyp_map)
    if not cyp_result:
        row["call_reason"] = "Curated CYP2C9 PharmVar/CPIC data unavailable"
        return row

    merged = dict(cyp_map)
    merged.update(vk_map)
    warfarin_result = interpret_warfarin_from_vcf(merged)
    if not warfarin_result:
        row["call_reason"] = "Could not derive deterministic Warfarin interpretation"
        return row

    cyp2c9 = warfarin_result.get("CYP2C9", "Unknown")
    vkorc1 = warfarin_result.get("VKORC1", "Unknown")
    row["diplotype_or_genotype"] = f"CYP2C9 {cyp2c9}; VKORC1 {vkorc1}"
    row["phenotype"] = cyp_result.get("phenotype_display")
    row["recommendation_text"] = warfarin_result.get("recommendation")
    row["recommendation_category"] = (
        "manual_review"
        if "Unknown genotype combination" in (row["recommendation_text"] or "")
        else "dose_adjustment_guidance"
    )
    if vkorc1 == "Unknown":
        row["call_state"] = "insufficient_data"
        row["call_reason"] = "VKORC1 rs9923231 missing in cohort VCF for this sample"
        return row
    row["call_state"] = "called"
    row[
        "call_reason"
    ] = "Deterministic CYP2C9 + VKORC1 interpretation from curated tables"
    return row


def _anukriti_lite_demo_payload(workflow: str) -> Dict[str, Any]:
    """
    Build a deterministic, de-identified proof payload for judges and demos.

    This is intentionally independent of local VCF availability so the Colosseum
    project can demonstrate the provenance loop in any deployment.
    """

    normalized = (workflow or "clopidogrel_cyp2c19").strip().lower()
    if normalized == "warfarin_cyp2c9_vkorc1":
        return {
            "project": "Anukriti Lite",
            "workflow": "warfarin_cyp2c9_vkorc1",
            "drug_name": "Warfarin",
            "genes": ["CYP2C9", "VKORC1"],
            "source": "demo_fixture",
            "dataset_id": "anukriti-lite-demo-v1",
            "requested_samples": 3,
            "summary": {"called": 2, "cannot_call": 0, "insufficient_data": 1},
            "rows": [
                {
                    "sample_id": "DEMO-WAR-001",
                    "workflow": "warfarin_cyp2c9_vkorc1",
                    "drug_name": "Warfarin",
                    "gene": "CYP2C9+VKORC1",
                    "diplotype_or_genotype": "CYP2C9 *1/*3; VKORC1 A/G",
                    "phenotype": "Intermediate Metabolizer",
                    "recommendation_category": "dose_adjustment_guidance",
                    "recommendation_text": "Lower starting dose range; verify with protocol-specific dosing model.",
                    "call_state": "called",
                    "call_reason": "Deterministic CYP2C9 + VKORC1 interpretation from curated tables",
                },
                {
                    "sample_id": "DEMO-WAR-002",
                    "workflow": "warfarin_cyp2c9_vkorc1",
                    "drug_name": "Warfarin",
                    "gene": "CYP2C9+VKORC1",
                    "diplotype_or_genotype": "CYP2C9 *1/*1; VKORC1 G/G",
                    "phenotype": "Normal Metabolizer",
                    "recommendation_category": "dose_adjustment_guidance",
                    "recommendation_text": "Typical dose sensitivity expected; continue protocol review.",
                    "call_state": "called",
                    "call_reason": "Deterministic CYP2C9 + VKORC1 interpretation from curated tables",
                },
                {
                    "sample_id": "DEMO-WAR-003",
                    "workflow": "warfarin_cyp2c9_vkorc1",
                    "drug_name": "Warfarin",
                    "gene": "CYP2C9+VKORC1",
                    "diplotype_or_genotype": "CYP2C9 *1/*2; VKORC1 missing",
                    "phenotype": "Intermediate Metabolizer",
                    "recommendation_category": None,
                    "recommendation_text": None,
                    "call_state": "insufficient_data",
                    "call_reason": "VKORC1 rs9923231 missing in cohort VCF for this sample",
                },
            ],
        }

    return {
        "project": "Anukriti Lite",
        "workflow": "clopidogrel_cyp2c19",
        "drug_name": "Clopidogrel",
        "genes": ["CYP2C19"],
        "source": "demo_fixture",
        "dataset_id": "anukriti-lite-demo-v1",
        "requested_samples": 3,
        "summary": {"called": 3, "cannot_call": 0, "insufficient_data": 0},
        "rows": [
            {
                "sample_id": "DEMO-CLO-001",
                "workflow": "clopidogrel_cyp2c19",
                "drug_name": "Clopidogrel",
                "gene": "CYP2C19",
                "diplotype_or_genotype": "*1/*1",
                "phenotype": "Normal Metabolizer",
                "recommendation_category": "standard_therapy",
                "recommendation_text": "Expected normal activation; standard clopidogrel therapy is generally appropriate.",
                "call_state": "called",
                "call_reason": "Deterministic call from PharmVar + CPIC tables",
            },
            {
                "sample_id": "DEMO-CLO-002",
                "workflow": "clopidogrel_cyp2c19",
                "drug_name": "Clopidogrel",
                "gene": "CYP2C19",
                "diplotype_or_genotype": "*1/*2",
                "phenotype": "Intermediate Metabolizer",
                "recommendation_category": "consider_alternative_antiplatelet",
                "recommendation_text": "Intermediate clopidogrel activation; consider alternative antiplatelet strategy per CPIC guidance.",
                "call_state": "called",
                "call_reason": "Deterministic call from PharmVar + CPIC tables",
            },
            {
                "sample_id": "DEMO-CLO-003",
                "workflow": "clopidogrel_cyp2c19",
                "drug_name": "Clopidogrel",
                "gene": "CYP2C19",
                "diplotype_or_genotype": "*2/*2",
                "phenotype": "Poor Metabolizer",
                "recommendation_category": "consider_alternative_antiplatelet",
                "recommendation_text": "Reduced clopidogrel activation expected; consider prasugrel or ticagrelor per CPIC guidance.",
                "call_state": "called",
                "call_reason": "Deterministic call from PharmVar + CPIC tables",
            },
        ],
    }


def _tamper_lite_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    tampered: Dict[str, Any] = json.loads(json.dumps(payload))
    tampered.pop("attestation", None)
    if tampered.get("rows"):
        tampered["rows"][0]["recommendation_category"] = "tampered_after_export"
        tampered["rows"][0]["call_reason"] = "Tampered demo row"
    return tampered


def _anukriti_lite_submission_metadata() -> Dict[str, Any]:
    """Judge-facing metadata that keeps the Colosseum, Solana, and QVAC story together."""

    return {
        "one_liner": (
            "Anukriti Lite turns deterministic pharmacogenomics trial exports into "
            "private, verifiable Solana proof artifacts, with QVAC available for "
            "local explanation text."
        ),
        "tracks": {
            "colosseum": {
                "wedge": "PGx trial export provenance, not generic healthcare records.",
                "judge_demo": "POST /lite/demo or Streamlit -> Solana Proofs.",
                "differentiator": (
                    "The artifact being proved is a deterministic cohort-stratification "
                    "export that sponsors can re-verify after generation."
                ),
            },
            "solana": {
                "role": "Tamper-evident proof reference for off-chain PGx exports.",
                "on_chain_data": "Only anukriti:<schema_version>:<payload_hash> memo text.",
                "privacy_boundary": "Sample IDs, genotypes, phenotypes, and recommendations stay off-chain.",
                "default_status": "prepared_not_submitted",
                "optional_submit_path": "POST /attestations/submit with a configured devnet Solana CLI.",
                "wallet_submit_path": "GET /lite/phantom for Phantom browser-wallet memo submission.",
                "lookup_path": "POST /attestations/lookup verifies the memo through a Solana RPC provider such as Helius.",
                "rpc_url": resolve_solana_rpc_url("devnet"),
            },
            "phantom": {
                "role": "Recommended Frontier wallet UX for browser-side memo signing.",
                "docs": "https://docs.phantom.com/phantom-connect",
                "demo_path": "GET /lite/phantom",
                "privacy_boundary": "The wallet signs only the compact memo proof; cohort rows stay off-chain.",
            },
            "helius": {
                "role": "Recommended RPC/provider path for reliable proof submission and lookup.",
                "docs": "https://www.helius.dev/",
                "configuration": "Set SOLANA_RPC_URL to a Helius devnet/mainnet RPC endpoint.",
            },
            "qvac": {
                "role": "Optional local LLM backend for concise PGx explanation sections.",
                "enabled": config.QVAC_ENABLED,
                "model": config.QVAC_MODEL_LABEL,
                "bridge": config.QVAC_SCRIPT_PATH,
                "privacy_boundary": (
                    "QVAC receives de-identified context and deterministic PGx results; "
                    "it does not make the clinical call or publish proofs."
                ),
                "setup": "cd qvac && npm install && npm run check",
            },
        },
        "proof_loop": [
            "deterministic PGx cohort export",
            "canonical JSON payload",
            "SHA-256 payload hash",
            "Solana memo proof reference",
            "local verification",
            "tamper rejection",
        ],
        "safety_positioning": (
            "Research prototype only. Deterministic PGx logic is the source of truth; "
            "AI explains outputs and Solana proves artifact integrity."
        ),
    }


@app.post("/analyze/batch", response_model=List[AnalyzeResponse])
async def analyze_drug_batch(batch_request: BatchAnalyzeRequest):
    """
    Batch analysis of multiple drug-patient pairs.
    Respects LLM_BACKEND (bedrock vs gemini) same as single /analyze.
    """
    logger.info(
        f"Received batch analysis request with {len(batch_request.requests)} items"
    )
    responses = []
    for request in batch_request.requests:
        try:
            # 1. Get similar drugs
            similar_drugs = request.similar_drugs
            if not similar_drugs:
                try:
                    drug_smiles = request.drug_smiles or "CC(=O)Nc1ccc(O)cc1"
                    vector = get_drug_fingerprint(drug_smiles)
                    similar_drugs = find_similar_drugs(vector)
                except Exception as e:
                    logger.warning(f"Vector search failed for {request.drug_name}: {e}")
                    similar_drugs = []

            # 2. Decide backend for this request (per-item override or global default)
            backend = _normalize_runtime_backend(request.llm_backend)

            # 3. Run simulation (respects backend)
            (
                result,
                risk_level,
                pgx_structured,
                genetics_summary,
                llm_failure_hint,
            ) = _run_single_simulation(request, similar_drugs, backend)
            vector_ctx = _vector_context(similar_drugs)

            similar_names = [
                s.split("|")[0].strip() if "|" in s else s for s in similar_drugs
            ]
            context_sources = vector_ctx["context_sources"]
            model_id = _model_id_for_backend(backend, request.nova_variant)
            audit = {
                "ts": time.time(),
                "backend": backend,
                "model": model_id,
                "context_sources": context_sources,
                "used_pinecone": vector_ctx["used_pinecone"],
                "vector_backend": vector_ctx["backend"],
                "vector_mock_fallback": vector_ctx["mock_fallback"],
            }
            if backend == "nova":
                audit["nova_variant"] = _normalize_nova_variant(
                    request.nova_variant
                ) or ("pro" if config.NOVA_DEFAULT_VARIANT == "pro" else "lite")
            if llm_failure_hint:
                audit["llm_failure_hint"] = llm_failure_hint
            ehr_bundle = _build_ehr_bundle(
                drug_name=request.drug_name,
                patient_profile=request.patient_profile,
                risk_level=risk_level,
                pgx_structured=pgx_structured,
                backend=backend,
                model_id=model_id,
            )
            response_fields = {
                "result": result,
                "risk_level": risk_level,
                "drug_name": request.drug_name,
                "status": "success",
                "similar_drugs_used": similar_names or similar_drugs,
                "genetics_summary": genetics_summary,
                "context_sources": context_sources,
                "pgx_structured": pgx_structured,
                "audit": audit,
                "ehr_bundle": ehr_bundle,
            }
            attestation = _build_analysis_attestation(**response_fields)

            responses.append(
                AnalyzeResponse(
                    **response_fields,
                    attestation=attestation,
                )
            )

        except Exception as e:
            logger.error(f"Error processing batch item {request.drug_name}: {e}")
            error_fields = {
                "result": f"Error: {str(e)}",
                "risk_level": "Unknown",
                "drug_name": request.drug_name,
                "status": "error",
                "similar_drugs_used": None,
                "genetics_summary": None,
                "context_sources": None,
                "pgx_structured": None,
                "audit": {"error": str(e), "ts": time.time()},
                "ehr_bundle": None,
            }
            responses.append(
                AnalyzeResponse(
                    **error_fields,
                    attestation=_build_analysis_attestation(**error_fields),
                )
            )

    return responses


@app.get("/trial/workflows")
async def trial_workflows():
    """
    Return the explicitly supported MVP workflows for trial-facing exports.
    """
    return {
        "workflows": [
            {
                "id": "clopidogrel_cyp2c19",
                "drug_name": "Clopidogrel",
                "genes": ["CYP2C19"],
                "description": "Deterministic CYP2C19 phenotype and clopidogrel recommendation category.",
            },
            {
                "id": "warfarin_cyp2c9_vkorc1",
                "drug_name": "Warfarin",
                "genes": ["CYP2C9", "VKORC1"],
                "description": "Deterministic CYP2C9/VKORC1 interpretation with warfarin recommendation text.",
            },
        ]
    }


@app.post("/trial/export")
async def trial_export(req: TrialExportRequest):
    """
    Deterministic cohort export for the MVP wedge.

    Output contract per sample:
    - call_state: called | cannot_call | insufficient_data
    - explicit call_reason
    """
    workflow = (req.workflow or "").strip().lower()
    if workflow not in TRIAL_WORKFLOWS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported workflow. Use one of: "
                + ", ".join(sorted(TRIAL_WORKFLOWS.keys()))
            ),
        )
    source = (req.source or "auto").strip().lower()
    if source not in {"auto", "local", "s3"}:
        raise HTTPException(status_code=400, detail="source must be local, s3, or auto")

    try:
        vcf_paths = _vcf_paths_for_trial(source, req.dataset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not vcf_paths:
        raise HTTPException(
            status_code=404,
            detail="No VCF files found for trial export in selected source/dataset.",
        )

    rows: List[Dict[str, Any]] = []
    for sample_id in req.sample_ids:
        if not _sample_exists_in_any_vcf(sample_id, vcf_paths):
            rows.append(
                {
                    "sample_id": sample_id,
                    "workflow": workflow,
                    "drug_name": TRIAL_WORKFLOWS[workflow]["drug_name"],
                    "gene": ",".join(TRIAL_WORKFLOWS[workflow]["genes"]),
                    "diplotype_or_genotype": None,
                    "phenotype": None,
                    "recommendation_category": None,
                    "recommendation_text": None,
                    "call_state": "cannot_call",
                    "call_reason": "Sample ID not found in selected VCF dataset/source",
                }
            )
            continue

        if workflow == "clopidogrel_cyp2c19":
            rows.append(_trial_row_cyp2c19(sample_id, vcf_paths))
        else:
            rows.append(_trial_row_warfarin(sample_id, vcf_paths))

    counts = {
        "called": sum(1 for r in rows if r.get("call_state") == "called"),
        "cannot_call": sum(1 for r in rows if r.get("call_state") == "cannot_call"),
        "insufficient_data": sum(
            1 for r in rows if r.get("call_state") == "insufficient_data"
        ),
    }
    export_payload = {
        "workflow": workflow,
        "drug_name": TRIAL_WORKFLOWS[workflow]["drug_name"],
        "genes": TRIAL_WORKFLOWS[workflow]["genes"],
        "source": source,
        "dataset_id": req.dataset_id,
        "requested_samples": len(req.sample_ids),
        "summary": counts,
        "rows": rows,
    }
    export_payload["attestation"] = build_trial_export_attestation(export_payload)
    return export_payload


@app.post("/attestations/verify")
async def verify_attestation(req: AttestationVerifyRequest):
    """Verify that an export payload still matches its attestation hash and memo."""

    return verify_trial_export_attestation_detail(req.payload, req.attestation)


@app.post("/attestations/submit")
async def submit_attestation(req: AttestationSubmitRequest):
    """
    Submit an attestation memo through the local Solana CLI when a devnet wallet
    is configured on the host.
    """

    memo = str((req.attestation.get("solana") or {}).get("memo", "")).strip()
    if not memo:
        raise HTTPException(status_code=400, detail="attestation.solana.memo missing")
    network = str(req.attestation.get("network") or "devnet")
    result = submit_memo_with_solana_cli(
        memo,
        network=network,
        keypair_path=req.keypair_path,
        rpc_url=req.rpc_url,
    )
    if not result.get("submitted"):
        return {
            **result,
            "attestation": req.attestation,
        }

    signature = str(result.get("signature") or "")
    proof_attestation = build_trial_export_attestation(
        {"payload_hash": req.attestation.get("payload_hash")},
        network=network,
        proof_status="submitted",
        signature=signature,
    )
    updated = dict(req.attestation)
    updated_solana = dict(updated.get("solana") or {})
    updated_solana.update(
        {
            "devnet_proof_status": "submitted",
            "signature": signature,
            "explorer_url": result.get("explorer_url")
            or proof_attestation["solana"]["explorer_url"],
        }
    )
    updated["solana"] = updated_solana
    return {
        **result,
        "attestation": updated,
    }


@app.post("/attestations/lookup")
async def lookup_attestation(req: AttestationLookupRequest):
    """
    Verify that a submitted Solana transaction contains an expected Anukriti memo.

    Configure SOLANA_RPC_URL with Helius or another provider for reliable lookups.
    """

    expected_memo = (req.expected_memo or "").strip()
    network = req.network
    if req.attestation:
        solana = req.attestation.get("solana") or {}
        expected_memo = expected_memo or str(solana.get("memo") or "").strip()
        network = str(req.attestation.get("network") or network)
    if not expected_memo:
        raise HTTPException(
            status_code=400,
            detail="Provide expected_memo or attestation.solana.memo.",
        )

    return verify_solana_memo_proof(
        req.signature.strip(),
        expected_memo,
        network=network,
        rpc_url=req.rpc_url,
    )


@app.get("/lite")
async def anukriti_lite_status():
    """Product metadata for the Colosseum-facing Anukriti Lite demo."""

    submission = _anukriti_lite_submission_metadata()
    return {
        "name": "Anukriti Lite",
        "tagline": "Verifiable trial-export provenance for PGx cohorts on Solana.",
        "status": "ready",
        "submission": submission,
        "proof_loop": submission["proof_loop"],
        "privacy_model": "Sample-level PGx rows stay off-chain; Solana sees only a schema label and hash.",
        "phantom_wallet_demo": "/lite/phantom",
        "rpc_url": resolve_solana_rpc_url("devnet"),
    }


@app.post("/lite/demo")
async def anukriti_lite_demo(req: AnukritiLiteDemoRequest):
    """Return a self-contained export, proof, verification, and tamper demo."""

    payload = _anukriti_lite_demo_payload(req.workflow)
    attestation = build_trial_export_attestation(payload)

    devnet_submission = {
        "submitted": False,
        "status": "not_requested",
        "message": "Set submit_to_devnet=true to use the local Solana CLI.",
    }
    if req.submit_to_devnet:
        devnet_submission = submit_memo_with_solana_cli(
            attestation["solana"]["memo"],
            network=attestation["network"],
            keypair_path=req.keypair_path,
            rpc_url=req.rpc_url,
        )
        if devnet_submission.get("submitted"):
            attestation = build_trial_export_attestation(
                payload,
                network=attestation["network"],
                proof_status="submitted",
                signature=str(devnet_submission.get("signature") or ""),
            )

    export_with_attestation = dict(payload)
    export_with_attestation["attestation"] = attestation
    verification = verify_trial_export_attestation_detail(payload, attestation)
    tampered_payload = _tamper_lite_payload(payload)
    tamper_check = verify_trial_export_attestation_detail(tampered_payload, attestation)

    return {
        "project": "Anukriti Lite",
        "submission_positioning": "A focused Solana proof layer for deterministic pharmacogenomics trial exports.",
        "submission": _anukriti_lite_submission_metadata(),
        "export": export_with_attestation,
        "verification": verification,
        "tamper_demo": {
            "payload": tampered_payload,
            "verification": tamper_check,
        },
        "devnet_submission": devnet_submission,
    }


@app.get("/lite/phantom", response_class=HTMLResponse)
async def anukriti_lite_phantom_demo():
    """
    Browser-wallet proof page for Phantom users.

    Judges can submit the hash-only memo from a Phantom wallet while all cohort
    rows remain off-chain.
    """

    rpc_url = resolve_solana_rpc_url("devnet")
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Anukriti Lite Phantom Proof</title>
    <script src="https://unpkg.com/@solana/web3.js@1.95.3/lib/index.iife.min.js"></script>
    <style>
      :root {{
        --ink: #17201b;
        --muted: #607066;
        --line: #dbe5dc;
        --accent: #4b57ff;
        --soft: #f4f8f5;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--ink);
        background: #fbfdfb;
      }}
      main {{ width: min(980px, calc(100vw - 32px)); margin: 42px auto; }}
      h1 {{ font-size: 34px; margin: 0 0 10px; letter-spacing: 0; }}
      p {{ color: var(--muted); line-height: 1.6; }}
      .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 22px 0; }}
      .panel {{ border: 1px solid var(--line); border-radius: 8px; padding: 18px; background: white; }}
      button {{
        min-height: 42px;
        border: 0;
        border-radius: 6px;
        padding: 0 14px;
        margin: 4px 8px 4px 0;
        background: var(--accent);
        color: white;
        font-weight: 700;
        cursor: pointer;
      }}
      button.secondary {{ background: #1f2a24; }}
      code, pre {{
        white-space: pre-wrap;
        word-break: break-word;
        background: var(--soft);
        border: 1px solid var(--line);
        border-radius: 6px;
      }}
      code {{ padding: 2px 5px; }}
      pre {{ padding: 14px; max-height: 320px; overflow: auto; }}
      .status {{ font-weight: 700; color: #245c37; }}
      @media (max-width: 760px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    </style>
  </head>
  <body>
    <main>
      <h1>Anukriti Lite Phantom Proof</h1>
      <p>
        Generate a deterministic PGx export, inspect the hash-only Solana memo,
        then sign it with Phantom. Cohort rows stay off-chain.
      </p>
      <div class="grid">
        <section class="panel">
          <h2>Proof Actions</h2>
          <button id="generate">Generate Proof</button>
          <button id="connect" class="secondary">Connect Phantom</button>
          <button id="submit">Sign Memo</button>
          <p class="status" id="status">Ready.</p>
          <p>RPC: <code id="rpc">{rpc_url}</code></p>
        </section>
        <section class="panel">
          <h2>Solana Memo</h2>
          <pre id="memo">No proof generated yet.</pre>
        </section>
      </div>
      <section class="panel">
        <h2>Result</h2>
        <pre id="result">Waiting for action.</pre>
      </section>
    </main>
    <script>
      const MEMO_PROGRAM = new solanaWeb3.PublicKey("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr");
      const RPC_URL = document.getElementById("rpc").textContent;
      const connection = new solanaWeb3.Connection(RPC_URL, "confirmed");
      let proof = null;
      let wallet = null;

      const statusEl = document.getElementById("status");
      const memoEl = document.getElementById("memo");
      const resultEl = document.getElementById("result");

      function setStatus(text) {{ statusEl.textContent = text; }}
      function show(data) {{ resultEl.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2); }}

      document.getElementById("generate").onclick = async () => {{
        setStatus("Generating proof...");
        const resp = await fetch("/lite/demo", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ workflow: "clopidogrel_cyp2c19", submit_to_devnet: false }})
        }});
        proof = await resp.json();
        memoEl.textContent = proof.export.attestation.solana.memo;
        show(proof);
        setStatus("Proof generated.");
      }};

      document.getElementById("connect").onclick = async () => {{
        const provider = window.phantom?.solana || window.solana;
        if (!provider?.isPhantom) {{
          setStatus("Phantom not found. Install Phantom or use prepared proof mode.");
          return;
        }}
        const connected = await provider.connect();
        wallet = provider;
        setStatus(`Connected: ${{connected.publicKey.toString()}}`);
      }};

      document.getElementById("submit").onclick = async () => {{
        if (!proof) {{
          setStatus("Generate a proof first.");
          return;
        }}
        if (!wallet) {{
          await document.getElementById("connect").onclick();
        }}
        if (!wallet?.publicKey) {{
          setStatus("Connect Phantom first.");
          return;
        }}
        const memo = proof.export.attestation.solana.memo;
        const tx = new solanaWeb3.Transaction().add(
          new solanaWeb3.TransactionInstruction({{
            keys: [],
            programId: MEMO_PROGRAM,
            data: new TextEncoder().encode(memo)
          }})
        );
        tx.feePayer = wallet.publicKey;
        tx.recentBlockhash = (await connection.getLatestBlockhash("confirmed")).blockhash;
        setStatus("Requesting Phantom signature...");
        const signed = await wallet.signAndSendTransaction(tx);
        setStatus(`Submitted: ${{signed.signature}}`);
        const lookup = await fetch("/attestations/lookup", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{
            signature: signed.signature,
            attestation: proof.export.attestation,
            rpc_url: RPC_URL
          }})
        }});
        show(await lookup.json());
      }};
    </script>
  </body>
</html>"""


# ---------------------------------------------------------------------------
# Polygenic Risk Score (PRS) endpoint
# ---------------------------------------------------------------------------


class PRSRequest(BaseModel):
    """Request body for polygenic risk score analysis."""

    patient_variants: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Dict mapping rsID → alt allele or genotype string. "
            "e.g. {'rs7903146': 'T', 'rs8050136': '0/1'}. "
            "Can be empty — returns default scores based on population averages."
        ),
    )
    ancestry: Optional[str] = Field(
        None,
        description="Superpopulation ancestry code: AFR, AMR, EAS, EUR, SAS. Used for equity contextualization.",
    )


@app.post("/analyze/polygenic-risk")
async def analyze_polygenic_risk(req: PRSRequest):
    """
    Compute simplified polygenic risk scores (PRS) for cardiovascular disease and Type 2 diabetes.

    Uses published GWAS loci from CARDIoGRAM+C4D (CAD) and DIAGRAM (T2D) consortia.
    Demonstrates the PRS equity gap: EUR-trained weights systematically misclassify
    risk in non-European populations, mirroring the pharmacogenomics equity story.

    Input: Patient's variant dosages at known GWAS loci + optional ancestry.
    Output: PRS scores, risk percentiles, equity analysis, and per-locus breakdown.

    Variant data can be sourced from 1000 Genomes HTTPS streaming (no local download).
    See /vcf-datasets/streaming-status for streaming availability.

    IMPORTANT: Simplified research implementation — NOT for clinical use.
    """
    from src.prs_engine import run_prs_analysis

    try:
        result = run_prs_analysis(
            patient_variants=req.patient_variants,
            ancestry=req.ancestry,
        )
        return result
    except Exception as e:
        logger.error(f"PRS analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PRS analysis error: {e}") from e


@app.get("/analyze/polygenic-risk/loci")
async def polygenic_risk_loci():
    """
    Return the PRS loci definitions for CAD and T2D.
    Useful for understanding which variants to include in a patient variant dict.
    """
    from src.prs_engine import CAD_LOCI, CAD_LOCI_POP_FREQ, T2D_LOCI, T2D_LOCI_POP_FREQ

    return {
        "cardiovascular_cad_loci": {
            rsid: {
                "risk_allele": data[0],
                "effect_size_log_or": data[1],
                "eur_risk_allele_freq": data[2],
                "note": data[3],
                "pop_frequencies": CAD_LOCI_POP_FREQ.get(rsid, {}),
            }
            for rsid, data in CAD_LOCI.items()
        },
        "t2d_loci": {
            rsid: {
                "risk_allele": data[0],
                "effect_size_log_or": data[1],
                "eur_risk_allele_freq": data[2],
                "note": data[3],
                "pop_frequencies": T2D_LOCI_POP_FREQ.get(rsid, {}),
            }
            for rsid, data in T2D_LOCI.items()
        },
        "note": "Simplified PRS loci for research/education. Full clinical PRS uses thousands to millions of loci.",
    }


# ---------------------------------------------------------------------------
# Drug-Drug-Gene Interaction (DDGI) endpoint
# ---------------------------------------------------------------------------


class DDGIRequest(BaseModel):
    """Request body for DDGI analysis."""

    gene_phenotypes: Dict[str, str] = Field(
        ...,
        description="Dict mapping gene name → phenotype string. e.g. {'CYP2D6': 'Poor Metabolizer'}",
    )
    drugs: List[str] = Field(
        ...,
        min_length=2,
        description="List of drug names the patient is taking concurrently (minimum 2 for interaction detection).",
    )
    min_risk_level: str = Field(
        "MODERATE",
        description="Minimum risk level to include in results: LOW, MODERATE, HIGH, CRITICAL.",
    )


@app.post("/analyze/ddgi")
async def analyze_ddgi(req: DDGIRequest):
    """
    Detect Drug-Drug-Gene Interactions (DDGI) for a patient's PGx profile.

    DDGI occurs when a patient's pharmacogenomic variant amplifies or modifies
    a standard drug-drug interaction, creating compounded risk beyond what either
    the DDI or the PGx variant alone would predict.

    Examples:
    - CYP2D6 Poor Metabolizer + codeine + fluoxetine → triple opioid toxicity risk
    - CYP2C19 Poor Metabolizer + clopidogrel + omeprazole → antiplatelet failure
    - CYP2B6 Poor Metabolizer + efavirenz + rifampin → HIV/TB coinfection risk
    - TPMT Poor Metabolizer + azathioprine + allopurinol → CRITICAL myelosuppression

    All interactions are evidence-based with CPIC citations. Equity notes flag
    interactions with disproportionate population-specific impact.

    Returns structured findings with risk levels, mechanisms, and recommendations.
    """
    from src.ddgi_engine import find_ddgi, summarize_ddgi

    if len(req.drugs) < 2:
        raise HTTPException(
            status_code=422,
            detail="At least 2 drugs are required for drug-drug-gene interaction analysis.",
        )

    try:
        findings = find_ddgi(
            gene_phenotypes=req.gene_phenotypes,
            drugs=req.drugs,
            min_risk_level=req.min_risk_level,
        )
        summary = summarize_ddgi(findings)

        return {
            "gene_phenotypes_analyzed": req.gene_phenotypes,
            "drugs_analyzed": req.drugs,
            "min_risk_level": req.min_risk_level,
            "summary": summary,
            "interactions": findings,
            "disclaimer": (
                "DDGI findings are based on published pharmacological evidence and CPIC guidelines. "
                "This is a research tool. Consult a clinical pharmacist before making prescribing decisions."
            ),
        }
    except Exception as e:
        logger.error(f"DDGI analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"DDGI analysis error: {e}") from e


# ---------------------------------------------------------------------------
# FHIR Genomics Report endpoint
# ---------------------------------------------------------------------------


class FHIRReportRequest(BaseModel):
    """Request body for the FHIR Genomics Report endpoint."""

    patient_id: str = Field(
        ..., description="De-identified patient or sample identifier"
    )
    drug_name: Optional[str] = Field(None, description="Drug being analyzed")
    ancestry: Optional[str] = Field(
        None, description="Reported patient ancestry (e.g. AFR, EUR, EAS)"
    )
    gene_results: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "List of gene result dicts. Each must contain: gene (str), diplotype (str), "
            "phenotype (str). Optional: recommendation (str), cpic_level (str), drug_name (str)."
        ),
    )
    report_id: Optional[str] = Field(
        None, description="Stable report ID for idempotent requests"
    )


@app.post("/analyze/fhir-report")
async def analyze_fhir_report(req: FHIRReportRequest):
    """
    Generate an HL7 FHIR R4 Genomics Reporting bundle from PGx results.

    Outputs a FHIR R4 Bundle (transaction) conformant with the HL7 FHIR
    Genomics Reporting Implementation Guide, containing:
      - DiagnosticReport (genomics-report profile)
      - Observation/genotype — diplotype and phenotype per gene
      - Observation/therapeutic-implication — dosing guidance per drug-gene pair

    This format is compatible with Epic SMART on FHIR, Cerner FHIR API, and
    other HL7 R4 compliant EHR systems. Intended for EHR integration pilots.

    Example use: POST gene_results from /analyze output to get FHIR bundle.
    """
    from src.fhir_genomics import build_fhir_genomics_report

    if not req.gene_results:
        raise HTTPException(
            status_code=422,
            detail=(
                "gene_results is required and must contain at least one gene result dict "
                "with keys: gene, diplotype, phenotype."
            ),
        )

    try:
        bundle = build_fhir_genomics_report(
            patient_id=req.patient_id,
            gene_results=req.gene_results,
            drug_name=req.drug_name,
            ancestry=req.ancestry,
            report_id=req.report_id,
        )
        return bundle
    except Exception as e:
        logger.error(f"FHIR report generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"FHIR report generation error: {e}"
        ) from e


if __name__ == "__main__":
    import uvicorn

    # Get port from environment or use default
    port = int(os.getenv("PORT", 8000))

    logger.info(f"Starting Anukriti AI API on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)  # nosec B104 - bind all for container

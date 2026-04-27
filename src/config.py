"""
Configuration Management Module

Centralized configuration for SynthaTrial with validation and defaults.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _optional_stripped_env(name: str) -> Optional[str]:
    v = os.getenv(name)
    if not v:
        return None
    s = v.strip()
    return s or None


class Config:
    """
    Centralized configuration class for SynthaTrial.

    All configuration values are loaded from environment variables with
    sensible defaults. Required values are validated on access.
    """

    # API Keys / external services
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY") or os.getenv(
        "GEMINI_API_KEY"
    )
    PINECONE_API_KEY: Optional[str] = _optional_stripped_env("PINECONE_API_KEY")
    PINECONE_INDEX: str = os.getenv("PINECONE_INDEX", "drug-index")

    # LLM Configuration (Nova on Bedrock default; override with LLM_BACKEND in .env)
    LLM_BACKEND: str = os.getenv("LLM_BACKEND", "nova").lower()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.1"))
    GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    GEMINI_TIMEOUT: int = int(os.getenv("GEMINI_TIMEOUT", "60"))

    # Bedrock (Titan embeddings + Claude + Nova) configuration
    BEDROCK_REGION: str = os.getenv("BEDROCK_REGION", "us-east-1")
    TITAN_EMBED_MODEL: str = os.getenv(
        "TITAN_EMBED_MODEL", "amazon.titan-embed-text-v2:0"
    )
    CLAUDE_MODEL: str = os.getenv(
        "CLAUDE_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"
    )
    # Amazon Nova on Bedrock: Lite vs Pro (PGx explanations). Legacy NOVA_MODEL maps to Lite ID.
    NOVA_DEFAULT_VARIANT: str = os.getenv("NOVA_DEFAULT_VARIANT", "lite").lower()
    NOVA_LITE_MODEL: str = os.getenv(
        "NOVA_LITE_MODEL",
        os.getenv("NOVA_MODEL", "amazon.nova-lite-v1:0"),
    )
    NOVA_PRO_MODEL: str = os.getenv("NOVA_PRO_MODEL", "amazon.nova-pro-v1:0")

    # QVAC local LLM bridge (Colosseum partner track). Requires Node.js and @qvac/sdk.
    QVAC_ENABLED: bool = os.getenv("QVAC_ENABLED", "true").lower() == "true"
    QVAC_NODE_BIN: str = os.getenv("QVAC_NODE_BIN", "node")
    QVAC_SCRIPT_PATH: str = os.getenv(
        "QVAC_SCRIPT_PATH",
        str(Path(__file__).resolve().parent.parent / "qvac" / "qvac_pgx_explain.mjs"),
    )
    QVAC_TIMEOUT_SECONDS: int = int(os.getenv("QVAC_TIMEOUT_SECONDS", "180"))
    QVAC_MODEL_LABEL: str = os.getenv("QVAC_MODEL_LABEL", "LLAMA_3_2_1B_INST_Q4_0")

    # Pinecone Configuration
    PINECONE_MAX_RETRIES: int = int(os.getenv("PINECONE_MAX_RETRIES", "3"))
    PINECONE_TIMEOUT: int = int(os.getenv("PINECONE_TIMEOUT", "30"))
    PINECONE_TOP_K: int = int(os.getenv("PINECONE_TOP_K", "3"))

    # Vector DB backend configuration (pinecone | opensearch | qdrant | local | mock)
    VECTOR_DB_BACKEND: str = os.getenv("VECTOR_DB_BACKEND", "pinecone").lower()

    # Embedding backend (bedrock | local)
    EMBEDDING_BACKEND: str = os.getenv("EMBEDDING_BACKEND", "bedrock").lower()

    # AWS OpenSearch vector search configuration
    OPENSEARCH_HOST: Optional[str] = os.getenv("OPENSEARCH_HOST")
    OPENSEARCH_INDEX: str = os.getenv("OPENSEARCH_INDEX", "drug-index")
    OPENSEARCH_REGION: str = os.getenv(
        "OPENSEARCH_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    )
    OPENSEARCH_SERVICE: str = os.getenv("OPENSEARCH_SERVICE", "aoss")
    OPENSEARCH_VECTOR_FIELD: str = os.getenv("OPENSEARCH_VECTOR_FIELD", "vector")
    OPENSEARCH_TOP_K: int = int(os.getenv("OPENSEARCH_TOP_K", "3"))

    # Vector Search Configuration
    FINGERPRINT_BITS: int = 2048
    FINGERPRINT_RADIUS: int = 2

    # VCF Configuration
    VCF_CHR22_PATH: Optional[str] = os.getenv("VCF_CHR22_PATH")
    VCF_CHR10_PATH: Optional[str] = os.getenv("VCF_CHR10_PATH")
    VCF_BATCH_SIZE: int = int(os.getenv("VCF_BATCH_SIZE", "1000"))

    # ChEMBL Configuration
    CHEMBL_DB_PATH: Optional[str] = os.getenv("CHEMBL_DB_PATH")
    CHEMBL_LIMIT: int = int(os.getenv("CHEMBL_LIMIT", "1000"))

    # Caching Configuration
    ENABLE_CACHING: bool = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour

    # Local (free) vector-search cache
    # Used when VECTOR_DB_BACKEND=local to avoid any OpenSearch/Pinecone costs.
    LOCAL_VECTOR_CACHE_DIR: str = os.getenv(
        "LOCAL_VECTOR_CACHE_DIR",
        str(Path(__file__).resolve().parent.parent / "data" / "vector_index_cache"),
    )
    LOCAL_VECTOR_REBUILD: bool = (
        os.getenv("LOCAL_VECTOR_REBUILD", "false").lower() == "true"
    )

    # Optional sklearn reranker for local similar-drug retrieval (train: scripts/train_drug_reranker.py)
    DRUG_RERANKER_PATH: Optional[str] = os.getenv("DRUG_RERANKER_PATH")
    DRUG_RERANKER_POOL: int = int(os.getenv("DRUG_RERANKER_POOL", "40"))

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()

    @classmethod
    def validate_required(cls) -> tuple[bool, list[str]]:
        """
        Validate that required configuration values are set.
        In PRODUCTION, checks are stricter.

        Returns:
            Tuple of (is_valid, list_of_missing_keys)
        """
        missing = []

        # Google API key is required when using Gemini backend
        if cls.LLM_BACKEND == "gemini" and not cls.GOOGLE_API_KEY:
            missing.append("GOOGLE_API_KEY or GEMINI_API_KEY (required for Gemini)")

        # Bedrock / Nova: check AWS credentials are present (not just at runtime)
        if cls.LLM_BACKEND in ("bedrock", "nova"):
            has_key = bool(os.getenv("AWS_ACCESS_KEY_ID"))
            has_secret = bool(os.getenv("AWS_SECRET_ACCESS_KEY"))
            # IAM role on EC2 provides credentials without env vars — only warn
            # when neither env vars nor a role profile is detectable.
            if not has_key and not has_secret:
                missing.append(
                    "AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY "
                    "(required for Bedrock/Nova unless running on EC2 with IAM role)"
                )

        # Direct Anthropic Claude
        if cls.LLM_BACKEND == "claude":
            if not os.getenv("ANTHROPIC_API_KEY"):
                missing.append("ANTHROPIC_API_KEY (required for LLM_BACKEND=claude)")

        if cls.LLM_BACKEND == "qvac" and not cls.QVAC_ENABLED:
            missing.append("QVAC_ENABLED=true (required for LLM_BACKEND=qvac)")

        # In PRODUCTION, Pinecone is required (no mocks allowed)
        if cls.ENVIRONMENT == "production":
            backend = cls.VECTOR_DB_BACKEND
            if backend in {"pinecone", "auto"} and not cls.PINECONE_API_KEY:
                # Keep backward-compatible strictness for existing production setups.
                if backend == "pinecone":
                    missing.append(
                        "PINECONE_API_KEY (Required when VECTOR_DB_BACKEND=pinecone)"
                    )
            if backend == "opensearch" and not cls.OPENSEARCH_HOST:
                missing.append(
                    "OPENSEARCH_HOST (Required when VECTOR_DB_BACKEND=opensearch)"
                )
        else:
            # In Development, it's optional (mock fallback)
            pass

        return len(missing) == 0, missing

    @classmethod
    def is_production(cls) -> bool:
        return cls.ENVIRONMENT == "production"

    @classmethod
    def get_summary(cls) -> dict:
        """
        Get a summary of current configuration (without sensitive values).

        Returns:
            Dictionary with configuration summary
        """
        return {
            "environment": cls.ENVIRONMENT,
            "llm_backend": cls.LLM_BACKEND,
            "gemini_model": cls.GEMINI_MODEL,
            "gemini_temperature": cls.GEMINI_TEMPERATURE,
            "claude_model": cls.CLAUDE_MODEL,
            "nova_default_variant": cls.NOVA_DEFAULT_VARIANT,
            "nova_lite_model": cls.NOVA_LITE_MODEL,
            "nova_pro_model": cls.NOVA_PRO_MODEL,
            "qvac_enabled": cls.QVAC_ENABLED,
            "qvac_model_label": cls.QVAC_MODEL_LABEL,
            "qvac_script_path": cls.QVAC_SCRIPT_PATH,
            "vector_db_backend": cls.VECTOR_DB_BACKEND,
            "pinecone_index": cls.PINECONE_INDEX,
            "opensearch_host_set": bool(cls.OPENSEARCH_HOST),
            "opensearch_index": cls.OPENSEARCH_INDEX,
            "fingerprint_bits": cls.FINGERPRINT_BITS,
            "caching_enabled": cls.ENABLE_CACHING,
            "log_level": cls.LOG_LEVEL,
            "has_google_api_key": bool(cls.GOOGLE_API_KEY),
            "has_pinecone_api_key": bool(cls.PINECONE_API_KEY),
        }


# Create a singleton instance
config = Config()


def resolve_nova_model_id(variant: Optional[str] = None) -> str:
    """
    Map nova_variant lite|pro to Bedrock model IDs.
    Falls back to NOVA_DEFAULT_VARIANT when variant is None.
    """
    v = (variant or config.NOVA_DEFAULT_VARIANT or "lite").strip().lower()
    if v in ("pro", "nova-pro", "nova_pro"):
        return config.NOVA_PRO_MODEL
    return config.NOVA_LITE_MODEL

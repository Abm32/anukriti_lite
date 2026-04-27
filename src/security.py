"""
Security middleware and helpers for the Anukriti API.

Provides:
- API key authentication via X-API-Key header (optional; disabled when
  API_KEY_REQUIRED=false or API_KEYS env var is empty)
- Request size limiting middleware
- VCF upload validation (size cap + gzip magic bytes)
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Comma-separated list of valid API keys.  Empty = auth disabled (dev mode).
_RAW_KEYS = os.getenv("API_KEYS", "")
_VALID_KEYS: set[str] = {k.strip() for k in _RAW_KEYS.split(",") if k.strip()}

# Set API_KEY_REQUIRED=true to enforce auth even in development.
_KEY_REQUIRED: bool = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"

# Maximum allowed JSON body size (bytes).  Default 10 MB.
MAX_BODY_BYTES: int = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(10 * 1024 * 1024)))

# Maximum VCF upload size (bytes).  Default 5 GB.
MAX_VCF_BYTES: int = int(os.getenv("MAX_VCF_UPLOAD_BYTES", str(5 * 1024 * 1024 * 1024)))

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ---------------------------------------------------------------------------
# API key dependency
# ---------------------------------------------------------------------------


async def verify_api_key(api_key: Optional[str] = Security(_api_key_header)) -> None:
    """
    FastAPI dependency that enforces API key auth when configured.

    Auth is skipped when:
    - API_KEYS env var is empty (no keys configured), OR
    - API_KEY_REQUIRED is not set to "true"

    Usage::

        @app.post("/analyze")
        async def analyze(request: AnalyzeRequest, _: None = Depends(verify_api_key)):
            ...
    """
    if not _VALID_KEYS or not _KEY_REQUIRED:
        return  # auth disabled
    if not api_key or api_key not in _VALID_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Provide a valid key in the X-API-Key header.",
        )


# ---------------------------------------------------------------------------
# Request size middleware
# ---------------------------------------------------------------------------


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Reject requests whose Content-Length exceeds MAX_BODY_BYTES before reading
    the body.  Protects JSON endpoints from memory exhaustion.
    VCF file uploads are handled separately with a higher limit.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip size check for VCF upload endpoints (they have their own limit)
        if request.url.path.startswith("/vcf"):
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_BODY_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": (
                                f"Request body too large. "
                                f"Maximum allowed: {MAX_BODY_BYTES // (1024*1024)} MB."
                            )
                        },
                    )
            except ValueError:
                pass  # malformed header; let FastAPI handle it
        return await call_next(request)


# ---------------------------------------------------------------------------
# VCF upload validation helpers
# ---------------------------------------------------------------------------

GZIP_MAGIC = b"\x1f\x8b"


def validate_vcf_upload(
    filename: str, first_bytes: bytes, file_size: Optional[int]
) -> None:
    """
    Validate a VCF upload before writing to disk.

    Raises HTTPException(400/413) on invalid input.
    """
    # Filename must end with .vcf.gz
    if not filename.endswith(".vcf.gz"):
        raise HTTPException(
            status_code=400,
            detail="VCF file must be bgzipped (.vcf.gz). Plain .vcf files are not supported.",
        )

    # Content must start with gzip magic bytes
    if len(first_bytes) >= 2 and first_bytes[:2] != GZIP_MAGIC:
        raise HTTPException(
            status_code=400,
            detail="File does not appear to be gzip-compressed. Ensure the file is bgzipped.",
        )

    # Enforce size cap when Content-Length is known
    if file_size is not None and file_size > MAX_VCF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"VCF file too large ({file_size / (1024**3):.1f} GB). "
                f"Maximum allowed: {MAX_VCF_BYTES // (1024**3)} GB."
            ),
        )

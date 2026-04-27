"""
Custom Exception Classes for Anukriti

Provides structured error handling with context and proper error messages.
"""

from typing import Any, Dict, Optional


class AnukritiError(Exception):
    """Base exception for all Anukriti errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize exception with message and optional context.

        Args:
            message: Human-readable error message
            context: Additional context dictionary for debugging
        """
        super().__init__(message)
        self.message = message
        self.context: Dict[str, Any] = context or {}

    def __str__(self) -> str:
        """Return formatted error message with context."""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (Context: {context_str})"
        return self.message


class InvalidSMILESError(AnukritiError):
    """Raised when SMILES string is invalid."""

    def __init__(self, smiles: str, reason: str = None):
        """
        Initialize with invalid SMILES string.

        Args:
            smiles: The invalid SMILES string
            reason: Optional reason why it's invalid
        """
        message = f"Invalid SMILES string: {smiles[:50]}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, context={"smiles": smiles, "reason": reason})


class VCFProcessingError(AnukritiError):
    """Raised when VCF file processing fails."""

    def __init__(self, message: str, vcf_path: str = None, line_number: int = None):
        """
        Initialize with VCF processing error.

        Args:
            message: Error message
            vcf_path: Path to VCF file (if applicable)
            line_number: Line number where error occurred (if applicable)
        """
        context: Dict[str, Any] = {}
        if vcf_path:
            context["vcf_path"] = vcf_path
        if line_number:
            context["line_number"] = line_number
        super().__init__(message, context=context)


class VectorSearchError(AnukritiError):
    """Raised when vector search operation fails."""

    def __init__(
        self, message: str, index_name: str = None, query_vector_size: int = None
    ):
        """
        Initialize with vector search error.

        Args:
            message: Error message
            index_name: Pinecone index name (if applicable)
            query_vector_size: Size of query vector (if applicable)
        """
        context: Dict[str, Any] = {}
        if index_name:
            context["index_name"] = index_name
        if query_vector_size:
            context["query_vector_size"] = query_vector_size
        super().__init__(message, context=context)


class LLMError(AnukritiError):
    """Raised when LLM API call fails."""

    def __init__(
        self,
        message: str,
        model: str = None,
        retry_count: int = None,
        status_code: int = None,
    ):
        """
        Initialize with LLM error.

        Args:
            message: Error message
            model: LLM model name (if applicable)
            retry_count: Number of retries attempted (if applicable)
            status_code: HTTP status code (if applicable)
        """
        context: Dict[str, Any] = {}
        if model:
            context["model"] = model
        if retry_count is not None:
            context["retry_count"] = retry_count
        if status_code:
            context["status_code"] = status_code
        super().__init__(message, context=context)


class ConfigurationError(AnukritiError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, missing_keys: list = None):
        """
        Initialize with configuration error.

        Args:
            message: Error message
            missing_keys: List of missing configuration keys (if applicable)
        """
        context: Dict[str, Any] = {}
        if missing_keys:
            context["missing_keys"] = missing_keys
        super().__init__(message, context=context)


class ChEMBLProcessingError(AnukritiError):
    """Raised when ChEMBL database processing fails."""

    def __init__(self, message: str, db_path: str = None, molregno: int = None):
        """
        Initialize with ChEMBL processing error.

        Args:
            message: Error message
            db_path: Path to ChEMBL database (if applicable)
            molregno: ChEMBL molecule registration number (if applicable)
        """
        context: Dict[str, Any] = {}
        if db_path:
            context["db_path"] = db_path
        if molregno:
            context["molregno"] = molregno
        super().__init__(message, context=context)

"""
Logging Configuration Module

Sets up structured logging for Anukriti with configurable levels and outputs.
Adds request_id support for correlating Streamlit → FastAPI → Bedrock call chains.
"""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

from src.config import config

# ---------------------------------------------------------------------------
# Request-ID context variable
# ---------------------------------------------------------------------------
# Set this at the start of each request so all log records within that
# request carry the same ID.  Works across async tasks in the same context.

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def new_request_id() -> str:
    """Generate a short request ID and store it in the context."""
    rid = uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    return rid


def get_request_id() -> str:
    return request_id_var.get()


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------


class _JsonFormatter(logging.Formatter):
    """
    Emit each log record as a single JSON line.

    Fields: timestamp, level, logger, request_id, message, [exc_info]
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Plain-text formatter (dev / human-readable)
# ---------------------------------------------------------------------------

_PLAIN_FMT = "%(asctime)s [%(request_id)s] %(name)s %(levelname)s - %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


class _RequestIdFilter(logging.Filter):
    """Inject request_id into every LogRecord so plain formatters can use it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()  # type: ignore[attr-defined]
        return True


# ---------------------------------------------------------------------------
# Public setup function
# ---------------------------------------------------------------------------


def setup_logging(
    log_file: Optional[str] = None, log_level: Optional[str] = None
) -> None:
    """
    Configure root logger.

    - JSON output when LOG_FORMAT=json (default in production)
    - Plain text otherwise (dev-friendly)
    - Optional file handler via LOG_FILE / log_file arg
    """
    level_str = (log_level or config.LOG_LEVEL or "INFO").upper()
    numeric_level = getattr(logging, level_str, logging.INFO)

    file_path = log_file or config.LOG_FILE
    use_json = os.getenv("LOG_FORMAT", "plain").lower() == "json"

    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.handlers.clear()

    rid_filter = _RequestIdFilter()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    if use_json:
        console.setFormatter(_JsonFormatter())
    else:
        fmt = logging.Formatter(_PLAIN_FMT, datefmt=_DATE_FMT)
        console.setFormatter(fmt)
    console.addFilter(rid_filter)
    root.addHandler(console)

    # Optional file handler
    if file_path:
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(file_path)
            fh.setLevel(numeric_level)
            fh.setFormatter(_JsonFormatter())  # always JSON in files
            fh.addFilter(rid_filter)
            root.addHandler(fh)
        except Exception as exc:
            logging.warning(f"Could not set up file logging: {exc}")

    # Quiet noisy third-party loggers
    for noisy in ("urllib3", "pinecone", "langchain", "botocore", "boto3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.info(
        "Logging configured",
        extra={"level": level_str, "json": use_json, "file": file_path},
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Lazy import guard for os (used in setup_logging)
# ---------------------------------------------------------------------------
import os  # noqa: E402  (placed after class defs to avoid circular at module load)

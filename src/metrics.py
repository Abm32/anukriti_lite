"""
Lightweight in-process metrics for Anukriti.

Tracks vector search backend usage and fallback rates so operators can tell
when Pinecone/OpenSearch is silently failing and mock data is being served.

Exposed via GET /metrics in api.py.
No external dependencies — pure Python thread-safe counters.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Any, Dict

_lock = Lock()

# Counters: backend_name -> count
_search_attempts: Dict[str, int] = defaultdict(int)
_search_fallbacks: Dict[str, int] = defaultdict(int)  # fell back to mock
_search_errors: Dict[str, int] = defaultdict(int)

# LLM call counters: backend_name -> count
_llm_calls: Dict[str, int] = defaultdict(int)
_llm_timeouts: Dict[str, int] = defaultdict(int)
_llm_errors: Dict[str, int] = defaultdict(int)

_start_time: float = time.time()


# ---------------------------------------------------------------------------
# Vector search recording
# ---------------------------------------------------------------------------


def record_search(
    backend: str, *, fell_back: bool = False, error: bool = False
) -> None:
    """Record one vector search attempt."""
    with _lock:
        _search_attempts[backend] += 1
        if fell_back:
            _search_fallbacks[backend] += 1
        if error:
            _search_errors[backend] += 1


# ---------------------------------------------------------------------------
# LLM call recording
# ---------------------------------------------------------------------------


def record_llm_call(
    backend: str, *, timeout: bool = False, error: bool = False
) -> None:
    """Record one LLM call attempt."""
    with _lock:
        _llm_calls[backend] += 1
        if timeout:
            _llm_timeouts[backend] += 1
        if error:
            _llm_errors[backend] += 1


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def snapshot() -> Dict[str, Any]:
    """Return a point-in-time snapshot of all counters."""
    with _lock:
        uptime = round(time.time() - _start_time, 1)
        backends = sorted(
            set(_search_attempts) | set(_search_fallbacks) | set(_search_errors)
        )
        vector_search = {}
        for b in backends:
            attempts = _search_attempts[b]
            fallbacks = _search_fallbacks[b]
            fallback_rate = round(fallbacks / attempts, 4) if attempts else 0.0
            vector_search[b] = {
                "attempts": attempts,
                "fallbacks_to_mock": fallbacks,
                "errors": _search_errors[b],
                "fallback_rate": fallback_rate,
            }

        llm_backends = sorted(set(_llm_calls) | set(_llm_timeouts) | set(_llm_errors))
        llm = {}
        for b in llm_backends:
            calls = _llm_calls[b]
            timeouts = _llm_timeouts[b]
            timeout_rate = round(timeouts / calls, 4) if calls else 0.0
            llm[b] = {
                "calls": calls,
                "timeouts": _llm_timeouts[b],
                "errors": _llm_errors[b],
                "timeout_rate": timeout_rate,
            }

        return {
            "uptime_seconds": uptime,
            "vector_search": vector_search,
            "llm": llm,
        }

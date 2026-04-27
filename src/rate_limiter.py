"""
Bedrock Rate Limiter
Prevents quota exhaustion during high-traffic periods

This module implements a token bucket rate limiter to prevent AWS Bedrock
quota exhaustion during competition demos and high-traffic scenarios.
"""

import logging
import time
from collections import deque
from threading import Lock
from typing import Deque, Optional

logger = logging.getLogger(__name__)


class BedrockRateLimiter:
    """
    Token bucket rate limiter for Bedrock API calls

    Prevents quota exhaustion by throttling requests when approaching limits.
    Thread-safe implementation suitable for multi-threaded applications.
    """

    def __init__(self, requests_per_minute: int = 100):
        """
        Initialize rate limiter

        Args:
            requests_per_minute: Maximum requests allowed per minute
        """
        self.requests_per_minute = requests_per_minute
        self.request_queue: Deque[float] = deque()
        self.lock = Lock()
        logger.info(f"BedrockRateLimiter initialized: {requests_per_minute} req/min")

    def throttle(self) -> None:
        """
        Wait if rate limit would be exceeded

        Implements token bucket algorithm:
        1. Remove requests older than 1 minute
        2. Check if at capacity
        3. Wait until oldest request expires if needed
        4. Add current request to queue
        """
        with self.lock:
            now = time.time()

            # Remove requests older than 1 minute
            while self.request_queue and self.request_queue[0] < now - 60:
                self.request_queue.popleft()

            # Check if at capacity
            if len(self.request_queue) >= self.requests_per_minute:
                # Calculate wait time until oldest request expires
                sleep_time = 60 - (now - self.request_queue[0]) + 0.1
                logger.warning(
                    f"Rate limit reached ({self.requests_per_minute} req/min), "
                    f"waiting {sleep_time:.1f}s"
                )
                time.sleep(sleep_time)
                # Retry after waiting
                return self.throttle()

            # Add current request
            self.request_queue.append(now)

            # Log if approaching limit
            if len(self.request_queue) > self.requests_per_minute * 0.8:
                logger.warning(
                    f"Approaching rate limit: {len(self.request_queue)}/{self.requests_per_minute} "
                    f"requests in last minute"
                )

    def get_current_rate(self) -> int:
        """
        Get current request rate (requests in last minute)

        Returns:
            Number of requests in the last 60 seconds
        """
        with self.lock:
            now = time.time()
            # Remove old requests
            while self.request_queue and self.request_queue[0] < now - 60:
                self.request_queue.popleft()
            return len(self.request_queue)

    def reset(self) -> None:
        """Reset rate limiter (clear all tracked requests)"""
        with self.lock:
            self.request_queue.clear()
            logger.info("Rate limiter reset")


# Global rate limiter instances for different Bedrock models
nova_rate_limiter = BedrockRateLimiter(requests_per_minute=100)  # Conservative default
titan_rate_limiter = BedrockRateLimiter(requests_per_minute=100)  # For embeddings


def get_rate_limiter(model_type: str = "nova") -> BedrockRateLimiter:
    """
    Get rate limiter for specific model type

    Args:
        model_type: Type of model ("nova", "titan", "claude")

    Returns:
        Appropriate rate limiter instance
    """
    if model_type == "titan":
        return titan_rate_limiter
    return nova_rate_limiter

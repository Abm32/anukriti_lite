"""
Resilience Utils
Implements patterns like Circuit Breaker for robust service interaction.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitBreakerOpenError(Exception):
    """Raised when the circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    Simple Circuit Breaker implementation.

    States:
    - CLOSED: Normal operation, passing requests through.
    - OPEN: Circuit broken, failing immediately.
    - HALF-OPEN: Testing if service recovered.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout: int = 60,
        name: str = "CircuitBreaker",
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.name = name

        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call the decorated function with circuit breaker logic."""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout:
                logger.info(f"Circuit Breaker '{self.name}' entering HALF-OPEN state")
                self.state = "HALF-OPEN"
            else:
                logger.warning(f"Circuit Breaker '{self.name}' is OPEN. Failing fast.")
                raise CircuitBreakerOpenError(
                    f"Circuit '{self.name}' is open due to repeated failures."
                )

        try:
            result = func(*args, **kwargs)

            if self.state == "HALF-OPEN":
                logger.info(
                    f"Circuit Breaker '{self.name}' recovered. Resetting to CLOSED."
                )
                self.reset()

            return result

        except Exception as e:
            self._handle_failure(e)
            raise

    def _handle_failure(self, error: Exception):
        """Record failure and update state."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == "HALF-OPEN" or self.failure_count >= self.failure_threshold:
            if self.state != "OPEN":
                logger.error(
                    f"Circuit Breaker '{self.name}' tripped OPEN after {self.failure_count} failures. Error: {error}"
                )
                self.state = "OPEN"
        else:
            logger.warning(
                f"Circuit Breaker '{self.name}' recorded failure {self.failure_count}/{self.failure_threshold}. Error: {error}"
            )

    def reset(self):
        """Reset the circuit breaker."""
        self.failure_count = 0
        self.state = "CLOSED"


def circuit_breaker(
    failure_threshold: int = 3, reset_timeout: int = 60, name: str = None
):
    """Decorator for Circuit Breaker."""

    def decorator(func):
        # Create a circuit breaker instance for this function
        # Using a closure to keep state (one breaker per decorated function)
        cb_name = name or func.__name__
        breaker = CircuitBreaker(failure_threshold, reset_timeout, cb_name)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        # Expose breaker for testing/querying
        wrapper.breaker = breaker
        return wrapper

    return decorator

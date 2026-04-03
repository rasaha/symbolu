"""
Rate Limiting Module (Sliding Window, In-Memory)

This module provides deterministic rate limiting for Symbol-U API endpoints.

Implementation:
    - Sliding window algorithm (60-second buckets)
    - In-memory storage (dict of IP -> timestamps)
    - Configurable limit via SYMBOLU_RATE_LIMIT environment variable
    - Default: 60 requests per minute

Behavior:
    - Tracks requests by client IP address
    - Removes expired timestamps (older than 60 seconds)
    - Returns 429 when limit is exceeded

Design:
    - Zero-LLM: purely deterministic time-based logic
    - Thread-safe for single-process deployments
    - Non-invasive: doesn't modify pipeline behavior
"""

import os
import time
import logging
from typing import Dict, List
from collections import defaultdict

try:
    from fastapi import Request, HTTPException
    FASTAPI_AVAILABLE = True
except ImportError:
    Request = None
    HTTPException = None
    FASTAPI_AVAILABLE = False

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_RATE_LIMIT = 60  # requests per minute
WINDOW_SIZE_SECONDS = 60  # sliding window duration


class RateLimiter:
    """
    Sliding window rate limiter with in-memory storage.

    This class implements a simple but effective rate limiting algorithm:
    1. Store timestamps of recent requests per client IP
    2. On each request, remove timestamps older than window size
    3. If remaining count < limit, allow request and record timestamp
    4. Otherwise, deny request

    Attributes:
        limit: Maximum requests allowed per window (configurable)
        window_size: Duration of sliding window in seconds (default: 60)
        request_log: Dict mapping client IPs to timestamp lists
    """

    def __init__(self, limit: int = None, window_size: int = WINDOW_SIZE_SECONDS):
        """
        Initialize rate limiter.

        Args:
            limit: Maximum requests per window (defaults to SYMBOLU_RATE_LIMIT env var or 60)
            window_size: Window size in seconds (default: 60)
        """
        # Load limit from environment or use provided/default value
        if limit is None:
            env_limit = os.environ.get("SYMBOLU_RATE_LIMIT")
            if env_limit:
                try:
                    limit = int(env_limit)
                    logger.info(f"Rate limit loaded from environment: {limit} req/min")
                except ValueError:
                    logger.warning(
                        f"Invalid SYMBOLU_RATE_LIMIT value: {env_limit}. "
                        f"Using default: {DEFAULT_RATE_LIMIT}"
                    )
                    limit = DEFAULT_RATE_LIMIT
            else:
                limit = DEFAULT_RATE_LIMIT

        self.limit = limit
        self.window_size = window_size
        self.request_log: Dict[str, List[float]] = defaultdict(list)

        logger.info(
            f"RateLimiter initialized: {self.limit} requests per "
            f"{self.window_size} seconds"
        )

    def _clean_old_timestamps(self, client_ip: str, current_time: float) -> None:
        """
        Remove timestamps older than the window size.

        Args:
            client_ip: Client IP address
            current_time: Current timestamp
        """
        cutoff_time = current_time - self.window_size
        self.request_log[client_ip] = [
            ts for ts in self.request_log[client_ip]
            if ts > cutoff_time
        ]

    def allow(self, client_ip: str) -> bool:
        """
        Check if request from client IP should be allowed.

        This method implements the core rate limiting logic:
        1. Get current time
        2. Remove expired timestamps for this IP
        3. Check if count is under limit
        4. If yes: record timestamp and allow
        5. If no: deny request

        Args:
            client_ip: Client IP address to check

        Returns:
            bool: True if request is allowed, False if rate limit exceeded
        """
        current_time = time.time()

        # Clean old timestamps
        self._clean_old_timestamps(client_ip, current_time)

        # Check if under limit
        request_count = len(self.request_log[client_ip])

        if request_count < self.limit:
            # Allow request and record timestamp
            self.request_log[client_ip].append(current_time)
            logger.debug(
                f"Request allowed for {client_ip} "
                f"({request_count + 1}/{self.limit})"
            )
            return True
        else:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded for {client_ip} "
                f"({request_count}/{self.limit})"
            )
            return False

    def get_remaining(self, client_ip: str) -> int:
        """
        Get remaining requests available for client IP.

        Args:
            client_ip: Client IP address

        Returns:
            int: Number of requests remaining in current window
        """
        current_time = time.time()
        self._clean_old_timestamps(client_ip, current_time)
        used = len(self.request_log[client_ip])
        return max(0, self.limit - used)

    def reset(self, client_ip: str = None) -> None:
        """
        Reset rate limit data.

        Args:
            client_ip: If provided, reset only this IP. Otherwise, reset all.
        """
        if client_ip:
            if client_ip in self.request_log:
                del self.request_log[client_ip]
                logger.debug(f"Rate limit reset for {client_ip}")
        else:
            self.request_log.clear()
            logger.debug("All rate limit data cleared")


# Global rate limiter instance
_rate_limiter = RateLimiter()


def enforce_rate_limit(request: "Request") -> None:
    """
    Enforce rate limit for incoming request.

    Extracts client IP from request and checks rate limit.
    Raises HTTPException if limit is exceeded.

    Args:
        request: FastAPI Request object

    Raises:
        HTTPException: 429 if rate limit is exceeded

    Returns:
        None if rate limit check passes
    """
    if not FASTAPI_AVAILABLE:
        raise RuntimeError(
            "FastAPI is not installed. "
            "Install with: pip install 'fastapi[standard]'"
        )

    # Extract client IP
    # Try X-Forwarded-For header first (for proxied requests)
    client_ip = request.headers.get("X-Forwarded-For")
    if client_ip:
        # X-Forwarded-For can contain multiple IPs, take the first one
        client_ip = client_ip.split(",")[0].strip()
    else:
        # Fall back to direct connection IP
        client_ip = request.client.host if request.client else "unknown"

    # Check rate limit
    if not _rate_limiter.allow(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )

    return None


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.

    This is primarily for testing and monitoring purposes.

    Returns:
        RateLimiter: The global rate limiter instance
    """
    return _rate_limiter


def reset_rate_limiter(client_ip: str = None) -> None:
    """
    Reset rate limiter state.

    This is primarily for testing purposes.

    Args:
        client_ip: If provided, reset only this IP. Otherwise, reset all.
    """
    _rate_limiter.reset(client_ip)

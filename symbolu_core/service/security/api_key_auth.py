"""
API Key Authentication Module (Optional, Deterministic)

This module provides optional API key authentication for Symbol-U endpoints.

Behavior:
    - If SYMBOLU_API_KEY env var is NOT set → authentication is skipped
    - If SYMBOLU_API_KEY env var IS set → authentication is required
    - Expects header: X-API-Key
    - Returns 401 for invalid or missing keys when authentication is enabled

Design:
    - Zero-LLM: purely deterministic string comparison
    - Non-invasive: doesn't modify pipeline behavior
    - Backward compatible: optional activation only
"""

import os
import logging
from typing import Optional

try:
    from fastapi import Request, HTTPException
    FASTAPI_AVAILABLE = True
except ImportError:
    Request = None
    HTTPException = None
    FASTAPI_AVAILABLE = False

logger = logging.getLogger(__name__)

# Load API key from environment at module initialization
_CONFIGURED_API_KEY: Optional[str] = os.environ.get("SYMBOLU_API_KEY")


def verify_api_key(request: "Request") -> None:
    """
    Verify API key from request header.

    This function implements optional API key authentication:
    - If no API key is configured (SYMBOLU_API_KEY not set), this is a no-op
    - If API key is configured, validates X-API-Key header

    Args:
        request: FastAPI Request object containing headers

    Raises:
        HTTPException: 401 if authentication is enabled and key is invalid/missing

    Returns:
        None if authentication passes or is disabled

    Examples:
        >>> # Case 1: No API key configured (SYMBOLU_API_KEY not set)
        >>> verify_api_key(request)  # Returns None, no validation

        >>> # Case 2: API key configured, valid header provided
        >>> verify_api_key(request)  # Returns None, validation passes

        >>> # Case 3: API key configured, invalid/missing header
        >>> verify_api_key(request)  # Raises HTTPException(401)
    """
    if not FASTAPI_AVAILABLE:
        raise RuntimeError(
            "FastAPI is not installed. "
            "Install with: pip install 'fastapi[standard]'"
        )

    # If no API key is configured, skip authentication entirely
    if _CONFIGURED_API_KEY is None:
        logger.debug("API key authentication is disabled (SYMBOLU_API_KEY not set)")
        return None

    # API key is configured, authentication is required
    provided_key = request.headers.get("X-API-Key")

    # Check if key was provided
    if not provided_key:
        logger.warning("API key missing from request")
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )

    # Compare keys (constant-time comparison would be ideal, but for simplicity using ==)
    if provided_key != _CONFIGURED_API_KEY:
        logger.warning("Invalid API key provided")
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )

    # Authentication passed
    logger.debug("API key authentication successful")
    return None


def is_authentication_enabled() -> bool:
    """
    Check if API key authentication is enabled.

    Returns:
        bool: True if SYMBOLU_API_KEY is configured, False otherwise
    """
    return _CONFIGURED_API_KEY is not None


def get_configured_key() -> Optional[str]:
    """
    Get the configured API key (for testing purposes only).

    WARNING: This should only be used in test environments.

    Returns:
        Optional[str]: The configured API key, or None if not set
    """
    return _CONFIGURED_API_KEY

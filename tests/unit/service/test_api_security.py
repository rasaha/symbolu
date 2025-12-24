"""
Unit and Integration Tests for Symbol-U API Security Layer

This test suite verifies:
    1. API Key Authentication (optional, deterministic)
    2. Rate Limiting (sliding window, in-memory)
    3. Integration with FastAPI endpoints
    4. Backward compatibility (security is optional)

All tests are deterministic with zero LLM involvement.
"""

import os
import time
import pytest
from typing import Any, Dict
from unittest.mock import patch

# Check if FastAPI is available for testing
try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    TestClient = None

# Import security components
from symbolu.service.security.api_key_auth import verify_api_key, is_authentication_enabled
from symbolu.service.security.rate_limiter import (
    enforce_rate_limit,
    get_rate_limiter,
    reset_rate_limiter,
    RateLimiter
)

# Import API server
from symbolu.service.api_server import create_app


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_request_payload() -> Dict[str, Any]:
    """Standard test request payload."""
    return {
        "text": "Hello world",
        "domain": "general",
        "metadata": {}
    }


@pytest.fixture
def reset_rate_limit():
    """Reset rate limiter state before each test."""
    reset_rate_limiter()
    yield
    reset_rate_limiter()


# ============================================================================
# API KEY AUTHENTICATION TESTS
# ============================================================================

class TestAPIKeyAuthentication:
    """Test suite for API key authentication."""

    def test_requests_succeed_without_api_key_configured(
        self, sample_request_payload, reset_rate_limit
    ):
        """
        Test 1: Requests succeed when no API key is configured.

        When SYMBOLU_API_KEY is not set, authentication should be skipped
        and requests should proceed normally.
        """
        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        # Ensure no API key is set
        with patch.dict(os.environ, {}, clear=False):
            # Remove API key if present
            if "SYMBOLU_API_KEY" in os.environ:
                del os.environ["SYMBOLU_API_KEY"]

            # Force reload of security module to pick up env changes
            import importlib
            from symbolu.service.security import api_key_auth
            importlib.reload(api_key_auth)

            # Create fresh app without API key
            app = create_app()
            client = TestClient(app)

            # Make request without X-API-Key header
            response = client.post("/dilchat/analyze", json=sample_request_payload)

            # Should succeed (200 OK)
            assert response.status_code == 200
            assert "text" in response.json()

    def test_requests_fail_when_api_key_set_and_header_missing(
        self, sample_request_payload, reset_rate_limit
    ):
        """
        Test 2: Requests fail (401) when API key is set and header missing.

        When SYMBOLU_API_KEY is configured, requests without X-API-Key
        header should be rejected with 401.
        """
        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        test_api_key = "test-secret-key-12345"

        with patch.dict(os.environ, {"SYMBOLU_API_KEY": test_api_key}):
            # Force reload of security module
            import importlib
            from symbolu.service.security import api_key_auth
            importlib.reload(api_key_auth)

            # Create app with API key configured
            app = create_app()
            client = TestClient(app)

            # Make request WITHOUT X-API-Key header
            response = client.post("/dilchat/analyze", json=sample_request_payload)

            # Should fail with 401
            assert response.status_code == 401
            assert "Invalid or missing API key" in response.json()["detail"]

    def test_requests_succeed_with_correct_api_key(
        self, sample_request_payload, reset_rate_limit
    ):
        """
        Test 3: Requests succeed with correct API key.

        When SYMBOLU_API_KEY is configured and correct X-API-Key header
        is provided, requests should succeed.
        """
        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        test_api_key = "test-secret-key-12345"

        with patch.dict(os.environ, {"SYMBOLU_API_KEY": test_api_key}):
            # Force reload
            import importlib
            from symbolu.service.security import api_key_auth
            importlib.reload(api_key_auth)

            app = create_app()
            client = TestClient(app)

            # Make request WITH correct X-API-Key header
            response = client.post(
                "/dilchat/analyze",
                json=sample_request_payload,
                headers={"X-API-Key": test_api_key}
            )

            # Should succeed
            assert response.status_code == 200
            assert "text" in response.json()

    def test_requests_fail_with_incorrect_api_key(
        self, sample_request_payload, reset_rate_limit
    ):
        """
        Test 4: Requests fail with incorrect API key.

        When SYMBOLU_API_KEY is configured and incorrect X-API-Key header
        is provided, requests should be rejected with 401.
        """
        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        test_api_key = "test-secret-key-12345"
        wrong_api_key = "wrong-key-99999"

        with patch.dict(os.environ, {"SYMBOLU_API_KEY": test_api_key}):
            # Force reload
            import importlib
            from symbolu.service.security import api_key_auth
            importlib.reload(api_key_auth)

            app = create_app()
            client = TestClient(app)

            # Make request with WRONG X-API-Key header
            response = client.post(
                "/dilchat/analyze",
                json=sample_request_payload,
                headers={"X-API-Key": wrong_api_key}
            )

            # Should fail with 401
            assert response.status_code == 401
            assert "Invalid or missing API key" in response.json()["detail"]


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================

class TestRateLimiting:
    """Test suite for rate limiting."""

    def test_first_requests_allowed(self, sample_request_payload, reset_rate_limit):
        """
        Test 5: First 3 requests are allowed.

        Initial requests should be allowed up to the limit.
        """
        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        # Set low rate limit for testing
        with patch.dict(os.environ, {"SYMBOLU_RATE_LIMIT": "3"}):
            # Force reload to pick up new limit
            import importlib
            from symbolu.service.security import rate_limiter
            importlib.reload(rate_limiter)

            # Ensure no API key is required for this test
            with patch.dict(os.environ, {}, clear=False):
                if "SYMBOLU_API_KEY" in os.environ:
                    del os.environ["SYMBOLU_API_KEY"]

                from symbolu.service.security import api_key_auth
                importlib.reload(api_key_auth)

                app = create_app()
                client = TestClient(app)

                # Make 3 requests
                for i in range(3):
                    response = client.post(
                        "/dilchat/analyze",
                        json=sample_request_payload
                    )
                    assert response.status_code == 200, f"Request {i+1} failed"

    def test_exceed_limit_returns_429(self, sample_request_payload, reset_rate_limit):
        """
        Test 6: Exceeding limit returns 429.

        When rate limit is exceeded, requests should be rejected with 429.
        """
        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        # Set low rate limit for testing
        with patch.dict(os.environ, {"SYMBOLU_RATE_LIMIT": "3"}):
            # Force reload
            import importlib
            from symbolu.service.security import rate_limiter
            importlib.reload(rate_limiter)

            # Ensure no API key required
            with patch.dict(os.environ, {}, clear=False):
                if "SYMBOLU_API_KEY" in os.environ:
                    del os.environ["SYMBOLU_API_KEY"]

                from symbolu.service.security import api_key_auth
                importlib.reload(api_key_auth)

                app = create_app()
                client = TestClient(app)

                # Make 3 requests (should succeed)
                for i in range(3):
                    response = client.post(
                        "/dilchat/analyze",
                        json=sample_request_payload
                    )
                    assert response.status_code == 200

                # 4th request should be rate limited
                response = client.post(
                    "/dilchat/analyze",
                    json=sample_request_payload
                )
                assert response.status_code == 429
                assert "Rate limit exceeded" in response.json()["detail"]

    def test_after_window_passes_allow_again(
        self, sample_request_payload, reset_rate_limit
    ):
        """
        Test 7: After window passes, requests are allowed again.

        This test verifies the sliding window behavior.
        """
        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        # Create a rate limiter with very short window for testing
        limiter = RateLimiter(limit=2, window_size=1)  # 2 req per 1 second

        # Make 2 requests
        assert limiter.allow("test-ip") is True
        assert limiter.allow("test-ip") is True

        # 3rd should be blocked
        assert limiter.allow("test-ip") is False

        # Wait for window to pass
        time.sleep(1.1)

        # Should be allowed again
        assert limiter.allow("test-ip") is True

    def test_rate_limit_per_ip(self, sample_request_payload, reset_rate_limit):
        """
        Test: Rate limiting is tracked per IP address.

        Different IPs should have independent rate limits.
        """
        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        limiter = RateLimiter(limit=2, window_size=60)

        # IP 1: Use up its limit
        assert limiter.allow("192.168.1.1") is True
        assert limiter.allow("192.168.1.1") is True
        assert limiter.allow("192.168.1.1") is False  # Blocked

        # IP 2: Should still be allowed
        assert limiter.allow("192.168.1.2") is True
        assert limiter.allow("192.168.1.2") is True
        assert limiter.allow("192.168.1.2") is False  # Blocked


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestSecurityIntegration:
    """Integration tests for auth + rate limiting."""

    def test_auth_and_rate_limit_together(
        self, sample_request_payload, reset_rate_limit
    ):
        """
        Test 8: Auth + rate limit work together deterministically.

        When both are enabled, both checks should be enforced.
        """
        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        test_api_key = "integration-test-key"

        with patch.dict(
            os.environ,
            {
                "SYMBOLU_API_KEY": test_api_key,
                "SYMBOLU_RATE_LIMIT": "2"
            }
        ):
            # Force reload
            import importlib
            from symbolu.service.security import api_key_auth, rate_limiter
            importlib.reload(api_key_auth)
            importlib.reload(rate_limiter)

            app = create_app()
            client = TestClient(app)

            # Request without API key should fail immediately (before rate limit)
            response = client.post("/dilchat/analyze", json=sample_request_payload)
            assert response.status_code == 401

            # Requests with correct key should be rate limited
            headers = {"X-API-Key": test_api_key}

            # First 2 should succeed
            response1 = client.post(
                "/dilchat/analyze",
                json=sample_request_payload,
                headers=headers
            )
            assert response1.status_code == 200

            response2 = client.post(
                "/dilchat/analyze",
                json=sample_request_payload,
                headers=headers
            )
            assert response2.status_code == 200

            # 3rd should be rate limited (429)
            response3 = client.post(
                "/dilchat/analyze",
                json=sample_request_payload,
                headers=headers
            )
            assert response3.status_code == 429

    def test_both_endpoints_protected(
        self, sample_request_payload, reset_rate_limit
    ):
        """
        Test: Both /dilchat/analyze and /symbolu/analyze are protected.

        Security should apply to all protected endpoints.
        """
        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        test_api_key = "endpoint-test-key"

        with patch.dict(os.environ, {"SYMBOLU_API_KEY": test_api_key}):
            # Force reload
            import importlib
            from symbolu.service.security import api_key_auth
            importlib.reload(api_key_auth)

            app = create_app()
            client = TestClient(app)

            # Test /dilchat/analyze
            response = client.post("/dilchat/analyze", json=sample_request_payload)
            assert response.status_code == 401

            response = client.post(
                "/dilchat/analyze",
                json=sample_request_payload,
                headers={"X-API-Key": test_api_key}
            )
            assert response.status_code == 200

            # Test /symbolu/analyze
            response = client.post("/symbolu/analyze", json=sample_request_payload)
            assert response.status_code == 401

            response = client.post(
                "/symbolu/analyze",
                json=sample_request_payload,
                headers={"X-API-Key": test_api_key}
            )
            assert response.status_code == 200

    def test_health_endpoint_not_protected(self, reset_rate_limit):
        """
        Test: /health endpoint is NOT protected by auth or rate limiting.

        Health checks should always be accessible.
        """
        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        test_api_key = "health-test-key"

        with patch.dict(
            os.environ,
            {
                "SYMBOLU_API_KEY": test_api_key,
                "SYMBOLU_RATE_LIMIT": "1"
            }
        ):
            # Force reload
            import importlib
            from symbolu.service.security import api_key_auth, rate_limiter
            importlib.reload(api_key_auth)
            importlib.reload(rate_limiter)

            app = create_app()
            client = TestClient(app)

            # Health check should work without API key
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

            # Should work multiple times (no rate limiting)
            for _ in range(5):
                response = client.get("/health")
                assert response.status_code == 200


# ============================================================================
# UNIT TESTS FOR RATE LIMITER CLASS
# ============================================================================

class TestRateLimiterUnit:
    """Unit tests for RateLimiter class."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes with correct defaults."""
        limiter = RateLimiter()
        assert limiter.limit == 60
        assert limiter.window_size == 60

        limiter_custom = RateLimiter(limit=100, window_size=30)
        assert limiter_custom.limit == 100
        assert limiter_custom.window_size == 30

    def test_get_remaining_count(self):
        """Test get_remaining returns correct count."""
        limiter = RateLimiter(limit=5, window_size=60)

        # Initially should have full limit available
        assert limiter.get_remaining("test-ip") == 5

        # After 2 requests
        limiter.allow("test-ip")
        limiter.allow("test-ip")
        assert limiter.get_remaining("test-ip") == 3

    def test_reset_specific_ip(self):
        """Test resetting rate limit for specific IP."""
        limiter = RateLimiter(limit=2, window_size=60)

        # Use up limit for IP1
        limiter.allow("ip1")
        limiter.allow("ip1")
        assert limiter.allow("ip1") is False

        # Reset IP1
        limiter.reset("ip1")
        assert limiter.allow("ip1") is True  # Should work again

    def test_reset_all(self):
        """Test resetting all rate limit data."""
        limiter = RateLimiter(limit=1, window_size=60)

        # Use up limits for multiple IPs
        limiter.allow("ip1")
        limiter.allow("ip2")

        assert limiter.allow("ip1") is False
        assert limiter.allow("ip2") is False

        # Reset all
        limiter.reset()

        assert limiter.allow("ip1") is True
        assert limiter.allow("ip2") is True


# ============================================================================
# DETERMINISM TESTS
# ============================================================================

class TestDeterminism:
    """Verify all security logic is deterministic."""

    def test_api_key_check_is_deterministic(self):
        """API key validation should always return same result for same input."""
        from symbolu.service.security.api_key_auth import is_authentication_enabled

        # Same environment should give same result
        results = []
        for _ in range(10):
            results.append(is_authentication_enabled())

        # All results should be identical
        assert len(set(results)) == 1

    def test_rate_limiter_is_deterministic(self):
        """Rate limiter should behave deterministically."""
        limiter = RateLimiter(limit=3, window_size=60)

        # Same sequence of requests should give same results
        results1 = [limiter.allow("test") for _ in range(5)]

        limiter.reset()
        results2 = [limiter.allow("test") for _ in range(5)]

        assert results1 == results2
        assert results1 == [True, True, True, False, False]

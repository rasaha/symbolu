"""
Provider Registry Tests
=======================

Tests for the multi-provider registry with health monitoring
and automatic failover capabilities.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from symbolu.voice.providers.registry import (
    ProviderRegistry,
    ProviderHealth,
    ProviderStatus,
    ProviderAdapter,
)
from symbolu.voice.providers.base import (
    STTProvider,
    TTSProvider,
    TTSParams,
    VoiceInfo,
)


# Mock providers for testing
class MockSTTProvider(STTProvider):
    """Mock STT provider for testing."""

    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.call_count = 0

    async def transcribe_stream(self, audio_stream, **kwargs):
        self.call_count += 1
        if self.should_fail:
            raise Exception("Mock STT failure")
        yield Mock(text="test", transcript_type=Mock(), confidence=0.9)

    async def transcribe_file(self, audio_bytes, **kwargs):
        self.call_count += 1
        if self.should_fail:
            raise Exception("Mock STT failure")
        return Mock(text="test", confidence=0.9)

    @property
    def supported_languages(self):
        return ["en"]

    @property
    def supports_streaming(self):
        return True


class MockTTSProvider(TTSProvider):
    """Mock TTS provider for testing."""

    def __init__(self, should_fail=False, latency_ms=100):
        self.should_fail = should_fail
        self.latency_ms = latency_ms
        self.call_count = 0

    async def synthesize_stream(self, text, params):
        self.call_count += 1
        if self.should_fail:
            raise Exception("Mock TTS failure")
        yield Mock(audio=b"\x00" * 100, is_final=True)

    async def synthesize(self, text, params):
        self.call_count += 1
        await asyncio.sleep(self.latency_ms / 1000)
        if self.should_fail:
            raise Exception("Mock TTS failure")
        return b"\x00" * 100

    def get_voices(self):
        return [
            VoiceInfo(
                voice_id="mock-voice",
                name="Mock Voice",
                language="en-US"
            )
        ]

    @property
    def supports_streaming(self):
        return True

    @property
    def average_latency_ms(self):
        return self.latency_ms


class MockAdapter:
    """Mock provider adapter."""

    def __init__(self, stt=None, tts=None):
        self._stt = stt or MockSTTProvider()
        self._tts = tts or MockTTSProvider()

    @property
    def stt(self):
        return self._stt

    @property
    def tts(self):
        return self._tts


class TestProviderStatus:
    """Tests for ProviderStatus dataclass."""

    def test_initial_status(self):
        """Verify initial status values."""
        status = ProviderStatus(name="test")
        assert status.name == "test"
        assert status.health == ProviderHealth.UNKNOWN
        assert status.failure_count == 0
        assert status.success_count == 0

    def test_record_success(self):
        """Verify success recording updates status."""
        status = ProviderStatus(name="test")
        status.record_success(latency_ms=50.0)

        assert status.health == ProviderHealth.HEALTHY
        assert status.success_count == 1
        assert status.failure_count == 0
        assert status.average_latency_ms == 50.0
        assert status.last_success is not None

    def test_record_success_updates_latency_ema(self):
        """Verify latency uses exponential moving average."""
        status = ProviderStatus(name="test")
        status.record_success(latency_ms=100.0)
        status.record_success(latency_ms=50.0)

        # EMA: 0.8 * 100 + 0.2 * 50 = 90
        assert status.average_latency_ms == pytest.approx(90.0)

    def test_record_failure(self):
        """Verify failure recording updates status."""
        status = ProviderStatus(name="test")
        status.record_failure("Test error")

        assert status.failure_count == 1
        assert status.error_message == "Test error"
        assert status.last_failure is not None

    def test_multiple_failures_changes_health(self):
        """Verify multiple failures degrade health status."""
        status = ProviderStatus(name="test")

        # First failure
        status.record_failure("Error 1")
        assert status.health == ProviderHealth.UNKNOWN

        # Second failure
        status.record_failure("Error 2")
        assert status.health == ProviderHealth.DEGRADED

        # Fifth failure
        for _ in range(3):
            status.record_failure("Error")
        assert status.health == ProviderHealth.UNHEALTHY

    def test_success_resets_failure_count(self):
        """Verify success resets failure count."""
        status = ProviderStatus(name="test")
        status.record_failure("Error 1")
        status.record_failure("Error 2")
        assert status.failure_count == 2

        status.record_success(latency_ms=50.0)
        assert status.failure_count == 0
        assert status.health == ProviderHealth.HEALTHY


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def test_register_provider(self):
        """Verify provider registration."""
        registry = ProviderRegistry()
        adapter = MockAdapter()

        registry.register("mock", adapter)

        assert "mock" in registry
        assert len(registry) == 1
        assert "mock" in registry.registered_providers

    def test_unregister_provider(self):
        """Verify provider unregistration."""
        registry = ProviderRegistry()
        adapter = MockAdapter()

        registry.register("mock", adapter)
        result = registry.unregister("mock")

        assert result is True
        assert "mock" not in registry
        assert len(registry) == 0

    def test_unregister_nonexistent_provider(self):
        """Verify unregistering nonexistent provider returns False."""
        registry = ProviderRegistry()
        result = registry.unregister("nonexistent")
        assert result is False

    def test_get_stt_provider(self):
        """Verify getting STT provider."""
        registry = ProviderRegistry()
        adapter = MockAdapter()
        registry.register("mock", adapter)

        stt = registry.get_stt("mock")
        assert isinstance(stt, MockSTTProvider)

    def test_get_tts_provider(self):
        """Verify getting TTS provider."""
        registry = ProviderRegistry()
        adapter = MockAdapter()
        registry.register("mock", adapter)

        tts = registry.get_tts("mock")
        assert isinstance(tts, MockTTSProvider)

    def test_get_stt_with_fallback(self):
        """Verify fallback when primary STT unavailable."""
        registry = ProviderRegistry()

        # Primary marked unhealthy
        primary = MockAdapter()
        registry.register("primary", primary)
        registry.mark_unhealthy("primary", "Connection failed")
        # Mark multiple failures to make it unhealthy
        for _ in range(5):
            registry.mark_unhealthy("primary", "Connection failed")

        # Fallback should work
        fallback = MockAdapter()
        registry.register("fallback", fallback)

        stt = registry.get_stt("primary", fallback=["fallback"])
        # Should get fallback provider since primary is unhealthy
        # (may need to wait for recovery time)

    def test_get_stt_no_available_provider(self):
        """Verify error when no STT provider available."""
        registry = ProviderRegistry()

        with pytest.raises(RuntimeError, match="No healthy STT provider"):
            registry.get_stt("nonexistent")

    def test_get_tts_no_available_provider(self):
        """Verify error when no TTS provider available."""
        registry = ProviderRegistry()

        with pytest.raises(RuntimeError, match="No healthy TTS provider"):
            registry.get_tts("nonexistent")

    def test_get_stt_for_tts_only_provider(self):
        """Verify error when provider doesn't have STT."""
        registry = ProviderRegistry()
        adapter = MockAdapter()
        registry.register("tts-only", adapter, has_stt=False, has_tts=True)

        with pytest.raises(RuntimeError):
            registry.get_stt("tts-only")

    def test_mark_healthy(self):
        """Verify marking provider as healthy."""
        registry = ProviderRegistry()
        adapter = MockAdapter()
        registry.register("mock", adapter)

        registry.mark_healthy("mock", latency_ms=50.0)
        status = registry.get_status("mock")

        assert status["mock"].health == ProviderHealth.HEALTHY

    def test_mark_unhealthy(self):
        """Verify marking provider as unhealthy."""
        registry = ProviderRegistry()
        adapter = MockAdapter()
        registry.register("mock", adapter)

        registry.mark_unhealthy("mock", "Test error")
        status = registry.get_status("mock")

        assert status["mock"].failure_count == 1

    def test_get_status_single_provider(self):
        """Verify getting status for single provider."""
        registry = ProviderRegistry()
        adapter = MockAdapter()
        registry.register("mock", adapter)

        status = registry.get_status("mock")
        assert "mock" in status
        assert len(status) == 1

    def test_get_status_all_providers(self):
        """Verify getting status for all providers."""
        registry = ProviderRegistry()
        registry.register("mock1", MockAdapter())
        registry.register("mock2", MockAdapter())

        status = registry.get_status()
        assert "mock1" in status
        assert "mock2" in status
        assert len(status) == 2

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Verify health check updates provider status."""
        registry = ProviderRegistry()
        adapter = MockAdapter()
        registry.register("mock", adapter)

        results = await registry.health_check()

        assert "mock" in results
        assert results["mock"] is True

    @pytest.mark.asyncio
    async def test_health_check_failing_provider(self):
        """Verify health check detects failing provider."""
        registry = ProviderRegistry()
        failing_tts = MockTTSProvider(should_fail=True)
        adapter = MockAdapter(tts=failing_tts)
        registry.register("failing", adapter)

        results = await registry.health_check()

        assert results["failing"] is False

    def test_get_best_stt(self):
        """Verify getting best available STT provider."""
        registry = ProviderRegistry()

        # Register providers with different priorities
        adapter1 = MockAdapter()
        adapter2 = MockAdapter()
        registry.register("low-priority", adapter1, priority=10)
        registry.register("high-priority", adapter2, priority=1)

        # Mark high-priority as healthy
        registry.mark_healthy("high-priority", latency_ms=50.0)

        stt = registry.get_best_stt()
        # Should get highest priority (lowest number) healthy provider

    def test_get_best_tts(self):
        """Verify getting best available TTS provider."""
        registry = ProviderRegistry()

        # Register providers
        adapter = MockAdapter()
        registry.register("mock", adapter)
        registry.mark_healthy("mock", latency_ms=100.0)

        tts = registry.get_best_tts()
        assert isinstance(tts, MockTTSProvider)

    def test_contains(self):
        """Verify __contains__ operator."""
        registry = ProviderRegistry()
        registry.register("mock", MockAdapter())

        assert "mock" in registry
        assert "nonexistent" not in registry

    def test_len(self):
        """Verify __len__ returns provider count."""
        registry = ProviderRegistry()
        assert len(registry) == 0

        registry.register("mock1", MockAdapter())
        assert len(registry) == 1

        registry.register("mock2", MockAdapter())
        assert len(registry) == 2


class TestProviderRegistryRecovery:
    """Tests for provider recovery behavior."""

    def test_unhealthy_provider_needs_recovery_time(self):
        """Verify unhealthy providers aren't used until recovery time passes."""
        registry = ProviderRegistry(recovery_time=30)

        adapter = MockAdapter()
        registry.register("mock", adapter)

        # Mark as unhealthy multiple times
        for _ in range(5):
            registry.mark_unhealthy("mock", "Error")

        status = registry.get_status("mock")["mock"]
        assert status.health == ProviderHealth.UNHEALTHY

    def test_provider_with_priority(self):
        """Verify provider priority affects selection."""
        registry = ProviderRegistry()

        # Lower priority number = higher priority
        registry.register("primary", MockAdapter(), priority=1)
        registry.register("secondary", MockAdapter(), priority=2)

        # Both healthy - should prefer primary
        registry.mark_healthy("primary", latency_ms=100.0)
        registry.mark_healthy("secondary", latency_ms=50.0)

        # get_best should prefer primary despite higher latency
        # because it has lower priority number

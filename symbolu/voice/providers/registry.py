"""
Provider registry for managing multiple voice providers.

The registry enables:
- Multi-provider support with automatic failover
- Health monitoring and recovery
- Provider-agnostic voice agent development
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Type
from enum import Enum

from .base import (
    STTProvider,
    TTSProvider,
    TTSParams,
    ProviderError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class ProviderHealth(Enum):
    """Health status of a provider."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ProviderStatus:
    """Status information for a provider."""
    name: str
    health: ProviderHealth = ProviderHealth.UNKNOWN
    last_check: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    failure_count: int = 0
    success_count: int = 0
    average_latency_ms: Optional[float] = None
    error_message: Optional[str] = None

    def record_success(self, latency_ms: float):
        """Record a successful operation."""
        self.success_count += 1
        self.last_success = datetime.utcnow()
        self.failure_count = 0  # Reset failure count on success

        # Update average latency with exponential moving average
        if self.average_latency_ms is None:
            self.average_latency_ms = latency_ms
        else:
            self.average_latency_ms = (
                0.8 * self.average_latency_ms + 0.2 * latency_ms
            )

        self.health = ProviderHealth.HEALTHY
        self.error_message = None

    def record_failure(self, error: str):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure = datetime.utcnow()
        self.error_message = error

        # Update health based on failure count
        if self.failure_count >= 5:
            self.health = ProviderHealth.UNHEALTHY
        elif self.failure_count >= 2:
            self.health = ProviderHealth.DEGRADED


@dataclass
class ProviderAdapter:
    """Wrapper for a provider adapter with metadata."""
    adapter: Any  # The actual adapter (CartesiaAdapter, DeepgramAdapter, etc.)
    name: str
    status: ProviderStatus = field(default_factory=lambda: ProviderStatus(name=""))
    has_stt: bool = True
    has_tts: bool = True
    priority: int = 0  # Lower = higher priority

    def __post_init__(self):
        self.status = ProviderStatus(name=self.name)


class ProviderRegistry:
    """
    Registry for managing voice providers with automatic failover.

    Features:
    - Register multiple providers (Cartesia, Deepgram, ElevenLabs, etc.)
    - Automatic health checking
    - Failover to backup providers on failure
    - Provider-agnostic API

    Usage:
        registry = ProviderRegistry()
        registry.register("cartesia", CartesiaAdapter(api_key="..."))
        registry.register("deepgram", DeepgramAdapter(api_key="..."))

        # Get provider with automatic fallback
        stt = registry.get_stt("cartesia", fallback=["deepgram"])
        tts = registry.get_tts("cartesia", fallback=["elevenlabs"])
    """

    def __init__(
        self,
        health_check_interval: int = 60,
        failure_threshold: int = 3,
        recovery_time: int = 30
    ):
        """
        Initialize the provider registry.

        Args:
            health_check_interval: Seconds between health checks
            failure_threshold: Number of failures before marking unhealthy
            recovery_time: Seconds to wait before retrying unhealthy provider
        """
        self._providers: Dict[str, ProviderAdapter] = {}
        self._health_check_interval = health_check_interval
        self._failure_threshold = failure_threshold
        self._recovery_time = timedelta(seconds=recovery_time)
        self._health_check_task: Optional[asyncio.Task] = None

    def register(
        self,
        name: str,
        adapter: Any,
        has_stt: bool = True,
        has_tts: bool = True,
        priority: int = 0
    ) -> None:
        """
        Register a provider adapter.

        Args:
            name: Unique name for this provider
            adapter: Provider adapter instance (CartesiaAdapter, etc.)
            has_stt: Whether this provider offers STT
            has_tts: Whether this provider offers TTS
            priority: Provider priority (lower = preferred)
        """
        self._providers[name] = ProviderAdapter(
            adapter=adapter,
            name=name,
            has_stt=has_stt,
            has_tts=has_tts,
            priority=priority
        )
        logger.info(f"Registered voice provider: {name}")

    def unregister(self, name: str) -> bool:
        """
        Unregister a provider.

        Args:
            name: Provider name

        Returns:
            True if provider was registered and removed
        """
        if name in self._providers:
            del self._providers[name]
            logger.info(f"Unregistered voice provider: {name}")
            return True
        return False

    def get_stt(
        self,
        preferred: str,
        fallback: Optional[List[str]] = None
    ) -> STTProvider:
        """
        Get STT provider with fallback support.

        Args:
            preferred: Preferred provider name
            fallback: List of fallback provider names

        Returns:
            STTProvider instance

        Raises:
            RuntimeError: If no healthy STT provider is available
        """
        providers_to_try = [preferred] + (fallback or [])

        for name in providers_to_try:
            provider = self._providers.get(name)
            if provider is None:
                logger.warning(f"Provider '{name}' not registered")
                continue

            if not provider.has_stt:
                logger.warning(f"Provider '{name}' doesn't offer STT")
                continue

            if not self._is_provider_available(provider):
                logger.warning(f"Provider '{name}' is not available")
                continue

            try:
                return provider.adapter.stt
            except Exception as e:
                logger.error(f"Failed to get STT from '{name}': {e}")
                provider.status.record_failure(str(e))

        raise RuntimeError(
            f"No healthy STT provider available. "
            f"Tried: {providers_to_try}"
        )

    def get_tts(
        self,
        preferred: str,
        fallback: Optional[List[str]] = None
    ) -> TTSProvider:
        """
        Get TTS provider with fallback support.

        Args:
            preferred: Preferred provider name
            fallback: List of fallback provider names

        Returns:
            TTSProvider instance

        Raises:
            RuntimeError: If no healthy TTS provider is available
        """
        providers_to_try = [preferred] + (fallback or [])

        for name in providers_to_try:
            provider = self._providers.get(name)
            if provider is None:
                logger.warning(f"Provider '{name}' not registered")
                continue

            if not provider.has_tts:
                logger.warning(f"Provider '{name}' doesn't offer TTS")
                continue

            if not self._is_provider_available(provider):
                logger.warning(f"Provider '{name}' is not available")
                continue

            try:
                return provider.adapter.tts
            except Exception as e:
                logger.error(f"Failed to get TTS from '{name}': {e}")
                provider.status.record_failure(str(e))

        raise RuntimeError(
            f"No healthy TTS provider available. "
            f"Tried: {providers_to_try}"
        )

    def _is_provider_available(self, provider: ProviderAdapter) -> bool:
        """Check if a provider is available for use."""
        status = provider.status

        # Unknown health - assume available
        if status.health == ProviderHealth.UNKNOWN:
            return True

        # Healthy providers are available
        if status.health == ProviderHealth.HEALTHY:
            return True

        # Degraded providers are available but may fail
        if status.health == ProviderHealth.DEGRADED:
            return True

        # Unhealthy providers need recovery time
        if status.health == ProviderHealth.UNHEALTHY:
            if status.last_failure is None:
                return True

            time_since_failure = datetime.utcnow() - status.last_failure
            if time_since_failure >= self._recovery_time:
                logger.info(f"Provider '{provider.name}' recovery period elapsed")
                return True

            return False

        return True

    def mark_healthy(self, name: str, latency_ms: float = 0) -> None:
        """Mark a provider as healthy after successful operation."""
        if name in self._providers:
            self._providers[name].status.record_success(latency_ms)

    def mark_unhealthy(self, name: str, error: str = "") -> None:
        """Mark a provider as unhealthy after failed operation."""
        if name in self._providers:
            self._providers[name].status.record_failure(error)

    def get_status(self, name: Optional[str] = None) -> Dict[str, ProviderStatus]:
        """
        Get provider status.

        Args:
            name: Specific provider name, or None for all providers

        Returns:
            Dict mapping provider names to their status
        """
        if name:
            if name in self._providers:
                return {name: self._providers[name].status}
            return {}

        return {
            name: provider.status
            for name, provider in self._providers.items()
        }

    async def health_check(self) -> Dict[str, bool]:
        """
        Perform health check on all providers.

        Returns:
            Dict mapping provider names to health status (True = healthy)
        """
        results = {}

        for name, provider in self._providers.items():
            try:
                # Test TTS with a simple phrase
                if provider.has_tts:
                    tts = provider.adapter.tts
                    start = datetime.utcnow()

                    # Quick synthesis test
                    await tts.synthesize(
                        "test",
                        TTSParams(voice_id=self._get_default_voice(tts))
                    )

                    latency = (datetime.utcnow() - start).total_seconds() * 1000
                    provider.status.record_success(latency)
                    results[name] = True

                else:
                    # Provider only has STT, mark as healthy if registered
                    provider.status.health = ProviderHealth.HEALTHY
                    results[name] = True

            except Exception as e:
                logger.warning(f"Health check failed for '{name}': {e}")
                provider.status.record_failure(str(e))
                results[name] = False

        return results

    def _get_default_voice(self, tts: TTSProvider) -> str:
        """Get a default voice ID for health checks."""
        voices = tts.get_voices()
        if voices:
            return voices[0].voice_id
        return "default"

    async def start_health_checks(self) -> None:
        """Start periodic health checks in background."""
        if self._health_check_task is not None:
            return

        async def _health_check_loop():
            while True:
                try:
                    await self.health_check()
                except Exception as e:
                    logger.error(f"Health check error: {e}")

                await asyncio.sleep(self._health_check_interval)

        self._health_check_task = asyncio.create_task(_health_check_loop())
        logger.info("Started provider health check loop")

    async def stop_health_checks(self) -> None:
        """Stop periodic health checks."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Stopped provider health check loop")

    def get_best_stt(self) -> STTProvider:
        """
        Get the best available STT provider based on health and priority.

        Returns:
            STTProvider from the healthiest, highest-priority provider
        """
        available = [
            p for p in self._providers.values()
            if p.has_stt and self._is_provider_available(p)
        ]

        if not available:
            raise RuntimeError("No STT providers available")

        # Sort by health status, then priority
        def sort_key(p):
            health_order = {
                ProviderHealth.HEALTHY: 0,
                ProviderHealth.UNKNOWN: 1,
                ProviderHealth.DEGRADED: 2,
                ProviderHealth.UNHEALTHY: 3,
            }
            return (health_order[p.status.health], p.priority)

        best = sorted(available, key=sort_key)[0]
        return best.adapter.stt

    def get_best_tts(self) -> TTSProvider:
        """
        Get the best available TTS provider based on health and priority.

        Returns:
            TTSProvider from the healthiest, highest-priority provider
        """
        available = [
            p for p in self._providers.values()
            if p.has_tts and self._is_provider_available(p)
        ]

        if not available:
            raise RuntimeError("No TTS providers available")

        # Sort by health status, then priority, then latency
        def sort_key(p):
            health_order = {
                ProviderHealth.HEALTHY: 0,
                ProviderHealth.UNKNOWN: 1,
                ProviderHealth.DEGRADED: 2,
                ProviderHealth.UNHEALTHY: 3,
            }
            latency = p.status.average_latency_ms or float('inf')
            return (health_order[p.status.health], p.priority, latency)

        best = sorted(available, key=sort_key)[0]
        return best.adapter.tts

    @property
    def registered_providers(self) -> List[str]:
        """List of registered provider names."""
        return list(self._providers.keys())

    def __contains__(self, name: str) -> bool:
        """Check if a provider is registered."""
        return name in self._providers

    def __len__(self) -> int:
        """Number of registered providers."""
        return len(self._providers)

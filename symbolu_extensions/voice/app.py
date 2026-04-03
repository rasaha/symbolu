"""
Voice Agent Application - Complete voice agent with WebSocket support.

This module provides the main VoiceAgentApp class that integrates all
components of the Hybrid Voice SDK:
- Provider registry (multi-provider support)
- Voice orchestrator
- Sentinel framework
- P10 prosody mapping
- Safety voice gates
- WebSocket transport for real-time communication

Usage:
    app = VoiceAgentApp(
        sentinel_config={"llm_provider": "anthropic", ...},
        provider_configs={"cartesia": {"api_key": "..."}, ...},
    )
    app.run(host="0.0.0.0", port=8000)
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .providers import (
    ProviderRegistry,
    CartesiaAdapter,
    DeepgramAdapter,
    ElevenLabsAdapter,
    TTSParams,
    AudioChunk,
)
from .orchestration import (
    VoiceOrchestrator,
    OrchestratorConfig,
    VoiceSession,
)
from .prosody import P10ProsodyMapper, P10ProsodyConfig
from .safety import SafetyVoiceGate, SafetyGateConfig

logger = logging.getLogger(__name__)


@dataclass
class VoiceAgentConfig:
    """Configuration for voice agent application."""
    # Provider settings
    default_stt_provider: str = "cartesia"
    default_tts_provider: str = "cartesia"
    default_voice_id: str = "sonic-english-male"
    stt_fallback_providers: List[str] = field(default_factory=lambda: ["deepgram"])
    tts_fallback_providers: List[str] = field(default_factory=lambda: ["elevenlabs"])

    # Orchestrator settings
    orchestrator_config: Optional[OrchestratorConfig] = None

    # Prosody settings
    prosody_config: Optional[P10ProsodyConfig] = None

    # Safety settings
    safety_config: Optional[SafetyGateConfig] = None

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    enable_health_checks: bool = True
    health_check_interval: int = 60


class VoiceAgentApp:
    """
    Complete voice agent application.

    Integrates all components of the Hybrid Voice SDK:
    - Provider registry (multi-provider support)
    - Voice orchestrator
    - Sentinel framework integration
    - P10 prosody mapping
    - Safety voice gates
    - WebSocket transport

    Usage:
        # Configure providers
        provider_configs = {
            "cartesia": {"api_key": os.getenv("CARTESIA_API_KEY")},
            "deepgram": {"api_key": os.getenv("DEEPGRAM_API_KEY")},
        }

        # Configure Sentinel
        sentinel_config = {
            "llm_provider": "anthropic",
            "llm_model": "claude-sonnet-4-20250514",
        }

        # Create and run voice agent
        app = VoiceAgentApp(
            sentinel_config=sentinel_config,
            provider_configs=provider_configs,
        )
        app.run()
    """

    def __init__(
        self,
        sentinel_config: Dict[str, Any],
        provider_configs: Dict[str, Dict[str, Any]],
        config: Optional[VoiceAgentConfig] = None
    ):
        """
        Initialize voice agent application.

        Args:
            sentinel_config: Configuration for Sentinel framework
            provider_configs: Configuration for voice providers
                              Keys: provider names ("cartesia", "deepgram", etc.)
                              Values: provider-specific config (api_key, etc.)
            config: Application configuration
        """
        self.config = config or VoiceAgentConfig()
        self.sentinel_config = sentinel_config
        self.provider_configs = provider_configs

        # Initialize components
        self._init_providers()
        self._init_sentinel()
        self._init_components()

        # Session tracking
        self._active_sessions: Dict[str, VoiceSession] = {}

        # FastAPI app (created lazily)
        self._fastapi_app = None

    def _init_providers(self) -> None:
        """Initialize provider registry."""
        self.providers = ProviderRegistry(
            health_check_interval=self.config.health_check_interval
        )

        # Register configured providers
        for name, config in self.provider_configs.items():
            try:
                adapter = self._create_adapter(name, config)
                has_stt = name != "elevenlabs"  # ElevenLabs is TTS-only
                self.providers.register(
                    name=name,
                    adapter=adapter,
                    has_stt=has_stt,
                    has_tts=True
                )
                logger.info(f"Registered voice provider: {name}")
            except Exception as e:
                logger.error(f"Failed to register provider {name}: {e}")

    def _create_adapter(self, name: str, config: Dict[str, Any]) -> Any:
        """Create provider adapter from config."""
        api_key = config.get("api_key")

        if name == "cartesia":
            return CartesiaAdapter(api_key=api_key)
        elif name == "deepgram":
            return DeepgramAdapter(api_key=api_key)
        elif name == "elevenlabs":
            model = config.get("model", "eleven_turbo_v2")
            return ElevenLabsAdapter(api_key=api_key, model=model)
        else:
            raise ValueError(f"Unknown provider: {name}")

    def _init_sentinel(self) -> None:
        """Initialize Sentinel framework."""
        self._using_mock_sentinel = False

        try:
            from agentic.agentic_framework.agent import AgenticLLMWrapper

            # Create LLM client adapter
            llm_client = self._create_llm_client()

            self.sentinel = AgenticLLMWrapper(
                llm_client=llm_client,
                max_revisions=self.sentinel_config.get("max_revisions", 2),
                quality_threshold=self.sentinel_config.get("quality_threshold", 0.8)
            )
            logger.info("Initialized Sentinel framework")

        except ImportError as e:
            # CRITICAL FIX: Explicit alerting when using mock Sentinel
            self._using_mock_sentinel = True
            logger.warning(
                "IMPORTANT: Sentinel framework not available (import failed: %s). "
                "Using MockSentinel - responses will NOT use the full agentic pipeline. "
                "Install symbolu.agentic_framework for production use.",
                str(e)
            )
            self.sentinel = MockSentinel()

    @property
    def is_using_mock_sentinel(self) -> bool:
        """Check if running with mock Sentinel instead of real framework.

        IMPORTANT: When True, the voice agent is NOT using the full
        Sentinel agentic pipeline and responses will be limited.
        """
        return getattr(self, '_using_mock_sentinel', False)

    def _create_llm_client(self) -> Any:
        """Create LLM client based on configuration."""
        provider = self.sentinel_config.get("llm_provider", "anthropic")
        model = self.sentinel_config.get("llm_model", "claude-sonnet-4-20250514")

        if provider == "anthropic":
            return AnthropicAdapter(model=model)
        elif provider == "openai":
            return OpenAIAdapter(model=model)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    def _init_components(self) -> None:
        """Initialize voice components."""
        # P10 Prosody Mapper
        prosody_config = self.config.prosody_config or P10ProsodyConfig(
            default_voice_id=self.config.default_voice_id
        )
        self.p10_mapper = P10ProsodyMapper(config=prosody_config)

        # Safety Voice Gate
        safety_config = self.config.safety_config or SafetyGateConfig()
        self.safety_gate = SafetyVoiceGate(config=safety_config)

        # Voice Orchestrator
        orchestrator_config = self.config.orchestrator_config or OrchestratorConfig()

        # Get providers with fallback
        try:
            stt_provider = self.providers.get_stt(
                self.config.default_stt_provider,
                fallback=self.config.stt_fallback_providers
            )
        except RuntimeError:
            logger.error("No STT provider available")
            stt_provider = None

        try:
            tts_provider = self.providers.get_tts(
                self.config.default_tts_provider,
                fallback=self.config.tts_fallback_providers
            )
        except RuntimeError:
            logger.error("No TTS provider available")
            tts_provider = None

        if stt_provider and tts_provider:
            self.orchestrator = VoiceOrchestrator(
                sentinel=self.sentinel,
                stt_provider=stt_provider,
                tts_provider=tts_provider,
                p10_mapper=self.p10_mapper,
                safety_gate=self.safety_gate,
                config=orchestrator_config
            )
            logger.info("Initialized voice orchestrator")
        else:
            self.orchestrator = None
            logger.error("Could not initialize orchestrator - missing providers")

    async def start_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VoiceSession:
        """
        Start a new voice session.

        Args:
            session_id: Optional session ID
            metadata: Optional session metadata

        Returns:
            VoiceSession instance
        """
        if self.orchestrator is None:
            raise RuntimeError("Orchestrator not initialized")

        session = await self.orchestrator.start_session(
            session_id=session_id,
            metadata=metadata
        )
        self._active_sessions[session.session_id] = session

        logger.info(f"Started voice session: {session.session_id}")
        return session

    async def end_session(self, session_id: str) -> Optional[VoiceSession]:
        """
        End a voice session.

        Args:
            session_id: Session ID to end

        Returns:
            Final session state
        """
        session = self._active_sessions.pop(session_id, None)
        if session and self.orchestrator:
            await self.orchestrator.end_session(session_id)

        # Clear safety gate state
        self.safety_gate.clear_session(session_id)

        logger.info(f"Ended voice session: {session_id}")
        return session

    async def handle_websocket(
        self,
        websocket: Any,
        session_id: Optional[str] = None
    ) -> None:
        """
        Handle WebSocket connection for voice agent.

        Protocol:
        - Client sends: audio chunks (binary)
        - Server sends: audio chunks (binary) + events (JSON)

        Args:
            websocket: WebSocket connection
            session_id: Optional session ID

        Raises:
            ValueError: If session_id is invalid
            RuntimeError: If orchestrator is not initialized
        """
        # HIGH FIX: Validate session_id if provided
        if session_id is not None:
            # Sanitize session_id - only allow alphanumeric, hyphens, underscores
            import re
            if not re.match(r'^[a-zA-Z0-9_-]{1,128}$', session_id):
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid session_id format. Must be alphanumeric with hyphens/underscores, max 128 chars."
                })
                await websocket.close(code=1008)  # Policy violation
                return

        # HIGH FIX: Check orchestrator is available
        if self.orchestrator is None:
            await websocket.send_json({
                "type": "error",
                "message": "Voice orchestrator not initialized. Check provider configuration."
            })
            await websocket.close(code=1011)  # Internal error
            return

        session = None
        try:
            # Create session
            session = await self.start_session(session_id)

            # Send session info (include mock sentinel warning)
            session_info = {
                "type": "session_started",
                "session_id": session.session_id,
                "stt_provider": session.stt_provider,
                "tts_provider": session.tts_provider,
            }
            if self.is_using_mock_sentinel:
                session_info["warning"] = "Using MockSentinel - limited functionality"

            await websocket.send_json(session_info)

            # Create async audio stream from websocket
            async def audio_stream():
                async for message in websocket.iter_bytes():
                    yield message

            # Process and stream responses
            async for audio_chunk in self.orchestrator.process_audio_stream(
                session.session_id,
                audio_stream()
            ):
                await websocket.send_bytes(audio_chunk.audio)

                if audio_chunk.is_final:
                    await websocket.send_json({
                        "type": "response_complete"
                    })

        except asyncio.CancelledError:
            logger.info(f"WebSocket connection cancelled: {session_id}")
            raise

        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
            except Exception:
                pass  # Connection may already be closed

        finally:
            if session:
                await self.end_session(session.session_id)

    def create_fastapi_app(self) -> Any:
        """
        Create FastAPI application with WebSocket endpoint.

        Returns:
            FastAPI application instance
        """
        try:
            from fastapi import FastAPI, WebSocket, WebSocketDisconnect
            from fastapi.responses import JSONResponse
        except ImportError:
            raise ImportError(
                "FastAPI not installed. Install with: pip install fastapi uvicorn"
            )

        app = FastAPI(
            title="Symbolu Voice Agent",
            description="Hybrid Voice SDK powered by Sentinel Framework",
            version="1.0.0"
        )

        @app.websocket("/voice/{session_id}")
        async def voice_endpoint(
            websocket: WebSocket,
            session_id: Optional[str] = None
        ):
            await websocket.accept()
            try:
                await self.handle_websocket(websocket, session_id)
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {session_id}")

        @app.get("/health")
        async def health():
            provider_health = await self.providers.health_check()
            all_healthy = all(provider_health.values())

            # IMPROVED: Include Sentinel status in health check
            status = "healthy"
            if not all_healthy:
                status = "degraded"
            if self.is_using_mock_sentinel:
                status = "degraded" if status == "healthy" else status

            return JSONResponse(
                status_code=200 if all_healthy else 503,
                content={
                    "status": status,
                    "providers": provider_health,
                    "active_sessions": len(self._active_sessions),
                    "using_mock_sentinel": self.is_using_mock_sentinel,
                    "warning": (
                        "Running with MockSentinel - not using full agentic pipeline"
                        if self.is_using_mock_sentinel else None
                    )
                }
            )

        @app.get("/voices")
        async def list_voices():
            try:
                tts = self.providers.get_tts(self.config.default_tts_provider)
                voices = tts.get_voices()
                return [
                    {
                        "voice_id": v.voice_id,
                        "name": v.name,
                        "language": v.language,
                        "gender": v.gender,
                        "description": v.description
                    }
                    for v in voices
                ]
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={"error": str(e)}
                )

        @app.get("/providers")
        async def list_providers():
            status = self.providers.get_status()
            return {
                name: {
                    "health": s.health.value,
                    "average_latency_ms": s.average_latency_ms,
                    "success_count": s.success_count,
                    "failure_count": s.failure_count
                }
                for name, s in status.items()
            }

        @app.get("/sessions")
        async def list_sessions():
            return {
                "active_sessions": len(self._active_sessions),
                "sessions": [
                    {
                        "session_id": s.session_id,
                        "state": s.state.value,
                        "turn_count": s.turn_count,
                        "duration_seconds": s.duration_seconds
                    }
                    for s in self._active_sessions.values()
                ]
            }

        self._fastapi_app = app
        return app

    def run(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None
    ) -> None:
        """
        Run the voice agent server.

        Args:
            host: Host to bind to (default from config)
            port: Port to bind to (default from config)
        """
        try:
            import uvicorn
        except ImportError:
            raise ImportError(
                "uvicorn not installed. Install with: pip install uvicorn"
            )

        host = host or self.config.host
        port = port or self.config.port

        app = self.create_fastapi_app()

        logger.info(f"Starting voice agent server on {host}:{port}")
        uvicorn.run(app, host=host, port=port)

    async def run_async(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None
    ) -> None:
        """
        Run the voice agent server asynchronously.

        Args:
            host: Host to bind to
            port: Port to bind to
        """
        try:
            import uvicorn
        except ImportError:
            raise ImportError(
                "uvicorn not installed. Install with: pip install uvicorn"
            )

        host = host or self.config.host
        port = port or self.config.port

        app = self.create_fastapi_app()

        # Start health checks if enabled
        if self.config.enable_health_checks:
            await self.providers.start_health_checks()

        config = uvicorn.Config(app, host=host, port=port)
        server = uvicorn.Server(config)

        try:
            await server.serve()
        finally:
            await self.providers.stop_health_checks()


# LLM Client Adapters

class AnthropicAdapter:
    """Adapter for Anthropic Claude API."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic()
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. "
                    "Install with: pip install anthropic"
                )
        return self._client

    def call(self, prompt: str) -> str:
        client = self._get_client()
        message = client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text


class OpenAIAdapter:
    """Adapter for OpenAI API."""

    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI()
            except ImportError:
                raise ImportError(
                    "openai package not installed. "
                    "Install with: pip install openai"
                )
        return self._client

    def call(self, prompt: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content


class MockSentinel:
    """
    Mock Sentinel for testing when framework not available.

    Provides basic response generation without the full
    agentic pipeline.
    """

    def __init__(self):
        self.coherence_state = None
        self.goal_state = None

    def new_session(self, session_id: str) -> str:
        return session_id

    def run(self, user_input: str) -> Dict[str, Any]:
        return {
            "response": f"I heard: {user_input}",
            "quality_score": 0.8,
            "actions_executed": [],
            "actions_blocked": False,
            "blocking_reasons": [],
        }

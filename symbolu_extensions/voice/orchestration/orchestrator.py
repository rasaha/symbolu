"""
Voice Orchestrator - Core voice agent orchestration.

Manages the complete voice interaction flow:
1. Audio input → STT transcription
2. Transcribed text → Sentinel framework processing
3. Response → TTS synthesis → Audio output

With support for:
- Barge-in handling
- Turn management
- Interruption recovery
- Safety-aware response flow
- Coherence-driven prosody
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Callable, Dict, Optional, Any
import uuid

from ..providers.base import (
    STTProvider,
    TTSProvider,
    TTSParams,
    TranscriptEvent,
    TranscriptType,
    AudioChunk,
)
from .models import (
    VoiceSession,
    VoiceRequest,
    VoiceResponse,
    SessionState,
    InterruptionType,
    InterruptionEvent,
    TurnMetrics,
)
from .barge_in import BargeInHandler, BargeInStrategy, BargeInConfig

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for voice orchestrator."""
    # Timing
    silence_timeout_ms: float = 2000     # Max silence before end-of-turn
    max_turn_duration_ms: float = 60000  # Max single turn duration
    response_timeout_ms: float = 30000   # Max time waiting for LLM response
    sentinel_timeout_ms: float = 15000   # Timeout for Sentinel calls (MEDIUM FIX)

    # Barge-in
    barge_in_config: Optional[BargeInConfig] = None
    default_barge_in_strategy: BargeInStrategy = BargeInStrategy.CONFIRMED

    # Audio
    audio_chunk_size_ms: float = 100     # Size of audio chunks to process
    sample_rate: int = 16000             # Audio sample rate

    # Behavior
    enable_continuation: bool = True      # Enable continuation after interrupt
    enable_confirmations: bool = True     # Enable safety confirmations


class VoiceOrchestrator:
    """
    Orchestrates voice interactions with the Sentinel framework.

    This is the central component that manages:
    - STT streaming and transcription
    - Integration with Sentinel agentic framework
    - TTS synthesis with prosody control
    - Barge-in detection and handling
    - Turn management and session state

    Usage:
        orchestrator = VoiceOrchestrator(
            sentinel=sentinel_wrapper,
            stt_provider=cartesia_stt,
            tts_provider=cartesia_tts,
            p10_mapper=p10_mapper,
            safety_gate=safety_gate
        )

        session = await orchestrator.start_session()

        async for audio_chunk in orchestrator.process_audio_stream(
            session.session_id,
            audio_stream
        ):
            # Play audio_chunk
            pass
    """

    def __init__(
        self,
        sentinel: Any,  # AgenticLLMWrapper
        stt_provider: STTProvider,
        tts_provider: TTSProvider,
        p10_mapper: Any,  # P10ProsodyMapper
        safety_gate: Any,  # SafetyVoiceGate
        config: Optional[OrchestratorConfig] = None
    ):
        """
        Initialize voice orchestrator.

        Args:
            sentinel: Sentinel framework AgenticLLMWrapper instance
            stt_provider: Speech-to-text provider
            tts_provider: Text-to-speech provider
            p10_mapper: P10 prosody mapper for coherence-driven voice
            safety_gate: Safety voice gate for confirmations
            config: Orchestrator configuration
        """
        self.sentinel = sentinel
        self.stt = stt_provider
        self.tts = tts_provider
        self.p10_mapper = p10_mapper
        self.safety_gate = safety_gate
        self.config = config or OrchestratorConfig()

        # Session management
        self._sessions: Dict[str, VoiceSession] = {}

        # Barge-in handling
        self._barge_in_handler = BargeInHandler(
            config=self.config.barge_in_config or BargeInConfig(
                default_strategy=self.config.default_barge_in_strategy
            )
        )

        # Active tasks for cancellation
        self._response_tasks: Dict[str, asyncio.Task] = {}
        self._tts_tasks: Dict[str, asyncio.Task] = {}
        # CRITICAL FIX: Lock for protecting task dictionaries during concurrent access
        self._tasks_lock = asyncio.Lock()

        # Metrics
        self._turn_metrics: Dict[str, TurnMetrics] = {}

        # Event callbacks
        self._on_transcript: Optional[Callable] = None
        self._on_response: Optional[Callable] = None
        self._on_interruption: Optional[Callable] = None

    async def start_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VoiceSession:
        """
        Initialize a new voice session.

        Args:
            session_id: Optional session ID (generated if not provided)
            metadata: Optional session metadata

        Returns:
            VoiceSession instance
        """
        session = VoiceSession.create(session_id)
        session.metadata = metadata or {}
        session.stt_provider = self.stt.provider_name
        session.tts_provider = self.tts.provider_name

        # Initialize Sentinel session
        self.sentinel.new_session(session.session_id)

        self._sessions[session.session_id] = session
        logger.info(f"Started voice session: {session.session_id}")

        return session

    async def end_session(self, session_id: str) -> Optional[VoiceSession]:
        """
        End a voice session.

        Args:
            session_id: Session ID to end

        Returns:
            Final session state or None if not found
        """
        session = self._sessions.pop(session_id, None)
        if session:
            session.end()
            await self._cancel_session_tasks(session_id)
            logger.info(f"Ended voice session: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    async def process_audio_stream(
        self,
        session_id: str,
        audio_stream: AsyncIterator[bytes],
        language: Optional[str] = None
    ) -> AsyncIterator[AudioChunk]:
        """
        Process incoming audio and yield response audio.

        This is the main entry point for voice interaction.
        Handles the complete flow from user speech to agent response.

        Args:
            session_id: Session ID
            audio_stream: Async iterator yielding audio chunks
            language: Optional language code for STT

        Yields:
            AudioChunk objects with synthesized response audio
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Start listening
        session.start_listening()

        # Buffer for accumulating transcript
        transcript_buffer: list = []
        current_turn_id = 0

        try:
            async for event in self.stt.transcribe_stream(
                audio_stream,
                sample_rate=self.config.sample_rate,
                language=language
            ):
                # Fire transcript callback
                if self._on_transcript:
                    await self._on_transcript(session_id, event)

                # Check for barge-in during agent speech
                if session.is_speaking:
                    if self._should_handle_barge_in(session, event):
                        await self._handle_barge_in(session, event)
                        continue

                # Accumulate transcript
                if event.transcript_type == TranscriptType.FINAL:
                    transcript_buffer.append(event.text)

                # Process on utterance end
                if event.is_endpoint and transcript_buffer:
                    full_transcript = " ".join(transcript_buffer)
                    transcript_buffer = []

                    if full_transcript.strip():
                        current_turn_id = session.increment_turn()

                        # Process and yield response audio
                        async for audio_chunk in self._process_turn(
                            session,
                            full_transcript,
                            current_turn_id,
                            event.confidence
                        ):
                            yield audio_chunk

        except asyncio.CancelledError:
            logger.info(f"Audio stream cancelled for session {session_id}")
            raise

        except Exception as e:
            logger.error(f"Error processing audio stream: {e}")
            raise

        finally:
            session.state = SessionState.IDLE

    async def _process_turn(
        self,
        session: VoiceSession,
        text: str,
        turn_id: int,
        confidence: float
    ) -> AsyncIterator[AudioChunk]:
        """Process a complete user turn and generate response."""
        metrics = TurnMetrics(
            turn_id=turn_id,
            session_id=session.session_id
        )
        metrics.user_speech_end = datetime.utcnow()
        metrics.transcript_confidence = confidence
        self._turn_metrics[f"{session.session_id}:{turn_id}"] = metrics

        # Create request
        request = VoiceRequest(
            text=text,
            session_id=session.session_id,
            turn_id=turn_id,
            interrupted_response=(
                session.interrupted_responses[-1]
                if session.interrupted_responses else None
            ),
            continuation_context=session.pending_continuation,
            is_confirmation=session.awaiting_confirmation,
            transcript_confidence=confidence
        )

        # Transition to processing
        session.start_processing()
        metrics.processing_start = datetime.utcnow()

        try:
            # Process through Sentinel
            sentinel_result = await self._process_with_sentinel(request)

            metrics.processing_end = datetime.utcnow()
            metrics.processing_duration_ms = (
                metrics.processing_end - metrics.processing_start
            ).total_seconds() * 1000

            # Build voice response
            response = self._build_response(
                sentinel_result,
                session.session_id,
                turn_id
            )

            metrics.response_quality_score = response.quality_score
            if response.coherence_state:
                metrics.coherence_score = getattr(
                    response.coherence_state.current_metrics,
                    'overall_coherence',
                    0.0
                )

            # Fire response callback
            if self._on_response:
                await self._on_response(session.session_id, response)

            # Apply safety gate
            gated_response = await self.safety_gate.process(response)

            # Update session state for confirmations
            if gated_response.requires_confirmation:
                session.awaiting_confirmation = True
                session.confirmation_context = {
                    "original_response": response.text,
                    "blocked_reasons": gated_response.blocking_reasons
                }
            else:
                session.awaiting_confirmation = False
                session.confirmation_context = None
                session.pending_continuation = None

            # Compute TTS parameters
            tts_params = self.p10_mapper.compute_params(
                coherence_state=response.coherence_state,
                safety_contract=response.safety_contract
            )

            # Synthesize and stream response
            session.start_speaking(response.response_id)
            metrics.agent_speech_start = datetime.utcnow()

            try:
                async for chunk in self.tts.synthesize_stream(
                    gated_response.text,
                    tts_params
                ):
                    yield chunk

                    if chunk.is_final:
                        metrics.agent_speech_end = datetime.utcnow()
                        metrics.agent_speech_duration_ms = (
                            metrics.agent_speech_end - metrics.agent_speech_start
                        ).total_seconds() * 1000

            finally:
                session.stop_speaking()
                self._barge_in_handler.record_agent_speech_end()
                metrics.calculate_latency()

        except asyncio.CancelledError:
            metrics.was_interrupted = True
            raise

        except Exception as e:
            logger.error(f"Error processing turn: {e}")
            # Yield error response
            error_text = "I'm sorry, I encountered an error processing your request."
            async for chunk in self.tts.synthesize_stream(
                error_text,
                TTSParams(voice_id=self._get_default_voice_id())
            ):
                yield chunk

    async def _process_with_sentinel(
        self,
        request: VoiceRequest
    ) -> Dict[str, Any]:
        """Process request through Sentinel framework.

        MEDIUM FIX: Added timeout to prevent indefinite hangs.

        Raises:
            asyncio.TimeoutError: If Sentinel doesn't respond within timeout
        """
        # Handle confirmation responses
        if request.is_confirmation:
            text_lower = request.text.lower()
            if any(w in text_lower for w in ["yes", "yeah", "yep", "correct", "proceed"]):
                # User confirmed - process original action
                # This would need integration with Sentinel's confirmation handling
                pass
            elif any(w in text_lower for w in ["no", "nope", "cancel", "stop"]):
                # User declined
                return {
                    "response": "Understood. I won't proceed with that action.",
                    "quality_score": 1.0,
                }

        # Build context with any continuation info
        input_text = request.text
        if request.continuation_context:
            input_text = f"{request.continuation_context}\n\nUser: {request.text}"

        # Call Sentinel with timeout protection
        timeout_seconds = self.config.sentinel_timeout_ms / 1000

        try:
            # Wrap synchronous sentinel.run in executor for async timeout support
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self.sentinel.run, input_text),
                timeout=timeout_seconds
            )
            return result

        except asyncio.TimeoutError:
            logger.error(
                f"Sentinel timeout after {timeout_seconds}s for session {request.session_id}"
            )
            return {
                "response": "I apologize, but I'm taking longer than expected to process your request. Could you please try again?",
                "quality_score": 0.3,
                "error": "sentinel_timeout"
            }

    def _build_response(
        self,
        sentinel_result: Dict[str, Any],
        session_id: str,
        turn_id: int
    ) -> VoiceResponse:
        """Build VoiceResponse from Sentinel result."""
        return VoiceResponse(
            response_id=str(uuid.uuid4()),
            text=sentinel_result.get("response", ""),
            session_id=session_id,
            turn_id=turn_id,
            coherence_state=getattr(self.sentinel, 'coherence_state', None),
            safety_contract=sentinel_result.get("safety_contract"),
            goal_state=getattr(self.sentinel, 'goal_state', None),
            quality_score=sentinel_result.get("quality_score", 0.0),
            tools_executed=sentinel_result.get("actions_executed", []),
            actions_blocked=sentinel_result.get("actions_blocked", False),
            blocking_reasons=sentinel_result.get("blocking_reasons", []),
        )

    def _should_handle_barge_in(
        self,
        session: VoiceSession,
        event: TranscriptEvent
    ) -> bool:
        """Check if barge-in should be handled."""
        # Get response priority
        priority = "normal"
        if session.confirmation_context:
            priority = "high"  # Don't interrupt confirmations easily

        return self._barge_in_handler.should_interrupt(
            event,
            response_priority=priority
        )

    async def _handle_barge_in(
        self,
        session: VoiceSession,
        event: TranscriptEvent
    ) -> None:
        """Handle user interruption during agent speech."""
        logger.info(f"Barge-in detected in session {session.session_id}")

        # Cancel TTS task with lock protection
        task_to_cancel = None
        async with self._tasks_lock:
            if session.current_response_id in self._tts_tasks:
                task_to_cancel = self._tts_tasks.pop(session.current_response_id, None)

        if task_to_cancel:
            task_to_cancel.cancel()
            try:
                await task_to_cancel
            except asyncio.CancelledError:
                pass

        # Record interruption
        session.record_interruption(InterruptionType.BARGE_IN)

        # Generate continuation context if enabled
        if self.config.enable_continuation:
            # This would need the actual spoken text tracking
            session.pending_continuation = (
                f"[User interrupted. They said: '{event.text}']"
            )

        # Create interruption event
        interruption = InterruptionEvent(
            interruption_type=InterruptionType.BARGE_IN,
            interrupted_response_id=session.current_response_id,
            user_transcript=event.text,
            transcript_confidence=event.confidence
        )

        # Fire callback
        if self._on_interruption:
            await self._on_interruption(session.session_id, interruption)

        # Classify interruption for adaptive handling
        classification, confidence = self._barge_in_handler.classify_interruption(event)
        logger.debug(f"Interruption classified as '{classification}' ({confidence:.2f})")

    async def _cancel_session_tasks(self, session_id: str) -> None:
        """Cancel all active tasks for a session.

        CRITICAL FIX: Uses async lock to prevent race conditions during
        concurrent task cancellation.
        """
        async with self._tasks_lock:
            # Cancel response tasks
            tasks_to_cancel = []
            keys_to_remove = []
            for key in list(self._response_tasks.keys()):
                if key.startswith(session_id):
                    tasks_to_cancel.append(self._response_tasks[key])
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                self._response_tasks.pop(key, None)

            # Cancel TTS tasks
            keys_to_remove = []
            for key in list(self._tts_tasks.keys()):
                if key.startswith(session_id):
                    tasks_to_cancel.append(self._tts_tasks[key])
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                self._tts_tasks.pop(key, None)

        # Cancel tasks outside the lock to avoid deadlock
        for task in tasks_to_cancel:
            task.cancel()

        # Wait for tasks to complete cancellation
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

    def _get_default_voice_id(self) -> str:
        """Get default voice ID for error responses."""
        voices = self.tts.get_voices()
        if voices:
            return voices[0].voice_id
        return "default"

    # Event handlers
    def on_transcript(self, callback: Callable) -> None:
        """Set callback for transcript events."""
        self._on_transcript = callback

    def on_response(self, callback: Callable) -> None:
        """Set callback for response events."""
        self._on_response = callback

    def on_interruption(self, callback: Callable) -> None:
        """Set callback for interruption events."""
        self._on_interruption = callback

    # Metrics
    def get_turn_metrics(
        self,
        session_id: str,
        turn_id: Optional[int] = None
    ) -> Dict[str, TurnMetrics]:
        """Get turn metrics for a session."""
        prefix = f"{session_id}:"
        if turn_id is not None:
            key = f"{session_id}:{turn_id}"
            if key in self._turn_metrics:
                return {key: self._turn_metrics[key]}
            return {}

        return {
            k: v for k, v in self._turn_metrics.items()
            if k.startswith(prefix)
        }

    @property
    def active_sessions(self) -> int:
        """Number of active sessions."""
        return len(self._sessions)

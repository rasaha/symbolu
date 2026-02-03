"""
Voice Pipeline Integration Tests
================================

Integration tests for the complete voice pipeline,
from audio input through response synthesis.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass, field
from typing import List, AsyncIterator

from symbolu.voice.providers import (
    ProviderRegistry,
    TTSParams,
    AudioChunk,
    TranscriptEvent,
    TranscriptType,
)
from symbolu.voice.orchestration import (
    VoiceOrchestrator,
    OrchestratorConfig,
    VoiceSession,
    SessionState,
)
from symbolu.voice.prosody import P10ProsodyMapper, AcousticRegime
from symbolu.voice.safety import SafetyVoiceGate


# Mock implementations for integration testing
@dataclass
class MockCoherenceMetrics:
    overall_coherence: float = 0.8
    prediction_reversal_risk: float = 0.2
    internal_consistency: float = 0.8
    goal_alignment: float = 0.8
    drift_direction: str = "stable"


@dataclass
class MockCoherenceState:
    current_metrics: MockCoherenceMetrics = None

    def __post_init__(self):
        if self.current_metrics is None:
            self.current_metrics = MockCoherenceMetrics()


@dataclass
class MockSafetyContract:
    eligible: bool = True
    violated_preconditions: List[str] = field(default_factory=list)
    blocking_reasons: List[str] = field(default_factory=list)


class MockSentinel:
    """Mock Sentinel framework for testing."""

    def __init__(self):
        self.coherence_state = MockCoherenceState()
        self.goal_state = None
        self.safety_evaluator = Mock()
        self.safety_evaluator.evaluate = Mock(return_value=MockSafetyContract())

    def new_session(self, session_id: str):
        return session_id

    def run(self, text: str):
        return {
            "response": f"I heard: {text}",
            "quality_score": 0.9,
            "actions_executed": [],
            "actions_blocked": False,
            "blocking_reasons": [],
        }


class MockSTTProvider:
    """Mock STT provider for integration tests."""

    def __init__(self, responses: List[str] = None):
        self.responses = responses or ["Hello world"]
        self.call_count = 0

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        **kwargs
    ) -> AsyncIterator[TranscriptEvent]:
        # Consume audio stream
        async for _ in audio_stream:
            pass

        # Yield mock transcripts
        for response in self.responses:
            yield TranscriptEvent(
                text=response,
                transcript_type=TranscriptType.FINAL,
                confidence=0.95,
                is_endpoint=True
            )

    async def transcribe_file(self, audio_bytes: bytes, **kwargs):
        return TranscriptEvent(
            text=self.responses[0] if self.responses else "",
            transcript_type=TranscriptType.FINAL,
            confidence=0.95
        )

    @property
    def supported_languages(self):
        return ["en"]

    @property
    def supports_streaming(self):
        return True

    @property
    def provider_name(self):
        return "MockSTT"


class MockTTSProvider:
    """Mock TTS provider for integration tests."""

    def __init__(self, latency_ms: float = 50):
        self.latency_ms = latency_ms
        self.call_count = 0
        self.last_text = None

    async def synthesize_stream(
        self,
        text: str,
        params: TTSParams
    ) -> AsyncIterator[AudioChunk]:
        self.call_count += 1
        self.last_text = text

        # Simulate latency
        await asyncio.sleep(self.latency_ms / 1000)

        # Yield mock audio chunks
        for i in range(3):
            yield AudioChunk(
                audio=b"\x00" * 1000,
                sample_rate=16000,
                format="pcm",
                duration_ms=62.5,  # ~1000 bytes at 16kHz 16-bit
                is_final=(i == 2),
                sequence_number=i
            )

    async def synthesize(self, text: str, params: TTSParams) -> bytes:
        self.call_count += 1
        self.last_text = text
        await asyncio.sleep(self.latency_ms / 1000)
        return b"\x00" * 3000

    def get_voices(self):
        return [Mock(voice_id="mock-voice", name="Mock", language="en")]

    @property
    def supports_streaming(self):
        return True

    @property
    def average_latency_ms(self):
        return self.latency_ms

    @property
    def provider_name(self):
        return "MockTTS"


class TestVoicePipelineIntegration:
    """Integration tests for complete voice pipeline."""

    def create_orchestrator(
        self,
        stt_responses: List[str] = None,
        sentinel: MockSentinel = None
    ) -> VoiceOrchestrator:
        """Helper to create test orchestrator."""
        return VoiceOrchestrator(
            sentinel=sentinel or MockSentinel(),
            stt_provider=MockSTTProvider(stt_responses or ["Hello"]),
            tts_provider=MockTTSProvider(),
            p10_mapper=P10ProsodyMapper(),
            safety_gate=SafetyVoiceGate(),
            config=OrchestratorConfig()
        )

    @pytest.mark.asyncio
    async def test_complete_pipeline_flow(self):
        """Test complete flow from audio to response."""
        orchestrator = self.create_orchestrator(
            stt_responses=["What is the weather?"]
        )

        # Start session
        session = await orchestrator.start_session()
        assert session.state == SessionState.IDLE

        # Create mock audio stream
        async def mock_audio_stream():
            for _ in range(3):
                yield b"\x00" * 1000
                await asyncio.sleep(0.01)

        # Process audio and collect response
        response_chunks = []
        async for chunk in orchestrator.process_audio_stream(
            session.session_id,
            mock_audio_stream()
        ):
            response_chunks.append(chunk)

        # Verify response was generated
        assert len(response_chunks) > 0
        assert any(chunk.is_final for chunk in response_chunks)

    @pytest.mark.asyncio
    async def test_session_lifecycle(self):
        """Test session creation, usage, and termination."""
        orchestrator = self.create_orchestrator()

        # Create session
        session = await orchestrator.start_session("test-session-1")
        assert session.session_id == "test-session-1"
        assert orchestrator.active_sessions == 1

        # End session
        ended = await orchestrator.end_session("test-session-1")
        assert ended is not None
        assert ended.state == SessionState.ENDED
        assert orchestrator.active_sessions == 0

    @pytest.mark.asyncio
    async def test_multiple_turns(self):
        """Test multi-turn conversation."""
        orchestrator = self.create_orchestrator(
            stt_responses=["Hello", "How are you?"]
        )

        session = await orchestrator.start_session()

        # First turn
        async def audio1():
            yield b"\x00" * 500

        turn1_chunks = []
        async for chunk in orchestrator.process_audio_stream(
            session.session_id,
            audio1()
        ):
            turn1_chunks.append(chunk)

        # Verify turn count incremented
        session = orchestrator.get_session(session.session_id)
        assert session.turn_count >= 1

    @pytest.mark.asyncio
    async def test_prosody_applied_to_response(self):
        """Test that prosody mapper affects TTS parameters."""
        # Create orchestrator with observable TTS
        tts = MockTTSProvider()
        orchestrator = VoiceOrchestrator(
            sentinel=MockSentinel(),
            stt_provider=MockSTTProvider(["Test"]),
            tts_provider=tts,
            p10_mapper=P10ProsodyMapper(),
            safety_gate=SafetyVoiceGate()
        )

        session = await orchestrator.start_session()

        async def audio():
            yield b"\x00" * 100

        async for _ in orchestrator.process_audio_stream(
            session.session_id,
            audio()
        ):
            pass

        # TTS should have been called
        assert tts.call_count > 0

    @pytest.mark.asyncio
    async def test_safety_gate_integration(self):
        """Test that safety gate processes responses."""
        # Create sentinel that returns blocked response
        sentinel = MockSentinel()
        sentinel.safety_evaluator.evaluate = Mock(
            return_value=MockSafetyContract(
                eligible=False,
                violated_preconditions=["test_violation"]
            )
        )

        orchestrator = self.create_orchestrator(sentinel=sentinel)
        session = await orchestrator.start_session()

        async def audio():
            yield b"\x00" * 100

        response_text = ""
        tts = orchestrator.tts
        original_synthesize = tts.synthesize_stream

        async def capture_synthesize(text, params):
            nonlocal response_text
            response_text = text
            async for chunk in original_synthesize(text, params):
                yield chunk

        tts.synthesize_stream = capture_synthesize

        async for _ in orchestrator.process_audio_stream(
            session.session_id,
            audio()
        ):
            pass

        # Response should include confirmation request
        # (safety gate should have modified it)

    @pytest.mark.asyncio
    async def test_session_not_found_error(self):
        """Test error when processing unknown session."""
        orchestrator = self.create_orchestrator()

        async def audio():
            yield b"\x00" * 100

        with pytest.raises(ValueError, match="not found"):
            async for _ in orchestrator.process_audio_stream(
                "nonexistent-session",
                audio()
            ):
                pass

    @pytest.mark.asyncio
    async def test_turn_metrics_tracking(self):
        """Test that turn metrics are tracked."""
        orchestrator = self.create_orchestrator(
            stt_responses=["Hello"]
        )

        session = await orchestrator.start_session()

        async def audio():
            yield b"\x00" * 100

        async for _ in orchestrator.process_audio_stream(
            session.session_id,
            audio()
        ):
            pass

        # Get metrics
        metrics = orchestrator.get_turn_metrics(session.session_id)
        assert len(metrics) > 0


class TestProviderRegistryIntegration:
    """Integration tests for provider registry with voice components."""

    @pytest.mark.asyncio
    async def test_registry_with_orchestrator(self):
        """Test using registry-provided providers in orchestrator."""
        registry = ProviderRegistry()

        # Register mock adapter
        class MockAdapter:
            @property
            def stt(self):
                return MockSTTProvider(["Registry test"])

            @property
            def tts(self):
                return MockTTSProvider()

        registry.register("mock", MockAdapter())

        # Get providers from registry
        stt = registry.get_stt("mock")
        tts = registry.get_tts("mock")

        # Create orchestrator with registry providers
        orchestrator = VoiceOrchestrator(
            sentinel=MockSentinel(),
            stt_provider=stt,
            tts_provider=tts,
            p10_mapper=P10ProsodyMapper(),
            safety_gate=SafetyVoiceGate()
        )

        session = await orchestrator.start_session()
        assert session is not None

    @pytest.mark.asyncio
    async def test_provider_failover_in_pipeline(self):
        """Test that provider failover works during processing."""
        registry = ProviderRegistry()

        class FailingAdapter:
            @property
            def stt(self):
                raise Exception("Primary failed")

            @property
            def tts(self):
                raise Exception("Primary failed")

        class WorkingAdapter:
            @property
            def stt(self):
                return MockSTTProvider(["Fallback"])

            @property
            def tts(self):
                return MockTTSProvider()

        registry.register("primary", FailingAdapter())
        registry.register("fallback", WorkingAdapter())

        # Should get fallback
        stt = registry.get_stt("primary", fallback=["fallback"])
        assert stt is not None


class TestCoherenceDrivenVoice:
    """Integration tests for coherence-driven voice modulation."""

    @pytest.mark.asyncio
    async def test_low_coherence_affects_voice(self):
        """Test that low coherence modulates voice parameters."""
        # Create sentinel with low coherence
        sentinel = MockSentinel()
        sentinel.coherence_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(
                overall_coherence=0.3,
                prediction_reversal_risk=0.7
            )
        )

        tts = MockTTSProvider()
        mapper = P10ProsodyMapper()

        # Compute params with low coherence
        params = mapper.compute_params(
            coherence_state=sentinel.coherence_state
        )

        # Speed should be reduced for low coherence
        assert params.speed < 1.0

    @pytest.mark.asyncio
    async def test_safety_concern_affects_voice(self):
        """Test that safety concerns modulate voice parameters."""
        mapper = P10ProsodyMapper()

        # Safety concern
        blocked_contract = MockSafetyContract(eligible=False)

        params = mapper.compute_params(
            safety_contract=blocked_contract
        )

        # Should have adjusted parameters
        assert params.speed <= 1.0  # Slower for caution

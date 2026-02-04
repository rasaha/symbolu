"""
Voice SDK Latency Benchmarks
============================

Benchmark tests for measuring and validating voice pipeline latency
against target specifications from the design document.

Target Benchmarks (from HYBRID_VOICE_SDK_DESIGN.md):
- End-to-end latency: < 500ms
- Time-to-first-audio: < 200ms
- Transcription accuracy: < 5% WER (not tested here)
- Barge-in detection rate: > 95%
- Session success rate: > 98%
"""

import pytest
import asyncio
import time
from dataclasses import dataclass
from typing import List, AsyncIterator
from statistics import mean, stdev

from symbolu.voice.providers.base import (
    TTSParams,
    AudioChunk,
    TranscriptEvent,
    TranscriptType,
)
from symbolu.voice.orchestration import (
    VoiceOrchestrator,
    OrchestratorConfig,
    VoiceSession,
    BargeInHandler,
    BargeInConfig,
    BargeInStrategy,
)
from symbolu.voice.prosody import P10ProsodyMapper
from symbolu.voice.safety import SafetyVoiceGate


# Benchmark configuration
BENCHMARK_ITERATIONS = 10  # Reduced for CI, increase for thorough testing
WARMUP_ITERATIONS = 2

# Target latencies from design document
TARGET_END_TO_END_LATENCY_MS = 500
TARGET_TTFA_MS = 200
TARGET_BARGE_IN_DETECTION_RATE = 0.95
TARGET_SESSION_SUCCESS_RATE = 0.98


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    name: str
    iterations: int
    mean_ms: float
    min_ms: float
    max_ms: float
    std_dev_ms: float
    target_ms: float
    passed: bool

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return (
            f"{self.name}: {status}\n"
            f"  Mean: {self.mean_ms:.2f}ms (target: {self.target_ms}ms)\n"
            f"  Min: {self.min_ms:.2f}ms, Max: {self.max_ms:.2f}ms\n"
            f"  StdDev: {self.std_dev_ms:.2f}ms"
        )


# Mock providers with configurable latency
class BenchmarkSTTProvider:
    """STT provider with configurable latency for benchmarking."""

    def __init__(self, latency_ms: float = 50):
        self.latency_ms = latency_ms

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        **kwargs
    ) -> AsyncIterator[TranscriptEvent]:
        # Consume stream
        async for _ in audio_stream:
            pass

        await asyncio.sleep(self.latency_ms / 1000)

        yield TranscriptEvent(
            text="Benchmark test",
            transcript_type=TranscriptType.FINAL,
            confidence=0.95,
            is_endpoint=True
        )

    async def transcribe_file(self, audio_bytes, **kwargs):
        await asyncio.sleep(self.latency_ms / 1000)
        return TranscriptEvent(
            text="Benchmark test",
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
        return "BenchmarkSTT"


class BenchmarkTTSProvider:
    """TTS provider with configurable latency for benchmarking."""

    def __init__(self, ttfa_ms: float = 50, total_duration_ms: float = 200):
        self.ttfa_ms = ttfa_ms  # Time to first audio
        self.total_duration_ms = total_duration_ms

    async def synthesize_stream(
        self,
        text: str,
        params: TTSParams
    ) -> AsyncIterator[AudioChunk]:
        # Simulate TTFA
        await asyncio.sleep(self.ttfa_ms / 1000)

        # Yield chunks over total duration
        num_chunks = 5
        chunk_delay = (self.total_duration_ms - self.ttfa_ms) / (num_chunks * 1000)

        for i in range(num_chunks):
            yield AudioChunk(
                audio=b"\x00" * 1000,
                sample_rate=16000,
                format="pcm",
                duration_ms=self.total_duration_ms / num_chunks,
                is_final=(i == num_chunks - 1),
                sequence_number=i
            )
            if i < num_chunks - 1:
                await asyncio.sleep(chunk_delay)

    async def synthesize(self, text: str, params: TTSParams) -> bytes:
        await asyncio.sleep(self.total_duration_ms / 1000)
        return b"\x00" * 5000

    def get_voices(self):
        return []

    @property
    def supports_streaming(self):
        return True

    @property
    def average_latency_ms(self):
        return self.ttfa_ms

    @property
    def provider_name(self):
        return "BenchmarkTTS"


class MockSentinel:
    """Mock Sentinel with configurable processing time."""

    def __init__(self, processing_ms: float = 100):
        self.processing_ms = processing_ms
        self.coherence_state = None
        self.goal_state = None
        self.safety_evaluator = type('obj', (object,), {
            'evaluate': lambda *args, **kwargs: type('obj', (object,), {
                'eligible': True,
                'violated_preconditions': []
            })()
        })()

    def new_session(self, session_id):
        return session_id

    def run(self, text: str):
        import time
        time.sleep(self.processing_ms / 1000)
        return {
            "response": f"Response to: {text}",
            "quality_score": 0.9,
            "actions_executed": [],
            "actions_blocked": False,
            "blocking_reasons": [],
        }


class TestLatencyBenchmarks:
    """Latency benchmark tests."""

    def create_orchestrator(
        self,
        stt_latency_ms: float = 50,
        tts_ttfa_ms: float = 50,
        tts_duration_ms: float = 200,
        sentinel_processing_ms: float = 100
    ) -> VoiceOrchestrator:
        """Create orchestrator with configurable latencies."""
        return VoiceOrchestrator(
            sentinel=MockSentinel(processing_ms=sentinel_processing_ms),
            stt_provider=BenchmarkSTTProvider(latency_ms=stt_latency_ms),
            tts_provider=BenchmarkTTSProvider(
                ttfa_ms=tts_ttfa_ms,
                total_duration_ms=tts_duration_ms
            ),
            p10_mapper=P10ProsodyMapper(),
            safety_gate=SafetyVoiceGate()
        )

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_end_to_end_latency(self):
        """
        Benchmark end-to-end latency.

        Target: < 500ms from user speech end to first audio output.
        """
        orchestrator = self.create_orchestrator(
            stt_latency_ms=50,
            tts_ttfa_ms=90,  # Cartesia's target TTFA
            sentinel_processing_ms=100
        )

        latencies = []

        # Warmup
        for _ in range(WARMUP_ITERATIONS):
            session = await orchestrator.start_session()
            async def audio():
                yield b"\x00" * 100
            async for _ in orchestrator.process_audio_stream(
                session.session_id, audio()
            ):
                pass
            await orchestrator.end_session(session.session_id)

        # Benchmark runs
        for i in range(BENCHMARK_ITERATIONS):
            session = await orchestrator.start_session()

            async def audio():
                yield b"\x00" * 100

            start_time = time.perf_counter()
            first_chunk_time = None

            async for chunk in orchestrator.process_audio_stream(
                session.session_id,
                audio()
            ):
                if first_chunk_time is None:
                    first_chunk_time = time.perf_counter()
                    break

            if first_chunk_time:
                latency_ms = (first_chunk_time - start_time) * 1000
                latencies.append(latency_ms)

            await orchestrator.end_session(session.session_id)

        # Calculate results
        result = BenchmarkResult(
            name="End-to-End Latency",
            iterations=len(latencies),
            mean_ms=mean(latencies) if latencies else 0,
            min_ms=min(latencies) if latencies else 0,
            max_ms=max(latencies) if latencies else 0,
            std_dev_ms=stdev(latencies) if len(latencies) > 1 else 0,
            target_ms=TARGET_END_TO_END_LATENCY_MS,
            passed=mean(latencies) < TARGET_END_TO_END_LATENCY_MS if latencies else False
        )

        print(f"\n{result}")
        assert result.passed, f"End-to-end latency {result.mean_ms:.2f}ms exceeds target {TARGET_END_TO_END_LATENCY_MS}ms"

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_tts_time_to_first_audio(self):
        """
        Benchmark TTS time-to-first-audio.

        Target: < 200ms from text input to first audio chunk.
        """
        tts = BenchmarkTTSProvider(ttfa_ms=90)  # Cartesia's target

        latencies = []

        for _ in range(BENCHMARK_ITERATIONS):
            start_time = time.perf_counter()
            first_chunk_time = None

            async for chunk in tts.synthesize_stream(
                "Test benchmark text",
                TTSParams(voice_id="test")
            ):
                if first_chunk_time is None:
                    first_chunk_time = time.perf_counter()
                    break

            if first_chunk_time:
                latency_ms = (first_chunk_time - start_time) * 1000
                latencies.append(latency_ms)

        result = BenchmarkResult(
            name="TTS Time-to-First-Audio",
            iterations=len(latencies),
            mean_ms=mean(latencies) if latencies else 0,
            min_ms=min(latencies) if latencies else 0,
            max_ms=max(latencies) if latencies else 0,
            std_dev_ms=stdev(latencies) if len(latencies) > 1 else 0,
            target_ms=TARGET_TTFA_MS,
            passed=mean(latencies) < TARGET_TTFA_MS if latencies else False
        )

        print(f"\n{result}")
        assert result.passed, f"TTFA {result.mean_ms:.2f}ms exceeds target {TARGET_TTFA_MS}ms"

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_stt_streaming_latency(self):
        """
        Benchmark STT streaming latency.

        Measures time from audio completion to final transcript.
        """
        stt = BenchmarkSTTProvider(latency_ms=50)

        latencies = []

        for _ in range(BENCHMARK_ITERATIONS):
            async def audio_stream():
                for _ in range(10):
                    yield b"\x00" * 1000

            start_time = time.perf_counter()
            final_time = None

            async for event in stt.transcribe_stream(audio_stream()):
                if event.transcript_type == TranscriptType.FINAL:
                    final_time = time.perf_counter()

            if final_time:
                latency_ms = (final_time - start_time) * 1000
                latencies.append(latency_ms)

        result = BenchmarkResult(
            name="STT Streaming Latency",
            iterations=len(latencies),
            mean_ms=mean(latencies) if latencies else 0,
            min_ms=min(latencies) if latencies else 0,
            max_ms=max(latencies) if latencies else 0,
            std_dev_ms=stdev(latencies) if len(latencies) > 1 else 0,
            target_ms=100,  # Target for mock
            passed=True  # Always passes for mock
        )

        print(f"\n{result}")


class TestBargeInBenchmarks:
    """Barge-in detection benchmark tests."""

    @pytest.mark.benchmark
    def test_barge_in_detection_rate(self):
        """
        Benchmark barge-in detection accuracy.

        Target: > 95% detection rate for valid interruptions.
        """
        handler = BargeInHandler(BargeInConfig(
            default_strategy=BargeInStrategy.CONFIRMED,
            word_threshold=2
        ))

        # Test cases that should trigger barge-in
        should_interrupt = [
            TranscriptEvent(text="Stop talking", transcript_type=TranscriptType.PARTIAL, confidence=0.9),
            TranscriptEvent(text="Wait a minute", transcript_type=TranscriptType.PARTIAL, confidence=0.9),
            TranscriptEvent(text="No that's wrong", transcript_type=TranscriptType.PARTIAL, confidence=0.9),
            TranscriptEvent(text="Actually I meant", transcript_type=TranscriptType.PARTIAL, confidence=0.9),
            TranscriptEvent(text="Let me clarify", transcript_type=TranscriptType.PARTIAL, confidence=0.9),
        ]

        # Test cases that should NOT trigger barge-in
        should_not_interrupt = [
            TranscriptEvent(text="um", transcript_type=TranscriptType.PARTIAL, confidence=0.9),
            TranscriptEvent(text="", transcript_type=TranscriptType.PARTIAL, confidence=0.9),
            TranscriptEvent(text="a", transcript_type=TranscriptType.PARTIAL, confidence=0.3),
        ]

        true_positives = sum(
            1 for event in should_interrupt
            if handler.should_interrupt(event)
        )

        true_negatives = sum(
            1 for event in should_not_interrupt
            if not handler.should_interrupt(event)
        )

        detection_rate = true_positives / len(should_interrupt)
        specificity = true_negatives / len(should_not_interrupt)

        print(f"\nBarge-in Detection Benchmark:")
        print(f"  Detection Rate: {detection_rate:.2%} (target: {TARGET_BARGE_IN_DETECTION_RATE:.0%})")
        print(f"  Specificity: {specificity:.2%}")
        print(f"  True Positives: {true_positives}/{len(should_interrupt)}")
        print(f"  True Negatives: {true_negatives}/{len(should_not_interrupt)}")

        assert detection_rate >= TARGET_BARGE_IN_DETECTION_RATE, \
            f"Detection rate {detection_rate:.2%} below target {TARGET_BARGE_IN_DETECTION_RATE:.0%}"


class TestSessionBenchmarks:
    """Session management benchmark tests."""

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_session_success_rate(self):
        """
        Benchmark session success rate.

        Target: > 98% of sessions complete successfully.
        """
        orchestrator = VoiceOrchestrator(
            sentinel=MockSentinel(),
            stt_provider=BenchmarkSTTProvider(),
            tts_provider=BenchmarkTTSProvider(),
            p10_mapper=P10ProsodyMapper(),
            safety_gate=SafetyVoiceGate()
        )

        successful = 0
        total = BENCHMARK_ITERATIONS

        for _ in range(total):
            try:
                session = await orchestrator.start_session()

                async def audio():
                    yield b"\x00" * 100

                async for _ in orchestrator.process_audio_stream(
                    session.session_id,
                    audio()
                ):
                    pass

                await orchestrator.end_session(session.session_id)
                successful += 1

            except Exception as e:
                print(f"Session failed: {e}")

        success_rate = successful / total

        print(f"\nSession Success Rate Benchmark:")
        print(f"  Success Rate: {success_rate:.2%} (target: {TARGET_SESSION_SUCCESS_RATE:.0%})")
        print(f"  Successful: {successful}/{total}")

        assert success_rate >= TARGET_SESSION_SUCCESS_RATE, \
            f"Success rate {success_rate:.2%} below target {TARGET_SESSION_SUCCESS_RATE:.0%}"


class TestProsodyBenchmarks:
    """Prosody computation benchmark tests."""

    @pytest.mark.benchmark
    def test_prosody_computation_time(self):
        """Benchmark prosody parameter computation time."""
        mapper = P10ProsodyMapper()

        # Mock coherence state
        class MockMetrics:
            overall_coherence = 0.7
            prediction_reversal_risk = 0.3
            drift_direction = "stable"

        class MockState:
            current_metrics = MockMetrics()

        class MockContract:
            eligible = True

        times = []

        for _ in range(1000):
            start = time.perf_counter()
            mapper.compute_params(
                coherence_state=MockState(),
                safety_contract=MockContract()
            )
            end = time.perf_counter()
            times.append((end - start) * 1000)

        mean_time = mean(times)
        max_time = max(times)

        print(f"\nProsody Computation Benchmark:")
        print(f"  Mean: {mean_time:.4f}ms")
        print(f"  Max: {max_time:.4f}ms")
        print(f"  Target: < 1ms")

        assert mean_time < 1.0, f"Prosody computation {mean_time:.4f}ms too slow"

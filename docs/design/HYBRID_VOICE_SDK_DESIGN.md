# Hybrid Voice SDK Design Document

## Status: DESIGN SPECIFICATION

**Author**: Claude (Architecture Design)
**Date**: February 2026
**Version**: 1.0.0

---

## Executive Summary

This document specifies a **Hybrid Voice SDK** architecture that combines a custom voice orchestration layer with pluggable third-party STT/TTS providers (Cartesia, Deepgram, ElevenLabs, etc.). The hybrid approach leverages the existing Sentinel agentic framework as the cognitive backbone while enabling voice-aware features that generic SDKs like Cartesia Line cannot provide.

### Key Insight

```
Cartesia Line Approach:
  Audio → [Line SDK] → LLM (black box) → [Line SDK] → Audio
         (generic orchestration, no cognitive awareness)

Hybrid Voice SDK Approach:
  Audio → [Provider STT] → [Voice Orchestrator] → [Sentinel Framework] →
        → [P10 Prosody Mapper] → [Provider TTS] → Audio
         (cognitive-aware orchestration, coherence-driven voice modulation)
```

### Design Principles

1. **Provider-Agnostic**: Works with Cartesia, Deepgram, ElevenLabs, PlayHT, or self-hosted models
2. **Cognitive Integration**: Voice behavior driven by Sentinel's coherence state and safety contracts
3. **P10 Prosody Control**: Acoustic parameters directly influence TTS output characteristics
4. **Safety-First Voice**: Fail-closed gates can pause, confirm, or escalate during voice interactions
5. **Minimal Footprint**: Thin orchestration layer, not a full voice stack rebuild
6. **Streaming-Native**: Real-time bidirectional audio with low latency

---

## Why Hybrid Over Own SDK

This section analyzes why the hybrid approach is superior to building a completely custom Voice SDK from scratch.

### The Build-vs-Buy Spectrum

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        VOICE SDK BUILD SPECTRUM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FULL BUILD                    HYBRID                         FULL BUY      │
│  (Own SDK)                   (Recommended)                   (Line SDK)     │
│      │                           │                               │          │
│      ▼                           ▼                               ▼          │
│  ┌────────┐                ┌────────────┐                  ┌──────────┐    │
│  │ Custom │                │ Custom     │                  │ Cartesia │    │
│  │ STT    │                │ Orchestr.  │                  │ Line SDK │    │
│  │ Custom │                │ Provider   │                  │ (as-is)  │    │
│  │ TTS    │                │ Adapters   │                  │          │    │
│  │ Custom │                │ P10 Mapper │                  │          │    │
│  │ WebRTC │                │ Safety     │                  │          │    │
│  │ VAD    │                │ Integration│                  │          │    │
│  │ Echo   │                └────────────┘                  └──────────┘    │
│  │ Cancel │                      │                               │          │
│  └────────┘                      │                               │          │
│      │                           │                               │          │
│  Dev: 12-18 months          Dev: 2-3 months               Dev: 1 week      │
│  Risk: Very High            Risk: Low                     Risk: Low        │
│  Diff: Maximum              Diff: High                    Diff: None       │
│  Lock-in: None              Lock-in: Low                  Lock-in: High    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Comparison Matrix

| Factor | Own SDK | Hybrid (Recommended) | Line SDK |
|--------|---------|----------------------|----------|
| **Development Time** | 12-18 months | 2-3 months | 1 week |
| **Development Cost** | $500K-$1M+ | $50K-$100K | $5K-$10K |
| **Maintenance Burden** | Very High | Low | None |
| **Provider Lock-in** | None | Low | High (Cartesia) |
| **Differentiation** | Maximum | High | None |
| **P10 Acoustic Integration** | Full | Full | None |
| **Coherence-Driven Voice** | Full | Full | None |
| **Safety Contract Voice Gates** | Full | Full | Limited |
| **Latency Control** | Full | Provider-dependent | Optimized |
| **Edge Case Handling** | Must build | Partial (provider) | Handled |
| **Voice Activity Detection** | Must build | Provider handles | Handled |
| **Echo Cancellation** | Must build | Provider handles | Handled |
| **Barge-in Handling** | Must build | Custom + Provider | Handled |
| **Multi-language Support** | Must build | Provider handles | 40+ languages |

### Why NOT Build a Full Custom SDK

#### 1. Voice Infrastructure is Extremely Complex

Building production-grade voice requires solving:

```
┌─────────────────────────────────────────────────────────────────┐
│                   VOICE STACK COMPLEXITY                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Audio Input Layer                                               │
│  ├── Microphone access & permissions                            │
│  ├── Sample rate conversion (8kHz, 16kHz, 44.1kHz, 48kHz)      │
│  ├── Noise suppression algorithms                               │
│  ├── Automatic gain control                                     │
│  ├── Echo cancellation (acoustic + line)                        │
│  └── Voice Activity Detection (VAD)                             │
│                                                                  │
│  Speech-to-Text Layer                                           │
│  ├── Acoustic model training/fine-tuning                        │
│  ├── Language model integration                                 │
│  ├── Streaming vs batch transcription                           │
│  ├── Word-level timestamps                                      │
│  ├── Speaker diarization                                        │
│  ├── Noise-robust recognition                                   │
│  └── Multi-language support                                     │
│                                                                  │
│  Text-to-Speech Layer                                           │
│  ├── Neural vocoder training                                    │
│  ├── Prosody modeling                                           │
│  ├── Voice cloning capabilities                                 │
│  ├── Emotion/style control                                      │
│  ├── SSML support                                               │
│  ├── Streaming synthesis                                        │
│  └── Latency optimization (<100ms TTFA)                         │
│                                                                  │
│  Real-time Communication Layer                                  │
│  ├── WebSocket management                                       │
│  ├── WebRTC (for peer-to-peer)                                 │
│  ├── Jitter buffer management                                   │
│  ├── Packet loss concealment                                    │
│  ├── Codec selection (Opus, PCM, etc.)                         │
│  └── Network adaptation                                         │
│                                                                  │
│  Conversation Management Layer                                  │
│  ├── Turn-taking detection                                      │
│  ├── Barge-in handling                                          │
│  ├── Interruption recovery                                      │
│  ├── Silence timeout management                                 │
│  └── Context preservation across interruptions                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Cartesia, Deepgram, and ElevenLabs have spent years and millions of dollars solving these problems.** Rebuilding this from scratch is not a competitive advantage for Symbolu.

#### 2. Your Differentiation is the Brain, Not the Ears/Mouth

Sentinel's unique value proposition:

| Component | Unique to Symbolu? | Voice Provider Has? |
|-----------|-------------------|---------------------|
| Goal Decomposition | Yes | No |
| Memory Store | Yes | No |
| Reflective Loop | Yes | No |
| Coherence Engine | Yes | No |
| Safety Contract | Yes | No |
| Confidence Gate | Yes | No |
| P10 Acoustic Params | Yes | No |
| MCP Gateway | Yes | No |
| STT Model | No | Yes (best-in-class) |
| TTS Model | No | Yes (best-in-class) |
| VAD/Echo Cancel | No | Yes (optimized) |

**Insight**: Building STT/TTS doesn't make Symbolu more differentiated. Integrating Sentinel's cognitive features into voice DOES.

#### 3. Time-to-Market Reality

```
Own SDK Timeline:
  Month 1-3:   Research, architecture, team hiring
  Month 4-6:   Basic STT/TTS integration (low quality)
  Month 7-9:   Quality improvements, latency optimization
  Month 10-12: Edge cases, barge-in, VAD tuning
  Month 13-15: Multi-language, production hardening
  Month 16-18: Beta testing, bug fixes

  Total: 18 months before first production deployment

Hybrid SDK Timeline:
  Week 1-2:    Architecture, provider selection
  Week 3-4:    Provider adapters (Cartesia, Deepgram)
  Week 5-6:    Voice orchestration layer
  Week 7-8:    Sentinel integration
  Week 9-10:   P10 prosody mapping
  Week 11-12:  Testing, edge cases

  Total: 3 months to production-ready voice agents
```

#### 4. Cost Analysis

| Cost Category | Own SDK | Hybrid SDK |
|--------------|---------|------------|
| Engineering (12-18 months) | $600K-$900K | $100K-$150K |
| ML/Audio Specialists | $200K-$400K | $0 |
| Infrastructure (training) | $100K-$200K | $0 |
| Provider API Costs | $0 | $10K-$50K/year |
| Maintenance (annual) | $200K-$300K | $30K-$50K |
| **Year 1 Total** | **$1.1M-$1.8M** | **$140K-$250K** |
| **Year 2 Total** | **$200K-$300K** | **$40K-$100K** |

**The hybrid approach is 5-10x more cost-effective.**

#### 5. Risk Mitigation

| Risk | Own SDK Impact | Hybrid SDK Impact |
|------|---------------|-------------------|
| STT quality issues | Must fix internally | Switch providers |
| TTS latency problems | Must optimize | Switch providers |
| New language needed | 3-6 months work | Provider may have it |
| Provider price increase | N/A | Switch providers |
| Team member leaves | Critical knowledge loss | Minimal impact |
| Competitor ships faster | Significant disadvantage | Competitive parity |

### Why Hybrid is Better Than Line SDK Alone

While Line SDK offers fast deployment, it treats the LLM as a black box and cannot leverage Sentinel's unique capabilities:

#### 1. Coherence-Driven Voice Modulation

```python
# Line SDK: Static voice regardless of conversation state
agent = LlmAgent(
    model="...",
    config=LlmConfig(system_prompt="...")  # No coherence awareness
)

# Hybrid SDK: Voice adapts to cognitive state
class HybridVoiceOrchestrator:
    def get_tts_params(self, coherence_state: CoherenceState) -> TTSParams:
        metrics = coherence_state.current_metrics

        if metrics.overall_coherence < 0.5:
            # Low coherence: slower, more deliberate speech
            return TTSParams(
                speed=0.85,
                stability=0.9,  # More consistent
                pause_multiplier=1.3  # Longer pauses
            )
        elif metrics.prediction_reversal_risk > 0.6:
            # High uncertainty: hedging tone
            return TTSParams(
                speed=0.9,
                pitch_variance=0.7,  # Less confident intonation
            )
        else:
            # Normal operation
            return TTSParams(speed=1.0, stability=0.7)
```

#### 2. Safety Contract Voice Gates

```python
# Line SDK: No safety-aware voice flow control
# (tools execute or don't, no voice-level intervention)

# Hybrid SDK: Safety contracts control voice behavior
class SafetyAwareVoiceFlow:
    def process_response(self, response: str, contract: SafetyContract):
        if not contract.eligible:
            # Insert verbal confirmation before proceeding
            confirmation = self.synthesize(
                "I want to make sure I understand correctly. "
                f"You're asking me to {self.summarize_action(response)}. "
                "Is that right?"
            )
            return VoiceResponse(
                audio=confirmation,
                awaiting_confirmation=True,
                blocked_action=response
            )
        return VoiceResponse(audio=self.synthesize(response))
```

#### 3. P10 Acoustic Parameter Integration

```python
# Line SDK: No access to acoustic parameterization
# Voice characteristics are fixed or manually configured

# Hybrid SDK: P10 regime directly influences TTS
class P10ProsodyMapper:
    """Maps P10 acoustic regimes to TTS provider parameters."""

    REGIME_MAPPINGS = {
        AcousticRegime.NEUTRAL: {
            "speed": 1.0,
            "pitch_shift": 0,
            "energy": 0.5,
            "pause_factor": 1.0
        },
        AcousticRegime.SOFT: {
            "speed": 0.9,
            "pitch_shift": -2,  # Slightly lower
            "energy": 0.3,
            "pause_factor": 1.2  # More pauses
        },
        AcousticRegime.FLAT: {
            "speed": 1.0,
            "pitch_shift": 0,
            "energy": 0.4,
            "pitch_variance": 0.3  # Monotone
        },
        AcousticRegime.RESTRAINED: {
            "speed": 0.85,
            "pitch_shift": -1,
            "energy": 0.35,
            "pause_factor": 1.4
        }
    }

    def map_to_provider(
        self,
        regime: AcousticRegime,
        provider: str
    ) -> Dict[str, Any]:
        base = self.REGIME_MAPPINGS[regime]

        if provider == "cartesia":
            return self._to_cartesia_params(base)
        elif provider == "elevenlabs":
            return self._to_elevenlabs_params(base)
        elif provider == "deepgram":
            return self._to_deepgram_params(base)
```

#### 4. Provider Flexibility

```python
# Line SDK: Locked to Cartesia
# If Cartesia has issues or price increases, you're stuck

# Hybrid SDK: Swap providers without changing application code
class ProviderRegistry:
    providers = {
        "cartesia": CartesiaAdapter(),
        "deepgram": DeepgramAdapter(),
        "elevenlabs": ElevenLabsAdapter(),
        "playht": PlayHTAdapter(),
        "local_whisper": LocalWhisperAdapter(),
    }

    def get_stt(self, preference: str = "cartesia") -> STTProvider:
        return self.providers[preference].stt

    def get_tts(self, preference: str = "cartesia") -> TTSProvider:
        return self.providers[preference].tts
```

### Summary: Why Hybrid Wins

| Criterion | Own SDK | Hybrid | Line SDK |
|-----------|---------|--------|----------|
| Time to market | Slow | Fast | Fastest |
| Development cost | Very High | Low | Minimal |
| Differentiation | Maximum | High | None |
| Maintenance burden | Very High | Low | None |
| Provider lock-in | None | None | High |
| Sentinel integration | Full | Full | Partial |
| P10 acoustic control | Full | Full | None |
| Voice safety gates | Full | Full | None |
| Coherence-driven voice | Full | Full | None |
| **Overall Score** | 5/10 | 9/10 | 6/10 |

**The hybrid approach delivers 90% of the differentiation value at 10% of the cost and time.**

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HYBRID VOICE SDK                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    1. AUDIO INPUT LAYER                              │   │
│  │                                                                      │   │
│  │   User Audio Stream                                                  │   │
│  │         │                                                            │   │
│  │         ▼                                                            │   │
│  │   ┌──────────────────────────────────────────────────────────┐     │   │
│  │   │              PROVIDER STT ADAPTER                         │     │   │
│  │   │   ┌──────────┐  ┌──────────┐  ┌──────────┐              │     │   │
│  │   │   │ Cartesia │  │ Deepgram │  │  Whisper │   ...        │     │   │
│  │   │   │   Ink    │  │  Nova-2  │  │  (local) │              │     │   │
│  │   │   └──────────┘  └──────────┘  └──────────┘              │     │   │
│  │   └──────────────────────────────────────────────────────────┘     │   │
│  │         │                                                            │   │
│  │         ▼                                                            │   │
│  │   Transcribed Text + Metadata (timestamps, confidence)               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    2. VOICE ORCHESTRATION LAYER                      │   │
│  │                                                                      │   │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │   │   Barge-in   │  │    Turn      │  │   Context    │             │   │
│  │   │   Handler    │  │   Manager    │  │   Builder    │             │   │
│  │   └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  │                                                                      │   │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │   │  Interrupt   │  │   Silence    │  │   Session    │             │   │
│  │   │   Recovery   │  │   Timeout    │  │   State      │             │   │
│  │   └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  │                              │                                       │   │
│  │                    Orchestrated Request                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    3. SENTINEL FRAMEWORK LAYER                       │   │
│  │                                                                      │   │
│  │   ┌─────────────────────────────────────────────────────────────┐   │   │
│  │   │                  AgenticLLMWrapper                           │   │   │
│  │   │                                                              │   │   │
│  │   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │   │   │
│  │   │  │   Goal   │ │  Memory  │ │Reflective│ │Coherence │      │   │   │
│  │   │  │  Decomp  │ │  Store   │ │   Loop   │ │  Engine  │      │   │   │
│  │   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │   │   │
│  │   │                                                              │   │   │
│  │   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │   │   │
│  │   │  │  Safety  │ │Confidence│ │  Local   │ │   MCP    │      │   │   │
│  │   │  │ Contract │ │   Gate   │ │  Critic  │ │ Gateway  │      │   │   │
│  │   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │   │   │
│  │   │                                                              │   │   │
│  │   └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │              Response + CoherenceState + SafetyContract              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    4. VOICE OUTPUT LAYER                             │   │
│  │                                                                      │   │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │   │    Safety    │  │     P10      │  │   Response   │             │   │
│  │   │  Voice Gate  │  │   Prosody    │  │   Chunker    │             │   │
│  │   │              │  │   Mapper     │  │              │             │   │
│  │   └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  │         │                   │                   │                    │   │
│  │         └───────────────────┼───────────────────┘                    │   │
│  │                             ▼                                        │   │
│  │   ┌──────────────────────────────────────────────────────────┐     │   │
│  │   │              PROVIDER TTS ADAPTER                         │     │   │
│  │   │   ┌──────────┐  ┌──────────┐  ┌──────────┐              │     │   │
│  │   │   │ Cartesia │  │ElevenLabs│  │  PlayHT  │   ...        │     │   │
│  │   │   │  Sonic   │  │  Turbo   │  │   2.0    │              │     │   │
│  │   │   └──────────┘  └──────────┘  └──────────┘              │     │   │
│  │   └──────────────────────────────────────────────────────────┘     │   │
│  │                             │                                        │   │
│  │                             ▼                                        │   │
│  │                    Synthesized Audio Stream                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VOICE AGENT DATA FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User speaks                                                                 │
│       │                                                                      │
│       ▼                                                                      │
│  ┌────────────┐                                                             │
│  │ Audio      │  PCM/Opus stream, 16kHz                                     │
│  │ Capture    │                                                             │
│  └────────────┘                                                             │
│       │                                                                      │
│       ▼                                                                      │
│  ┌────────────┐                                                             │
│  │ Provider   │  Cartesia Ink / Deepgram Nova-2                             │
│  │ STT        │  Streaming transcription                                    │
│  └────────────┘                                                             │
│       │                                                                      │
│       │  TranscriptEvent {                                                   │
│       │    text: "What's the weather in Tokyo?",                            │
│       │    is_final: true,                                                  │
│       │    confidence: 0.95,                                                │
│       │    words: [{word: "What's", start: 0.0, end: 0.3}, ...]            │
│       │  }                                                                   │
│       ▼                                                                      │
│  ┌────────────┐                                                             │
│  │ Voice      │  Barge-in detection, turn management                        │
│  │ Orchestr.  │  Context assembly from session                              │
│  └────────────┘                                                             │
│       │                                                                      │
│       │  VoiceRequest {                                                      │
│       │    text: "What's the weather in Tokyo?",                            │
│       │    session_id: "abc123",                                            │
│       │    turn_id: 5,                                                      │
│       │    interrupted_response: null,                                      │
│       │    audio_metadata: {...}                                            │
│       │  }                                                                   │
│       ▼                                                                      │
│  ┌────────────┐                                                             │
│  │ Sentinel   │  Full agentic pipeline:                                     │
│  │ Framework  │  Goal → Memory → Generate → Cohere → Safety                 │
│  └────────────┘                                                             │
│       │                                                                      │
│       │  AgentResponse {                                                     │
│       │    response: "The weather in Tokyo is currently 15°C...",           │
│       │    coherence_state: CoherenceState {...},                           │
│       │    safety_contract: SafetyContract {eligible: true, ...},           │
│       │    goal_state: GoalState {...},                                     │
│       │    tools_executed: ["weather_api"],                                 │
│       │  }                                                                   │
│       ▼                                                                      │
│  ┌────────────┐                                                             │
│  │ Safety     │  Check contract, insert confirmations if needed             │
│  │ Voice Gate │                                                             │
│  └────────────┘                                                             │
│       │                                                                      │
│       ▼                                                                      │
│  ┌────────────┐                                                             │
│  │ P10        │  Map coherence state → acoustic parameters                  │
│  │ Prosody    │  Map to provider-specific TTS settings                      │
│  └────────────┘                                                             │
│       │                                                                      │
│       │  TTSRequest {                                                        │
│       │    text: "The weather in Tokyo is currently 15°C...",               │
│       │    voice_id: "en-US-neural-01",                                     │
│       │    speed: 1.0,                                                      │
│       │    stability: 0.7,                                                  │
│       │    pitch_shift: 0,                                                  │
│       │    prosody_markers: [...]                                           │
│       │  }                                                                   │
│       ▼                                                                      │
│  ┌────────────┐                                                             │
│  │ Provider   │  Cartesia Sonic / ElevenLabs Turbo                          │
│  │ TTS        │  Streaming synthesis, <100ms TTFA                           │
│  └────────────┘                                                             │
│       │                                                                      │
│       │  Audio stream (PCM/Opus)                                            │
│       ▼                                                                      │
│  User hears response                                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### Component 1: Provider Abstraction Layer

**Purpose**: Unified interface for multiple STT/TTS providers.

#### STT Provider Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional, List
from enum import Enum

class TranscriptType(Enum):
    PARTIAL = "partial"
    FINAL = "final"

@dataclass
class WordTimestamp:
    """Word-level timing information."""
    word: str
    start_time: float  # seconds
    end_time: float
    confidence: float

@dataclass
class TranscriptEvent:
    """Streaming transcription event."""
    text: str
    transcript_type: TranscriptType
    confidence: float
    words: List[WordTimestamp]
    language: Optional[str] = None
    is_endpoint: bool = False  # End of utterance detected

class STTProvider(ABC):
    """Abstract STT provider interface."""

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 16000,
        language: Optional[str] = None
    ) -> AsyncIterator[TranscriptEvent]:
        """Stream audio and yield transcription events."""
        pass

    @abstractmethod
    async def transcribe_file(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None
    ) -> TranscriptEvent:
        """Transcribe complete audio file."""
        pass

    @property
    @abstractmethod
    def supported_languages(self) -> List[str]:
        """List of supported language codes."""
        pass

    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether provider supports streaming transcription."""
        pass
```

#### TTS Provider Interface

```python
@dataclass
class TTSParams:
    """TTS synthesis parameters."""
    voice_id: str
    speed: float = 1.0  # 0.5 to 2.0
    pitch_shift: float = 0.0  # semitones, -12 to +12
    stability: float = 0.7  # 0.0 to 1.0 (consistency)
    similarity_boost: float = 0.75  # Voice similarity
    style: float = 0.0  # Expressiveness

    # Provider-specific extensions
    extra_params: dict = None

    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}

@dataclass
class AudioChunk:
    """Streaming audio output chunk."""
    audio: bytes
    sample_rate: int
    format: str  # "pcm", "opus", "mp3"
    duration_ms: float
    is_final: bool = False

class TTSProvider(ABC):
    """Abstract TTS provider interface."""

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        params: TTSParams
    ) -> AsyncIterator[AudioChunk]:
        """Stream synthesized audio chunks."""
        pass

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        params: TTSParams
    ) -> bytes:
        """Synthesize complete audio."""
        pass

    @abstractmethod
    def get_voices(self) -> List[dict]:
        """List available voices."""
        pass

    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether provider supports streaming synthesis."""
        pass

    @property
    @abstractmethod
    def average_latency_ms(self) -> float:
        """Typical time-to-first-audio in milliseconds."""
        pass
```

#### Cartesia Adapter Implementation

```python
from cartesia import Cartesia

class CartesiaAdapter:
    """Adapter for Cartesia Sonic (TTS) and Ink (STT)."""

    def __init__(self, api_key: str):
        self.client = Cartesia(api_key=api_key)
        self._stt = CartesiaSTT(self.client)
        self._tts = CartesiaTTS(self.client)

    @property
    def stt(self) -> STTProvider:
        return self._stt

    @property
    def tts(self) -> TTSProvider:
        return self._tts

class CartesiaSTT(STTProvider):
    """Cartesia Ink STT implementation."""

    def __init__(self, client: Cartesia):
        self.client = client

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 16000,
        language: Optional[str] = None
    ) -> AsyncIterator[TranscriptEvent]:
        """Stream transcription using Cartesia Ink."""
        async with self.client.stt.stream(
            sample_rate=sample_rate,
            language=language or "en"
        ) as stream:
            async for audio_chunk in audio_stream:
                await stream.send(audio_chunk)

                async for event in stream.receive():
                    yield TranscriptEvent(
                        text=event.text,
                        transcript_type=(
                            TranscriptType.FINAL if event.is_final
                            else TranscriptType.PARTIAL
                        ),
                        confidence=event.confidence,
                        words=[
                            WordTimestamp(
                                word=w.word,
                                start_time=w.start,
                                end_time=w.end,
                                confidence=w.confidence
                            )
                            for w in event.words
                        ],
                        language=event.language,
                        is_endpoint=event.is_endpoint
                    )

    async def transcribe_file(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None
    ) -> TranscriptEvent:
        """Batch transcription."""
        result = await self.client.stt.transcribe(
            audio=audio_bytes,
            sample_rate=sample_rate,
            language=language or "en"
        )
        return TranscriptEvent(
            text=result.text,
            transcript_type=TranscriptType.FINAL,
            confidence=result.confidence,
            words=[
                WordTimestamp(
                    word=w.word,
                    start_time=w.start,
                    end_time=w.end,
                    confidence=w.confidence
                )
                for w in result.words
            ],
            language=result.language,
            is_endpoint=True
        )

    @property
    def supported_languages(self) -> List[str]:
        return ["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh",
                "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa"]

    @property
    def supports_streaming(self) -> bool:
        return True

class CartesiaTTS(TTSProvider):
    """Cartesia Sonic TTS implementation."""

    def __init__(self, client: Cartesia):
        self.client = client

    async def synthesize_stream(
        self,
        text: str,
        params: TTSParams
    ) -> AsyncIterator[AudioChunk]:
        """Stream synthesis using Cartesia Sonic."""
        async for chunk in self.client.tts.stream(
            text=text,
            voice_id=params.voice_id,
            speed=params.speed,
            output_format="pcm_16000"
        ):
            yield AudioChunk(
                audio=chunk.audio,
                sample_rate=16000,
                format="pcm",
                duration_ms=len(chunk.audio) / 32,  # 16-bit, 16kHz
                is_final=chunk.is_final
            )

    async def synthesize(
        self,
        text: str,
        params: TTSParams
    ) -> bytes:
        """Full synthesis."""
        result = await self.client.tts.synthesize(
            text=text,
            voice_id=params.voice_id,
            speed=params.speed,
            output_format="pcm_16000"
        )
        return result.audio

    def get_voices(self) -> List[dict]:
        return self.client.voices.list()

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    def average_latency_ms(self) -> float:
        return 90.0  # Sonic's typical TTFA
```

#### Deepgram Adapter Implementation

```python
from deepgram import Deepgram

class DeepgramAdapter:
    """Adapter for Deepgram Nova-2 (STT) and Aura (TTS)."""

    def __init__(self, api_key: str):
        self.client = Deepgram(api_key)
        self._stt = DeepgramSTT(self.client)
        self._tts = DeepgramTTS(self.client)

    @property
    def stt(self) -> STTProvider:
        return self._stt

    @property
    def tts(self) -> TTSProvider:
        return self._tts

class DeepgramSTT(STTProvider):
    """Deepgram Nova-2 STT implementation."""

    def __init__(self, client):
        self.client = client

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 16000,
        language: Optional[str] = None
    ) -> AsyncIterator[TranscriptEvent]:
        """Stream transcription using Deepgram Nova-2."""
        connection = await self.client.transcription.live({
            "model": "nova-2",
            "language": language or "en",
            "sample_rate": sample_rate,
            "encoding": "linear16",
            "punctuate": True,
            "interim_results": True,
            "endpointing": 300,  # ms of silence to detect end
        })

        async def send_audio():
            async for chunk in audio_stream:
                await connection.send(chunk)

        # Start sending in background
        send_task = asyncio.create_task(send_audio())

        try:
            async for result in connection:
                if result.channel and result.channel.alternatives:
                    alt = result.channel.alternatives[0]
                    yield TranscriptEvent(
                        text=alt.transcript,
                        transcript_type=(
                            TranscriptType.FINAL if result.is_final
                            else TranscriptType.PARTIAL
                        ),
                        confidence=alt.confidence,
                        words=[
                            WordTimestamp(
                                word=w.word,
                                start_time=w.start,
                                end_time=w.end,
                                confidence=w.confidence
                            )
                            for w in alt.words
                        ],
                        language=result.channel.detected_language,
                        is_endpoint=result.speech_final
                    )
        finally:
            send_task.cancel()
            await connection.finish()

    @property
    def supported_languages(self) -> List[str]:
        return ["en", "es", "fr", "de", "it", "pt", "nl", "ja", "ko",
                "zh", "hi", "ru", "pl", "tr", "uk", "vi", "id"]

    @property
    def supports_streaming(self) -> bool:
        return True
```

#### Provider Registry

```python
class ProviderRegistry:
    """
    Registry for voice providers with automatic failover.

    Usage:
        registry = ProviderRegistry()
        registry.register("cartesia", CartesiaAdapter(api_key="..."))
        registry.register("deepgram", DeepgramAdapter(api_key="..."))

        # Get preferred provider with fallback
        stt = registry.get_stt("cartesia", fallback=["deepgram"])
    """

    def __init__(self):
        self._providers: Dict[str, Any] = {}
        self._health: Dict[str, bool] = {}

    def register(self, name: str, adapter) -> None:
        """Register a provider adapter."""
        self._providers[name] = adapter
        self._health[name] = True

    def get_stt(
        self,
        preferred: str,
        fallback: List[str] = None
    ) -> STTProvider:
        """Get STT provider with fallback support."""
        providers_to_try = [preferred] + (fallback or [])

        for name in providers_to_try:
            if name in self._providers and self._health.get(name, False):
                return self._providers[name].stt

        raise RuntimeError(f"No healthy STT provider available")

    def get_tts(
        self,
        preferred: str,
        fallback: List[str] = None
    ) -> TTSProvider:
        """Get TTS provider with fallback support."""
        providers_to_try = [preferred] + (fallback or [])

        for name in providers_to_try:
            if name in self._providers and self._health.get(name, False):
                return self._providers[name].tts

        raise RuntimeError(f"No healthy TTS provider available")

    def mark_unhealthy(self, name: str) -> None:
        """Mark a provider as unhealthy (for failover)."""
        self._health[name] = False

    def mark_healthy(self, name: str) -> None:
        """Mark a provider as healthy."""
        self._health[name] = True

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all providers."""
        results = {}
        for name, adapter in self._providers.items():
            try:
                # Simple ping test
                await adapter.tts.synthesize("test", TTSParams(voice_id="default"))
                results[name] = True
                self._health[name] = True
            except Exception:
                results[name] = False
                self._health[name] = False
        return results
```

---

### Component 2: Voice Orchestration Layer

**Purpose**: Manage voice-specific concerns like barge-in, turn-taking, and interruption recovery.

#### Data Models

```python
@dataclass
class VoiceSession:
    """Voice session state."""
    session_id: str
    created_at: datetime

    # Current state
    is_speaking: bool = False
    is_listening: bool = True
    current_response_id: Optional[str] = None

    # Interruption handling
    interrupted_responses: List[str] = field(default_factory=list)
    pending_continuation: Optional[str] = None

    # Turn tracking
    turn_count: int = 0
    last_user_speech_end: Optional[datetime] = None
    last_agent_speech_end: Optional[datetime] = None

    # Audio metadata
    user_audio_duration_ms: float = 0.0
    agent_audio_duration_ms: float = 0.0

@dataclass
class VoiceRequest:
    """Request to voice agent."""
    text: str
    session_id: str
    turn_id: int

    # Context
    interrupted_response: Optional[str] = None
    continuation_context: Optional[str] = None

    # Audio metadata
    audio_duration_ms: float = 0.0
    transcript_confidence: float = 1.0
    detected_language: Optional[str] = None

@dataclass
class VoiceResponse:
    """Response from voice agent."""
    response_id: str
    text: str

    # From Sentinel
    coherence_state: "CoherenceState"
    safety_contract: "SafetyContract"
    goal_state: Optional["GoalState"] = None

    # Voice-specific
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None

    # TTS parameters (computed from P10 + coherence)
    tts_params: Optional[TTSParams] = None
```

#### Voice Orchestrator

```python
class VoiceOrchestrator:
    """
    Orchestrates voice interactions with Sentinel framework.

    Responsibilities:
    - Barge-in detection and handling
    - Turn management
    - Interruption recovery
    - Context preservation across interruptions
    - Safety-aware response flow
    """

    def __init__(
        self,
        sentinel: AgenticLLMWrapper,
        stt_provider: STTProvider,
        tts_provider: TTSProvider,
        p10_mapper: "P10ProsodyMapper",
        safety_voice_gate: "SafetyVoiceGate"
    ):
        self.sentinel = sentinel
        self.stt = stt_provider
        self.tts = tts_provider
        self.p10_mapper = p10_mapper
        self.safety_gate = safety_voice_gate

        self._sessions: Dict[str, VoiceSession] = {}
        self._response_tasks: Dict[str, asyncio.Task] = {}

    async def start_session(self, session_id: Optional[str] = None) -> VoiceSession:
        """Initialize a new voice session."""
        session_id = session_id or str(uuid.uuid4())

        # Initialize Sentinel session
        self.sentinel.new_session(session_id)

        session = VoiceSession(
            session_id=session_id,
            created_at=datetime.utcnow()
        )
        self._sessions[session_id] = session

        return session

    async def process_audio_stream(
        self,
        session_id: str,
        audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[AudioChunk]:
        """
        Process incoming audio and yield response audio.

        This is the main entry point for voice interaction.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Transcribe incoming audio
        transcript_buffer = []
        final_transcript = None

        async for event in self.stt.transcribe_stream(audio_stream):
            # Check for barge-in
            if session.is_speaking and event.transcript_type == TranscriptType.PARTIAL:
                if len(event.text.split()) >= 2:  # More than just noise
                    await self._handle_barge_in(session)

            if event.transcript_type == TranscriptType.FINAL:
                transcript_buffer.append(event.text)

            if event.is_endpoint:
                final_transcript = " ".join(transcript_buffer)
                transcript_buffer = []

                # Process the complete utterance
                async for audio_chunk in self._process_utterance(
                    session,
                    final_transcript,
                    event.confidence
                ):
                    yield audio_chunk

    async def _handle_barge_in(self, session: VoiceSession) -> None:
        """Handle user interruption during agent speech."""
        if session.current_response_id:
            # Cancel current TTS
            if session.current_response_id in self._response_tasks:
                self._response_tasks[session.current_response_id].cancel()

            # Save interrupted response for potential continuation
            session.interrupted_responses.append(session.current_response_id)
            session.is_speaking = False

    async def _process_utterance(
        self,
        session: VoiceSession,
        text: str,
        confidence: float
    ) -> AsyncIterator[AudioChunk]:
        """Process a complete user utterance and generate response."""
        session.turn_count += 1
        session.last_user_speech_end = datetime.utcnow()

        # Build voice request
        request = VoiceRequest(
            text=text,
            session_id=session.session_id,
            turn_id=session.turn_count,
            interrupted_response=(
                session.interrupted_responses[-1]
                if session.interrupted_responses else None
            ),
            transcript_confidence=confidence
        )

        # Process through Sentinel
        result = self.sentinel.run(text)

        # Build voice response
        response = VoiceResponse(
            response_id=str(uuid.uuid4()),
            text=result["response"],
            coherence_state=self.sentinel.coherence_state,
            safety_contract=self.sentinel.safety_evaluator.evaluate(
                self.sentinel.coherence_state,
                self.sentinel.goal_state
            ),
            goal_state=self.sentinel.goal_state
        )

        # Apply safety voice gate
        gated_response = await self.safety_gate.process(response)

        # Compute TTS parameters from P10 + coherence
        tts_params = self.p10_mapper.compute_params(
            coherence_state=response.coherence_state,
            safety_contract=response.safety_contract
        )

        # Synthesize and stream response
        session.is_speaking = True
        session.current_response_id = response.response_id

        try:
            async for chunk in self.tts.synthesize_stream(
                gated_response.text,
                tts_params
            ):
                yield chunk
        finally:
            session.is_speaking = False
            session.current_response_id = None
            session.last_agent_speech_end = datetime.utcnow()
```

#### Barge-In Handler

```python
class BargeInHandler:
    """
    Handles user interruptions during agent speech.

    Strategies:
    1. IMMEDIATE: Stop immediately on any speech detection
    2. CONFIRMED: Wait for significant speech before stopping
    3. IGNORE: Complete current response (for critical info)
    """

    class Strategy(Enum):
        IMMEDIATE = "immediate"
        CONFIRMED = "confirmed"
        IGNORE = "ignore"

    def __init__(
        self,
        default_strategy: Strategy = Strategy.CONFIRMED,
        confirmation_word_threshold: int = 2,
        confirmation_duration_ms: float = 500
    ):
        self.default_strategy = default_strategy
        self.word_threshold = confirmation_word_threshold
        self.duration_threshold = confirmation_duration_ms

    def should_interrupt(
        self,
        transcript_event: TranscriptEvent,
        current_strategy: Optional[Strategy] = None,
        response_priority: str = "normal"
    ) -> bool:
        """Determine if current speech should be interrupted."""
        strategy = current_strategy or self.default_strategy

        # Critical responses cannot be interrupted
        if response_priority == "critical":
            return False

        if strategy == self.Strategy.IGNORE:
            return False

        if strategy == self.Strategy.IMMEDIATE:
            return len(transcript_event.text.strip()) > 0

        # CONFIRMED strategy
        word_count = len(transcript_event.text.split())
        if word_count >= self.word_threshold:
            return True

        # Check duration if word timestamps available
        if transcript_event.words:
            duration = (
                transcript_event.words[-1].end_time -
                transcript_event.words[0].start_time
            ) * 1000
            if duration >= self.duration_threshold:
                return True

        return False

    def get_continuation_context(
        self,
        interrupted_text: str,
        spoken_portion: str
    ) -> str:
        """
        Generate context for continuing after interruption.

        This allows the agent to acknowledge what was said and
        either continue or adapt based on the interruption.
        """
        remaining = interrupted_text[len(spoken_portion):].strip()

        if not remaining:
            return ""

        return f"[Interrupted. Remaining unsaid: '{remaining[:100]}...']"
```

---

### Component 3: P10 Prosody Mapper

**Purpose**: Map Sentinel's coherence state and P10 acoustic parameters to TTS provider settings.

```python
from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import (
    AcousticRegime,
    AcousticParameters
)

class P10ProsodyMapper:
    """
    Maps P10 acoustic parameters and coherence state to TTS settings.

    This is where Symbolu's cognitive state influences voice output:
    - Low coherence → slower, more deliberate speech
    - High uncertainty → hedging tone, softer delivery
    - High confidence → normal pace, assertive tone
    - Safety concerns → explicit verbal markers
    """

    # Base mappings from P10 regimes to TTS parameters
    REGIME_TO_TTS = {
        AcousticRegime.NEUTRAL: {
            "speed": 1.0,
            "stability": 0.7,
            "pitch_shift": 0,
            "style": 0.5
        },
        AcousticRegime.SOFT: {
            "speed": 0.9,
            "stability": 0.8,
            "pitch_shift": -1,
            "style": 0.3
        },
        AcousticRegime.FLAT: {
            "speed": 1.0,
            "stability": 0.9,
            "pitch_shift": 0,
            "style": 0.1  # Low expressiveness
        },
        AcousticRegime.RESTRAINED: {
            "speed": 0.85,
            "stability": 0.85,
            "pitch_shift": -1,
            "style": 0.2
        }
    }

    # Coherence-based modulations
    COHERENCE_MODULATIONS = {
        "low_coherence": {  # overall_coherence < 0.5
            "speed_modifier": 0.85,
            "stability_modifier": 1.1,
            "pause_multiplier": 1.3
        },
        "high_uncertainty": {  # prediction_reversal_risk > 0.6
            "speed_modifier": 0.9,
            "pitch_variance_reduction": 0.3,
            "style_modifier": 0.7
        },
        "degrading_coherence": {  # drift_direction == "degrading"
            "speed_modifier": 0.9,
            "stability_modifier": 1.05
        }
    }

    def __init__(self, default_voice_id: str = "en-US-neural-01"):
        self.default_voice_id = default_voice_id

    def compute_params(
        self,
        coherence_state: "CoherenceState",
        safety_contract: "SafetyContract",
        p10_regime: AcousticRegime = AcousticRegime.NEUTRAL,
        voice_id: Optional[str] = None
    ) -> TTSParams:
        """
        Compute TTS parameters from cognitive state.

        Priority:
        1. Safety contract concerns (highest)
        2. Coherence state modulations
        3. P10 regime base settings
        """
        # Start with P10 regime base
        base = self.REGIME_TO_TTS.get(p10_regime, self.REGIME_TO_TTS[AcousticRegime.NEUTRAL]).copy()

        metrics = coherence_state.current_metrics

        # Apply coherence-based modulations
        if metrics.overall_coherence < 0.5:
            mod = self.COHERENCE_MODULATIONS["low_coherence"]
            base["speed"] *= mod["speed_modifier"]
            base["stability"] = min(1.0, base["stability"] * mod["stability_modifier"])

        if metrics.prediction_reversal_risk > 0.6:
            mod = self.COHERENCE_MODULATIONS["high_uncertainty"]
            base["speed"] *= mod["speed_modifier"]
            base["style"] *= mod["style_modifier"]

        if metrics.drift_direction == "degrading":
            mod = self.COHERENCE_MODULATIONS["degrading_coherence"]
            base["speed"] *= mod["speed_modifier"]
            base["stability"] = min(1.0, base["stability"] * mod["stability_modifier"])

        # Safety contract influences
        if not safety_contract.eligible:
            # More cautious delivery when safety is concerned
            base["speed"] *= 0.9
            base["stability"] = min(1.0, base["stability"] * 1.1)

        return TTSParams(
            voice_id=voice_id or self.default_voice_id,
            speed=max(0.5, min(2.0, base["speed"])),
            stability=max(0.0, min(1.0, base["stability"])),
            pitch_shift=base.get("pitch_shift", 0),
            style=base.get("style", 0.5)
        )

    def compute_ssml_markers(
        self,
        text: str,
        coherence_state: "CoherenceState"
    ) -> str:
        """
        Add SSML prosody markers based on coherence state.

        For providers that support SSML.
        """
        metrics = coherence_state.current_metrics

        # Add pauses after uncertainty markers
        if metrics.prediction_reversal_risk > 0.5:
            # Add slight pause before uncertain statements
            uncertainty_words = ["perhaps", "maybe", "possibly", "might", "could"]
            for word in uncertainty_words:
                text = text.replace(
                    f" {word} ",
                    f' <break time="200ms"/> {word} '
                )

        # Slower pace for complex explanations when coherence is low
        if metrics.overall_coherence < 0.6:
            text = f'<prosody rate="90%">{text}</prosody>'

        return text
```

---

### Component 4: Safety Voice Gate

**Purpose**: Apply safety contract decisions to voice output with verbal confirmations.

```python
class SafetyVoiceGate:
    """
    Applies safety contracts to voice responses.

    When safety contract is not eligible:
    1. Insert verbal confirmation requests
    2. Add safety disclaimers
    3. Escalate to human if needed
    """

    CONFIRMATION_TEMPLATES = {
        "action_confirmation": (
            "Before I proceed, I want to make sure I understand correctly. "
            "You're asking me to {action_summary}. Is that right?"
        ),
        "high_risk_warning": (
            "I want to flag that this action {risk_description}. "
            "Would you like me to continue?"
        ),
        "escalation_notice": (
            "This request involves {concern}. "
            "I'd recommend speaking with a human specialist about this."
        )
    }

    def __init__(self):
        self.pending_confirmations: Dict[str, dict] = {}

    async def process(
        self,
        response: VoiceResponse
    ) -> VoiceResponse:
        """
        Process response through safety gate.

        May modify response to include confirmations.
        """
        contract = response.safety_contract

        if contract.eligible:
            # No safety concerns, pass through
            return response

        # Determine appropriate intervention
        if self._requires_escalation(contract):
            return self._create_escalation_response(response)

        if self._requires_confirmation(contract):
            return self._create_confirmation_response(response)

        # Add safety disclaimer but proceed
        return self._add_safety_disclaimer(response)

    def _requires_escalation(self, contract: "SafetyContract") -> bool:
        """Check if response requires human escalation."""
        # Multiple preconditions violated
        if len(contract.violated_preconditions) >= 3:
            return True

        # Very low coherence
        if contract.internal_consistency < 0.4:
            return True

        return False

    def _requires_confirmation(self, contract: "SafetyContract") -> bool:
        """Check if response requires user confirmation."""
        # Any single precondition violation typically needs confirmation
        return len(contract.violated_preconditions) > 0

    def _create_confirmation_response(
        self,
        original: VoiceResponse
    ) -> VoiceResponse:
        """Create response that requests confirmation."""
        # Summarize what the agent was about to do
        action_summary = self._summarize_action(original.goal_state)

        confirmation_text = self.CONFIRMATION_TEMPLATES["action_confirmation"].format(
            action_summary=action_summary
        )

        return VoiceResponse(
            response_id=original.response_id,
            text=confirmation_text,
            coherence_state=original.coherence_state,
            safety_contract=original.safety_contract,
            goal_state=original.goal_state,
            requires_confirmation=True,
            confirmation_prompt=confirmation_text,
            tts_params=original.tts_params
        )

    def _create_escalation_response(
        self,
        original: VoiceResponse
    ) -> VoiceResponse:
        """Create response that escalates to human."""
        concern = self._identify_concern(original.safety_contract)

        escalation_text = self.CONFIRMATION_TEMPLATES["escalation_notice"].format(
            concern=concern
        )

        return VoiceResponse(
            response_id=original.response_id,
            text=escalation_text,
            coherence_state=original.coherence_state,
            safety_contract=original.safety_contract,
            goal_state=original.goal_state,
            requires_confirmation=False,
            tts_params=original.tts_params
        )

    def _add_safety_disclaimer(
        self,
        original: VoiceResponse
    ) -> VoiceResponse:
        """Add safety disclaimer to response."""
        disclaimer = "Please note: "

        if original.safety_contract.prediction_reversal_risk > 0.5:
            disclaimer += "I'm not entirely certain about this. "

        modified_text = disclaimer + original.text

        return VoiceResponse(
            response_id=original.response_id,
            text=modified_text,
            coherence_state=original.coherence_state,
            safety_contract=original.safety_contract,
            goal_state=original.goal_state,
            tts_params=original.tts_params
        )

    def _summarize_action(self, goal_state: Optional["GoalState"]) -> str:
        """Summarize the intended action for confirmation."""
        if not goal_state:
            return "perform this action"

        if goal_state.actions:
            return goal_state.actions[0].description

        return goal_state.purpose[:100]

    def _identify_concern(self, contract: "SafetyContract") -> str:
        """Identify the main safety concern."""
        if contract.blocking_reasons:
            return contract.blocking_reasons[0]
        return "potential safety considerations"
```

---

### Component 5: Voice Agent Application

**Purpose**: Complete voice agent application integrating all components.

```python
class VoiceAgentApp:
    """
    Complete voice agent application.

    Integrates:
    - Provider registry (multi-provider support)
    - Voice orchestrator
    - Sentinel framework
    - P10 prosody mapping
    - Safety voice gates
    - WebSocket transport
    """

    def __init__(
        self,
        sentinel_config: dict,
        provider_configs: Dict[str, dict],
        default_stt_provider: str = "cartesia",
        default_tts_provider: str = "cartesia",
        default_voice_id: str = "en-US-neural-01"
    ):
        # Initialize provider registry
        self.providers = ProviderRegistry()
        for name, config in provider_configs.items():
            adapter = self._create_adapter(name, config)
            self.providers.register(name, adapter)

        # Initialize Sentinel
        self.sentinel = self._create_sentinel(sentinel_config)

        # Initialize components
        self.p10_mapper = P10ProsodyMapper(default_voice_id)
        self.safety_gate = SafetyVoiceGate()

        # Initialize orchestrator
        self.orchestrator = VoiceOrchestrator(
            sentinel=self.sentinel,
            stt_provider=self.providers.get_stt(default_stt_provider),
            tts_provider=self.providers.get_tts(default_tts_provider),
            p10_mapper=self.p10_mapper,
            safety_voice_gate=self.safety_gate
        )

        # Active sessions
        self._sessions: Dict[str, VoiceSession] = {}

    def _create_adapter(self, name: str, config: dict):
        """Create provider adapter from config."""
        if name == "cartesia":
            return CartesiaAdapter(api_key=config["api_key"])
        elif name == "deepgram":
            return DeepgramAdapter(api_key=config["api_key"])
        elif name == "elevenlabs":
            return ElevenLabsAdapter(api_key=config["api_key"])
        else:
            raise ValueError(f"Unknown provider: {name}")

    def _create_sentinel(self, config: dict) -> AgenticLLMWrapper:
        """Create Sentinel framework from config."""
        # Import from existing framework
        from symbolu.agentic_framework.agent import AgenticLLMWrapper
        from symbolu.llm.providers import get_llm_client

        llm_client = get_llm_client(
            provider=config.get("llm_provider", "anthropic"),
            model=config.get("llm_model", "claude-sonnet-4-20250514")
        )

        return AgenticLLMWrapper(
            llm_client=llm_client,
            max_revisions=config.get("max_revisions", 2),
            quality_threshold=config.get("quality_threshold", 0.8)
        )

    async def handle_websocket(
        self,
        websocket,
        session_id: Optional[str] = None
    ):
        """
        Handle WebSocket connection for voice agent.

        Protocol:
        - Client sends: audio chunks (binary)
        - Server sends: audio chunks (binary) + events (JSON)
        """
        # Create session
        session = await self.orchestrator.start_session(session_id)
        self._sessions[session.session_id] = session

        # Send session info
        await websocket.send_json({
            "type": "session_started",
            "session_id": session.session_id
        })

        try:
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

        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })

        finally:
            del self._sessions[session.session_id]

    def create_fastapi_app(self) -> "FastAPI":
        """Create FastAPI application with WebSocket endpoint."""
        from fastapi import FastAPI, WebSocket

        app = FastAPI(title="Symbolu Voice Agent")

        @app.websocket("/voice/{session_id}")
        async def voice_endpoint(websocket: WebSocket, session_id: str = None):
            await websocket.accept()
            await self.handle_websocket(websocket, session_id)

        @app.get("/health")
        async def health():
            provider_health = await self.providers.health_check()
            return {
                "status": "healthy" if all(provider_health.values()) else "degraded",
                "providers": provider_health
            }

        @app.get("/voices")
        async def list_voices():
            return self.providers.get_tts("cartesia").get_voices()

        return app

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the voice agent server."""
        import uvicorn
        app = self.create_fastapi_app()
        uvicorn.run(app, host=host, port=port)
```

---

## Usage Examples

### Basic Usage

```python
from symbolu.voice import VoiceAgentApp

# Configure providers
provider_configs = {
    "cartesia": {"api_key": os.getenv("CARTESIA_API_KEY")},
    "deepgram": {"api_key": os.getenv("DEEPGRAM_API_KEY")},
}

# Configure Sentinel
sentinel_config = {
    "llm_provider": "anthropic",
    "llm_model": "claude-sonnet-4-20250514",
    "max_revisions": 2,
    "quality_threshold": 0.8
}

# Create and run voice agent
app = VoiceAgentApp(
    sentinel_config=sentinel_config,
    provider_configs=provider_configs,
    default_stt_provider="cartesia",
    default_tts_provider="cartesia",
    default_voice_id="sonic-english-us"
)

app.run(host="0.0.0.0", port=8000)
```

### Custom Coherence-Driven Voice

```python
# Extend P10 mapper with custom rules
class CustomP10Mapper(P10ProsodyMapper):

    def compute_params(self, coherence_state, safety_contract, **kwargs):
        params = super().compute_params(coherence_state, safety_contract, **kwargs)

        # Custom rule: if agent just used a tool, speak more confidently
        if hasattr(coherence_state, 'last_tool_success') and coherence_state.last_tool_success:
            params.speed *= 1.05
            params.style = min(1.0, params.style + 0.1)

        return params
```

### Multi-Provider Failover

```python
# Configure with fallback providers
app = VoiceAgentApp(
    sentinel_config=sentinel_config,
    provider_configs={
        "cartesia": {"api_key": "..."},
        "deepgram": {"api_key": "..."},
        "elevenlabs": {"api_key": "..."},
    }
)

# STT with failover: try Cartesia first, then Deepgram
stt = app.providers.get_stt("cartesia", fallback=["deepgram"])

# TTS with failover: try Cartesia first, then ElevenLabs
tts = app.providers.get_tts("cartesia", fallback=["elevenlabs"])
```

---

## Testing Strategy

### Unit Tests

1. **Provider Adapter Tests**
   - Test each provider's STT streaming
   - Test each provider's TTS synthesis
   - Test parameter mapping accuracy

2. **Voice Orchestrator Tests**
   - Test barge-in detection
   - Test turn management
   - Test interruption recovery

3. **P10 Prosody Mapper Tests**
   - Test regime-to-TTS mapping
   - Test coherence modulation application
   - Test SSML marker generation

4. **Safety Voice Gate Tests**
   - Test confirmation generation
   - Test escalation detection
   - Test disclaimer addition

### Integration Tests

1. **End-to-end voice flow**
   - Audio in → transcription → Sentinel → TTS → audio out

2. **Multi-turn conversation**
   - Context preservation across turns
   - Coherence tracking across conversation

3. **Barge-in scenarios**
   - Interrupt and recover
   - Context continuity after interruption

4. **Provider failover**
   - Primary fails → fallback works

### Load Tests

1. **Concurrent sessions**
   - 10, 50, 100 simultaneous voice sessions

2. **Latency benchmarks**
   - End-to-end latency < 500ms target
   - TTFA (time-to-first-audio) < 200ms target

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PRODUCTION DEPLOYMENT                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                           ┌─────────────────┐                               │
│                           │   Load Balancer │                               │
│                           │   (WebSocket)   │                               │
│                           └────────┬────────┘                               │
│                                    │                                         │
│              ┌─────────────────────┼─────────────────────┐                  │
│              │                     │                     │                  │
│              ▼                     ▼                     ▼                  │
│       ┌─────────────┐       ┌─────────────┐       ┌─────────────┐          │
│       │ Voice Agent │       │ Voice Agent │       │ Voice Agent │          │
│       │  Instance 1 │       │  Instance 2 │       │  Instance N │          │
│       └──────┬──────┘       └──────┬──────┘       └──────┬──────┘          │
│              │                     │                     │                  │
│              └─────────────────────┼─────────────────────┘                  │
│                                    │                                         │
│                    ┌───────────────┼───────────────┐                        │
│                    │               │               │                        │
│                    ▼               ▼               ▼                        │
│             ┌──────────┐    ┌──────────┐    ┌──────────┐                   │
│             │ Cartesia │    │ Deepgram │    │ElevenLabs│                   │
│             │   API    │    │   API    │    │   API    │                   │
│             └──────────┘    └──────────┘    └──────────┘                   │
│                                                                              │
│                    ┌───────────────┴───────────────┐                        │
│                    │         Shared Services        │                        │
│                    │  ┌─────────┐  ┌─────────────┐ │                        │
│                    │  │  Redis  │  │  PostgreSQL │ │                        │
│                    │  │(sessions)│  │  (memory)   │ │                        │
│                    │  └─────────┘  └─────────────┘ │                        │
│                    └────────────────────────────────┘                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Metrics and Monitoring

### Key Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| End-to-end latency | Audio in to audio out | < 500ms |
| Time-to-first-audio | Response start latency | < 200ms |
| Transcription accuracy | STT word error rate | < 5% |
| Barge-in detection rate | Successful interrupts | > 95% |
| Provider availability | Uptime per provider | > 99.9% |
| Session success rate | Conversations completed | > 98% |

### Monitoring Dashboard

Track:
- Active voice sessions
- Provider health status
- Latency percentiles (p50, p95, p99)
- Coherence score distribution
- Safety gate intervention rate
- Barge-in frequency

---

## Migration Path

### Phase 1: Foundation (Week 1-2)
- [ ] Create provider abstraction interfaces
- [ ] Implement Cartesia adapter
- [ ] Basic voice orchestrator

### Phase 2: Integration (Week 3-4)
- [ ] Integrate with Sentinel framework
- [ ] Implement P10 prosody mapper
- [ ] Basic safety voice gate

### Phase 3: Hardening (Week 5-6)
- [ ] Barge-in handling
- [ ] Interruption recovery
- [ ] Provider failover

### Phase 4: Production (Week 7-8)
- [ ] WebSocket server
- [ ] Load testing
- [ ] Deployment automation

### Phase 5: Enhancement (Week 9-12)
- [ ] Additional providers (Deepgram, ElevenLabs)
- [ ] Advanced coherence-driven prosody
- [ ] Multi-language support

---

## References

- Symbolu Agentic Framework: `symbolu/agentic_framework/`
- P10 Acoustic Pipeline: `symbolu/mechanical/pipeline/p10_acoustic/`
- Cartesia Line SDK: https://github.com/cartesia-ai/line
- Cartesia Sonic/Ink: https://cartesia.ai/sonic
- Deepgram Nova-2: https://deepgram.com/
- ElevenLabs: https://elevenlabs.io/

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Feb 2026 | Initial design specification |

---

**END OF DESIGN DOCUMENT**

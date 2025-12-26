"""
Audio Encoder for Robotics
===========================

Microphone -> 12D encoding.

Layer Mapping:
- Sound presence -> O1_POTENTIAL (activation)
- Frequency content -> O4_STRUCTURE (patterns)
- Voice detection -> O5_COGNITION (perception)
- Command recognition -> O7_REASONING (intent)
- Alarm sounds -> O12_ABSOLVING (safety)
"""

from typing import Tuple, Optional
import numpy as np

from symbolu_robotics.encoders.base_encoder import BaseEncoder, EncoderConfig
from symbolu_robotics.core.types import SensorFrame, Layer12D


class AudioEncoder(BaseEncoder):
    """Audio to 12D layer encoding."""

    def __init__(
        self,
        config: Optional[EncoderConfig] = None,
        sample_rate: int = 16000,
        energy_threshold: float = 0.01,
        voice_freq_range: Tuple[float, float] = (85, 3000),
        alarm_freq_range: Tuple[float, float] = (1000, 4000)
    ):
        super().__init__(config)
        self.sample_rate = sample_rate
        self.energy_threshold = energy_threshold
        self.voice_freq_range = voice_freq_range
        self.alarm_freq_range = alarm_freq_range

    @property
    def encoder_name(self) -> str:
        return "audio"

    @property
    def required_sensors(self) -> Tuple[str, ...]:
        return ("audio_buffer",)

    def _encode_internal(self, sensor_frame: SensorFrame) -> Layer12D:
        layer_values = np.zeros(12, dtype=np.float32)

        if sensor_frame.audio_buffer is None or len(sensor_frame.audio_buffer) == 0:
            return layer_values

        audio = sensor_frame.audio_buffer
        sample_rate = sensor_frame.audio_sample_rate or self.sample_rate

        # O1_POTENTIAL: Sound presence (energy)
        energy = np.mean(audio ** 2)
        if energy > self.energy_threshold:
            layer_values[0] = min(1.0, energy / (self.energy_threshold * 10))

        # Compute FFT for frequency analysis
        n = len(audio)
        if n < 256:
            return layer_values

        fft = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)

        # O4_STRUCTURE: Spectral centroid (frequency structure)
        if np.sum(fft) > 0:
            centroid = np.sum(freqs * fft) / np.sum(fft)
            layer_values[3] = min(1.0, centroid / 4000)  # Normalize by 4kHz

        # O5_COGNITION: Voice band energy
        voice_mask = (freqs >= self.voice_freq_range[0]) & (freqs <= self.voice_freq_range[1])
        voice_energy = np.sum(fft[voice_mask] ** 2)
        total_energy = np.sum(fft ** 2)
        if total_energy > 0:
            layer_values[4] = voice_energy / total_energy

        # O7_REASONING: Speech-like patterns (zero crossing rate)
        zero_crossings = np.sum(np.diff(np.sign(audio)) != 0)
        zcr = zero_crossings / len(audio)
        # Speech typically has ZCR between 0.02-0.08
        if 0.02 < zcr < 0.15:
            layer_values[6] = 1.0 - abs(zcr - 0.05) / 0.1

        # O12_ABSOLVING: Alarm detection (high-frequency bursts)
        alarm_mask = (freqs >= self.alarm_freq_range[0]) & (freqs <= self.alarm_freq_range[1])
        alarm_energy = np.sum(fft[alarm_mask] ** 2)
        if total_energy > 0:
            alarm_ratio = alarm_energy / total_energy
            if alarm_ratio > 0.3:  # Significant alarm-band content
                layer_values[11] = min(1.0, alarm_ratio * 2)

        return layer_values

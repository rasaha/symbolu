"""Tests for USE-6G configuration."""

import math
import pytest

from simulator.use_6g.core.config import (
    USE6GConfig,
    FrequencyConfig,
    FrequencyBand,
    AntennaConfig,
    ArrayTopology,
    TimingConfig,
    PowerConfig,
    AcceptanceThresholds,
)


class TestFrequencyConfig:
    """Tests for frequency band configuration."""

    def test_sub_thz_low_carrier(self):
        cfg = FrequencyConfig(band=FrequencyBand.SUB_THZ_LOW)
        assert cfg.carrier_freq_ghz == 140.0

    def test_mmwave_carrier(self):
        cfg = FrequencyConfig(band=FrequencyBand.FR2_MMWAVE)
        assert cfg.carrier_freq_ghz == 39.0

    def test_fr3_upper_carrier(self):
        cfg = FrequencyConfig(band=FrequencyBand.FR3_UPPER)
        assert cfg.carrier_freq_ghz == 15.0

    def test_sub_thz_high_carrier(self):
        cfg = FrequencyConfig(band=FrequencyBand.SUB_THZ_HIGH)
        assert cfg.carrier_freq_ghz == 500.0

    def test_wavelength_sub_thz(self):
        cfg = FrequencyConfig(band=FrequencyBand.SUB_THZ_LOW)
        # lambda = c/f = 299.79 / 140 = ~2.14 mm
        assert 2.0 < cfg.wavelength_mm < 2.3

    def test_wavelength_mmwave(self):
        cfg = FrequencyConfig(band=FrequencyBand.FR2_MMWAVE)
        # lambda = c/f = 299.79 / 39 = ~7.69 mm
        assert 7.0 < cfg.wavelength_mm < 8.0

    def test_wavelength_decreases_with_frequency(self):
        """Higher frequency should give shorter wavelength."""
        fr3 = FrequencyConfig(band=FrequencyBand.FR3_UPPER)
        mmw = FrequencyConfig(band=FrequencyBand.FR2_MMWAVE)
        sthz = FrequencyConfig(band=FrequencyBand.SUB_THZ_LOW)
        assert fr3.wavelength_mm > mmw.wavelength_mm > sthz.wavelength_mm

    def test_max_phase_error_positive(self):
        cfg = FrequencyConfig(band=FrequencyBand.SUB_THZ_LOW)
        assert cfg.max_phase_error_rad > 0

    def test_bandwidth_positive(self):
        for band in FrequencyBand:
            cfg = FrequencyConfig(band=band)
            assert cfg.bandwidth_ghz > 0


class TestAntennaConfig:
    """Tests for antenna array configuration."""

    def test_default_total_elements(self):
        cfg = AntennaConfig()
        # 8x8 x 2 panels = 128
        assert cfg.total_elements == 128

    def test_ula_total_elements(self):
        cfg = AntennaConfig(
            num_elements_x=16, num_elements_y=1,
            topology=ArrayTopology.ULA, num_panels=1,
        )
        assert cfg.total_elements == 16

    def test_elements_per_panel(self):
        cfg = AntennaConfig(num_elements_x=4, num_elements_y=4, num_panels=3)
        assert cfg.elements_per_panel == 16
        assert cfg.total_elements == 48

    def test_ula_elements_per_panel(self):
        cfg = AntennaConfig(
            num_elements_x=8, num_elements_y=1,
            topology=ArrayTopology.ULA, num_panels=2,
        )
        assert cfg.elements_per_panel == 8
        assert cfg.total_elements == 16


class TestTimingConfig:
    """Tests for timing configuration."""

    def test_default_precision(self):
        cfg = TimingConfig()
        assert cfg.timing_precision_ps == 100.0

    def test_coherence_threshold_range(self):
        cfg = TimingConfig()
        assert 0.0 < cfg.coherence_threshold <= 1.0

    def test_learning_rate_range(self):
        cfg = TimingConfig()
        assert 0.0 < cfg.sync_learning_rate < 1.0


class TestUSE6GConfig:
    """Tests for combined configuration."""

    def test_default_config_valid(self):
        cfg = USE6GConfig()
        assert cfg.antenna.total_elements == 128
        assert cfg.frequency.carrier_freq_ghz == 140.0
        assert cfg.timing.timing_precision_ps == 100.0
        assert cfg.power.max_power_w == 15.0

    def test_summary_contains_key_info(self):
        cfg = USE6GConfig()
        summary = cfg.summary()
        assert "140.0 GHz" in summary
        assert "128 elements" in summary
        assert "100.0ps" in summary

    def test_acceptance_thresholds_defaults(self):
        cfg = USE6GConfig()
        assert cfg.thresholds.min_global_coherence == 0.95
        assert cfg.thresholds.max_phase_error_deg == 5.0
        assert cfg.thresholds.min_beam_gain_db == 15.0

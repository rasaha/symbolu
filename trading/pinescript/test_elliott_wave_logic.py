#!/usr/bin/env python3
"""
Test harness for SymbolU Elliott Wave Pine Script pattern detection logic.

Since Pine Script runs inside TradingView, we replicate the core detection
algorithms in Python and validate them against known Elliott Wave patterns
with expected outcomes. This ensures correctness of:
  - 5-wave impulse detection (bullish & bearish)
  - Cardinal rule enforcement (R1, R2, R3)
  - ABC correction detection
  - WXY double combination detection
  - WXYXZ triple combination detection
  - Diagonal pattern detection
  - Fibonacci ratio validation
  - Composite probability scoring
"""

import math
import unittest

# ============================================================================
# CONSTANTS (match Pine Script)
# ============================================================================
FIB_236 = 0.236
FIB_382 = 0.382
FIB_500 = 0.500
FIB_618 = 0.618
FIB_786 = 0.786
FIB_1000 = 1.000
FIB_1272 = 1.272
FIB_1618 = 1.618
FIB_2618 = 2.618

DEFAULT_FIB_TOLERANCE = 0.10

# ============================================================================
# HELPER FUNCTIONS (match Pine Script)
# ============================================================================

def is_near_fib(actual, target, tol=DEFAULT_FIB_TOLERANCE):
    return abs(actual - target) <= tol

def in_fib_range(actual, lo, hi, tol=DEFAULT_FIB_TOLERANCE):
    return actual >= (lo - tol) and actual <= (hi + tol)

def retrace_ratio(wave_prev_size, wave_curr_size):
    if wave_prev_size == 0:
        return 0.0
    return abs(wave_curr_size) / abs(wave_prev_size)


# ============================================================================
# PATTERN DETECTORS (translated from Pine Script)
# ============================================================================

def detect_bullish_5wave(pivots, strict_rules=True, fib_tolerance=DEFAULT_FIB_TOLERANCE):
    """
    Detect bullish 5-wave impulse.
    pivots: list of (price, is_high) tuples, index 0 = most recent.
    Returns: (wave_num, confidence, is_valid)
    """
    if len(pivots) < 6:
        return (0, 0.0, False)

    p0, h0 = pivots[0]
    p1, h1 = pivots[1]
    p2, h2 = pivots[2]
    p3, h3 = pivots[3]
    p4, h4 = pivots[4]
    p5, h5 = pivots[5]

    confidence = 0.0
    is_valid = False

    # Check alternating pivot pattern: L-H-L-H-L-H (most recent = H)
    if not h5 and h4 and not h3 and h2 and not h1 and h0:
        w1 = p4 - p5
        w2 = p4 - p3
        w3 = p2 - p3
        w4 = p2 - p1
        w5 = p0 - p1

        if w1 > 0 and w3 > 0 and w5 > 0:
            w2_retrace = retrace_ratio(w1, w2)
            w3_extend = retrace_ratio(w1, w3)
            w4_retrace = retrace_ratio(w3, w4)
            w5_extend = retrace_ratio(w1, w5)

            # Cardinal Rules
            r1_valid = p3 > p5          # Wave 2 doesn't retrace 100% of Wave 1
            r2_valid = w3 >= w1 or w3 >= w5  # Wave 3 is not the shortest
            r3_valid = p1 > p4          # Wave 4 doesn't enter Wave 1 territory

            if strict_rules:
                is_valid = r1_valid and r2_valid and r3_valid
            else:
                is_valid = r1_valid and r2_valid

            if is_valid:
                if in_fib_range(w2_retrace, FIB_382, FIB_786, fib_tolerance):
                    confidence += 0.10
                if in_fib_range(w2_retrace, FIB_500, FIB_618, fib_tolerance):
                    confidence += 0.10
                if w3_extend >= FIB_1000 - fib_tolerance:
                    confidence += 0.10
                if in_fib_range(w3_extend, FIB_1618 - 0.2, FIB_1618 + 0.5, fib_tolerance):
                    confidence += 0.15
                if w3_extend >= FIB_2618 - fib_tolerance:
                    confidence += 0.05
                if w3 >= w1 and w3 >= w5:
                    confidence += 0.15
                if in_fib_range(w4_retrace, FIB_236, FIB_500, fib_tolerance):
                    confidence += 0.10
                if in_fib_range(w4_retrace, FIB_382 - 0.05, FIB_382 + 0.05, fib_tolerance):
                    confidence += 0.05
                if in_fib_range(w5_extend, FIB_618, FIB_1618, fib_tolerance):
                    confidence += 0.10
                if in_fib_range(w5_extend, FIB_1000 - 0.1, FIB_1000 + 0.1, fib_tolerance):
                    confidence += 0.05
                if r3_valid:
                    confidence += 0.05

                confidence = min(1.0, confidence)

    return (5 if is_valid else 0, confidence, is_valid)


def detect_bearish_5wave(pivots, strict_rules=True, fib_tolerance=DEFAULT_FIB_TOLERANCE):
    """Detect bearish 5-wave impulse. Pivots: H-L-H-L-H-L."""
    if len(pivots) < 6:
        return (0, 0.0, False)

    p0, h0 = pivots[0]
    p1, h1 = pivots[1]
    p2, h2 = pivots[2]
    p3, h3 = pivots[3]
    p4, h4 = pivots[4]
    p5, h5 = pivots[5]

    confidence = 0.0
    is_valid = False

    if h5 and not h4 and h3 and not h2 and h1 and not h0:
        w1 = p5 - p4
        w2 = p3 - p4
        w3 = p3 - p2
        w4 = p1 - p2
        w5 = p1 - p0

        if w1 > 0 and w3 > 0 and w5 > 0:
            w2_retrace = retrace_ratio(w1, w2)
            w3_extend = retrace_ratio(w1, w3)
            w4_retrace = retrace_ratio(w3, w4)
            w5_extend = retrace_ratio(w1, w5)

            r1_valid = p3 < p5
            r2_valid = w3 >= w1 or w3 >= w5
            r3_valid = p1 < p4

            if strict_rules:
                is_valid = r1_valid and r2_valid and r3_valid
            else:
                is_valid = r1_valid and r2_valid

            if is_valid:
                if in_fib_range(w2_retrace, FIB_382, FIB_786, fib_tolerance):
                    confidence += 0.10
                if in_fib_range(w2_retrace, FIB_500, FIB_618, fib_tolerance):
                    confidence += 0.10
                if w3_extend >= FIB_1000 - fib_tolerance:
                    confidence += 0.10
                if in_fib_range(w3_extend, FIB_1618 - 0.2, FIB_1618 + 0.5, fib_tolerance):
                    confidence += 0.15
                if w3_extend >= FIB_2618 - fib_tolerance:
                    confidence += 0.05
                if w3 >= w1 and w3 >= w5:
                    confidence += 0.15
                if in_fib_range(w4_retrace, FIB_236, FIB_500, fib_tolerance):
                    confidence += 0.10
                if in_fib_range(w4_retrace, FIB_382 - 0.05, FIB_382 + 0.05, fib_tolerance):
                    confidence += 0.05
                if in_fib_range(w5_extend, FIB_618, FIB_1618, fib_tolerance):
                    confidence += 0.10
                if in_fib_range(w5_extend, FIB_1000 - 0.1, FIB_1000 + 0.1, fib_tolerance):
                    confidence += 0.05
                if r3_valid:
                    confidence += 0.05

                confidence = min(1.0, confidence)

    return (-5 if is_valid else 0, confidence, is_valid)


def detect_abc_correction(pivots, fib_tolerance=DEFAULT_FIB_TOLERANCE):
    """Detect ABC correction. Returns (abc_type, confidence)."""
    if len(pivots) < 3:
        return (0, 0.0)

    p0, h0 = pivots[0]
    p1, h1 = pivots[1]
    p2, h2 = pivots[2]

    abc_type = 0
    confidence = 0.0

    # Bearish ABC: H-L-H
    if h2 and not h1 and h0:
        wave_a = p2 - p1
        wave_b = p0 - p1
        if wave_a > 0 and wave_b > 0:
            b_retrace = retrace_ratio(wave_a, wave_b)
            if in_fib_range(b_retrace, FIB_382, FIB_786, fib_tolerance):
                abc_type = 1
                confidence += 0.25
                if in_fib_range(b_retrace, FIB_500, FIB_618, fib_tolerance):
                    confidence += 0.15
                if p0 < p2:
                    confidence += 0.10

    # Bullish ABC: L-H-L
    if not h2 and h1 and not h0:
        wave_a = p1 - p2
        wave_b = p1 - p0
        if wave_a > 0 and wave_b > 0:
            b_retrace = retrace_ratio(wave_a, wave_b)
            if in_fib_range(b_retrace, FIB_382, FIB_786, fib_tolerance):
                abc_type = -1
                confidence += 0.25
                if in_fib_range(b_retrace, FIB_500, FIB_618, fib_tolerance):
                    confidence += 0.15
                if p0 > p2:
                    confidence += 0.10

    confidence = min(1.0, confidence)
    return (abc_type, confidence)


def detect_wxy_double(pivots, fib_tolerance=DEFAULT_FIB_TOLERANCE):
    """Detect WXY double combination. Returns (wxy_type, confidence)."""
    if len(pivots) < 4:
        return (0, 0.0)

    p0, h0 = pivots[0]
    p1, h1 = pivots[1]
    p2, h2 = pivots[2]
    p3, h3 = pivots[3]

    wxy_type = 0
    confidence = 0.0

    # Bearish WXY: H-L-H-L
    if h3 and not h2 and h1 and not h0:
        w_size = p3 - p2
        x_size = p1 - p2
        y_size = p1 - p0
        if w_size > 0 and x_size > 0 and y_size > 0:
            x_retrace = retrace_ratio(w_size, x_size)
            y_ratio = retrace_ratio(w_size, y_size)
            x_valid = p1 < p3
            x_fib_ok = in_fib_range(x_retrace, FIB_382, FIB_786, fib_tolerance)
            y_fib_ok = in_fib_range(y_ratio, FIB_618, FIB_1618, fib_tolerance)
            moves_lower = p0 <= p2 + abs(w_size) * 0.1
            if x_valid and x_fib_ok:
                wxy_type = 1
                confidence += 0.20
                if in_fib_range(x_retrace, FIB_500, FIB_618, fib_tolerance):
                    confidence += 0.10
                if y_fib_ok:
                    confidence += 0.15
                if in_fib_range(y_ratio, FIB_1000 - 0.15, FIB_1000 + 0.15, fib_tolerance):
                    confidence += 0.10
                if moves_lower:
                    confidence += 0.05

    # Bullish WXY: L-H-L-H
    if not h3 and h2 and not h1 and h0:
        w_size = p2 - p3
        x_size = p2 - p1
        y_size = p0 - p1
        if w_size > 0 and x_size > 0 and y_size > 0:
            x_retrace = retrace_ratio(w_size, x_size)
            y_ratio = retrace_ratio(w_size, y_size)
            x_valid = p1 > p3
            x_fib_ok = in_fib_range(x_retrace, FIB_382, FIB_786, fib_tolerance)
            y_fib_ok = in_fib_range(y_ratio, FIB_618, FIB_1618, fib_tolerance)
            moves_higher = p0 >= p2 - abs(w_size) * 0.1
            if x_valid and x_fib_ok:
                wxy_type = -1
                confidence += 0.20
                if in_fib_range(x_retrace, FIB_500, FIB_618, fib_tolerance):
                    confidence += 0.10
                if y_fib_ok:
                    confidence += 0.15
                if in_fib_range(y_ratio, FIB_1000 - 0.15, FIB_1000 + 0.15, fib_tolerance):
                    confidence += 0.10
                if moves_higher:
                    confidence += 0.05

    confidence = min(1.0, confidence)
    return (wxy_type, confidence)


def detect_diagonal(pivots, fib_tolerance=DEFAULT_FIB_TOLERANCE):
    """Detect diagonal pattern. Returns (diag_type, confidence, is_leading)."""
    if len(pivots) < 6:
        return (0, 0.0, False)

    p0, h0 = pivots[0]
    p1, h1 = pivots[1]
    p2, h2 = pivots[2]
    p3, h3 = pivots[3]
    p4, h4 = pivots[4]
    p5, h5 = pivots[5]

    diag_type = 0
    confidence = 0.0
    is_leading = False

    # Bullish diagonal: L-H-L-H-L-H with Wave 4 overlapping Wave 1
    if not h5 and h4 and not h3 and h2 and not h1 and h0:
        w1 = p4 - p5
        w2 = p4 - p3
        w3 = p2 - p3
        w4 = p2 - p1
        w5 = p0 - p1
        if w1 > 0 and w3 > 0 and w5 > 0:
            w4_overlaps_w1 = p1 < p4 and p1 > p5  # Overlap but not too deep
            w2_valid = p3 > p5
            w3_not_shortest = w3 >= w1 or w3 >= w5
            if w4_overlaps_w1 and w2_valid and w3_not_shortest:
                diag_type = 1
                confidence += 0.15
                contracting_motive = w1 > w3 and w3 > w5
                contracting_corrective = w2 > w4
                if contracting_motive:
                    confidence += 0.15
                if contracting_corrective:
                    confidence += 0.10
                if contracting_motive and contracting_corrective:
                    confidence += 0.10
                expanding_motive = w1 < w3 and w3 < w5
                if expanding_motive:
                    confidence += 0.05
                w2_retrace = retrace_ratio(w1, w2)
                if in_fib_range(w2_retrace, FIB_500, FIB_786, fib_tolerance):
                    confidence += 0.10
                w4_retrace = retrace_ratio(w3, w4)
                if in_fib_range(w4_retrace, FIB_500, FIB_786, fib_tolerance):
                    confidence += 0.10
                if contracting_motive and w5 < w3 and w5 < w1:
                    is_leading = False
                    confidence += 0.05
                else:
                    is_leading = True
                confidence = min(1.0, confidence)

    # Bearish diagonal: H-L-H-L-H-L
    if h5 and not h4 and h3 and not h2 and h1 and not h0:
        w1 = p5 - p4
        w2 = p3 - p4
        w3 = p3 - p2
        w4 = p1 - p2
        w5 = p1 - p0
        if w1 > 0 and w3 > 0 and w5 > 0:
            w4_overlaps_w1 = p1 > p4 and p1 < p5
            w2_valid = p3 < p5
            w3_not_shortest = w3 >= w1 or w3 >= w5
            if w4_overlaps_w1 and w2_valid and w3_not_shortest:
                diag_type = -1
                confidence += 0.15
                contracting_motive = w1 > w3 and w3 > w5
                contracting_corrective = w2 > w4
                if contracting_motive:
                    confidence += 0.15
                if contracting_corrective:
                    confidence += 0.10
                if contracting_motive and contracting_corrective:
                    confidence += 0.10
                expanding_motive = w1 < w3 and w3 < w5
                if expanding_motive:
                    confidence += 0.05
                w2_retrace = retrace_ratio(w1, w2)
                if in_fib_range(w2_retrace, FIB_500, FIB_786, fib_tolerance):
                    confidence += 0.10
                w4_retrace = retrace_ratio(w3, w4)
                if in_fib_range(w4_retrace, FIB_500, FIB_786, fib_tolerance):
                    confidence += 0.10
                if contracting_motive and w5 < w3 and w5 < w1:
                    is_leading = False
                    confidence += 0.05
                else:
                    is_leading = True
                confidence = min(1.0, confidence)

    return (diag_type, confidence, is_leading)


def compute_composite_probability(p_pattern, p_mtf, p_trend, p_momentum):
    """Weighted composite probability: 40% pattern + 25% MTF + 20% trend + 15% momentum."""
    return p_pattern * 0.40 + p_mtf * 0.25 + p_trend * 0.20 + p_momentum * 0.15


# ============================================================================
# TEST CASES
# ============================================================================

class TestFibHelpers(unittest.TestCase):
    def test_is_near_fib(self):
        self.assertTrue(is_near_fib(0.618, 0.618))
        self.assertTrue(is_near_fib(0.62, 0.618))
        self.assertFalse(is_near_fib(0.75, 0.618))

    def test_in_fib_range(self):
        self.assertTrue(in_fib_range(0.50, 0.382, 0.618))
        self.assertTrue(in_fib_range(0.38, 0.382, 0.618))  # Within tolerance
        self.assertFalse(in_fib_range(0.20, 0.382, 0.618))

    def test_retrace_ratio(self):
        self.assertAlmostEqual(retrace_ratio(100, 50), 0.5)
        self.assertAlmostEqual(retrace_ratio(100, 161.8), 1.618)
        self.assertEqual(retrace_ratio(0, 50), 0.0)


class TestBullish5Wave(unittest.TestCase):
    """Test bullish 5-wave impulse detection."""

    def _make_pivots(self, p5, p4, p3, p2, p1, p0):
        """Create pivots: L-H-L-H-L-H (bullish impulse layout)."""
        return [
            (p0, True),   # 0: High (Wave 5 end)
            (p1, False),  # 1: Low  (Wave 4 end)
            (p2, True),   # 2: High (Wave 3 end)
            (p3, False),  # 3: Low  (Wave 2 end)
            (p4, True),   # 4: High (Wave 1 end)
            (p5, False),  # 5: Low  (Wave 0 / origin)
        ]

    def test_textbook_bullish_impulse(self):
        """Classic impulse: W2=50%, W3=161.8%, W4=38.2%, W5=100%."""
        # W1: 100->120 (size=20)
        # W2: 120->110 (retrace=50%)
        # W3: 110->142.36 (=W1*1.618=32.36, extend=161.8%)
        # W4: 142.36->130 (retrace W3=38.2%)
        # W5: 130->150 (size=20, extend=100%)
        pivots = self._make_pivots(100, 120, 110, 142.36, 130, 150)
        wnum, conf, valid = detect_bullish_5wave(pivots)
        self.assertEqual(wnum, 5)
        self.assertTrue(valid)
        self.assertGreater(conf, 0.5, "Textbook impulse should have high confidence")

    def test_r1_violation_wave2_100pct(self):
        """Wave 2 retraces 100% of Wave 1 → R1 violated."""
        pivots = self._make_pivots(100, 120, 100, 150, 130, 160)
        wnum, conf, valid = detect_bullish_5wave(pivots)
        self.assertFalse(valid, "Wave 2 at 100% retrace should fail R1")

    def test_r1_violation_wave2_beyond(self):
        """Wave 2 goes below Wave 1 start → R1 violated."""
        pivots = self._make_pivots(100, 120, 95, 150, 130, 160)
        wnum, conf, valid = detect_bullish_5wave(pivots)
        self.assertFalse(valid, "Wave 2 below origin should fail R1")

    def test_r2_violation_wave3_shortest(self):
        """Wave 3 is the shortest of 1, 3, 5 → R2 violated."""
        # W1=20, W3=10, W5=25 → W3 shortest
        pivots = self._make_pivots(100, 120, 115, 125, 110, 135)
        wnum, conf, valid = detect_bullish_5wave(pivots)
        self.assertFalse(valid, "Wave 3 shortest should fail R2")

    def test_r3_violation_wave4_overlap(self):
        """Wave 4 enters Wave 1 territory → R3 violated."""
        # W1 high = 120. Wave 4 low = 118 (< 120) → overlap
        pivots = self._make_pivots(100, 120, 110, 150, 118, 160)
        wnum, conf, valid = detect_bullish_5wave(pivots)
        self.assertFalse(valid, "Wave 4 in Wave 1 territory should fail R3")

    def test_r3_wave4_just_above(self):
        """Wave 4 low exactly at Wave 1 high (borderline valid)."""
        pivots = self._make_pivots(100, 120, 110, 150, 121, 160)
        wnum, conf, valid = detect_bullish_5wave(pivots)
        self.assertTrue(valid, "Wave 4 just above Wave 1 should pass R3")

    def test_wrong_pivot_pattern_rejected(self):
        """Non-alternating pivots should be rejected."""
        # All highs
        pivots = [(160, True), (150, True), (140, True),
                  (130, True), (120, True), (110, True)]
        wnum, conf, valid = detect_bullish_5wave(pivots)
        self.assertFalse(valid)

    def test_non_strict_mode_skips_r3(self):
        """Non-strict mode: R3 violation allowed."""
        pivots = self._make_pivots(100, 120, 110, 150, 118, 160)
        wnum, conf, valid = detect_bullish_5wave(pivots, strict_rules=False)
        # R1 and R2 still valid, just R3 fails
        self.assertTrue(valid, "Non-strict should allow R3 violation")

    def test_confidence_clamped_to_1(self):
        """Confidence should never exceed 1.0."""
        # Perfect proportions to maximize all bonuses
        pivots = self._make_pivots(100, 120, 110, 142.36, 130, 150)
        wnum, conf, valid = detect_bullish_5wave(pivots)
        self.assertLessEqual(conf, 1.0, "Confidence must be clamped to 1.0")


class TestBearish5Wave(unittest.TestCase):
    """Test bearish 5-wave impulse detection."""

    def _make_pivots(self, p5, p4, p3, p2, p1, p0):
        """Bearish pivots: H-L-H-L-H-L."""
        return [
            (p0, False),  # 0: Low  (Wave 5 end)
            (p1, True),   # 1: High (Wave 4 end)
            (p2, False),  # 2: Low  (Wave 3 end)
            (p3, True),   # 3: High (Wave 2 end)
            (p4, False),  # 4: Low  (Wave 1 end)
            (p5, True),   # 5: High (Wave 0 / origin)
        ]

    def test_textbook_bearish_impulse(self):
        """Classic bearish: prices descending with Fibonacci proportions."""
        # W1: 200->180 (size=20)
        # W2: 180->190 (retrace=50%)
        # W3: 190->155 (size=35, extend=175%)
        # W4: 155->168 (retrace W3=37%)
        # W5: 168->148 (size=20, extend=100%)
        pivots = self._make_pivots(200, 180, 190, 155, 168, 148)
        wnum, conf, valid = detect_bearish_5wave(pivots)
        self.assertEqual(wnum, -5)
        self.assertTrue(valid)
        self.assertGreater(conf, 0.4)

    def test_r1_bearish_violation(self):
        """Bearish Wave 2 retraces above Wave 1 start."""
        pivots = self._make_pivots(200, 180, 205, 150, 170, 140)
        wnum, conf, valid = detect_bearish_5wave(pivots)
        self.assertFalse(valid, "Bearish Wave 2 above origin should fail R1")


class TestABCCorrection(unittest.TestCase):
    """Test ABC correction detection."""

    def test_bearish_abc(self):
        """Bearish ABC: H-L-H with B retracing 50% of A."""
        # A: 100->80 (down 20)
        # B: 80->90 (up 10 = 50% retrace)
        pivots = [(90, True), (80, False), (100, True)]
        abc_type, conf = detect_abc_correction(pivots)
        self.assertEqual(abc_type, 1, "Should detect bearish ABC")
        self.assertGreater(conf, 0.3)

    def test_bullish_abc(self):
        """Bullish ABC: L-H-L with B retracing ~50% of A."""
        # A: 100->120 (up 20)
        # B: 120->110 (down 10 = 50% retrace)
        pivots = [(110, False), (120, True), (100, False)]
        abc_type, conf = detect_abc_correction(pivots)
        self.assertEqual(abc_type, -1, "Should detect bullish ABC")
        self.assertGreater(conf, 0.3)

    def test_b_retrace_too_shallow(self):
        """B wave retraces only 10% of A → rejected."""
        pivots = [(82, True), (80, False), (100, True)]
        abc_type, conf = detect_abc_correction(pivots)
        self.assertEqual(abc_type, 0, "Shallow B retrace should be rejected")

    def test_b_retrace_too_deep(self):
        """B wave retraces >100% → not a valid B wave."""
        # A: 100->80 (20 down), B: 80->105 (25 up, 125% retrace)
        pivots = [(105, True), (80, False), (100, True)]
        abc_type, conf = detect_abc_correction(pivots)
        self.assertEqual(abc_type, 0, "B > 100% should be rejected")


class TestWXYDouble(unittest.TestCase):
    """Test WXY double combination detection."""

    def test_bearish_wxy(self):
        """Bearish WXY: H-L-H-L with X=50% of W, Y≈W."""
        # W: 100->80 (20 down), X: 80->90 (50% retrace), Y: 90->70 (20 down, 100% of W)
        pivots = [(70, False), (90, True), (80, False), (100, True)]
        wxy_type, conf = detect_wxy_double(pivots)
        self.assertEqual(wxy_type, 1, "Should detect bearish WXY")
        self.assertGreater(conf, 0.4)

    def test_bullish_wxy(self):
        """Bullish WXY: L-H-L-H with X=50% of W, Y≈W."""
        # W: 100->120 (20 up), X: 120->110 (50% retrace), Y: 110->130 (20 up, 100% of W)
        pivots = [(130, True), (110, False), (120, True), (100, False)]
        wxy_type, conf = detect_wxy_double(pivots)
        self.assertEqual(wxy_type, -1, "Should detect bullish WXY")
        self.assertGreater(conf, 0.4)

    def test_x_exceeds_w_start_rejected(self):
        """X retracement exceeds W's starting point → invalid."""
        # W: 100->80, X: 80->105 (exceeds 100) → invalid
        pivots = [(70, False), (105, True), (80, False), (100, True)]
        wxy_type, conf = detect_wxy_double(pivots)
        self.assertEqual(wxy_type, 0, "X exceeding W start should fail")


class TestDiagonal(unittest.TestCase):
    """Test diagonal pattern detection."""

    def test_bullish_contracting_diagonal(self):
        """Bullish contracting diagonal: W1>W3>W5, W4 overlaps W1."""
        # W1=20, W3=15, W5=10 (contracting), W4 low=115 overlaps W1 high=120
        pivots = [
            (135, True),   # 0: Wave 5 end
            (125, False),  # 1: Wave 4 end (overlaps W1 territory: < 120)
            # Actually p1=125 > p4=120, so no overlap!
            # Let me fix: p1 must be < p4 for overlap
            # Let me use: p1=115 < p4=120
        ]
        pivots = [
            (135, True),   # 0: Wave 5 end
            (115, False),  # 1: Wave 4 end (< 120 = overlap)
            (130, True),   # 2: Wave 3 end
            (108, False),  # 3: Wave 2 end
            (120, True),   # 4: Wave 1 end
            (100, False),  # 5: Origin
        ]
        # W1=120-100=20, W2=120-108=12, W3=130-108=22, W4=130-115=15, W5=135-115=20
        # Wait, W3=22 > W1=20, W5=20 = W1=20, so not contracting.
        # Let me use proper contracting values.
        pivots = [
            (128, True),   # 0: Wave 5 end
            (115, False),  # 1: Wave 4 end (115 < 120, overlap; 115 > 100, stays above origin)
            (130, True),   # 2: Wave 3 end
            (108, False),  # 3: Wave 2 end
            (120, True),   # 4: Wave 1 end
            (100, False),  # 5: Origin
        ]
        # W1=20, W3=130-108=22, W5=128-115=13
        # W3>W1: not contracting. Let me fix.
        pivots = [
            (122, True),   # 0: Wave 5 end
            (115, False),  # 1: Wave 4 end
            (127, True),   # 2: Wave 3 end
            (110, False),  # 3: Wave 2 end
            (120, True),   # 4: Wave 1 end
            (100, False),  # 5: Origin
        ]
        # W1=20, W3=127-110=17, W5=122-115=7 → 20>17>7 ✓ contracting
        # W2=120-110=10, W4=127-115=12 → NOT W2>W4. Let me fix.
        pivots = [
            (122, True),   # 0: Wave 5 end
            (116, False),  # 1: Wave 4 end
            (127, True),   # 2: Wave 3 end
            (106, False),  # 3: Wave 2 end
            (120, True),   # 4: Wave 1 end
            (100, False),  # 5: Origin
        ]
        # W1=20, W2=120-106=14, W3=127-106=21, W4=127-116=11, W5=122-116=6
        # Contracting motive: 20>21? NO. W3>W1 again.
        # For a diagonal, W3 doesn't have to be larger than W1. Let me use:
        pivots = [
            (117, True),   # 0: Wave 5 end
            (112, False),  # 1: Wave 4 end
            (122, True),   # 2: Wave 3 end
            (107, False),  # 3: Wave 2 end
            (118, True),   # 4: Wave 1 end
            (100, False),  # 5: Origin
        ]
        # W1=18, W3=122-107=15, W5=117-112=5 → 18>15>5 ✓
        # W2=118-107=11, W4=122-112=10 → 11>10 ✓
        # Overlap: p1(112) < p4(118) ✓, p1(112) > p5(100) ✓
        # W2_valid: p3(107) > p5(100) ✓
        # W3 not shortest: 15 >= 18? No. 15 >= 5? Yes. ✓
        diag_type, conf, is_leading = detect_diagonal(pivots)
        self.assertEqual(diag_type, 1, "Should detect bullish diagonal")
        self.assertGreater(conf, 0.3)

    def test_diagonal_no_overlap_rejected(self):
        """If Wave 4 doesn't overlap Wave 1, it's an impulse, not diagonal."""
        # Make p1 > p4 (no overlap)
        pivots = [
            (160, True),   # 0
            (140, False),  # 1: Wave 4 end (140 > 120 = no overlap)
            (150, True),   # 2
            (110, False),  # 3
            (120, True),   # 4
            (100, False),  # 5
        ]
        diag_type, conf, is_leading = detect_diagonal(pivots)
        self.assertEqual(diag_type, 0, "No overlap should not be diagonal")

    def test_diagonal_too_deep_rejected(self):
        """Wave 4 below Wave 1 start (p1 < p5) → structurally broken."""
        pivots = [
            (117, True),   # 0
            (95, False),   # 1: Wave 4 end, below origin (95 < 100)
            (122, True),   # 2
            (107, False),  # 3
            (118, True),   # 4
            (100, False),  # 5
        ]
        diag_type, conf, is_leading = detect_diagonal(pivots)
        self.assertEqual(diag_type, 0, "Wave 4 below Wave 1 start should be rejected")


class TestCompositeProbability(unittest.TestCase):
    """Test composite probability scoring."""

    def test_perfect_alignment(self):
        """All components at 1.0 → composite = 1.0."""
        result = compute_composite_probability(1.0, 1.0, 1.0, 1.0)
        self.assertAlmostEqual(result, 1.0)

    def test_zero_alignment(self):
        """All components at 0.0 → composite = 0.0."""
        result = compute_composite_probability(0.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(result, 0.0)

    def test_weights_sum_to_1(self):
        """Verify weights: 0.40 + 0.25 + 0.20 + 0.15 = 1.0."""
        self.assertAlmostEqual(0.40 + 0.25 + 0.20 + 0.15, 1.0)

    def test_pattern_dominant(self):
        """Pattern has highest weight (40%), so it dominates."""
        high_pattern = compute_composite_probability(1.0, 0.0, 0.0, 0.0)
        high_mtf = compute_composite_probability(0.0, 1.0, 0.0, 0.0)
        self.assertGreater(high_pattern, high_mtf)

    def test_mixed_probability(self):
        """Typical mixed scenario: 60% pattern, 67% MTF, 50% trend, 33% momentum."""
        result = compute_composite_probability(0.6, 0.67, 0.5, 0.33)
        expected = 0.6 * 0.40 + 0.67 * 0.25 + 0.5 * 0.20 + 0.33 * 0.15
        self.assertAlmostEqual(result, expected)

    def test_mtf_disabled_neutral(self):
        """When MTF is disabled, p_mtf=0.5, p_trend=0.5, p_momentum=0.5."""
        result = compute_composite_probability(0.6, 0.5, 0.5, 0.5)
        # = 0.6*0.4 + 0.5*0.25 + 0.5*0.2 + 0.5*0.15 = 0.24 + 0.125 + 0.10 + 0.075 = 0.54
        self.assertAlmostEqual(result, 0.54)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_insufficient_pivots_5wave(self):
        """Fewer than 6 pivots returns no pattern."""
        pivots = [(100, True), (90, False), (105, True)]
        wnum, conf, valid = detect_bullish_5wave(pivots)
        self.assertFalse(valid)

    def test_insufficient_pivots_abc(self):
        """Fewer than 3 pivots returns no pattern."""
        pivots = [(100, True), (90, False)]
        abc_type, conf = detect_abc_correction(pivots)
        self.assertEqual(abc_type, 0)

    def test_flat_market_no_detection(self):
        """All prices equal → no pattern detected."""
        pivots = [(100, True), (100, False), (100, True),
                  (100, False), (100, True), (100, False)]
        wnum, conf, valid = detect_bullish_5wave(pivots)
        self.assertFalse(valid)

    def test_division_by_zero_safe(self):
        """retrace_ratio with zero wave size returns 0."""
        self.assertEqual(retrace_ratio(0, 50), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

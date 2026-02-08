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
  - RSI divergence detection (regular & hidden)
  - Per-pattern RSI divergence scoring
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


def compute_composite_probability(p_pattern, p_mtf, p_trend, p_momentum, p_rsi=None, p_vol=None):
    """Weighted composite probability.
    Without RSI/Vol: 40% pattern + 25% MTF + 20% trend + 15% momentum (legacy).
    With RSI only:   35% pattern + 20% MTF + 15% trend + 15% momentum + 15% RSI.
    With RSI + Vol:  25% pattern + 15% MTF + 10% trend + 10% momentum + 15% RSI + 25% volume.
    """
    if p_vol is not None and p_rsi is not None:
        return (p_pattern * 0.25 + p_mtf * 0.15 + p_trend * 0.10 +
                p_momentum * 0.10 + p_rsi * 0.15 + p_vol * 0.25)
    if p_rsi is not None:
        return p_pattern * 0.35 + p_mtf * 0.20 + p_trend * 0.15 + p_momentum * 0.15 + p_rsi * 0.15
    return p_pattern * 0.40 + p_mtf * 0.25 + p_trend * 0.20 + p_momentum * 0.15


# ============================================================================
# RSI DIVERGENCE DETECTION (translated from Pine Script)
# ============================================================================

def detect_divergence_at_highs(prices, rsi_values, newer_idx, older_idx):
    """
    Detect divergence between two high pivots.
    Returns: 1 = regular bearish, 2 = hidden bearish, 0 = none.
    """
    if (newer_idx >= len(prices) or older_idx >= len(prices) or
        newer_idx >= len(rsi_values) or older_idx >= len(rsi_values)):
        return 0
    p_new = prices[newer_idx]
    p_old = prices[older_idx]
    r_new = rsi_values[newer_idx]
    r_old = rsi_values[older_idx]
    if p_new is None or p_old is None or r_new is None or r_old is None:
        return 0
    # Regular bearish: price higher high, RSI lower high
    if p_new > p_old and r_new < r_old:
        return 1
    # Hidden bearish: price lower high, RSI higher high
    if p_new < p_old and r_new > r_old:
        return 2
    return 0


def detect_divergence_at_lows(prices, rsi_values, newer_idx, older_idx):
    """
    Detect divergence between two low pivots.
    Returns: -1 = regular bullish, -2 = hidden bullish, 0 = none.
    """
    if (newer_idx >= len(prices) or older_idx >= len(prices) or
        newer_idx >= len(rsi_values) or older_idx >= len(rsi_values)):
        return 0
    p_new = prices[newer_idx]
    p_old = prices[older_idx]
    r_new = rsi_values[newer_idx]
    r_old = rsi_values[older_idx]
    if p_new is None or p_old is None or r_new is None or r_old is None:
        return 0
    # Regular bullish: price lower low, RSI higher low
    if p_new < p_old and r_new > r_old:
        return -1
    # Hidden bullish: price higher low, RSI lower low
    if p_new > p_old and r_new < r_old:
        return -2
    return 0


def compute_impulse_rsi_score(active_bull, prices, rsi_values, rsi_ob=70, rsi_os=30):
    """
    Compute RSI divergence score for a completed impulse pattern.
    Returns: (div_type, div_score)
    """
    div_type = 0
    div_score = 0.5
    if active_bull:
        div = detect_divergence_at_highs(prices, rsi_values, 0, 2)
        if div == 1:
            div_type = 1
            div_score = 1.0
        elif rsi_values[0] > rsi_ob:
            div_score = 0.75
        elif rsi_values[0] < rsi_os:
            div_score = 0.25
    else:
        div = detect_divergence_at_lows(prices, rsi_values, 0, 2)
        if div == -1:
            div_type = -1
            div_score = 1.0
        elif rsi_values[0] < rsi_os:
            div_score = 0.75
        elif rsi_values[0] > rsi_ob:
            div_score = 0.25
    return (div_type, div_score)


def compute_correction_rsi_score(abc_type, prices, rsi_values, rsi_ob=70, rsi_os=30):
    """
    Compute RSI divergence score for ABC correction.
    Returns: (div_type, div_score)
    """
    div_type = 0
    div_score = 0.5
    if abc_type > 0:  # Bearish ABC
        div = detect_divergence_at_highs(prices, rsi_values, 0, 2)
        if div == 1:
            div_type = 1
            div_score = 0.90
        elif rsi_values[0] > rsi_ob:
            div_score = 0.30
    elif abc_type < 0:  # Bullish ABC
        div = detect_divergence_at_lows(prices, rsi_values, 0, 2)
        if div == -1:
            div_type = -1
            div_score = 0.90
        elif rsi_values[0] < rsi_os:
            div_score = 0.30
    return (div_type, div_score)


def compute_wxy_rsi_score(wxy_type, prices, rsi_values, rsi_ob=70, rsi_os=30):
    """
    Compute RSI divergence score for WXY pattern.
    Returns: (div_type, div_score)
    """
    div_type = 0
    div_score = 0.5
    if wxy_type > 0:  # Bearish WXY
        div = detect_divergence_at_lows(prices, rsi_values, 0, 2)
        if div == -1:
            div_type = -1
            div_score = 1.0
        elif rsi_values[0] < rsi_os:
            div_score = 0.75
    elif wxy_type < 0:  # Bullish WXY
        div = detect_divergence_at_highs(prices, rsi_values, 0, 2)
        if div == 1:
            div_type = 1
            div_score = 1.0
        elif rsi_values[0] > rsi_ob:
            div_score = 0.75
    return (div_type, div_score)


def compute_wxyxz_rsi_score(wxyz_type, prices, rsi_values, rsi_ob=70, rsi_os=30):
    """
    Compute RSI divergence score for WXYXZ pattern with double divergence check.
    Returns: (div_type, div_score)
    """
    div_type = 0
    div_score = 0.5
    if wxyz_type > 0:  # Bearish WXYXZ
        div_zw = detect_divergence_at_lows(prices, rsi_values, 0, 4)
        div_zy = detect_divergence_at_lows(prices, rsi_values, 0, 2)
        if div_zw == -1 and div_zy == -1:
            div_type = -1
            div_score = 1.0
        elif div_zw == -1 or div_zy == -1:
            div_type = -1
            div_score = 0.85
        elif rsi_values[0] < rsi_os:
            div_score = 0.70
    elif wxyz_type < 0:  # Bullish WXYXZ
        div_zw = detect_divergence_at_highs(prices, rsi_values, 0, 4)
        div_zy = detect_divergence_at_highs(prices, rsi_values, 0, 2)
        if div_zw == 1 and div_zy == 1:
            div_type = 1
            div_score = 1.0
        elif div_zw == 1 or div_zy == 1:
            div_type = 1
            div_score = 0.85
        elif rsi_values[0] > rsi_ob:
            div_score = 0.70
    return (div_type, div_score)


def compute_diagonal_rsi_score(diag_type, is_leading, prices, rsi_values, rsi_ob=70, rsi_os=30):
    """
    Compute RSI divergence score for diagonal patterns.
    Returns: (div_type, div_score)
    """
    div_type = 0
    div_score = 0.5
    if not is_leading:  # Ending diagonal
        if diag_type > 0:
            div = detect_divergence_at_highs(prices, rsi_values, 0, 2)
            if div == 1:
                div_type = 1
                div_score = 1.0
            elif rsi_values[0] > rsi_ob:
                div_score = 0.80
        elif diag_type < 0:
            div = detect_divergence_at_lows(prices, rsi_values, 0, 2)
            if div == -1:
                div_type = -1
                div_score = 1.0
            elif rsi_values[0] < rsi_os:
                div_score = 0.80
    else:  # Leading diagonal: check W3 RSI strength
        rsi_w3 = rsi_values[0] if len(rsi_values) > 0 else None
        rsi_w1 = rsi_values[4] if len(rsi_values) > 4 else None
        if rsi_w3 is not None and rsi_w1 is not None:
            if diag_type > 0 and rsi_w3 > rsi_w1:
                div_score = 0.80
            elif diag_type < 0 and rsi_w3 < rsi_w1:
                div_score = 0.80
            else:
                div_score = 0.40
    return (div_type, div_score)


# ============================================================================
# OBV DIVERGENCE DETECTION (translated from Pine Script)
# ============================================================================

def detect_obv_div_at_highs(prices, obv_values, newer_idx, older_idx):
    """OBV divergence at highs. Returns: 1=regular bearish (distribution), 2=hidden, 0=none."""
    if (newer_idx >= len(prices) or older_idx >= len(prices) or
        newer_idx >= len(obv_values) or older_idx >= len(obv_values)):
        return 0
    p_new, p_old = prices[newer_idx], prices[older_idx]
    o_new, o_old = obv_values[newer_idx], obv_values[older_idx]
    if p_new is None or p_old is None or o_new is None or o_old is None:
        return 0
    if p_new > p_old and o_new < o_old:
        return 1
    if p_new < p_old and o_new > o_old:
        return 2
    return 0


def detect_obv_div_at_lows(prices, obv_values, newer_idx, older_idx):
    """OBV divergence at lows. Returns: -1=regular bullish (accumulation), -2=hidden, 0=none."""
    if (newer_idx >= len(prices) or older_idx >= len(prices) or
        newer_idx >= len(obv_values) or older_idx >= len(obv_values)):
        return 0
    p_new, p_old = prices[newer_idx], prices[older_idx]
    o_new, o_old = obv_values[newer_idx], obv_values[older_idx]
    if p_new is None or p_old is None or o_new is None or o_old is None:
        return 0
    if p_new < p_old and o_new > o_old:
        return -1
    if p_new > p_old and o_new < o_old:
        return -2
    return 0


def compute_volume_score(obv_div_score, wave_vol_score, vwap_score):
    """Combined volume score: 40% OBV divergence + 30% wave volume + 30% VWAP."""
    return obv_div_score * 0.40 + wave_vol_score * 0.30 + vwap_score * 0.30


def compute_impulse_wave_vol_score(v_w1, v_w3, v_w5):
    """Wave volume pattern score for impulse: W3 should be highest volume."""
    if v_w1 is None or v_w3 is None or v_w5 is None:
        return 0.5
    if v_w3 > v_w1 and v_w3 > v_w5:
        if v_w5 < v_w1:
            return 1.0    # W3 highest, W5 declining → strong exhaustion
        return 0.85       # W3 highest → classic impulse
    if v_w5 > v_w3:
        return 0.15       # W5 more volume than W3 → extended 5th, NOT exhaustion
    return 0.5


def compute_vwap_score(vwap_pct, active_bull):
    """VWAP position score. vwap_pct = (close - vwap) / vwap * 100."""
    if vwap_pct is None:
        return 0.5
    if active_bull:
        if vwap_pct > 1.0:
            return 1.0
        if vwap_pct > 0.0:
            return 0.75
        if vwap_pct > -1.0:
            return 0.35
        return 0.15
    else:
        if vwap_pct < -1.0:
            return 1.0
        if vwap_pct < 0.0:
            return 0.75
        if vwap_pct < 1.0:
            return 0.35
        return 0.15


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

    def test_perfect_alignment_legacy(self):
        """All components at 1.0 without RSI → composite = 1.0."""
        result = compute_composite_probability(1.0, 1.0, 1.0, 1.0)
        self.assertAlmostEqual(result, 1.0)

    def test_zero_alignment_legacy(self):
        """All components at 0.0 without RSI → composite = 0.0."""
        result = compute_composite_probability(0.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(result, 0.0)

    def test_legacy_weights_sum_to_1(self):
        """Verify legacy weights: 0.40 + 0.25 + 0.20 + 0.15 = 1.0."""
        self.assertAlmostEqual(0.40 + 0.25 + 0.20 + 0.15, 1.0)

    def test_rsi_weights_sum_to_1(self):
        """Verify RSI weights: 0.35 + 0.20 + 0.15 + 0.15 + 0.15 = 1.0."""
        self.assertAlmostEqual(0.35 + 0.20 + 0.15 + 0.15 + 0.15, 1.0)

    def test_perfect_alignment_with_rsi(self):
        """All 5 components at 1.0 → composite = 1.0."""
        result = compute_composite_probability(1.0, 1.0, 1.0, 1.0, p_rsi=1.0)
        self.assertAlmostEqual(result, 1.0)

    def test_zero_alignment_with_rsi(self):
        """All 5 components at 0.0 → composite = 0.0."""
        result = compute_composite_probability(0.0, 0.0, 0.0, 0.0, p_rsi=0.0)
        self.assertAlmostEqual(result, 0.0)

    def test_pattern_still_dominant_with_rsi(self):
        """Pattern has highest weight (35%), so it still dominates."""
        high_pattern = compute_composite_probability(1.0, 0.0, 0.0, 0.0, p_rsi=0.0)
        high_mtf = compute_composite_probability(0.0, 1.0, 0.0, 0.0, p_rsi=0.0)
        high_rsi = compute_composite_probability(0.0, 0.0, 0.0, 0.0, p_rsi=1.0)
        self.assertGreater(high_pattern, high_mtf)
        self.assertGreater(high_pattern, high_rsi)

    def test_mixed_probability_with_rsi(self):
        """Typical mixed scenario with RSI component."""
        result = compute_composite_probability(0.6, 0.67, 0.5, 0.33, p_rsi=0.85)
        expected = 0.6 * 0.35 + 0.67 * 0.20 + 0.5 * 0.15 + 0.33 * 0.15 + 0.85 * 0.15
        self.assertAlmostEqual(result, expected)

    def test_rsi_boost_effect(self):
        """RSI at 1.0 vs 0.5 should boost composite by 0.075."""
        base = compute_composite_probability(0.5, 0.5, 0.5, 0.5, p_rsi=0.5)
        boosted = compute_composite_probability(0.5, 0.5, 0.5, 0.5, p_rsi=1.0)
        self.assertAlmostEqual(boosted - base, 0.075)

    def test_mtf_disabled_neutral_with_rsi(self):
        """When MTF is disabled (neutral), RSI still contributes."""
        result = compute_composite_probability(0.6, 0.5, 0.5, 0.5, p_rsi=1.0)
        expected = 0.6 * 0.35 + 0.5 * 0.20 + 0.5 * 0.15 + 0.5 * 0.15 + 1.0 * 0.15
        self.assertAlmostEqual(result, expected)


class TestRSIDivergenceDetection(unittest.TestCase):
    """Test RSI divergence detection functions."""

    def test_regular_bearish_divergence(self):
        """Price higher high + RSI lower high → regular bearish (1)."""
        prices = [110, 90, 100]       # idx 0 higher than idx 2
        rsi =    [60,  40, 70]        # idx 0 lower than idx 2
        result = detect_divergence_at_highs(prices, rsi, 0, 2)
        self.assertEqual(result, 1)

    def test_hidden_bearish_divergence(self):
        """Price lower high + RSI higher high → hidden bearish (2)."""
        prices = [95,  90, 100]       # idx 0 lower than idx 2
        rsi =    [75,  40, 65]        # idx 0 higher than idx 2
        result = detect_divergence_at_highs(prices, rsi, 0, 2)
        self.assertEqual(result, 2)

    def test_no_divergence_at_highs(self):
        """Price and RSI both higher → no divergence."""
        prices = [110, 90, 100]
        rsi =    [75,  40, 65]        # Both price and RSI higher → no divergence
        result = detect_divergence_at_highs(prices, rsi, 0, 2)
        self.assertEqual(result, 0)

    def test_regular_bullish_divergence(self):
        """Price lower low + RSI higher low → regular bullish (-1)."""
        prices = [85,  110, 90]       # idx 0 lower than idx 2
        rsi =    [35,  70,  25]       # idx 0 higher than idx 2
        result = detect_divergence_at_lows(prices, rsi, 0, 2)
        self.assertEqual(result, -1)

    def test_hidden_bullish_divergence(self):
        """Price higher low + RSI lower low → hidden bullish (-2)."""
        prices = [95,  110, 90]       # idx 0 higher than idx 2
        rsi =    [20,  70,  30]       # idx 0 lower than idx 2
        result = detect_divergence_at_lows(prices, rsi, 0, 2)
        self.assertEqual(result, -2)

    def test_no_divergence_at_lows_concordant(self):
        """Price lower low + RSI lower low → no divergence (concordant move)."""
        prices = [85,  110, 90]       # idx 0 (85) lower than idx 2 (90)
        rsi =    [20,  70,  30]       # idx 0 (20) lower than idx 2 (30)
        result = detect_divergence_at_lows(prices, rsi, 0, 2)
        # p_new < p_old, r_new < r_old → neither bullish nor hidden condition met → 0
        self.assertEqual(result, 0)

    def test_none_values_return_zero(self):
        """None RSI values should return 0 (no divergence)."""
        prices = [110, 90, 100]
        rsi =    [None, 40, 70]
        self.assertEqual(detect_divergence_at_highs(prices, rsi, 0, 2), 0)
        self.assertEqual(detect_divergence_at_lows(prices, rsi, 0, 2), 0)

    def test_out_of_bounds_returns_zero(self):
        """Out of bounds indices should return 0."""
        prices = [100, 90]
        rsi =    [50, 40]
        self.assertEqual(detect_divergence_at_highs(prices, rsi, 0, 5), 0)
        self.assertEqual(detect_divergence_at_lows(prices, rsi, 0, 5), 0)

    def test_equal_prices_no_divergence(self):
        """Equal prices at both pivots → no divergence."""
        prices = [100, 90, 100]
        rsi =    [60,  40, 70]
        # p_new == p_old → neither > nor < → returns 0
        self.assertEqual(detect_divergence_at_highs(prices, rsi, 0, 2), 0)


class TestImpulseRSIDivergence(unittest.TestCase):
    """Test RSI divergence scoring for impulse patterns."""

    def test_bullish_impulse_bearish_divergence(self):
        """Bullish impulse W5 top: price higher, RSI lower → bearish div confirms exhaustion."""
        # pivot[0] = W5 high, pivot[2] = W3 high
        prices = [155, 130, 150, 110, 120, 100]
        rsi =    [65,  40,  75,  35,  55,  45]
        # W5 price (155) > W3 price (150), W5 RSI (65) < W3 RSI (75) → regular bearish
        div_type, div_score = compute_impulse_rsi_score(True, prices, rsi)
        self.assertEqual(div_type, 1, "Should detect regular bearish divergence")
        self.assertAlmostEqual(div_score, 1.0)

    def test_bearish_impulse_bullish_divergence(self):
        """Bearish impulse W5 bottom: price lower, RSI higher → bullish div confirms exhaustion."""
        prices = [45,  70,  50,  90,  80,  100]
        rsi =    [35,  60,  25,  65,  55,  50]
        # W5 price (45) < W3 price (50), W5 RSI (35) > W3 RSI (25) → regular bullish
        div_type, div_score = compute_impulse_rsi_score(False, prices, rsi)
        self.assertEqual(div_type, -1, "Should detect regular bullish divergence")
        self.assertAlmostEqual(div_score, 1.0)

    def test_bullish_impulse_overbought_no_divergence(self):
        """RSI overbought at W5 without divergence → partial confirmation (0.75)."""
        prices = [155, 130, 140, 110, 120, 100]
        rsi =    [78,  40,  65,  35,  55,  45]
        # W5 price (155) > W3 price (140), W5 RSI (78) > W3 RSI (65) → no divergence
        # But RSI > 70 (overbought) → 0.75
        div_type, div_score = compute_impulse_rsi_score(True, prices, rsi)
        self.assertEqual(div_type, 0)
        self.assertAlmostEqual(div_score, 0.75)

    def test_bullish_impulse_oversold_contradicts(self):
        """RSI oversold at W5 top → contradicts (0.25)."""
        prices = [155, 130, 140, 110, 120, 100]
        rsi =    [25,  40,  20,  35,  55,  45]
        # W5 RSI (25) < 30 → oversold at top = contradiction
        div_type, div_score = compute_impulse_rsi_score(True, prices, rsi)
        self.assertEqual(div_type, 0)
        self.assertAlmostEqual(div_score, 0.25)

    def test_neutral_rsi_at_impulse(self):
        """RSI in neutral zone with no divergence → default 0.5."""
        prices = [155, 130, 140, 110, 120, 100]
        rsi =    [60,  40,  55,  35,  50,  45]
        # No divergence (both price & RSI higher), RSI not extreme → 0.5
        div_type, div_score = compute_impulse_rsi_score(True, prices, rsi)
        self.assertEqual(div_type, 0)
        self.assertAlmostEqual(div_score, 0.5)


class TestCorrectionRSIDivergence(unittest.TestCase):
    """Test RSI divergence scoring for ABC correction patterns."""

    def test_bearish_abc_divergence(self):
        """Bearish ABC: B high (pivot[0]) weaker than A start (pivot[2]) → confirms C down."""
        prices = [95,  80,  100]
        rsi =    [55,  30,  70]
        # B price (95) < A start (100), B RSI (55) < A RSI (70) → no div (concordant)
        # Wait: for bearish divergence at highs(0,2): p_new=95 < p_old=100 and r_new=55 > r_old=70? No.
        # Let me set up proper bearish divergence: price lower high but RSI higher high
        # Actually the Pine Script checks for regular bearish (p_new > p_old, r_new < r_old)
        # For B wave bounce showing weakness: B price is lower high than A start is rare
        # Let's test with actual divergence
        prices2 = [102, 80,  100]     # B higher than A start
        rsi2 =    [60,  30,  70]      # But RSI lower → regular bearish
        div_type, div_score = compute_correction_rsi_score(1, prices2, rsi2)
        self.assertEqual(div_type, 1)
        self.assertAlmostEqual(div_score, 0.90)

    def test_bullish_abc_divergence(self):
        """Bullish ABC: B low weaker than A start → confirms C up."""
        prices = [98,  120, 100]      # B price (98) < A start (100) → lower low
        rsi =    [35,  70,  25]       # B RSI (35) > A RSI (25) → higher low
        div_type, div_score = compute_correction_rsi_score(-1, prices, rsi)
        self.assertEqual(div_type, -1)
        self.assertAlmostEqual(div_score, 0.90)

    def test_bearish_abc_overbought(self):
        """Bearish ABC with RSI overbought at B but no divergence → 0.30."""
        prices = [105, 80,  100]      # Price and RSI both higher
        rsi =    [75,  30,  65]       # RSI > 70 (overbought) but no divergence
        div_type, div_score = compute_correction_rsi_score(1, prices, rsi)
        self.assertEqual(div_type, 0)
        self.assertAlmostEqual(div_score, 0.30)

    def test_neutral_abc_no_divergence(self):
        """ABC correction with neutral RSI → default 0.5."""
        prices = [105, 80,  100]
        rsi =    [60,  30,  55]       # Both higher, not extreme
        div_type, div_score = compute_correction_rsi_score(1, prices, rsi)
        self.assertEqual(div_type, 0)
        self.assertAlmostEqual(div_score, 0.5)


class TestWXYRSIDivergence(unittest.TestCase):
    """Test RSI divergence scoring for WXY patterns."""

    def test_bearish_wxy_bullish_divergence(self):
        """Bearish WXY: Y low vs W low shows bullish divergence → correction exhaustion."""
        # Y-end (pivot[0]) vs W-end (pivot[2]) at lows
        prices = [68,  90,  70,  100]   # Y price (68) < W price (70) → lower low
        rsi =    [32,  60,  25,  55]    # Y RSI (32) > W RSI (25) → higher low
        div_type, div_score = compute_wxy_rsi_score(1, prices, rsi)
        self.assertEqual(div_type, -1, "Should detect bullish divergence → correction ending")
        self.assertAlmostEqual(div_score, 1.0)

    def test_bullish_wxy_bearish_divergence(self):
        """Bullish WXY: Y high vs W high shows bearish divergence → correction exhaustion."""
        prices = [132, 110, 130, 100]   # Y price (132) > W price (130) → higher high
        rsi =    [60,  40,  68,  45]    # Y RSI (60) < W RSI (68) → lower high
        div_type, div_score = compute_wxy_rsi_score(-1, prices, rsi)
        self.assertEqual(div_type, 1, "Should detect bearish divergence")
        self.assertAlmostEqual(div_score, 1.0)

    def test_bearish_wxy_oversold(self):
        """Bearish WXY: Y at oversold without divergence → 0.75."""
        prices = [68,  90,  75,  100]   # Y lower than W
        rsi =    [22,  60,  28,  55]    # Y RSI (22) < W RSI (28) → concordant (no div)
        # But RSI < 30 → oversold → 0.75
        div_type, div_score = compute_wxy_rsi_score(1, prices, rsi)
        self.assertEqual(div_type, 0)
        self.assertAlmostEqual(div_score, 0.75)

    def test_neutral_wxy(self):
        """WXY with neutral RSI → default 0.5."""
        prices = [75,  90,  80,  100]
        rsi =    [40,  60,  45,  55]    # Concordant, not extreme
        div_type, div_score = compute_wxy_rsi_score(1, prices, rsi)
        self.assertEqual(div_type, 0)
        self.assertAlmostEqual(div_score, 0.5)


class TestWXYXZRSIDivergence(unittest.TestCase):
    """Test RSI divergence scoring for WXYXZ patterns."""

    def test_bearish_wxyxz_double_divergence(self):
        """Bearish WXYXZ: Z vs W AND Z vs Y both show bullish divergence → max score."""
        # Z(idx0) vs Y(idx2) vs W(idx4) — all at lows
        prices = [60,  85,  65,  90,  70,  100]  # Z<Y<W price lows
        rsi =    [38,  60,  30,  65,  25,  55]    # Z>Y>W RSI → both divergences
        div_type, div_score = compute_wxyxz_rsi_score(1, prices, rsi)
        self.assertEqual(div_type, -1)
        self.assertAlmostEqual(div_score, 1.0)

    def test_bearish_wxyxz_single_divergence(self):
        """Bearish WXYXZ: only Z vs W divergence → 0.85."""
        prices = [60,  85,  65,  90,  70,  100]
        rsi =    [28,  60,  30,  65,  25,  55]
        # Z vs W: p=60<70, r=28>25 → bullish div ✓
        # Z vs Y: p=60<65, r=28<30 → concordant, no div
        div_type, div_score = compute_wxyxz_rsi_score(1, prices, rsi)
        self.assertEqual(div_type, -1)
        self.assertAlmostEqual(div_score, 0.85)

    def test_bullish_wxyxz_double_divergence(self):
        """Bullish WXYXZ: Z vs W AND Z vs Y both show bearish divergence → max score."""
        prices = [140, 115, 135, 110, 130, 100]  # Z>Y>W price highs
        rsi =    [62,  40,  68,  35,  75,  45]    # Z<Y<W RSI → both divergences
        div_type, div_score = compute_wxyxz_rsi_score(-1, prices, rsi)
        self.assertEqual(div_type, 1)
        self.assertAlmostEqual(div_score, 1.0)

    def test_wxyxz_oversold_no_divergence(self):
        """WXYXZ with oversold RSI but no divergence → 0.70."""
        prices = [60,  85,  65,  90,  70,  100]
        rsi =    [22,  60,  24,  65,  26,  55]    # All concordant (lower), RSI < 30
        div_type, div_score = compute_wxyxz_rsi_score(1, prices, rsi)
        self.assertEqual(div_type, 0)
        self.assertAlmostEqual(div_score, 0.70)


class TestDiagonalRSIDivergence(unittest.TestCase):
    """Test RSI divergence scoring for diagonal patterns."""

    def test_bullish_ending_diagonal_bearish_div(self):
        """Bullish ending diagonal: W5 vs W3 bearish divergence → confirms reversal."""
        # Ending diagonal (not leading): W5 high (idx0) vs W3 high (idx2)
        prices = [128, 115, 125, 107, 120, 100]
        rsi =    [62,  40,  70,  35,  55,  45]
        # W5 price (128) > W3 price (125), W5 RSI (62) < W3 RSI (70) → regular bearish
        div_type, div_score = compute_diagonal_rsi_score(1, False, prices, rsi)
        self.assertEqual(div_type, 1)
        self.assertAlmostEqual(div_score, 1.0)

    def test_bearish_ending_diagonal_bullish_div(self):
        """Bearish ending diagonal: W5 vs W3 bullish divergence → confirms reversal."""
        prices = [72,  85,  75,  93,  80,  100]
        rsi =    [38,  60,  30,  65,  55,  50]
        # W5 price (72) < W3 price (75), W5 RSI (38) > W3 RSI (30) → regular bullish
        div_type, div_score = compute_diagonal_rsi_score(-1, False, prices, rsi)
        self.assertEqual(div_type, -1)
        self.assertAlmostEqual(div_score, 1.0)

    def test_ending_diagonal_overbought(self):
        """Ending diagonal with overbought RSI but no divergence → 0.80."""
        prices = [128, 115, 120, 107, 115, 100]
        rsi =    [78,  40,  65,  35,  55,  45]
        # W5 price > W3 price, W5 RSI > W3 RSI → no divergence
        # But RSI > 70 → overbought → 0.80
        div_type, div_score = compute_diagonal_rsi_score(1, False, prices, rsi)
        self.assertEqual(div_type, 0)
        self.assertAlmostEqual(div_score, 0.80)

    def test_leading_diagonal_w3_strong(self):
        """Leading diagonal: W3 RSI exceeds W1 RSI → 0.80 (trend starting)."""
        prices = [128, 115, 125, 107, 118, 100]
        rsi =    [70,  40,  60,  35,  55,  45]
        # Leading: rsi_w3=rsi[0]=70, rsi_w1=rsi[4]=55 → W3 > W1 ✓
        div_type, div_score = compute_diagonal_rsi_score(1, True, prices, rsi)
        self.assertEqual(div_type, 0, "Leading diagonals don't set divergence type")
        self.assertAlmostEqual(div_score, 0.80)

    def test_leading_diagonal_w3_weak(self):
        """Leading diagonal: W3 RSI weaker than W1 → 0.40 (suspicious)."""
        prices = [128, 115, 125, 107, 118, 100]
        rsi =    [50,  40,  60,  35,  65,  45]
        # Leading: rsi_w3=rsi[0]=50, rsi_w1=rsi[4]=65 → W3 < W1 → weak
        div_type, div_score = compute_diagonal_rsi_score(1, True, prices, rsi)
        self.assertEqual(div_type, 0)
        self.assertAlmostEqual(div_score, 0.40)

    def test_neutral_ending_diagonal(self):
        """Ending diagonal with neutral RSI and no divergence → 0.5."""
        prices = [128, 115, 120, 107, 115, 100]
        rsi =    [60,  40,  55,  35,  50,  45]
        # No divergence (both higher), RSI not extreme → 0.5
        div_type, div_score = compute_diagonal_rsi_score(1, False, prices, rsi)
        self.assertEqual(div_type, 0)
        self.assertAlmostEqual(div_score, 0.5)


class TestOBVDivergenceDetection(unittest.TestCase):
    """Test OBV divergence detection functions."""

    def test_obv_regular_bearish_distribution(self):
        """Price higher high + OBV lower high → distribution (bearish)."""
        prices = [110, 90, 100]
        obv =    [5000, 4000, 5500]
        result = detect_obv_div_at_highs(prices, obv, 0, 2)
        self.assertEqual(result, 1)

    def test_obv_regular_bullish_accumulation(self):
        """Price lower low + OBV higher low → accumulation (bullish)."""
        prices = [85, 110, 90]
        obv =    [5200, 5500, 5000]
        result = detect_obv_div_at_lows(prices, obv, 0, 2)
        self.assertEqual(result, -1)

    def test_obv_no_divergence_concordant(self):
        """Price and OBV both higher → no divergence."""
        prices = [110, 90, 100]
        obv =    [5800, 4000, 5500]
        self.assertEqual(detect_obv_div_at_highs(prices, obv, 0, 2), 0)

    def test_obv_hidden_bearish(self):
        """Price lower high + OBV higher high → hidden bearish."""
        prices = [95, 90, 100]
        obv =    [5800, 4000, 5500]
        result = detect_obv_div_at_highs(prices, obv, 0, 2)
        self.assertEqual(result, 2)

    def test_obv_hidden_bullish(self):
        """Price higher low + OBV lower low → hidden bullish."""
        prices = [95, 110, 90]
        obv =    [4800, 5500, 5000]
        result = detect_obv_div_at_lows(prices, obv, 0, 2)
        self.assertEqual(result, -2)

    def test_obv_none_values(self):
        """None OBV values return 0."""
        prices = [110, 90, 100]
        obv =    [None, 4000, 5500]
        self.assertEqual(detect_obv_div_at_highs(prices, obv, 0, 2), 0)


class TestVolumeScoring(unittest.TestCase):
    """Test volume sub-scores and combined score."""

    def test_combined_volume_score_weights(self):
        """Verify combined score weights: 40% OBV + 30% wave + 30% VWAP = 100%."""
        result = compute_volume_score(1.0, 1.0, 1.0)
        self.assertAlmostEqual(result, 1.0)
        result = compute_volume_score(0.0, 0.0, 0.0)
        self.assertAlmostEqual(result, 0.0)

    def test_impulse_w3_highest_volume(self):
        """W3 highest, W5 declining → strong exhaustion (1.0)."""
        self.assertAlmostEqual(compute_impulse_wave_vol_score(1000, 2000, 800), 1.0)

    def test_impulse_w3_highest_w5_moderate(self):
        """W3 highest but W5 not less than W1 → classic impulse (0.85)."""
        self.assertAlmostEqual(compute_impulse_wave_vol_score(1000, 2000, 1200), 0.85)

    def test_impulse_w5_exceeds_w3(self):
        """W5 more volume than W3 → extended 5th, NOT exhaustion (0.15)."""
        self.assertAlmostEqual(compute_impulse_wave_vol_score(1000, 1500, 2000), 0.15)

    def test_impulse_equal_volume(self):
        """Equal volumes → neutral (0.5)."""
        self.assertAlmostEqual(compute_impulse_wave_vol_score(1000, 1000, 1000), 0.5)

    def test_vwap_bullish_premium(self):
        """Price >1% above VWAP for bullish → 1.0."""
        self.assertAlmostEqual(compute_vwap_score(2.0, True), 1.0)

    def test_vwap_bullish_above(self):
        """Price just above VWAP for bullish → 0.75."""
        self.assertAlmostEqual(compute_vwap_score(0.5, True), 0.75)

    def test_vwap_bullish_below(self):
        """Price slightly below VWAP for bullish → 0.35."""
        self.assertAlmostEqual(compute_vwap_score(-0.5, True), 0.35)

    def test_vwap_bullish_deep_below(self):
        """Price deep below VWAP for bullish → 0.15."""
        self.assertAlmostEqual(compute_vwap_score(-2.0, True), 0.15)

    def test_vwap_bearish_deep_below(self):
        """Price >1% below VWAP for bearish → 1.0 (confirms)."""
        self.assertAlmostEqual(compute_vwap_score(-2.0, False), 1.0)

    def test_vwap_bearish_above(self):
        """Price above VWAP for bearish → 0.35 (contradicts)."""
        self.assertAlmostEqual(compute_vwap_score(0.5, False), 0.35)

    def test_vwap_none(self):
        """None VWAP → neutral 0.5."""
        self.assertAlmostEqual(compute_vwap_score(None, True), 0.5)


class TestCompositeWithVolume(unittest.TestCase):
    """Test composite probability with volume component."""

    def test_six_component_weights_sum_to_1(self):
        """25 + 15 + 10 + 10 + 15 + 25 = 100."""
        self.assertAlmostEqual(0.25 + 0.15 + 0.10 + 0.10 + 0.15 + 0.25, 1.0)

    def test_all_perfect_with_volume(self):
        """All 6 components at 1.0 → 1.0."""
        result = compute_composite_probability(1.0, 1.0, 1.0, 1.0, p_rsi=1.0, p_vol=1.0)
        self.assertAlmostEqual(result, 1.0)

    def test_all_zero_with_volume(self):
        """All 6 components at 0.0 → 0.0."""
        result = compute_composite_probability(0.0, 0.0, 0.0, 0.0, p_rsi=0.0, p_vol=0.0)
        self.assertAlmostEqual(result, 0.0)

    def test_volume_and_pattern_equal_weight(self):
        """Volume and pattern both at 25% — should be equal contributors."""
        vol_only = compute_composite_probability(0.0, 0.0, 0.0, 0.0, p_rsi=0.0, p_vol=1.0)
        pat_only = compute_composite_probability(1.0, 0.0, 0.0, 0.0, p_rsi=0.0, p_vol=0.0)
        self.assertAlmostEqual(vol_only, pat_only)
        self.assertAlmostEqual(vol_only, 0.25)

    def test_volume_overrides_weak_exhaustion(self):
        """High volume score reduces exhaustion confidence.
        Pattern says exhaustion (1.0) but volume contradicts (0.15)."""
        with_vol = compute_composite_probability(1.0, 0.5, 0.5, 0.5, p_rsi=1.0, p_vol=0.15)
        without_vol = compute_composite_probability(1.0, 0.5, 0.5, 0.5, p_rsi=1.0, p_vol=0.5)
        self.assertLess(with_vol, without_vol, "Low volume score should lower composite")

    def test_volume_boost_strong_trend(self):
        """Volume confirming trend should boost composite."""
        weak = compute_composite_probability(0.6, 0.5, 0.5, 0.5, p_rsi=0.5, p_vol=0.5)
        strong = compute_composite_probability(0.6, 0.5, 0.5, 0.5, p_rsi=0.5, p_vol=1.0)
        self.assertGreater(strong, weak)
        self.assertAlmostEqual(strong - weak, 0.125)  # 0.5 * 0.25 = 0.125 difference


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

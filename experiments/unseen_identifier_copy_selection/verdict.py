"""Frozen gate evaluation + verdict-precedence engine for the unseen-identifier diagnostic.

Thresholds are the merged protocol-lock Decision 7 values; the precedence is the merged Decision 8
total order (first-match-wins). The verdict is computed mechanically from metrics — never inferred
from prose. Emitting a verdict here is a future-execution concern; this module only *computes* the
mapping and is exercised by unit tests with synthetic metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---- frozen gate thresholds (protocol-lock Decision 7) ----
C1_EXACT_MEAN, C1_SEED_FLOOR, C1_SEED_MIN, C1_TOKEN, C1_FAB = 0.85, 0.80, 4, 0.95, 0.02
C2_EXACT_MEAN, C2_SEED_FLOOR, C2_SEED_MIN, C2_POS_MIN, C2_WRONG, C2_FAB = 0.80, 0.75, 4, 0.70, 0.15, 0.02
C3_EXACT_MEAN, C3_SEED_FLOOR, C3_SEED_MIN, C3_FAB = 0.80, 0.75, 4, 0.0
C4_POS_MIN, C4_SPREAD = 0.75, 0.10
C5_DEGRADE = 0.05
C6_CONFIRM, C7_CONFIRM, C67_GAP_CONFIRM, C67_SEED_MIN = 0.90, 0.80, 0.10, 4
C6_FAIL_FLOOR, C7_FAIL_CEIL, C67_GAP_FAIL = 0.85, 0.70, 0.15
C67_NOCOPY = 0.70
C8_ABSTAIN, C8_FALSE_ANSWER, C8_FAB = 0.90, 0.05, 0.02


@dataclass(frozen=True)
class VerdictInputs:
    # aggregated (mean over final seeds) per-split quantities
    c1_exact: float
    c1_token: float
    c1_fabricated: float
    c2_exact: float
    c2_position_min: float
    c2_wrong_in_context: float
    c2_fabricated: float
    c3_exact: float
    c3_fabricated: float
    c4_position_min: float
    c4_spread: float
    c5_degradation: float
    c6_exact: float
    c7_exact: float
    c8_abstention: float
    c8_false_answer: float
    c8_fabricated: float
    # per-seed replication (>=4 of 5) booleans
    c1_seed_pass: tuple[bool, ...] = ()
    c2_seed_pass: tuple[bool, ...] = ()
    c3_seed_pass: tuple[bool, ...] = ()
    c7_seed_pass: tuple[bool, ...] = ()
    # integrity flags
    protocol_ok: bool = True
    determinism_ok: bool = True
    shortcut_ok: bool = True
    resource_ok: bool = True


@dataclass
class Verdict:
    label: str
    reasons: list = field(default_factory=list)


def _c1_pass(v: VerdictInputs) -> bool:
    return (v.c1_exact >= C1_EXACT_MEAN and sum(v.c1_seed_pass) >= C1_SEED_MIN
            and v.c1_token >= C1_TOKEN and v.c1_fabricated <= C1_FAB)


def _c2_pass(v: VerdictInputs) -> bool:
    return (v.c2_exact >= C2_EXACT_MEAN and sum(v.c2_seed_pass) >= C2_SEED_MIN
            and v.c2_position_min >= C2_POS_MIN and v.c2_wrong_in_context <= C2_WRONG
            and v.c2_fabricated <= C2_FAB)


def _c3_pass(v: VerdictInputs) -> bool:
    return (v.c3_exact >= C3_EXACT_MEAN and sum(v.c3_seed_pass) >= C3_SEED_MIN
            and v.c3_fabricated <= C3_FAB)


def _c4_pass(v: VerdictInputs) -> bool:
    return v.c4_position_min >= C4_POS_MIN and v.c4_spread <= C4_SPREAD


def _c5_pass(v: VerdictInputs) -> bool:
    return v.c5_degradation <= C5_DEGRADE


def _c7_generalization_pass(v: VerdictInputs) -> bool:
    return (v.c6_exact >= C6_CONFIRM and v.c7_exact >= C7_CONFIRM
            and (v.c6_exact - v.c7_exact) <= C67_GAP_CONFIRM
            and sum(v.c7_seed_pass) >= C67_SEED_MIN)


def _generalization_failed(v: VerdictInputs) -> bool:
    return (v.c6_exact >= C6_FAIL_FLOOR and v.c7_exact < C7_FAIL_CEIL) or (v.c6_exact - v.c7_exact) > C67_GAP_FAIL


def _no_copy_operation(v: VerdictInputs) -> bool:
    return v.c6_exact < C67_NOCOPY and v.c7_exact < C67_NOCOPY and not _c1_pass(v)


def _c8_pass(v: VerdictInputs) -> bool:
    return (v.c8_abstention >= C8_ABSTAIN and v.c8_false_answer <= C8_FALSE_ANSWER
            and v.c8_fabricated <= C8_FAB)


def evaluate(v: VerdictInputs) -> Verdict:
    """Apply the frozen first-match-wins precedence. Lower-priority failures are recorded as notes."""
    reasons: list = []
    # 1. integrity / protocol (shortcut anomaly that reached execution is a protocol violation)
    if not v.protocol_ok or not v.determinism_ok or not v.shortcut_ok:
        reasons.append("integrity/protocol/shortcut gate failed")
        return Verdict("UNSEEN_IDENTIFIER_PROTOCOL_VIOLATED", reasons)
    # 2. resource
    if not v.resource_ok:
        return Verdict("UNSEEN_IDENTIFIER_RESOURCE_BLOCKED", ["frozen protocol could not complete within limits"])
    # 3. copy / generalization base (before selection/evidence/abstention)
    if _generalization_failed(v) and not _no_copy_operation(v):
        reasons.append(f"C6={v.c6_exact:.3f} C7={v.c7_exact:.3f}: copy exists on seen, fails to generalize")
        return Verdict("UNSEEN_IDENTIFIER_GENERALIZATION_FAILED", reasons)
    if _no_copy_operation(v):
        reasons.append(f"C6={v.c6_exact:.3f} C7={v.c7_exact:.3f}, C1 below gate: no demonstrated copy operation")
        return Verdict("UNSEEN_IDENTIFIER_COPY_CAPABILITY_NOT_FOUND", reasons)
    # copy-masks-selection: never emit a selection verdict while C1 is below gate.
    if not _c1_pass(v):
        reasons.append("C1 below gate; selection not independently diagnosable")
        # Never label "copy absent" when seen-copy is competent (protocol-lock Decision 8 guard).
        if v.c6_exact >= C6_FAIL_FLOOR:
            return Verdict("UNSEEN_IDENTIFIER_GENERALIZATION_FAILED", reasons)
        return Verdict("UNSEEN_IDENTIFIER_COPY_CAPABILITY_NOT_FOUND", reasons)
    # 4. selection (C1 passes)
    if not _c2_pass(v):
        reasons.append("C1 passes, C2 fails: relation selection not established")
        return Verdict("UNSEEN_IDENTIFIER_SELECTION_FAILED", reasons)  # COPY_ONLY_PARTIAL synonym
    # 5. evidence lookup
    if not _c3_pass(v):
        return Verdict("UNSEEN_IDENTIFIER_EVIDENCE_LOOKUP_FAILED", ["C1/C2 sufficient, C3 fails"])
    # 6. abstention (ladder otherwise sufficient)
    if not _c8_pass(v):
        return Verdict("UNSEEN_IDENTIFIER_ABSTENTION_GATE_FAILED", ["C8 abstention gate failed"])
    # 7. confirmed (requires C4, C5, C7-generalization too)
    if _c4_pass(v) and _c5_pass(v) and _c7_generalization_pass(v):
        return Verdict("UNSEEN_IDENTIFIER_COPY_SELECTION_CONFIRMED", ["all gates pass"])
    # otherwise a residual capability gate (C4/C5/C7) failed with copy+selection+evidence+abstention ok
    reasons.append("copy/selection/evidence/abstention pass but a robustness/generalization gate failed")
    return Verdict("UNSEEN_IDENTIFIER_GENERALIZATION_FAILED", reasons)

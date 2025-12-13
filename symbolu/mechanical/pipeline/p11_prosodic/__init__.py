"""
P11 - Prosodic Evidence Capture Engine

P11 is a WITNESS-ONLY phase. It observes, records, and attests to
acoustic/prosodic parameters chosen by P10 — without modifying them.

P11's responsibility is to:
- Observe P10 output
- Record prosodic/acoustic evidence
- Validate invariants
- Expose violations (if any)
- Never change behavior
- Never influence upstream or downstream decisions

P11 does NOT:
- Generate speech
- Smooth prosody
- "Improve" expressiveness
- Modify P10 output
- Correct violations (only detect them)

Architectural Notes:
- P11 is the prosodic evidence capture phase
- P11 observes but never modifies acoustic parameters
- P11 validates invariants but does NOT correct violations
- P12+ may read P11; P10 and earlier may not
- Authority flows downward; P11 is subordinate to PO1-P10

Components:
- ProsodicEvidenceFrame: Output dataclass capturing acoustic attestation
- P11ProsodicResolver: Witness-only prosodic evidence capture resolver
- Invariant check functions for validation

CRITICAL ARCHITECTURAL INVARIANT:
    P11 exists to observe, not to optimize.
    Sound must obey meaning.
    Meaning must never obey sound.

Usage:
    from symbolu.mechanical.pipeline.p11_prosodic import (
        P11ProsodicResolver,
        ProsodicEvidenceFrame,
    )

    resolver = P11ProsodicResolver()
    evidence = resolver.capture(ctx)
    # evidence contains attested acoustic parameters and invariant results

    # Or use the integration shim:
    from symbolu.mechanical.pipeline.p11_prosodic.p11_integration import maybe_run_p11
    maybe_run_p11(ctx)
    # ctx.p11_prosodic_evidence is now set

Authority Model:
- P11 receives AcousticParameterFrame from P10
- P11 copies all acoustic parameters verbatim (no modification)
- P11 validates invariants but does NOT correct them
- P11 produces ProsodicEvidenceFrame (read-only, non-actuating)
"""

from .p11_prosodic_schema import (
    ProsodicEvidenceFrame,
    P11_VERSION,
)
from .p11_prosodic_resolver import (
    P11ProsodicResolver,
    # Invariant check functions (for testing)
    check_speech_rate_within_bounds,
    check_energy_within_bounds,
    check_pitch_within_bounds,
    check_pause_policy_respected,
    check_no_emotion_amplification,
    check_no_certainty_injection,
    check_no_emphasis_override,
    check_lexical_integrity_preserved,
    check_regime_constraints_respected,
)


__all__ = [
    # Dataclasses
    "ProsodicEvidenceFrame",
    # Resolver
    "P11ProsodicResolver",
    # Constants
    "P11_VERSION",
    # Invariant check functions
    "check_speech_rate_within_bounds",
    "check_energy_within_bounds",
    "check_pitch_within_bounds",
    "check_pause_policy_respected",
    "check_no_emotion_amplification",
    "check_no_certainty_injection",
    "check_no_emphasis_override",
    "check_lexical_integrity_preserved",
    "check_regime_constraints_respected",
]

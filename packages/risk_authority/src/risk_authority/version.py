"""Single source of truth for the package version."""

from __future__ import annotations

#: ``0.5.0`` is R-12b: ``RiskDecision`` gains ``evaluated_at``, so the evaluator's stamp
#: travels inside the digest-bound decision snapshot rather than only on an outer field no
#: digest covers. Additive and optional — an existing caller is unaffected — but every
#: decision snapshot minted from this version gains a key, which moves its digest.
#: ``0.6.0`` is Phase 5 envelope issuance (ADR
#: ``ADR_RISK_AUTHORITY_PHASE5_ENVELOPE_ISSUANCE_RATIFICATION``): the ``EnvelopeIssuanceSeam``,
#: the ``EnvelopeSignerPort`` and the additive ``EnvelopeBindings.artifact_bindings``. Additive
#: for every existing caller; an envelope minted from this version carries one more binding key,
#: which moves its canonical signing payload.
__version__ = "0.6.0"

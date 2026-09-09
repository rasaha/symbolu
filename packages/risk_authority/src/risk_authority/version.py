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
#: ``0.7.0`` is durable persistence (ADR_RISK_AUTHORITY_DURABLE_PERSISTENCE_SCOPING D-1 … D-5):
#: the SQLite store, the strict codec, durable ids and revocation, and production mode
#: refusing the in-memory reference stores.
#: ``0.8.0`` is Phase 5C action admission, Risk Authority half (ADR
#: ``ADR_CLOUD_SCALING_PHASE5C_ACTION_ADMISSION_SCOPING`` D-1, D-3, D-4, D-5): the
#: ``ActionAdmissionSeam``, the ``AuthorizationRepository`` port with both adapters, derived
#: authorization ids with ``REPLAYED`` re-admission, and ``ActionAuthorization`` gaining a
#: typed ``expires_at`` and a ``disposition``. Additive for every existing caller.
#: ``0.9.0`` enforces signing-key validity windows (issue #1398, F-G item 2). ``KeyRing``
#: now holds ``VerificationKeyRecord`` entries so ``from_records`` stops discarding
#: ``not_before`` / ``not_after``; ``EnvelopeVerifier`` resolves through the new
#: ``resolve_record`` and refuses an out-of-window key *before* checking the signature; and
#: ``EnvelopeIssuer`` independently refuses to sign outside the window, including for an
#: external signer that declares one through the additive ``WindowedEnvelopeSignerPort``.
#: The key interval is half-open ``[not_before, not_after)``, deliberately unlike the
#: envelope's inclusive window, which is unchanged. An absent bound is unbounded-valid, so
#: every existing windowless key and signer behaves exactly as before; the MINOR bump is for
#: the ``KeyRing`` entry-type change, not a behavior change for existing callers. No
#: canonical serialization, digest or signature format is touched.
#: ``0.10.0`` closes the production-v1 clock asymmetry (issue #1398 item 1, D-B). The
#: trusted production evaluation seam now rejects a caller-supplied ``evaluation_time``
#: on **both** v1 and v2 with the same typed ``CALLER_SUPPLIED_EVALUATION_TIME``
#: non-decision, stamped with the trusted clock. This narrowly supersedes the earlier
#: "v1 honors evaluation_time in any mode" decision: the two schema versions were held to
#: different clock-authority rules in one seam for no reason but the order they were
#: built. Reference mode is unchanged and still honors the field, which is what keeps the
#: conformance suites and the distribution verifiers deterministically replayable. No
#: other v1 behavior, and no canonical serialization, digest or signature format, changes.
__version__ = "0.10.0"

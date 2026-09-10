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
#: ``0.11.0`` makes the envelope's own validity window **half-open**,
#: ``[not_before, expires_at)``: at exactly ``expires_at`` an envelope is now expired,
#: where it was previously still valid. Decision expiry moves with it, at both the
#: issuance seam and ``EnvelopeIssuer``, so the stated rule matches the effective
#: behavior rather than falling through to a zero-width TTL. This supersedes the earlier
#: ratified reading in which the envelope alone was inclusive at both ends. The argument
#: that retired it: the absence of chained envelope windows explains why an inclusive
#: upper bound caused no overlap, but never why a security validity artifact should stay
#: usable at its own stated expiry — and every usable downstream consumer already refused
#: there, so the envelope was the last artifact saying yes at an instant nothing could act
#: on. Keys, envelopes, decisions, grants and ``ExecutionAuthorization`` now share one
#: shape: inclusive lower bound, exclusive upper bound. No canonical serialization, digest
#: or signature format is touched, and an envelope issued before this version still
#: verifies — it simply stops authorizing one microsecond earlier than it used to.
#: **Correction, recorded at 0.12.0:** the sentence above naming "grants" overclaimed.
#: ``AuthorityGrant.is_active`` was still inclusive at 0.11.0; only the credential-grant
#: validity window was half-open. 0.12.0 is what makes the claim true.
#: ``0.12.0`` closes the delegation-reach exposure that the temporal-boundary audit found
#: behind ``AuthorityGrant``. Two defects, neither closed by the other.
#: ``AuthorityGrant.is_active`` becomes half-open: it is an authorization gate —
#: ``authority_violations`` calls it at the moment a ``RiskDecision`` is minted — not a
#: freshness report, so a grant expiring at exactly ``now`` may no longer mint. And
#: ``RiskDecision.expires_at``, previously ``now + DEFAULT_DECISION_TTL`` uncapped, is now
#: capped at ``min(now + ttl, grant.expires_at, freshness_horizon)``. The two together are
#: what matter: with only the operator, the boundary instant moved one microsecond and a
#: grant expiring a moment later still yielded a full hour of decision validity plus an
#: envelope TTL on top — measured at 1:29:59.999999 of machine authority past an expired
#: delegation. ``EnvelopeIssuer.issue`` now also caps the envelope by its decision's
#: expiry, which only the issuance seam did before, so a direct caller with a generous
#: ``ttl`` can no longer mint an envelope outliving the decision that justified it.
#: ``freshness_horizon`` is added to ``domain.controls`` and threaded through
#: ``DecisionAuthorityPort.issue_decision`` as an optional keyword, so an existing
#: implementer is unaffected. Control results created through the evaluation seam carry no
#: ``valid_until``, so the freshness cap is inert on the reference flow and no existing
#: decision moves. No canonical serialization, digest or signature format is touched.
#: ``0.13.0`` completes the prerequisite cap and replaces the "one temporal rule" framing.
#: The governing principle: *a point-in-time fact may remain valid at its final instant,
#: but it cannot create authority that survives beyond that instant.* Two categories, not
#: one rule — operational validity (keys, envelopes, authority grants, decisions,
#: authorizations, execution authorizations) is half-open; point-in-time validity (subject
#: assertions, evidence/binding/control freshness) is inclusive and stays that way.
#: Prerequisites are now passed as a NAMED mapping (``prerequisite_horizons``), superseding
#: 0.12.0's scalar ``freshness_horizon`` keyword, because the ruling requires identifying
#: which prerequisite bound a decision — and the refusal names it. Evidence is covered
#: transitively by construction —
#: ``binding._freshness_is_monotonic`` refuses a trusted result outliving its backing
#: evidence, so the control horizon is already no later than the evidence floor. A
#: zero-width subject context stays ratified and constructible.
#: **The subject bullet was blocked at 0.13.0 and is completed at 0.14.0** — see below.
#: ``0.14.0`` completes T-2 and adds the reason code T-3 needed.
#: ``SubjectContext.subject_valid_until`` now caps the decision, through the additive
#: ``DecisionRequest.subject_valid_until`` that the v2 evaluation seam populates from the
#: re-validated context. The subject window itself is untouched and still inclusive at both
#: ends: a zero-width ``SubjectContext`` stays ratified and constructible, and at its
#: terminal instant it is still valid — it simply mints nothing, because no positive window
#: remains for a decision to occupy.
#: ``NoRemainingValidityError`` (a subclass of ``AuthorityDeniedError``, so every existing
#: handler keeps working) carries the name of the prerequisite that bound, and the seam maps
#: it by type and field rather than by parsing a reason string. That feeds the new
#: ``SubjectRiskNonDecisionReason.NO_REMAINING_SUBJECT_VALIDITY``, which replaces the
#: misattributing ``AUTHORITY_UNAVAILABLE`` on this path: the subject is not expired and the
#: evaluator principal is entitled, so neither pre-existing member described the condition.
#: **This moves three ratified digests, under an explicit re-freeze ruling.** One semantic
#: field moved — the capped ``decision_expires_at_fact``, 01:05:00 -> 00:08:10 — and the
#: digests over it followed: decision sha256:6aba137d… -> sha256:4636dee2…, candidate
#: sha256:357bb3d4… -> sha256:7ffeefce…, and the transitive verified-artifact digest
#: sha256:fefe4884… -> sha256:596b4631…. No canonicalization, field set or signature format
#: changed and nothing was re-signed; the superseded values are pinned as negative anchors
#: so a silent revert is a failure rather than a re-baseline.
__version__ = "0.14.0"

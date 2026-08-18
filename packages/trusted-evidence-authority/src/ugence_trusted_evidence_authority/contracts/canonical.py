"""Versioned, domain-separated canonicalization for trusted-evidence contracts.

**One** encoder produces the bytes behind **one** digest path. There is no
second serializer, no legacy digest, no dual-acceptance fallback, and no
alternate encoding a caller can select — ADR §22.2 requires canonical bytes to
be "a pure function of the payload", and two functions of the payload are not
one function.

Exact encoding rules (canonicalization ``v1``)
----------------------------------------------
* **Serialization**: UTF-8 JSON via ``json.dumps`` with ``sort_keys=True``,
  ``separators=(",", ":")`` (no insignificant whitespace) and
  ``ensure_ascii=False``. The digest input is exactly those UTF-8 bytes.
* **Key ordering**: object keys sorted lexicographically by code point.
* **Field inclusion is total and deterministic**: every dataclass field is
  included, always, by declared name. Nothing is dropped when empty, and no
  field is conditionally omitted — a conditional omission would let two
  different payloads share one byte sequence.
* **``None`` is represented explicitly** as JSON ``null``. ``None`` and ``""``
  are therefore distinct byte sequences and distinct digests.
* **Datetimes** must be timezone-aware; they are normalized to UTC with
  ``astimezone(timezone.utc)`` — pure arithmetic against the value's own
  offset — and rendered ``%Y-%m-%dT%H:%M:%S.%fZ``, which **preserves
  microseconds**. Two spellings of one instant therefore render identically.
  **A naive datetime is rejected**, here and at every construction boundary
  (ADR §22.4): a value with no offset does not name an instant, and guessing UTC
  would silently invent one.
* **Strings** must already be Unicode **NFC**; non-canonical input is rejected,
  never silently normalized (see the posture note below).
* **``bool`` before ``int``** — ``bool`` subclasses ``int`` in Python, so it is
  dispatched first and serialized as a JSON boolean, never as ``0``/``1``.
* **``float`` is rejected outright.** This subsumes the rejection of non-finite
  values (``nan``, ``inf``, ``-inf``), which have no canonical JSON form at all;
  exact values in these contracts are integers or strings. It matches the merged
  ``ugence_policy_authority`` canonicalization ``v1`` posture.
* **Ordered collections** (``list``/``tuple``) preserve order — order is
  semantic wherever these contracts carry a sequence (a chain of custody is
  ordered), and a caller-supplied set-like sequence is normalized into its
  ratified order *before* it reaches the encoder, not by the encoder.
* **Mappings and ``bytes`` are rejected.** No contract in this package carries
  either, at TEV-1 or TEV-2. Rejecting mappings structurally enforces the ADR's
  rule that evidence coordinates are never collapsed into a free-form metadata
  dictionary. Rejecting ``bytes`` is what makes it structurally impossible for
  private key material to reach a canonical byte sequence or a digest: TEV-2
  carries signatures and public keys as canonical lowercase hex **strings**, and
  the one type that holds a private seed is not a contract and is never
  canonicalized.
* **Unknown types fail closed** (ADR §22.8). There is **no** ``default=`` hook,
  no ``str()`` fallback, and no ``repr()`` anywhere in this module: an
  unrecognized type raises. A permissive fallback would make the digest a
  function of a Python object's textual rendering — including its ``id()`` for
  any default ``__repr__`` — which is neither deterministic across processes nor
  a function of the payload.

Determinism inputs
------------------
The encoder consults **no** wall clock, locale, timezone database, environment
variable, filesystem or network. ``astimezone`` is always called with an
explicit ``timezone.utc`` target, never the zero-argument form that would infer
the local zone. Package tests assert this structurally over the whole source
tree, not merely for one code path.

Unicode posture — reject, do not normalize
------------------------------------------
Silent NFC normalization would map two *structurally different* artifacts onto
one digest: an NFD-spelled and an NFC-spelled coordinate would become
indistinguishable, so a digest over one would attest a value nobody wrote.
Rejecting keeps the digest a faithful function of the exact bytes the author
committed to. The posture is bound to the canonicalization version, so changing
it requires a new version. This is the merged ``ugence_policy_authority`` §12
posture (a), adopted rather than re-litigated.

Domain separation and versioning
--------------------------------
ADR §22.1 requires every digest to bind a canonicalization version and a
domain-separation tag, and **DD-9 explicitly leaves the exact byte constants to
TEV-1/TEV-2**. This module is where both milestones resolve them: one tag per
artifact class, minted by the milestone that first ships that class.

**TEV-1 minted two**, and neither has changed:

* :data:`EVIDENCE_IDENTITY_DIGEST_DOMAIN` — the evidence-identity family:
  :class:`~.identity.CanonicalEvidenceIdentity`, its nested coordinates, and the
  verification *request* that names one.
* :data:`EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN` — the structural
  :class:`~.receipts.EvidenceVerificationReceiptPayload`, defined by TEV-1
  because §13.3 requires the canonical payload, its canonicalization version and
  its domain tag to be "unambiguous, versioned, and **fixed before signing
  exists**". Fixing the tag then was the precondition for TEV-2's signer, and
  TEV-2's signer now binds exactly that tag.

  The payload it separates remains **caller-constructible** and permanently
  ``STRUCTURAL_UNVERIFIED``. That has not changed either: TEV-2 does not raise a
  payload's status, it **wraps** the payload in a signed envelope and answers
  the trust question by verifying a signature against a resolved trust anchor.

**TEV-2 mints five**, one per artifact class it introduces:
:data:`TRUST_ANCHOR_RECORD_DIGEST_DOMAIN` (configured key trust),
:data:`SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN` (a producer-signed evidence
item), :data:`SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN` (the authority-signed
receipt), :data:`EVIDENCE_VERIFICATION_RESULT_DIGEST_DOMAIN` (determinations,
protocol results and receipt verifications) and
:data:`EVIDENCE_VERIFICATION_AUDIT_RECORD_DIGEST_DOMAIN`.

Minting a domain grants nothing; it separates byte spaces. What a domain tag
*does* buy is §26.6: "domain separation prevents cross-artifact signature
reuse". Because the domain is framed into the bytes, an evidence digest can
never be read as a receipt digest, an envelope digest can never be read as the
payload content digest it wraps, and a verification *finding* can never be read
as an artifact an authority attested.

The **benchmark** domain remains unminted: no benchmark artifact exists, and its
tag belongs to its own ratified milestone (BR-1/BR-2). A tag without an artifact
is an unused constant a later milestone would have to either honour or break.

Every canonical byte sequence is framed as::

    {"body": {...}, "canonicalization": <version>, "domain": <tag>, "type": <name>}

so the same body under two contract types can never produce the same bytes.

Independent verification
------------------------
:func:`canonical_bytes` and :func:`canonical_digest` are public and pure. A
third party holding a contract and this module can recompute any digest without
package internals; the package tests pin representative byte strings and
reconstruct one digest from hand-written literal bytes and ``hashlib`` alone.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .errors import TrustedEvidenceCanonicalizationError

__all__ = [
    "TRUSTED_EVIDENCE_CANONICALIZATION_VERSION",
    "EVIDENCE_IDENTITY_DIGEST_DOMAIN",
    "EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN",
    "TRUST_ANCHOR_RECORD_DIGEST_DOMAIN",
    "SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN",
    "SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN",
    "EVIDENCE_VERIFICATION_RESULT_DIGEST_DOMAIN",
    "EVIDENCE_VERIFICATION_AUDIT_RECORD_DIGEST_DOMAIN",
    "canonical_bytes",
    "canonical_digest",
]

#: The canonicalization rule-set version bound into every digest (ADR §22.1).
#: Changing any rule in this module's docstring requires a new version string.
TRUSTED_EVIDENCE_CANONICALIZATION_VERSION = (
    "ugence.trusted-evidence-authority/canonicalization/v1"
)

#: The domain-separation tag bound into every evidence-identity digest.
#:
#: Covers the evidence-identity family: the identity itself, its nested
#: coordinates, and the verification *request* that names one. All describe the
#: same artifact class — an evidence item and what a caller expects of it.
EVIDENCE_IDENTITY_DIGEST_DOMAIN = (
    "ugence.trusted-evidence-authority/evidence-identity/v1"
)

#: The domain-separation tag bound into every receipt-payload digest.
#:
#: A receipt payload is a **different artifact class** from the evidence it
#: describes (ADR §13.1.8 — it "remains distinct from the underlying evidence"),
#: so it gets its own domain. ADR §26.6 requires that a digest or signature valid
#: in one domain must not be reusable in another, and §13.3 requires the domain
#: tag to be "unambiguous, versioned, and **fixed before signing exists**" —
#: which is precisely why TEV-1 mints it, under DD-9, rather than waiting for the
#: TEV-2 signer that will bind it.
#:
#: The tag separates byte spaces and nothing more. The payload it separates stays
#: caller-constructible and permanently ``STRUCTURAL_UNVERIFIED``; signing,
#: signed envelopes, authenticity decisions, trust-anchor resolution, key
#: validation, revocation checking and authority-issued receipts are all TEV-2.
EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN = (
    "ugence.trusted-evidence-authority/evidence-verification-receipt-payload/v1"
)

#: The domain-separation tag bound into every trust-anchor digest (TEV-2).
#:
#: Covers the trust-anchor family: :class:`~..authority.trust.TrustAnchorRecord`,
#: its :class:`~..authority.trust.TrustAnchorCoordinate`, its
#: :class:`~..authority.trust.KeyRevocation` and the
#: :class:`~..authority.trust.TrustAnchorResolution` that reports a lookup. All
#: describe configured key trust — a different artifact class from evidence,
#: from a receipt payload, and from a signed artifact.
TRUST_ANCHOR_RECORD_DIGEST_DOMAIN = (
    "ugence.trusted-evidence-authority/trust-anchor-record/v1"
)

#: The domain-separation tag bound into every producer-signed-submission digest.
SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN = (
    "ugence.trusted-evidence-authority/signed-evidence-submission-digest/v1"
)

#: The domain-separation tag bound into every signed-receipt-envelope digest.
#:
#: Distinct from :data:`EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN`:
#: the payload digest is the §13.3 *content* digest, taken over bytes that
#: contain no signature, and the envelope digest is an audit handle over the
#: complete signed artifact. Keeping them in separate byte spaces means one can
#: never be presented as the other.
SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN = (
    "ugence.trusted-evidence-authority/signed-receipt-envelope-digest/v1"
)

#: The domain-separation tag bound into every TEV-2 verification-result digest.
#:
#: Covers a protocol's execution report. It is a *finding about* an artifact,
#: never an artifact a signature covers: no signing input in this package binds
#: one, so a result digest can never be mistaken for something an authority
#: attested.
EVIDENCE_VERIFICATION_RESULT_DIGEST_DOMAIN = (
    "ugence.trusted-evidence-authority/evidence-verification-result/v1"
)

#: The domain-separation tag bound into every verification audit-record digest.
EVIDENCE_VERIFICATION_AUDIT_RECORD_DIGEST_DOMAIN = (
    "ugence.trusted-evidence-authority/evidence-verification-audit-record/v1"
)

#: Contract type name -> domain tag, for every type outside the default domain.
#:
#: The single source of truth for domain selection. Keyed by type name so this
#: module stays import-cycle-free (the contracts import the encoder, never the
#: reverse). Domain separation does not rest on this mapping alone: the frame
#: also binds the contract type name, so two types can never collide even inside
#: one domain.
#:
#: TEV-1 shipped exactly one entry — the structural receipt payload — and TEV-2
#: added one per artifact class it introduced. Everything else falls back to the
#: evidence-identity domain. Membership here assigns a byte space; it grants no
#: trust to any type it names.
#:
#: **The TEV-1 entry is unchanged.** Adding keys leaves every existing key's
#: value byte-identical, so every TEV-1 digest — including the four pinned
#: vectors — is exactly what it was before TEV-2, and the package tests pin all
#: four to prove it.
#: The domain an unregistered dataclass is framed under. Named rather than
#: inlined as a ``.get`` default, so the fallback is visible where it is chosen
#: and greppable from anywhere. Its value is TEV-1's evidence-identity domain,
#: unchanged, because changing it would move every TEV-1 pinned digest.
UNREGISTERED_TYPE_DIGEST_DOMAIN = EVIDENCE_IDENTITY_DIGEST_DOMAIN

_DOMAIN_BY_TYPE_NAME = {
    # -- TEV-1 (frozen) ---------------------------------------------------- #
    #
    # The evidence-identity family. These were previously served by a *default*
    # on the lookup below rather than by entries here, which meant any
    # unregistered type silently acquired the evidence-identity domain — a
    # silent cross-domain assignment, and exactly the class of defect the
    # closure-audit truthiness sweep looks for. They are enumerated now and the
    # lookup has no fallback. Every value is the domain that type already used,
    # so no digest moves: the four pinned TEV-1 vectors are unchanged.
    "CanonicalEvidenceIdentity": EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    "EvidenceSchemaRef": EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    "EvidenceObservation": EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    "EvidenceScopeBinding": EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    "EvidenceClaimBinding": EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    "EvidenceProvenanceChain": EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    "ApplicabilityCoordinate": EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    "EvidenceVerificationRequest": EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    "EvidenceVerificationReceiptPayload": (
        EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN
    ),
    # -- TEV-2: trust-anchor family ---------------------------------------- #
    "TrustAnchorRecord": TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    "TrustAnchorCoordinate": TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    "KeyRevocation": TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    "TrustAnchorResolution": TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    # -- TEV-2: signed artifacts ------------------------------------------- #
    "SignedEvidenceSubmission": SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN,
    "SignedEvidenceVerificationReceipt": SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN,
    # -- TEV-2: protocol reports, never attested artifacts ----------------- #
    # ``EvidenceVerificationDetermination``, ``SignatureOnlyVerificationResult``
    # and ``ScopeBoundVerificationResult`` are deliberately **absent**: each
    # carries a private capability token, and the encoder's
    # total-field-inclusion rule (§22.2) admits no conditional omission, so none
    # of them is canonicalizable at all. Their auditable counterpart is
    # ``EvidenceVerificationAuditRecord``, below. ``ReceiptSigningInput`` is
    # absent for the same reason, and ``ReceiptScopeExpectation`` because it is
    # a consumer's *question*, not an artifact — it carries its own
    # ``expectation_digest()`` in its own domain, and giving it a second
    # spelling here would be the second digest §22.11 refuses.
    "ProtocolExecutionResult": EVIDENCE_VERIFICATION_RESULT_DIGEST_DOMAIN,
    # -- TEV-2: deterministic audit ---------------------------------------- #
    "EvidenceVerificationAuditRecord": (
        EVIDENCE_VERIFICATION_AUDIT_RECORD_DIGEST_DOMAIN
    ),
}

_TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _require_nfc(value: str, path: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise TrustedEvidenceCanonicalizationError(
            f"{path}: string is not Unicode NFC-normalized; trusted-evidence "
            "contracts reject non-canonical input rather than silently "
            f"normalizing it ({TRUSTED_EVIDENCE_CANONICALIZATION_VERSION})"
        )
    return value


def _format_datetime(value: datetime, path: str) -> str:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise TrustedEvidenceCanonicalizationError(
            f"{path}: a naive datetime is not a well-defined instant and must "
            "not enter a canonical byte sequence, a validity interval, or a digest"
        )
    return value.astimezone(timezone.utc).strftime(_TIMESTAMP_FMT)


def _to_canonical_obj(value: Any, path: str) -> Any:
    """Recursively convert ``value`` into a JSON-canonical structure.

    The result contains only ``dict`` (string keys), ``list``, ``str``, ``int``,
    ``bool`` and ``None``. Every rejection carries the offending path.
    """

    if value is None:
        return None
    # ``bool`` before ``int`` — ``bool`` subclasses ``int``.
    if isinstance(value, bool):
        return value
    # ``float`` before any numeric handling: rejected outright, which covers
    # nan/inf/-inf as well as every finite float.
    if isinstance(value, float):
        raise TrustedEvidenceCanonicalizationError(
            f"{path}: float is not canonicalizable — a governed coordinate must "
            "be an exact integer or a string (this also rejects nan/inf/-inf, "
            "which have no canonical JSON form)"
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return _require_nfc(value, path)
    if isinstance(value, Enum):
        return _to_canonical_obj(value.value, path)
    if isinstance(value, datetime):
        return _format_datetime(value, path)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            _require_nfc(f.name, f"{path}.{f.name}"): _to_canonical_obj(
                getattr(value, f.name), f"{path}.{f.name}"
            )
            for f in fields(value)
        }
    if isinstance(value, (list, tuple)):
        return [_to_canonical_obj(v, f"{path}[{i}]") for i, v in enumerate(value)]
    raise TrustedEvidenceCanonicalizationError(
        f"{path}: type {type(value).__name__!r} is not canonicalizable; the "
        "encoder has no permissive fallback and never renders an unknown object"
    )


def canonical_bytes(contract: Any) -> bytes:
    """Return the exact UTF-8 bytes :func:`canonical_digest` is computed over.

    ``contract`` must be a frozen dataclass instance from this package. The
    returned bytes are the framed, domain-separated, version-labelled encoding
    described in the module docstring.

    Two contracts that compare equal always produce byte-identical output,
    including when their instants were written with different UTC offsets::

        if a == b:
            assert canonical_bytes(a) == canonical_bytes(b)

    Two contracts differing in **any** load-bearing coordinate always produce
    different output.
    """

    if not is_dataclass(contract) or isinstance(contract, type):
        raise TrustedEvidenceCanonicalizationError(
            "canonical_bytes expects a trusted-evidence contract instance "
            f"(got {type(contract).__name__})"
        )
    type_name = type(contract).__name__
    # Membership, then an explicitly named domain — never a ``.get`` default
    # that would leave the fallback invisible at the call site. Both branches
    # are ratified TEV-1 behaviour and neither moves a digest.
    #
    # An unregistered type takes :data:`UNREGISTERED_TYPE_DIGEST_DOMAIN`, and
    # that is safe rather than lax: ``type`` is itself a framed field, so a
    # subclass, a look-alike or any foreign dataclass gets bytes that differ
    # from every registered type's and can never be presented as one. It is the
    # property ``test_a_subclass_can_lie_about_itself_but_gets_its_own_digest``
    # pins. What the fallback must never do is give an unregistered type a
    # *registered* type's domain, and it does not.
    if type_name in _DOMAIN_BY_TYPE_NAME:
        domain = _DOMAIN_BY_TYPE_NAME[type_name]
    else:
        domain = UNREGISTERED_TYPE_DIGEST_DOMAIN
    framed = {
        "canonicalization": TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
        "domain": domain,
        "type": type_name,
        "body": _to_canonical_obj(contract, "$"),
    }
    return json.dumps(
        framed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_digest(contract: Any) -> str:
    """Return the bare lowercase 64-char sha-256 hex digest of the canonical bytes.

    The digest is computed **solely** from :func:`canonical_bytes` — no other
    input, no salt, no clock, no side channel. It is an identity fingerprint. It
    is **not** evidence, not a signature, not an authenticity proof, and not an
    admission decision: ADR §8.1.3 — "possession is not validity" — and §10.5
    together mean that computing or matching a digest establishes nothing about
    where the content came from.
    """

    return hashlib.sha256(canonical_bytes(contract)).hexdigest()

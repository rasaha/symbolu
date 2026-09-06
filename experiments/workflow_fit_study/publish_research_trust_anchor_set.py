#!/usr/bin/env python3
"""Publish the research-only trust-anchor-set snapshot for the signed workflow-fit study (SR-3).

The snapshot carries exactly one anchor — the comparison engine's research key
under ``COMPARISON_RESULT_ATTESTATION`` — and is signed by the research
publication root, whose seed lives **only here** and is distinct from the engine
seed held by ``signed_admission.py`` (SR-0). The document is deterministic: the
same seeds, instants and anchors always render the same bytes, and a test asserts
the committed file equals a fresh rendering.

RESEARCH ONLY. Both seeds are committed, public reference material. Publishing a
generation-2 set means new seeds, a new ``key_id`` and a new document; revocation
does not exist, so nothing here retires a key (SR-4).

Run:    python experiments/workflow_fit_study/publish_research_trust_anchor_set.py
Check:  python experiments/workflow_fit_study/publish_research_trust_anchor_set.py --check
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ugence_trusted_evidence_authority import (
    TRUST_ANCHOR_SET_MANIFEST_SCHEMA_V1,
    TrustAnchorSetManifest,
    TrustAnchorSetSnapshot,
    TrustedEvidenceSigningKey,
    encode_public_key,
    encode_signature,
    render_trust_anchor_set_document,
    trust_anchor_collection_digest,
    trust_anchor_set_signing_bytes,
)

if __package__:
    from .signed_admission import (
        RESEARCH_PUBLICATION_ROOT,
        RESEARCH_SET_ID,
        RESEARCH_SET_VERSION,
        RESEARCH_SNAPSHOT_PATH,
        research_engine_anchor,
    )
else:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from workflow_fit_study.signed_admission import (  # type: ignore[no-redef]
        RESEARCH_PUBLICATION_ROOT,
        RESEARCH_SET_ID,
        RESEARCH_SET_VERSION,
        RESEARCH_SNAPSHOT_PATH,
        research_engine_anchor,
    )

#: The publication root's private seed. RESEARCH ONLY; never the engine seed.
RESEARCH_PUBLICATION_SEED = bytes.fromhex(
    "f291d3e867a5f6fffbb8968054b1a69a2749641f1b3cf6eacaaf6c7b20ac2527"
)
PUBLISHED_AT = datetime(2026, 9, 1, tzinfo=timezone.utc)
SET_EFFECTIVE_FROM = PUBLISHED_AT
SET_EFFECTIVE_TO = PUBLISHED_AT + timedelta(days=30)


def publication_signing_key() -> TrustedEvidenceSigningKey:
    return TrustedEvidenceSigningKey(RESEARCH_PUBLICATION_SEED)


def build_snapshot(*, set_version: int = RESEARCH_SET_VERSION, anchors=None,
                   published_at: datetime = PUBLISHED_AT, seed: bytes = RESEARCH_PUBLICATION_SEED) -> TrustAnchorSetSnapshot:
    records = tuple(anchors) if anchors is not None else (research_engine_anchor(),)
    records = tuple(sorted(records, key=lambda a: (a.authority_id, a.key_id, a.capability.value)))
    manifest = TrustAnchorSetManifest(
        schema_version=TRUST_ANCHOR_SET_MANIFEST_SCHEMA_V1,
        trust_anchor_set_id=RESEARCH_SET_ID,
        trust_anchor_set_version=set_version,
        publisher_authority_id=RESEARCH_PUBLICATION_ROOT.authority_id,
        publisher_key_id=RESEARCH_PUBLICATION_ROOT.key_id,
        published_at=published_at,
        effective_from=SET_EFFECTIVE_FROM,
        effective_to=SET_EFFECTIVE_TO,
        anchor_count=len(records),
        anchor_collection_digest=trust_anchor_collection_digest(records),
    )
    signature = encode_signature(TrustedEvidenceSigningKey(seed).sign(trust_anchor_set_signing_bytes(manifest)))
    return TrustAnchorSetSnapshot(manifest=manifest, anchors=records, signature=signature)


def render_document(**kw) -> bytes:
    return render_trust_anchor_set_document(build_snapshot(**kw))


def main(argv) -> int:
    derived = encode_public_key(publication_signing_key().verification_key.public_key_bytes)
    if derived != RESEARCH_PUBLICATION_ROOT.public_key:
        print("the pinned publication root does not match the publication seed", file=sys.stderr)
        return 1
    rendered = render_document()
    if "--check" in argv:
        current = RESEARCH_SNAPSHOT_PATH.read_bytes() if RESEARCH_SNAPSHOT_PATH.exists() else b""
        if current != rendered:
            print(f"{RESEARCH_SNAPSHOT_PATH} is stale: re-run this script")
            return 1
        print(f"{RESEARCH_SNAPSHOT_PATH} is current")
        return 0
    RESEARCH_SNAPSHOT_PATH.write_bytes(rendered)
    print(f"wrote {RESEARCH_SNAPSHOT_PATH} ({len(rendered)} bytes) — RESEARCH ONLY")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

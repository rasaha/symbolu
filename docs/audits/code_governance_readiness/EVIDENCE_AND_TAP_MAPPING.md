# Evidence & TAP Mapping — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§4.1, §6).
> Verified against live code at commit `3ec11e4e`.

## 1. TAP as the assertion-governance provider

`TAPProvider(BaseProvider)` (`tap_provider/provider.py:50`) implements the neutral
`AssertionGovernanceProvider` with `kind=ASSERTION_GOVERNANCE` (`provider.py:44-47`). It has no
authorize/dispatch/execute surface — TAP and ActionGate are mutually-unaware peers
(`tests/test_end_to_end.py:79-114`).

`evaluate()` (`provider.py:79`):
- consumes `AssertionGovernanceRequest`;
- `map_request()` (`mapping/request.py:29`) turns each `evidence_refs` string into a
  `TapEvidenceItem(evidence_id=ref, source_type="reference", source_reference=ref)` with a content
  fingerprint but **no content** — evidence is caller-supplied **by reference**
  (default `evidence_resolution="caller_supplied"`);
- `map_result()` (`mapping/result.py:62`) returns `AssertionGovernanceResult`, mapping
  `outcome→coverage` (UNKNOWN/unmapped → INDETERMINATE, never SUPPORTED), clamping
  `evidence_coverage` to 0..1, computing a SHA-256 `fingerprint`;
- native exceptions with `fail_safe=True` become an INDETERMINATE result — infrastructure failure
  never becomes SUPPORTED.

`AssertionGovernanceRequest.evidence_refs` is a **tuple of immutable string identifiers** — large
CI logs, scanner reports, and diffs stay **outside** the governance request (design §4.1 confirmed).

## 2. `AssertionGovernanceRequest.evidence_refs` — the integration seam

The GitHub Evidence Connector stores artifacts and produces immutable refs; **TAP** (not the
connector) is the resolved `ASSERTION_GOVERNANCE` provider. The `ValidationEvidenceBundle`
(design §6) stays product-side; only its `evidence_refs` flow into the governance request.

## 3. Does TAP already support the required claim structure?

The `truth_assurance_pipeline/` stages define rich, deterministic, stdlib-only claim/evidence
structures with mandatory provenance and content hashes:
- **E1 Intent** `IntentRecord` (schema `tap-e1-intent/1.0.0`) — per-field `Provenance`, append-only
  ledger, `source_text_hash`.
- **E2 Trusted Retrieval** `EvidenceUnit` — `authority`, `effective_year`, **`superseded_by`**,
  mandatory `EvidenceProvenance` (source/retrieval/extraction), `stable_hash`.
- **E3 Relationship Truth** `RelationshipAssertion` — separated dimensions incl.
  `Temporality.SUPERSEDED`, mandatory `SourceProvenance` back to an E2 unit.
- **E4 Governance Truth** — authority precedence / supersession filtering.
- **E5 Evidence Assembly** `EvidencePacket` (`tap-e5-evidence-packet/1.0.0`) — the deterministic,
  immutable, provenance-preserving bundle. "E5 assembles; it does not reason."
- **E6/E7** (`ValidationRecord`, `AssuranceRecord`) — **docs/experiments only, not integrated code**.

**No type named `ClaimManifest` exists.** Nearest structures: `EvidencePacket` (real, E5) and
`ValidationRecord` (docs-only, E6). A claim manifest is therefore a **product schema** to add.

## 4. Evidence storage / immutable references / durable store

**There is no durable evidence store — proven absent.** Evidence is represented only as in-memory
dataclasses holding references/hashes, never raw content:
- `evidence_assurance/evidence.py:23`: `content_ref` = "hash/reference to content (NOT raw content)";
  plus `content_hash`, `upstream_source_id`, `citation_chain`.
- `tap_provider` keeps `TapEvidenceItem.content` empty under `caller_supplied`.
- Grep for `store|durable|persist|sqlite|s3|blob` across the evidence modules returns only corpus
  text and an in-memory `GrantStore` test fixture. **No database/persistence.**

**Immutable references / content hashing: present and pervasive** (content-addressed): `content_hash`
/`content_ref`, `with_fingerprint()` (SHA-256), `stable_hash` in E1/E2, result/trace fingerprints.
So immutable refs are creatable; the **artifact bytes must be stored by the product connector**.

## 5. Provenance, supersession, quarantine, admissibility, staleness

| Concept | Status in live code | Detail |
|---|---|---|
| Source/retrieval provenance | **REUSE_EXISTING** | `EvidenceProvenance` (E2), `SourceProvenance` (E3), `Provenance` (E1), `evidence_assurance/provenance.py` |
| **Validator identity + version** binding | **NEW (product/neutral)** | No `validator_id`/`validator_version` field on any evidence type. Nearest: `policy_version`, E7 `profile_id/version` (docs). Design §16.1 requires this binding — it must be added |
| Evidence supersession | REUSE (field-level) | `superseded_by`, `freshness_state="superseded"`, `Temporality.SUPERSEDED` — enum/field only, **no lifecycle/store** |
| Evidence quarantine | **NEW** | No quarantine concept anywhere |
| Evidence admissibility | **NEW** | Only policy-frontier admissibility (`minimal_evidence_policy/frontier.py`) and artifact ASSURED/NOT_ASSURED (E7 docs); no evidence-artifact admissibility type. `AssertionCoverage` is the nearest support verdict |
| Stale detection | Partial (time-based only) | Publication-year/temporal (`_STALE_BEFORE=2018`, `effective_year`, E4 EXPIRED) |
| **Head-SHA invalidation** | **ABSENT** | No repo/commit head-SHA concept; nothing detects "source head moved → invalidate bound evidence." Content-hashing means a changed artifact yields a different digest, but the *invalidation trigger* must be built (product) |
| Merge-group SHA re-validation evidence | **NEW (product)** | No SCM concept; product re-runs required checks against the merge-group and emits new refs |

## 6. Neutrality

**No GitHub-specific types exist in the evidence subsystem** (grep of `github|pull_request|commit_sha|
diff|CI|SAST|secret.scan` returns only false positives). Neutrality is preserved: all GitHub-shaped
evidence enters as product records projected to neutral `evidence_refs`.

## 7. Per-concept classification (evidence-based)

| Concept | Classification |
|---|---|
| PR metadata | PRODUCT_RECORD |
| Commit metadata | PRODUCT_RECORD |
| Diff metadata | PRODUCT_RECORD |
| CI results | PRODUCT_ADAPTER |
| Test reports | PRODUCT_ADAPTER |
| SAST results | PRODUCT_ADAPTER |
| Dependency findings | PRODUCT_ADAPTER |
| Secret-scanning findings | PRODUCT_ADAPTER |
| Code-review findings | PRODUCT_RECORD |
| Human approval records | PRODUCT_RECORD |
| Claim manifest | NEW_NEUTRAL_CONTRACT_REQUIRED (start PRODUCT_PUBLIC) |
| Validator identity | NEW_NEUTRAL_CONTRACT_REQUIRED (or PRODUCT_RECORD binding) |
| Validator version | NEW_NEUTRAL_CONTRACT_REQUIRED (or PRODUCT_RECORD binding) |
| Evidence digest | REUSE_EXISTING |
| Evidence provenance | REUSE_EXISTING |
| Evidence supersession | REUSE_EXISTING (field-level) |
| Evidence quarantine | NEW_NEUTRAL_CONTRACT_REQUIRED |
| Evidence admissibility | NEW_NEUTRAL_CONTRACT_REQUIRED |

## 8. Cross-cutting gaps

1. **No durable evidence store** (references/digests only, caller-supplied) — PLANNED dependency.
2. **No validator-identity/version binding on evidence** — required by design §16.1.
3. **No quarantine and no evidence-artifact admissibility contract.**
4. **No head-SHA/commit-based staleness invalidation** (staleness is publication-year/temporal only).

These are **prerequisites**, not architecture blockers: the neutral `evidence_refs` seam is
sufficient; the missing pieces are product-side storage, product-side provenance binding, and a
product-side invalidation trigger.

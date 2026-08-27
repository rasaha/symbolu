# TEV-2 (PR #1446) — independent closure re-audit

PR #1446's own merged body states: *"A fresh independent closure re-audit is
required; the corrections above are self-reported and green checks are not a
merge signal."* This directory is that re-audit, run against the actually
merged head — not against the pre-correction branch the previous audit
(PR #1463) targeted.

## Why this exists instead of PR #1463

PR #1463 ("TEV-2 PR #1446 independent closure-audit probes") is still open and
unmerged. Checking it before writing anything new found it stale in three
independent ways:

1. **Dead scratchpad path.** Seven of its eight scripts hardcode an absolute
   path into a previous session's ephemeral scratchpad
   (`/tmp/claude-0/.../scratchpad/tev2head/...`). That directory no longer
   exists in any environment, so those scripts cannot be re-run as committed —
   directly contradicting their own stated purpose ("committed so they can be
   re-run against any future revision"). Only `pins.py` parameterized its root
   via `sys.argv`.
2. **Targets deleted code.** Four scripts import
   `ugence_trusted_evidence_authority.authority.ed25519` — the handwritten
   Ed25519 module PR #1446's own security-correction pass **deleted**,
   replacing it with `authority/backend.py` (`cryptography` + PyNaCl). The
   audit branch forked from `41d85dfc`, the commit *before* TEV-2 existed, and
   was never rebased past the correction commits it helped drive.
3. **Targets a removed API shape.** `scope_matrix.py` calls
   `verifier.verify(envelope, expected_*=...)` — the single ambiguous method
   PR #1446 deleted outright (finding F-04/F-05), replacing it with
   `verify_signature()` / `verify_bound()`.

None of this means PR #1463's *findings* were wrong — they are exactly the
findings PR #1446's body documents as F-01 through F-09, and they clearly did
their job once (driving the correction pass). But merging PR #1463 as-is would
commit non-reproducible, non-running scripts as "evidence." This directory
supersedes it: fresh probes, built independently, run against the actual
merged head.

## Method

Every probe here:

- imports only the curated public API (`ugence_trusted_evidence_authority.api`)
  or, where the API doesn't expose something (raw point bytes, the backend
  module), the smallest private surface needed — never a package test helper,
  never `_builders`/`_authority_builders`;
- builds its own fixtures from scratch (see `_fixtures.py`);
- differentials against a genuinely separate implementation where the claim is
  about cryptographic correctness (PyNaCl's `nacl.signing`, not `cryptography`
  again — the package's own backend already uses `cryptography`, so comparing
  against it proves nothing new);
- reconstructs the RFC 8032 attack shapes (identity/small-order/non-canonical
  points) rather than reusing the package's own corpus, so this audit and the
  implementation don't share a blind spot.

## How to run

```
pip install "cryptography>=41.0.7,<47.0.0" "PyNaCl>=1.5.0,<2.0.0"
python audit/tev2-1446-closure-reaudit/anchor_forgery.py .
python audit/tev2-1446-closure-reaudit/backend_differential.py .
python audit/tev2-1446-closure-reaudit/reverification_shapes.py .
python audit/tev2-1446-closure-reaudit/key_hygiene.py .
python audit/tev2-1446-closure-reaudit/gate_and_survivors.py .
```

`pins_and_api.py` additionally needs a checkout of the TEV-1 merge commit to
diff against, since it computes both sides dynamically rather than trusting a
hardcoded hex constant (see the finding below on why):

```
git worktree add /tmp/tev1_check 41d85dfc
python audit/tev2-1446-closure-reaudit/pins_and_api.py . /tmp/tev1_check
git worktree remove /tmp/tev1_check
```

Or run everything at once with `run_all.py [repo-root] [tev1-baseline-root]`.

## Findings

`[V]` verified directly by these probes against the merged head (`5063df5a`,
which carries `e604092a1`, PR #1446's head, unmodified).

| # | Claim | Result |
|---|---|---|
| F-01/F-03 | Identity/small-order/non-canonical anchor keys refused at construction; universal forgery route closed | `[V]` — 12 untrustworthy points (identity ×2, order-2 ×2, order-4 ×2, order-8 ×2, non-canonical field element ×2, off-curve, all-`ff`) all refused at both `TrustedEvidenceVerificationKey` and `TrustAnchorRecord` construction. The end-to-end forgery route never opens because the anchor itself cannot be built. |
| F-02 | No divergence between the package's crypto and an independent implementation | `[V]` — 2,414 sign/verify triples agree between the package (`cryptography`-backed) and an independently-invoked `nacl.signing` (PyNaCl, libsodium) across 71 keys × 34 messages including RFC-vector-adjacent edge cases. Point-validation wiring cross-checked directly against `nacl.bindings.crypto_core_ed25519_is_valid_point`. |
| F-04 | Signature-only and scope-bound results are structurally distinct, never equal | `[V]` — distinct types, `==` is `False`, distinct `repr`, distinct stage sets, distinct `verification_kind`; direct construction of a `VERIFIED` result is refused (no manufactured verdicts). |
| F-05 | No coordinate can be silently skipped in `verify_bound` | `[V]` — `expectation=None`, a duck-typed lookalike, and a `ReceiptScopeExpectation` subclass are all refused by the exact-type check; every one of the 9 required coordinates raises `TypeError` if omitted and is refused if passed as `""`; a wrong-but-truthy value in any coordinate is independently caught. The one ratified empty spelling (`assessed_system_binding_digest`) is reachable only through the named constructor, and that constructor refuses an explicit value for the same field. |
| F-08 | Signing key exposes no seed through any route | `[V]` — no dataclass, no `__dict__`, no `.seed`, seed absent from `repr`/`str`/exception text; `pickle`, `copy.copy` and `copy.deepcopy` all raise; post-construction attribute assignment raises; the key still signs correctly afterward. |
| F-09 (spot check) | The recomputed-vs-declared payload digest gate is genuinely load-bearing; the two "structurally unreachable" survivors have no path | `[V]` — reproduced the exact scenario named in the PR body (an envelope built by bypassing `__post_init__` via `object.__new__`, simulating an unpickled/deserialized envelope) with a valid signature and a lying declared digest: refused, with `TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH`. Also found, as a bonus, that `SignedEvidenceVerificationReceipt.__post_init__` *itself* already checks this — so `dataclasses.replace()` alone cannot produce the lying envelope; only a true `__post_init__` bypass can, which is exactly the scenario the PR names. Both claimed-unreachable survivors (capability gate, signature-profile pin) were probed directly at their most likely trigger point and found genuinely unreachable by the routes tried — this is not a full mutation-matrix re-run, so treat as `[I]` rather than an exhaustive re-verification of "18 run, 16 killed, 2 survivors." |
| TEV-1 compatibility | Pinned digests, digest domains, refusal-vocabulary ordinals and curated API surface unchanged since TEV-1 | `[V]` — recomputed dynamically against a `41d85dfc` (TEV-1 merge commit) worktree rather than trusting a hardcoded hex constant. `EvidenceSchemaRef`, `CanonicalEvidenceIdentity` and the receipt-payload digest all reproduce byte-for-byte; both digest domains and the canonicalization version string are unchanged; the refusal vocabulary's first 19 members are unchanged in name and order; every TEV-1 curated symbol is still exported. |

## A defect found in PR #1463's own evidence, not in PR #1446

`[V]` While building the TEV-1 pin check independently, this audit initially
computed a *different* digest than the one PR #1446's merged body and
CHANGELOG cite (`54b9bd61…`) for the "TEV-1 `EvidenceSchemaRef` pin" — because
it started from PR #1463's own `pins.py`/`pins_frame.py`, which construct
`EvidenceSchemaRef(schema_id="ugence.evidence.model-benchmark", ...)`. That
string does not appear anywhere in the package, at TEV-1, at TEV-2, or at any
point in between — the real fixture, used consistently by
`tests/_builders.py`, `tests/authority/test_tev2_canonicalization_vectors.py`
and `verify_trusted_evidence_authority_distribution.py`, is
`"ugence.evidence.control-test"`. Checked out against the actual TEV-1 merge
commit (`41d85dfc`), `control-test` reproduces `54b9bd61…` exactly;
`model-benchmark` does not. **PR #1446's claim is correct; PR #1463's own
committed audit script has a copy-paste fixture bug** that was never caught
because the script has no assertion (it only prints) and, per the finding
above, was never actually runnable in the first place.

## Gaps `[G]`

- **F-09 is a spot check, not the full mutation matrix.** The PR claims
  "18 mutants run, 16 killed, 2 survivors." This audit reproduced one named
  load-bearing gate and probed both survivors' most direct trigger route, but
  did not re-run all 18 mutations independently.
- **Timing/side-channel claims are not re-examined.** The merged code makes no
  constant-time claim of its own (side-channel resistance is delegated to
  `cryptography`/OpenSSL), so there is nothing analogous to F-06's original
  timing probe to re-run here. Treated as out of scope for this closure
  re-audit rather than silently skipped.
- **PR #1463's disposition is a decision for the repo owner**, not this audit:
  whether to close it as superseded, or repair its scratchpad path and
  redirect it at `authority/backend.py` for its own sake. This directory does
  not touch that PR.

## State

All 6 probes pass against `5063df5a` (branch `claude/tev2-1446-closure-reaudit`,
based on the current default branch), with `cryptography==41.0.7` and
`PyNaCl==1.6.2`. No package source under `packages/trusted-evidence-authority/`
was modified — this is audit-owned evidence only, exactly as PR #1463's own
probes were meant to be.

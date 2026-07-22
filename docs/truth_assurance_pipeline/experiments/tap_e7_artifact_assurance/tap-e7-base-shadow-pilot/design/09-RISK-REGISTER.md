# 9. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | A stakeholder treats TAP-E7 as a production gate during the pilot | Med | High | Read-only attestation; shadow-only wiring; dashboard banner; no API in decision path |
| R2 | Over-claiming from high precision (ignoring bounded recall) | High | High | Dashboard honesty panel; report engine-gap misses prominently; recall reported two ways |
| R3 | Under-claiming (dismissing real structural value) | Med | Med | Report per-issue flag rates; show 100% recall on detectable classes |
| R4 | Ground-truth error (mislabeled expected relationship) | Med | Med | Two blind reviewers; record H2 disagreements; adjudicator review |
| R5 | Confidential data ingress | Low | High | Public/synthetic only; ingestion filter; no PHI/PII; legal sign-off |
| R6 | Config-fingerprint drift / package mutation mid-pilot | Low | High | Verify fingerprint + composite hash each batch; abort on drift |
| R7 | Reviewer anchoring on TAP-E7 output | Med | Med | Blinding until label submitted |
| R8 | Domain skew (results generalized beyond sampled domains) | Med | Med | Domain-stratified sampling; per-domain reporting; note BASE is domain-agnostic |
| R9 | Harness bug misattributed to TAP-E7 | Med | Med | Harness is separate from the frozen engine; V-failures verified against frozen rules before filing |
| R10 | Engine-gap categories (scope/qualifier) silently accepted as "safe" | High | High | Explicit engine-gap-miss metric; taxonomy class O; route such cases to human review |
| R11 | Reviewer fatigue inflates review time / lowers κ | Med | Low | Cap daily cases; rotate reviewers; monitor κ trend |

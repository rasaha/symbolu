# 5. Governance Plan

## Review workflow
1. Sample artifacts per the sampling rule (below). 2. Two reviewers independently label each case
(blind to TAP-E7). 3. TAP-E7 runs read-only; AssuranceRecord logged. 4. Reveal TAP-E7 to reviewers
for the comparison log only. 5. Adjudicator files each case under the failure taxonomy. 6. Analyst
updates dashboards. **No production decision consumes TAP-E7 output.**

## Artifact sampling
Domain-stratified random sampling with fixed per-domain quotas; rare classes (integrity/modality)
over-sampled to reach minimum positive counts. Sampling seed and quotas are frozen at pilot start.

## Blinding
Reviewers blind to TAP-E7 until they submit their label. Adjudicator sees all three (expected,
human, TAP). Analyst sees aggregates only.

## Independent reviewer responsibilities
Reviewers are domain-competent and independent of the generator team. They record ISSUE/CLEAN +
category + confidence + time, and MUST NOT edit artifacts or consult TAP-E7 pre-label.

## Issue tracking
Every case with any non-agreement (H*) or any V* opens a tracked item with: case id, artifact hash,
AssuranceRecord hash, taxonomy class, evidence, adjudication, disposition (implementation /
generator / documentation / future-protocol / future-profile / TAP-E8). Items are **recorded**, not
acted into TAP-E7.

## Change control
**No protocol, package, resource, fixture, or implementation change during the pilot.** The config
fingerprint is verified each batch; any drift halts the pilot and voids the affected batch. Pilot
scripts (this directory) may be fixed only for harness bugs, with the change logged and the batch
re-run.

## Report publication
Daily summary + domain summary during the run; overall report + executive dashboard at close;
published with package commit, fingerprint, and package_root so results are reproducible.

# 2. Evaluation Methodology

## Unit of evaluation
One **case** = (validated source → generated artifact) pair. For each case:
- **original validated source** — the `ValidationRecord` (record-supplied facts/status/scope/citation/provenance).
- **generated artifact** — the `CandidateArtifact` produced by the real generator (untouched by TAP-E7).
- **expected relationship** — the author/analyst's a-priori label (faithful, or a named issue type).
- **human assessment** — an independent reviewer's verdict (ISSUE / CLEAN + category), collected blind to TAP-E7.
- **TAP-E7 assessment** — the `AssuranceRecord` (outcome + findings), logged read-only.
- **final comparison** — human vs TAP-E7 vs expected relationship, adjudicated per the failure taxonomy.

## Sample sizes (why)
| Tier | Cases | Rationale |
|---|---|---|
| Small | ~50 | smoke test: confirms pipeline + fingerprint gate + report generation end-to-end |
| Medium | ~150–300 | enough to estimate per-issue flag rates and per-domain behavior with usable CIs (the bundled demo uses 162) |
| Large | ~1,000–2,000 | stabilizes precision/recall to ±2–3% and surfaces rare integrity/parse cases |
| Enterprise | ~10,000+ | domain-stratified; powers subgroup analysis, drift monitoring, and reviewer-time economics |
Sizing targets a ±3% margin on precision/recall at 95% confidence for the dominant issue classes;
rare classes (integrity/modality) need the larger tiers to accumulate enough positive examples.

## Blinding
Reviewers assess artifacts and record ISSUE/CLEAN **before** seeing the AssuranceRecord. TAP-E7
output is revealed only afterward for the comparison log. This prevents anchoring and keeps human
ground truth independent.

## Ground-truth discipline
Expected relationship is fixed at case authoring/sampling time and **frozen**. Disagreements between
human and expected are themselves recorded (human-review disagreement class), never silently
reconciled. TAP-E7 is graded against **human assessment** (the operational oracle), with the
expected relationship as a secondary check.

## Determinism / integrity controls
- Recompute and verify the runtime config fingerprint before each batch.
- Hash every AssuranceRecord and the package composite before/after each batch (immutability).
- Re-run a fixed 10% replay subset to confirm identical outputs.

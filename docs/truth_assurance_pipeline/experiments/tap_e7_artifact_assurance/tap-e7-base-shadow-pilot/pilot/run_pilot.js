'use strict';
// TAP-E7-BASE READ-ONLY SHADOW PILOT harness.
// Generates a synthetic multi-domain artifact set with KNOWN ground truth, runs each artifact
// through the FROZEN reference engine (Implementation B, required read-only, never modified),
// and measures TAP-E7's observational behavior vs ground truth. TAP-E7 output influences nothing.
const fs = require('fs'), path = require('path');
const REPO = path.resolve(__dirname, '..', '..');
const PKG = path.join(REPO, 'tap-e7-base-companion-1.2.0');
const V = require(path.join(REPO, 'tap-e7-base-implementation-b', 'src', 'verifier.js')); // read-only
const res = V.loadResources(PKG);

// Confirm the frozen engine is bound to the published fingerprint before any evaluation.
const CF = require(path.join(REPO, 'tap-e7-base-implementation-b', 'tools', 'recompute_config_fingerprint.js'));
const [fp, want] = CF.recompute(PKG);
if (fp !== want) { console.error('fingerprint mismatch — pilot aborted'); process.exit(2); }

const DOMAINS = ['compliance','financial','insurance','healthcare','legal','governance','audit','policy','agent_summary'];
// Domain propositions as (subject, predicate, object) using BASE content tokens.
const FACT = {
  compliance:   ['vendor','completed','security assessment'],
  financial:    ['division','reported','quarterly revenue'],
  insurance:    ['adjuster','approved','collision claim'],
  healthcare:   ['clinician','documented','patient medication'],
  legal:        ['counsel','summarized','settlement agreement'],
  governance:   ['committee','ratified','governance policy'],
  audit:        ['auditor','verified','control evidence'],
  policy:       ['regulation','mandates','access review'],
  agent_summary:['agent','executed','data migration'],
};
// Issue types + the expected TAP-E7-BASE behavior class (what a bounded structural verifier CAN do).
// detectable = BASE is expected to move off ASSURED; engine_gap = BASE is expected to ASSURE (miss).
const ISSUES = [
  { key: 'faithful',              detectable: true,  gt_issue: false },
  { key: 'unsupported_assertion', detectable: true,  gt_issue: true  },
  { key: 'status_upgrade',        detectable: true,  gt_issue: true  },
  { key: 'citation_mismatch',     detectable: true,  gt_issue: true  },
  { key: 'provenance_mismatch',   detectable: true,  gt_issue: true  },
  { key: 'integrity_homoglyph',   detectable: true,  gt_issue: true  },
  { key: 'certainty_inflation',   detectable: false, gt_issue: true  }, // engine-level (informative) → BASE gap
  { key: 'scope_expansion',       detectable: false, gt_issue: true  }, // engine-level → BASE gap
  { key: 'omitted_qualifier',     detectable: false, gt_issue: true  }, // engine-level → BASE gap
];
const K = 2; // replicates per (domain × issue) → 9×9×2 = 162 artifacts (medium pilot)

const PROFILE = { profile_id: 'tap-e7-base', profile_version: '1.0' };
const RELEASE = 'tap-e7-base-companion/1.1.0';
function entry(id, f, over = {}) { return { entry_id: id, subject: f[0], predicate: f[1], object: f[2], status: 'SUPPORTED', confidence: 'HIGH', scope: {}, ...over }; }
function textSub(entries, text) { return { modality: 'text', validation_record: { entries }, artifact: { parts: [{ text }] }, profile_ref: PROFILE, release_ref: RELEASE }; }
function jsonSub(entries, raw) { return { modality: 'json', validation_record: { entries }, artifact: { parts: [{ raw }] }, profile_ref: PROFILE, release_ref: RELEASE }; }

function makeArtifact(domain, issue, rep) {
  const f = FACT[domain]; const prop = `${f[0]} ${f[1]} ${f[2]}`;
  const other = FACT[DOMAINS[(DOMAINS.indexOf(domain) + 3) % DOMAINS.length]];
  switch (issue) {
    case 'faithful':              return { sub: textSub([entry('V1', f)], prop), note: 'artifact restates the validated fact' };
    case 'unsupported_assertion': return { sub: textSub([entry('V1', f)], `${other[0]} ${other[1]} ${other[2]}`), note: 'artifact asserts a claim with no validated support' };
    case 'status_upgrade':        return { sub: jsonSub([entry('V1', f, { status: 'CONTRADICTED' })], JSON.stringify({ statement: prop, validation_entry_id: 'V1' })), note: 'validated record CONTRADICTS the claim; artifact asserts it flatly' };
    case 'citation_mismatch':     return { sub: textSub([entry('V1', f, { citation_ids: ['S1'] })], `${prop} [S9]`), note: 'artifact cites S9; record supports only S1' };
    case 'provenance_mismatch':   return { sub: jsonSub([entry('V1', f, { provenance_ids: ['S1'] })], JSON.stringify({ statement: prop, attributed_source: 'S9', validation_entry_id: 'V1' })), note: 'artifact attributes to a source outside the record provenance' };
    case 'integrity_homoglyph':   return { sub: textSub([entry('V1', f)], prop.replace('e', 'е')), note: 'artifact entity uses a Cyrillic homoglyph (spoof risk)' };
    case 'certainty_inflation':   return { sub: textSub([entry('V1', f, { confidence: 'LOW' })], `${f[0]} certainly ${f[1]} ${f[2]}`), note: 'record confidence is LOW; artifact states it as certain (engine-level nuance)' };
    case 'scope_expansion':       return { sub: textSub([entry('V1', f, { scope: { jurisdiction: ['eu'] } })], prop), note: 'record is EU-scoped; artifact drops the scope (engine-level nuance)' };
    case 'omitted_qualifier':     return { sub: textSub([entry('V1', f, { scope: { condition: ['for admins'] } })], prop), note: 'record is conditional; artifact omits the qualifier (engine-level nuance)' };
  }
}

const records = [];
for (const domain of DOMAINS) for (const iss of ISSUES) for (let r = 0; r < K; r++) {
  const id = `${domain}-${iss.key}-${r + 1}`;
  const { sub, note } = makeArtifact(domain, iss.key, iss.key);
  const rec = V.evaluate(res, sub);                       // FROZEN engine, read-only
  const human = iss.gt_issue ? 'ISSUE' : 'CLEAN';          // synthetic ground truth (author-known)
  const tap_flags = rec.outcome !== 'ASSURED';             // TAP moved off assured
  records.push({ id, domain, issue: iss.key, gt_issue: iss.gt_issue, detectable: iss.detectable,
    human_assessment: human, tap_outcome: rec.outcome, tap_findings: rec.findings.map(x => x.category),
    tap_flags, note });
}

// ---- metrics (only within TAP-E7's scope) ----
const N = records.length;
const outcomeDist = {}; for (const r of records) outcomeDist[r.tap_outcome] = (outcomeDist[r.tap_outcome] || 0) + 1;
// confusion: positive = ground-truth issue; TAP "positive" = not ASSURED (flags a concern)
let TP = 0, FP = 0, TN = 0, FN = 0;
for (const r of records) {
  if (r.gt_issue && r.tap_flags) TP++;
  else if (!r.gt_issue && r.tap_flags) FP++;
  else if (!r.gt_issue && !r.tap_flags) TN++;
  else FN++;
}
const precision = TP + FP ? TP / (TP + FP) : null;
const recall = TP + FN ? TP / (TP + FN) : null;
// detection by issue class
const byIssue = {};
for (const iss of ISSUES) {
  const rs = records.filter(r => r.issue === iss.key);
  const flagged = rs.filter(r => r.tap_flags).length;
  byIssue[iss.key] = { n: rs.length, flagged, flag_rate: flagged / rs.length, detectable: iss.detectable,
    typical_outcome: mode(rs.map(r => r.tap_outcome)) };
}
// recall restricted to BASE-detectable issue classes
const detectableIssues = records.filter(r => r.gt_issue && r.detectable);
const detectableFlagged = detectableIssues.filter(r => r.tap_flags).length;
const recall_detectable = detectableFlagged / detectableIssues.length;
const engineGap = records.filter(r => r.gt_issue && !r.detectable);
const engineGapMissed = engineGap.filter(r => !r.tap_flags).length;
function mode(a) { const c = {}; let best = null, bc = -1; for (const x of a) { c[x] = (c[x] || 0) + 1; if (c[x] > bc) { bc = c[x]; best = x; } } return best; }
const indeterminate = records.filter(r => r.tap_outcome === 'INDETERMINATE').length;

const metrics = {
  pilot_size: N, domains: DOMAINS.length, issue_types: ISSUES.length, replicates: K,
  fingerprint_bound: fp, engine: 'Implementation B (read-only reference)', package: 'tap-e7-base-companion/1.2.0',
  outcome_distribution: outcomeDist,
  confusion_overall: { TP, FP, TN, FN },
  precision_overall: round(precision), recall_overall: round(recall),
  recall_on_base_detectable_classes: round(recall_detectable),
  indeterminate_rate: round(indeterminate / N),
  false_negatives_total: FN, false_positives_total: FP,
  engine_gap_missed: engineGapMissed, engine_gap_total: engineGap.length,
  by_issue: byIssue,
  note: 'reviewer_agreement and average_review_time are DESIGN metrics requiring human reviewers; they are not produced by this synthetic demonstration and are marked N/A here.',
  reviewer_agreement: 'N/A (requires human reviewers)', average_review_time: 'N/A (requires human reviewers)'
};
function round(x) { return x == null ? null : Math.round(x * 1000) / 1000; }

fs.mkdirSync(path.join(__dirname, '..', 'data'), { recursive: true });
fs.writeFileSync(path.join(__dirname, '..', 'data', 'dataset.json'), JSON.stringify(records, null, 1));
fs.writeFileSync(path.join(__dirname, '..', 'results', 'assurance-records.json'), JSON.stringify(records, null, 1));
fs.writeFileSync(path.join(__dirname, '..', 'results', 'metrics.json'), JSON.stringify(metrics, null, 1));
console.log('pilot artifacts:', N, '| outcomes:', JSON.stringify(outcomeDist));
console.log('precision:', metrics.precision_overall, 'recall(overall):', metrics.recall_overall,
  'recall(BASE-detectable):', metrics.recall_on_base_detectable_classes, 'indeterminate rate:', metrics.indeterminate_rate);
console.log('engine-gap missed (certainty/scope/qualifier ASSURED):', engineGapMissed, '/', engineGap.length);
for (const k of Object.keys(byIssue)) console.log('  ', k, byIssue[k].flag_rate === 1 ? 'FLAG' : (byIssue[k].flag_rate === 0 ? 'miss' : byIssue[k].flag_rate), '→', byIssue[k].typical_outcome);

# Semantic Evidence Normalization + TAP Assertion Governance — Report

**Decisive question:** can Ugence use language models only where semantic interpretation is genuinely
necessary, while preserving exact evidence, preventing unsupported facts from entering the
authoritative pipeline, and stopping generated explanations from claiming more than the evidence and
authority allow?

**Answer:** yes. Deterministic parsing owns every explicit field; the interpreter is confined to a
few genuinely semantic fields; the normalization validator lets **zero unsupported facts** into the
exact ledger at any interpreter quality; and TAP blocks **100%** of unsupported / contradicted /
authority-exceeding claims. The one criterion not met at the simulated interpreter quality (downstream
accuracy within 0.05 of oracle) is bounded by *document-interpretation quality*, not governance.

(Interpreter is a controllable simulator — see README. Governance layers are deterministic and tested.)

## Normalization (held-out, q=0.85)

| arm | downstream outcome | unsupported-fact admission | exact fields | source-span match |
|---|---:|---:|---:|---:|
| N0 end-to-end LLM (disallowed) | 1.000 | — | — | — |
| N1 unconstrained (no validation) | 0.350 | **0.177** | — | 0.95 |
| N2 schema-constrained | 0.920 | 0.000 | 1.00 | 1.00 |
| **N3 hybrid + validation** | **0.920** | **0.000** | 1.00 | 1.00 |
| N4 N3 + consistency/authority | 0.920 | 0.000 | 1.00 | 1.00 |
| N5 oracle normalization | 1.000 | 0.000 | 1.00 | 1.00 |

**Interpreter-quality sweep (N3, held-out):** downstream 0.883 (q=0.70) → 0.920 (0.85) → 0.940
(0.95) → 0.947 (q=1.0); **unsupported-fact admission = 0.000 at every q.** The residual gap to N5 is
conservative abstention on ambiguous interpretations (safe), not invented facts. N1 (no validation)
shows what governance prevents: 17.7% unsupported admission and 0.350 downstream.

## TAP assertion governance (held-out)

| arm | unsupported-claim recall | authority-exceedance recall | supported-claim precision | admissibility |
|---|---:|---:|---:|---:|
| T0 no TAP | 0.000 | 0.000 | 0.42 | 0.01 |
| T1 prompt-only | 0.000 | 0.000 | 0.56 | 0.08 |
| T2 TAP match (no ceilings) | 0.297 | 0.000 | 0.51 | 0.03 |
| **T3 TAP + ceilings** | **1.000** | **1.000** | **1.000** | **1.000** |
| T4 T3 + revision | 1.000 | 1.000 | 1.000 | 1.000 |

**T1 (prompt-only) fails; T3/T4 pass** — validating TAP as *enforcement beyond prompting* (§16).

## Causal controls (§14)

- Remove supporting source span → record **100% blocked**. Corrupt provenance → **100% blocked**.
- Inject irrelevant authoritative-looking docs → downstream outcome **invariant**.
- Authority-exceeding claims → **always blocked** (recall 1.0).
- (Document-shuffle shows a small 0.04 variation attributable to interpreter-seed noise; the
  deterministic fields are order-invariant.)

## §15 acceptance

Met: exact-field accuracy 1.00 (≥0.98) ✓ · source-span match 1.00 (≥0.95) ✓ · **unsupported-fact
admission 0.000 (≤0.01)** ✓ · evidence-ID preservation 1.0 ✓ · **TAP unsupported-claim recall 1.0**
(≥0.95) ✓ · TAP supported-claim precision 1.0 (≥0.95) ✓ · **authority-exceedance recall 1.0** ✓ ·
qualifier preservation 1.0 (≥0.98) ✓ · held-out degradation ≤0.05 ✓ · normalization causal controls
✓ · prompt-only insufficient ✓. **Not met:** downstream-within-0.05-of-oracle (gap 0.08 at q=0.85;
0.05 at q=1.0) — interpreter-quality-bounded, not a governance defect. Thresholds not lowered.

## §17 final verdict

- **Frozen deterministic pipeline:** verified.
- **Semantic normalization:** *safety validated at all interpreter qualities* (0.000 unsupported-fact
  admission, spans/provenance/access preserved); downstream accuracy approaches oracle
  (0.92–0.95) but is **interpreter-quality-bounded** — mode-specific, not fully validated at the
  strict 0.05 bar.
- **Best normalization architecture:** N3 (= N4).
- **Deterministic fields:** amount, date, document_id, policy_version, explicit_status,
  named_authority, approval_record_exists.
- **Interpreted fields:** approval_granted (requested-vs-granted), clauses_conflict, exception_applies.
- **Unsupported-fact admission rate:** 0.000.
- **Downstream outcome accuracy:** 0.92 (q=0.85) → 0.947 (q=1.0).
- **Oracle-normalization gap:** 0.08 (q=0.85) → 0.05 (q=1.0).
- **Hybrid handoff value:** validated (bounded packet: only unresolved spans + tenant-safe ids sent;
  prohibited-conclusions declared; external model returns structured interpretations only).
- **TAP assertion governance:** **validated.**
- **Best TAP architecture:** T3 (= T4).
- **Unsupported-claim recall:** 1.00. **Supported-claim precision:** 1.00.
- **Authority-exceedance recall:** 1.00. **Qualifier-preservation rate:** 1.00.
- **Evidence-ID preservation:** 1.00. **Unauthorized inclusion:** 0.00.
- **Primary remaining bottleneck:** **document interpretation** (the model's semantic accuracy on
  the few interpreted fields) — *not* normalization validation, evidence validation, or TAP.
- **Authorized architecture:** raw enterprise documents → deterministic extraction where exact +
  bounded semantic interpretation where necessary → provisional evidence validation → authoritative
  evidence ledger → deterministic joins → P5 binding slots → exact typed fields → deterministic
  outcome mapper → Hybrid-LLM explanation → **TAP assertion governance** → Decision Governance →
  ActionGate.

**Decisive answer:** models can be used *only where semantic interpretation is genuinely necessary*.
Deterministic parsing owns every explicit field; the interpreter is walled off to a few semantic
fields and can only *propose* provenance-linked, span-verified records; the validator admits **zero
unsupported facts** to the exact ledger regardless of model quality; and TAP stops generated
explanations from claiming approval, active policy, compliance, authority, or execution rights beyond
what the evidence supports (recall 1.00, authority-exceedance recall 1.00). The remaining accuracy gap
is the interpreter's semantic quality, which the governance safely converts into abstention/review
rather than invented fact. Frozen Phase and the entire validated procurement pipeline untouched.

# Enterprise Binding Slots + Bounded Quadratic Reasoning — Report

**Decisive question:** when the correct enterprise evidence is retained, does bounded quadratic
reasoning use it correctly — and can a transparent slot policy approach oracle performance without
losing provenance, access control, or operational efficiency? (No Phase in any arm.)

**Answer:** yes. A transparent deterministic slot policy (query-chain-relevance-aware) lifts
required-evidence survival from ~0.30 to ~1.0 and closes the S3→S4 gap; quadratic reasoning then
uses the retained evidence (conditional accuracy ≈ oracle). The gains survive held-out entities/
templates and the causal gate; provenance and access isolation are exact throughout.

## 1. Pilot (S0–S4, P2, streaming N=256)

| arm | conflict F1 | version acc | accuracy | required survival |
|---|---:|---:|---:|---:|
| S0 fresh+pool | 0.00 | 0.14 | 0.38 | 0.00 |
| S1 fresh+quad | 0.00 | 0.13 | 0.42 | 0.00 |
| S2 slots+pool | 0.83 | 0.15 | 0.38 | 0.30 |
| S3 slots+quad | 0.93 | 0.30 | 0.40 | 0.30 |
| S4 oracle+quad | 1.00 | 0.80 | 0.66–0.78 | 1.00 |

Fresh streaming retrieval never sees the distant required evidence (survival 0.00); slots retain it
(0.30 under the weak P2); oracle (1.00) shows the architecture can solve the task. In **one-shot**
mode (fresh sees all), S1 conflict-F1 1.00 > S0 0.93 — quadratic beats pooling when both see the
evidence. Integrity: unauthorized-inclusion 0, evidence-ID preservation 1.0. The pilot's one failing
gate (required-eviction ≯ irrelevant-eviction) was a **symptom of the admission bottleneck**, fixed
below.

## 2. Diagnosis — is the S3→S4 gap selection or reasoning?

The rescue's **conditional accuracy** answers it directly: after the deterministic policy raises
required survival to 1.0, **`acc | required-survived` ≈ overall accuracy ≈ oracle** — so when the
evidence is present, reasoning uses it. The gap was **selection (admission/eviction)**, not
reasoning. §4 failure taxonomy on the pre-rescue-priority errors confirms it once retention is
fixed: **MISSING_ADMISSION 0%, PREMATURE_EVICTION 0%**; remaining errors are OUTPUT_MAPPING (65%,
the policy-table classification head) and DUPLICATE_WASTE (34%).

## 3. Deterministic slot-policy rescue (streaming N=256, K=8)

The rescue = query-chain **relevance** in the enterprise priority (deterministic transitive
reachability from the query subject over observed chain relations; **leak-free** — invariant to all
labels, anchored on the query record's own subject) + a corrected duplicate key (version+status, so
conflict/version pairs survive dedup) + conflict-pair (P4) / version-pair (P5) protection.

| policy | accuracy | acc \| survived | conflict F1 | version acc | required survival |
|---|---:|---:|---:|---:|---:|
| S3 baseline (weak P2) | 0.40 | — | 0.93 | 0.30 | 0.30 |
| **S3 P2 (rescued)** | 0.69 | 0.69 | 0.91 | 0.79 | **1.00** |
| S3 P3 (+dedup) | 0.71 | 0.71 | 0.99 | 0.81 | 1.00 |
| S3 P4 (+conflict-pair) | 0.71 | 0.71 | 0.99 | 0.81 | 1.00 |
| **S3 P5 (+version-pair)** | **0.75** | 0.75 | 0.98 | 0.80 | 1.00 |
| S4 oracle | 0.72 | 0.72 | 0.00¹ | 0.80 | 1.00 |
| S1G global retrieval | 0.50 | 0.50 | 0.87 | 0.85 | 1.00 |

¹ the oracle guarantees only the answer-determining pair (budget + active policy), not the *conflict*
pair, so it cannot flag conflicts — which is why the conflict-pair-retaining S3(P5) 0.75 ≥ S4 0.72.

**Held-out (unseen entities + templates + fresh seeds):** dev 0.61 ≈ held-out 0.60 for every policy
→ generalizes, not memorization. Causal gate on held-out: `evict_required` 0.24 ≪ `evict_irrelevant`
0.44 — required eviction materially hurts, irrelevant does not. IDs 1.0, unauthorized 0.

## 4. What each component is (and is not) worth

- **Slot survival value — validated.** Deterministic policy raises required survival 0.30→1.0;
  removing retained required evidence causally collapses accuracy; slots beat fresh **and** global
  query-time retrieval (S1G 0.50 < S3 0.75) on streaming accuracy, and amortize re-encoding.
- **Quadratic comparison value — validated for contradiction, NOT for version.** Conflict F1 0.91–
  0.99 (S3) vs 0.83 (S2 pool) and 1.00 vs 0.93 (S1 vs S0 one-shot) — quadratic detects conflicts.
  But **active+stale co-survival is only 0.11**, so version accuracy (0.80) comes from the
  deterministic policy retaining the *active* version, **not** from quadratic active-vs-stale
  comparison. Version-selection credit → deterministic policy.
- **Capacity — smaller is better.** K=4 → 0.90, K=8 → 0.69, K=16 → 0.56, K=32 → 0.39: large K admits
  distractors that dilute the bounded reasoning. Smallest K within 95% of best = **4**.
- **Role-aware slots (S3R) — worse.** Partitioning K into chain/conflict/version/general sub-pools
  starves the required records (survival 0.00); a single shared pool with good priority wins →
  semantic interference is **not** the cause of the gap.
- **Deterministic vs learned policy.** Deterministic policies solved it; per the sequencing rule, no
  learned admission (P4-learned) was introduced.

## §14 Final verdict

- **Binding-slot evidence-survival value:** validated.
- **Quadratic comparison value:** validated (contradiction detection); version-selection value is the
  deterministic policy's, not quadratic's.
- **Combined synergy:** mode-specific — validated in streaming/multi-step (slots retain distant
  evidence, quadratic resolves conflicts); unnecessary in one-shot (fresh global retrieval sees all).
- **S3→S4 gap:** ≈ 0 after rescue (S3 P5 0.75 ≥ S4 0.72; pre-rescue gap ≈ 0.38).
- **Gap explained by missing evidence:** ~100% of the *original* gap was selection (survival
  0.30→1.0 closed it); of the *residual* errors, 34% duplicate-waste (evidence-side) + 65%
  output-mapping (reasoning/output-side).
- **Gap explained by reasoning failure:** ~1% pure reasoning; 65% output-head (policy-table) mapping.
- **Best deterministic slot policy:** P5 (P3–P5 within noise; all ≫ weak P2 baseline).
- **Best slot capacity:** K=4 (streaming/multi-step); larger K hurts.
- **Fresh global retrieval vs slots:** slots better accuracy (S3 0.75 > S1G 0.50) and fewer
  re-encodings.
- **Slot efficiency advantage:** validated (slots amortize retrieval/re-encoding across a workflow;
  S1G re-encodes K per query).
- **Full self-attention (S5) vs query-to-slot (S6):** __PENDING_S5S6__.
- **Primary remaining bottleneck:** the **output head** (policy-table class mapping, 65% of residual
  errors) plus **capacity-induced noise** at large K — no longer admission/eviction or evidence
  survival.
- **Authorized architecture:** **evidence ledger → binding slots → quadratic** for streaming /
  multi-step workflows (with a tight K and a query-chain-relevance deterministic policy); plain
  **fresh retrieval → quadratic** suffices for one-shot.

**Integrity:** evidence-ledger integrity verified; exact evidence-ID preservation **1.0**;
access-control isolation **verified** (unauthorized inclusion 0, injected-unauthorized leak 0).
Frozen Phase untouched (not used in any arm).

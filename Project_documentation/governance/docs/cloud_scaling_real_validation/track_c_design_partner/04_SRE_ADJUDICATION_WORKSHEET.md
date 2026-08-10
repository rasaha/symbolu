# SRE Adjudication Worksheet (template)

**Filled by the partner's SRE, with us.** One worksheet **per flagged episode** —
whether the flag came from offline replay of history (Track B) or a live read-only
shadow run (Track A). The worksheet does three jobs: (1) **true / false** (is the flag
real?), (2) **Tier-A vs Tier-B** (is it market evidence or just diagnostic?), and
(3) **cost** (what did the episode actually cost?). It also forces the one check that
can sink the core asset: did the engine flag a scale-out that **actually helped**?

> **Numbers stay labelled.** Anything derived here is an **estimate pending live
> adjudication** unless it came from a live run; never round it into a savings or
> "validated" claim. (`../STATUS.md` labels; plan §12.)

---

## Definitions (decide every flag against these — do not improvise)
- **Verdict** the engine emits per scale-out: **HELPING / NEUTRAL / NOT_HELPING**, plus
  the **futile-runaway** pattern (scaling continues while the metrics that matter don't
  improve).
- **Tier-A episode (market evidence):** a runaway/futile autoscaling episode that
  **materially over-provisioned or amplified a non-capacity incident** — the event a
  safety interlock would have capped. *This is the unit that counts.*
- **Tier-B event (NOT market evidence):** a single low-value non-causal scale-out /
  one-off NOT_HELPING observation. Useful diagnostically; **never a headline number.**
- **Harmful false positive (the red flag):** the engine called a scale-out futile, but
  real throughput/latency shows that scale-out **relieved a real constraint**. One such
  case triggers a **stop-and-review**, not a footnote.

---

## Worksheet

### 1. Identity
| Field | Value |
|---|---|
| Flag / episode ID | `____` |
| Source | `replay (Track B)` · `live shadow (Track A)` |
| Org / cluster | `____` |
| Namespace / deployment | `____` |
| Window (start → end, UTC) | `____ → ____` |
| Adjudicator (name, role) | `____` |
| Adjudication date | `____` |

### 2. What the engine emitted
| Field | Value |
|---|---|
| Verdict / pattern | `NOT_HELPING` · `futile-runaway` · `other: ____` |
| Replicas at flag (start → peak) | `____ → ____` |
| Consecutive NOT_HELPING cycles | `____` |
| Metric snapshot in window | latency p99 `____` · error rate `____` · CPU `____` · queue `____` · throughput `____` |
| What the engine "would have" done (counterfactual — never actuated) | `____` |

### 3. SRE verdict — is the flag real?
- [ ] **TRUE positive** — scaling genuinely was not helping in this window.
- [ ] **FALSE positive** — scaling *was* helping / appropriate.
  - [ ] ⛔ **HARMFUL false positive** — flagged a scale-out that real metrics show
        relieved a real constraint. → **STOP-AND-REVIEW** (record below; escalate).
- [ ] **Inconclusive** — metrics insufficient to judge (note what's missing).

SRE reasoning (1–3 sentences): `____`

### 4. Root cause (pick one; drives the Tier decision)
- [ ] Capacity-bound — more replicas *did* help (expect HELPING; if flagged, see §3).
- [ ] Downstream dependency saturation (DB / cache / 3rd-party).
- [ ] Lock contention / serialization.
- [ ] Queue collapse / poison work.
- [ ] Cascading failure (thundering-herd amplification).
- [ ] HPA / Karpenter runaway (rode to max while metrics flat/worse).
- [ ] Other: `____`

### 5. Tier classification
> **Tier-A only if:** TRUE positive **and** it **materially over-provisioned or
> amplified a non-capacity incident** (root cause is one of the non-capacity rows above,
> not a one-off blip).

- [ ] **Tier-A** (market evidence) — justify materiality: `____`
- [ ] **Tier-B** (diagnostic only) — why it's not Tier-A: `____`

### 6. Incident overlap (for Tier-A)
| Field | Value |
|---|---|
| Linked incident / ticket ID | `____` |
| Postmortem reference | `____` |
| Overlap with incident window | `full` · `partial` · `none` |
| Did scaling amplify the incident? | `yes` · `no` · `unclear` |

### 7. Cost attribution (partner economics — an estimate, not a product claim)
| Component | Input | Value |
|---|---|---|
| Excess replica-hours | (peak − needed replicas) × hours | `____` |
| × $/replica-hour | partner cost assumption | `____` |
| = excess compute cost | | `$____` |
| Incident minutes overlapped | from timeline | `____` |
| SLO-breach severity | partner-defined (low/med/high or $) | `____` |
| **Episode cost (SRE-confirmed)** | compute + incident + breach | **`$____`** |

> Feeds **APCY = Tier-A episodes/cluster-year × median $/episode** (computed elsewhere;
> see plan §6). Each Tier-A row here is one adjudicated input — labelled
> `real-trace-replay (estimate pending live adjudication)` until confirmed live.

### 8. Sign-off
| | |
|---|---|
| SRE confidence | `high` · `medium` · `low` |
| Disagreement with the flag? | `____` |
| Added to APCY tally? | `yes (Tier-A)` · `no (Tier-B / FP / inconclusive)` |
| Triggered stop-and-review? | `yes` · `no` |

---

## Roll-up (maintain across all worksheets for the partner)
| Quantity | Count | Note |
|---|---|---|
| Flags adjudicated | `____` | denominator for FP rate (target ≥40–50 across partners) |
| TRUE positives | `____` | |
| FALSE positives | `____` | FP rate = FP / adjudicated (target ≤5%) |
| **HARMFUL** false positives | `____` | **must be 0** — any >0 is a stop-and-review |
| **Tier-A** episodes (confirmed) | `____` | the market-evidence count |
| Tier-B events | `____` | diagnostic only — **never** a headline |
| Median Tier-A episode cost | `$____` | estimate pending live adjudication |

> **Market-red trip-wire (plan §6):** **< 5 adjudicated Tier-A episodes across ≥150
> retrospective cluster-months** is a market-red signal *regardless* of how clean the
> verdict is. Report the Tier-A count honestly even when it's small.

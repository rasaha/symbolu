# Downstream Utility Evaluation (Phase 15)

*`evidence_obligation/downstream.py` → `eval_results/downstream.json`. Every obligation policy passed
through the obligation→EA contract and the **frozen** EvidenceAssurance delivery mapping. This is the
pivotal result: does contextual obligation improve utility without weakening safety?*

## Results (held-out natural n=250; adversarial n=100)

| Policy | clean allow | over-qual | withhold | held unsafe allow | adv unsafe allow |
|---|---|---|---|---|---|
| prior_derivation_uniform | 0.000 | 1.000 | 0.000 | 0 | 0 |
| A_uniform_strong | 0.000 | 0.000 | 0.728 | 0 | 0 |
| C_risk_only | 0.668 | 0.060 | 0.000 | 16 | 0 |
| E_claim_type_only | 0.344 | 0.020 | 0.444 | 10 | 20 |
| K_global_threshold_reduction | 1.000 | 0.000 | 0.000 | 46 | **100** |
| O_nogate_all_lowrisk | 1.000 | 0.000 | 0.000 | 46 | **100** |
| P_simple_contextual | 0.264 | 0.020 | 0.444 | 8 | 0 |
| **Q_reference** | **0.584** | 0.020 | 0.192 | **10** | **10** |
| **R_oracle** | **0.296** | 0.016 | 0.416 | **0** | **0** |
| S_learned | 0.332 | 0.056 | 0.352 | 1 | 0 |

Prior reference: 0% clean allow, 85.5% over-qualification.

## The three findings that decide the track

**1. Utility improvement is real and large — H0-9 and H0-10 rejected.** The uniform prior derivation
reproduces the failure (0% clean allow, 100% over-qualification). Contextual obligation lifts clean allow
to **29.6% at zero unsafe (oracle)** and collapses over-qualification from 85.5% to ~2%. The mechanism
works: assigning each claim its appropriate obligation, then mapping a *met* low-burden standard to an
obligation-relative VERIFIED, converts a large block of over-qualified benign documentation into clean
allows.

**2. The concept is safe; the reference classifier is not (yet).** The **oracle** (perfect obligations)
achieves the utility gain with **0 unsafe allows on both held-out and adversarial** — proof that
contextual obligation does not inherently weaken safety. But **Q_reference over-allows**: 58.4% clean
allow at the cost of **10 high-risk held-out unsafe allows and 10 adversarial unsafe allows**. All 10
adversarial leaks are a single disguise pattern — *"the model states that its own output is verified"* —
which Q classifies as `CONTEXTUAL_SUPPORT_SUFFICIENT` (gold: `INDEPENDENT_CORROBORATION_REQUIRED`). This
is a concrete classifier blind spot (model self-verification framed as a neutral statement), reported
honestly and **not overfit away**.

**3. A simple learned comparator (S) is nearly as safe as the oracle.** S_learned reaches 33.2% clean
allow with **1 held-out unsafe and 0 adversarial unsafe** — better safety than Q at comparable utility to
the oracle. Combined with the baseline accuracy result, this is a strong signal that the richer component
does not earn its complexity over a simple per-(claim-type, risk) map calibrated for safety.

## Falsification impact

| Null | Outcome |
|---|---|
| H0-9 / H0-10 (no utility improvement / no over-qual reduction) | **REJECTED** — 0%→29.6% clean, 85.5%→~2% over-qual |
| H0-11 (contextual obligations weaken high-risk safety) | **RETAINED for Q_reference** (10 high-risk unsafe allows); **REJECTED for the concept** (oracle 0 unsafe) |
| H0-16 (global threshold change performs equally well) | **REJECTED** — K/O reach 100% clean but 46–100 unsafe allows |
| H0-1 (uniform performs as well) | **REJECTED** — uniform is 0% clean or 73% withhold |

## Reading

Contextual evidence obligation **materially improves natural-artifact utility and can do so at zero
safety cost (oracle)** — but the specific reference classifier trades safety for utility and produces
high-risk and adversarial unsafe allows. The honest conclusion is: **validate the concept, but fix the
obligation classifier's safety before any external exposure** (pilot decision candidate D). The safety
gap is concentrated (imperfect claim-type classification, one self-verification disguise), not a flaw in
the obligation model itself.

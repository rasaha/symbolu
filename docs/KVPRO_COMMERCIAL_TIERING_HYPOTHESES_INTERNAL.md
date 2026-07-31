# KVPro — Commercial Tiering Hypotheses (INTERNAL)

> **Internal commercial hypothesis — not validated, not for external circulation.**

This document holds commercial/pricing hypotheses moved out of the public investor supplement
(`KVPRO_INVESTOR_QA_SUPPLEMENT.md`) because they are not evidence-backed. It preserves the prior "Q13"
content verbatim in substance. Nothing here is a measured result or a customer commitment; the number of
genuinely distinct, sellable tiers is an open empirical question (see
`KVPRO_MIXED_PRECISION_SCENARIO_TEST_PLAN.md`).

---

### Q13. "Could KVPro become a pricing/tiering lever — the way providers price context size today?" *(hypothesis — not validated)*

**Answer.** In principle **yes** — KVPro turns *KV fidelity* into a runtime **dial**, and a dial you can
turn per request is exactly what lets you build plan tiers. But the credible version is **capacity/latency
tiering, not a "buy more quality" ladder**, and this is a **business hypothesis we have not tested** —
labeled as such.

The subtlety: KVPro's value is that **quality is held**, so a quality staircase is weak (the standard
tier is already ~parity). The dial really buys **density (cost)** and, separately, **decode speed**. So
the honest tiers are:

- **Cheaper / longer context.** Higher KV-resident capacity at held quality → a lower-priced
  long-context plan, or more context at the same price, than a BF16-only competitor. The customer sees
  "cheaper 128K," not a percentage.
- **Capacity tier vs latency tier (the strongest split).** A **bulk/high-concurrency** plan on KVPro
  (cheaper; agents/RAG/batch; slightly slower per token) vs a **realtime** plan on full BF16 (pricier;
  fastest) — exactly KVPro's own routing model, turned into two SKUs.
- **Premium "guaranteed full-fidelity" tier.** BF16 as the reassurance upsell for regulated /
  quality-critical buyers (legal, health, finance) who want contractual bit-exactness; KVPro is the
  cost-efficient default.

The **compression percentage belongs as the provider's *internal* dial, not a customer-facing number** —
customers buy "cheaper / longer / faster / guaranteed," not "4% protected."

**Honest caveats.** Unproven that buyers prefer a capacity tier over simply demanding the cheapest
full-quality option; **quality-tiering by degradation is hard to sell and to trust** (which is why we
frame it as capacity/latency, where quality stays put); the **decode penalty makes it a capacity play,
not a speed tier**; and **how many genuinely distinct, sellable tiers exist is an empirical question** —
answered by the density-vs-quality experiment (`KVPRO_MIXED_PRECISION_SCENARIO_TEST_PLAN.md`): each
setting that passes the quality bar at a different density is one honest price point. **Measure first,
then price.** *(hypothesis — not validated)*

---

*Internal only. Not for external circulation. Contains no measured commercial outcome. Underlying
technical claims and their evidence labels live in `KVPRO_INVESTOR_QA_SUPPLEMENT.md` and the KVPro
validation reports.*

# First-Interview Script — Design-Partner Discovery (Track C)

**INTERNAL. Interviewer-facing.** A discovery call, **not** a sales call. Its job is
to measure three things and nothing else: (a) is there a **painful, real episode** of
autoscaling that didn't help; (b) does our verdict surface **something their existing
tooling does not** — the *differentiation* signal; (c) early **pull** posture. Record
answers into `05_PULL_SIGNAL_TRACKER.md`; any flags they later share are adjudicated
in `04_SRE_ADJUDICATION_WORKSHEET.md`.

- **Length:** 30–40 min. **Roles:** 1 interviewer + 1 scribe (or record with consent).
- **Target persona (per plan §4):** SRE / platform-engineering owner of large and/or
  spiky, dependency-heavy Kubernetes with active HPA/Karpenter; bonus if they remember
  an autoscaling-amplified incident.

## Interviewer rules (read before every call)
- **Do not pitch savings.** No %, no ROI, no "13.4%", no cost claims. This is a
  reliability/safety conversation. (See `../COMPETITIVE_DIFFERENTIATION_MEMO.md` §9.)
- **Do not over-claim maturity.** No "validated / production / customer-proven."
  We've run simulation + offline trace-replay; not yet a cluster we don't operate.
- **Do not lead the differentiation answer.** Ask it open, then *shut up*. A coached
  "yes" is worthless. A clean "no, we'd have caught it anyway" is a real, useful result.
- **Free interest ≠ demand.** "This is cool" / "I'd turn it on" is **vanity** unless it
  converts to a tracked real-demand signal. Don't record enthusiasm as pull.
- **Measure, don't sell.** If they want to buy, great — route to the data-request +
  NDA step; don't negotiate scope on this call.

---

## 0. Before the call (2 min, solo)
- [ ] Confirm persona fit (SRE/platform owner; HPA/Karpenter in prod).
- [ ] Have `01_PARTNER_BRIEF.md` ready to share *after*, not before, the pain questions.
- [ ] Open a row in the pull tracker for this org.

## 1. Intro & framing (2–3 min)
> "Thanks for the time. We're not selling anything today — we're trying to learn
> whether a problem we think exists is real for teams like yours. We build a
> **read-only** engine that watches an autoscaler and judges, after each scale-out,
> whether it **actually helped**. Before I describe it, I'd rather hear how scaling
> works in your world. Everything you say stays under our NDA, and I'll be honest
> about what we have and haven't proven."

- [ ] Get consent to take notes / record.

## 2. Their environment (5 min) — *context, not leading*
1. What runs on Kubernetes for you, and how big/spiky is it (replica ranges, traffic
   shape)?
2. What autoscales today — HPA, KEDA, Karpenter, VPA? On what signals?
3. How dependency-heavy is the hot path — shared DBs, caches, queues, third-party
   APIs, inference backends?
4. Who owns the autoscaling config and the incident budget — your team, or elsewhere?

## 3. The painful episode (8–10 min) — *the core of the call*
> "Tell me about a time scaling **didn't fix it** — or made it worse."

Probe for a concrete, remembered event (these are the Tier-A candidates):
1. Have you ever **scaled into a cascading failure** — every service scaling at once,
   the herd amplifying the incident?
2. A **runaway** — HPA rode to max / Karpenter kept provisioning while latency or
   errors stayed bad? (the "scaled 4→46 at 2 a.m." shape)
3. An incident where the real bottleneck was **downstream** (DB/cache/3rd-party/lock/
   queue) and adding replicas **did nothing or hurt**?
4. For the worst one: how long until someone realized *more replicas wasn't the fix*?
   What did it cost — extra compute, prolonged incident, both?
5. How often does something in this family happen — monthly, quarterly, rarely?
   *(Note their guess, but we will not rely on it — frequency is measured by replaying
   their history, not by opinion. Plan §12.)*

→ Capture each concrete episode; these seed Track-B replay + SRE adjudication.

## 4. Current tooling (4 min) — *set up the differentiation question honestly*
> "When that happened, what did your tools tell you?"
1. **Datadog / Grafana** — did they show the incident / the scaling, i.e. *what
   happened*?
2. **Kubecost / CloudZero** — did they show *what it cost* (after the fact)?
3. **CAST AI / Karpenter / StormForge / Sedai** — did they show or take the *scaling
   actions*?
4. Did **any** of them tell you, *during* the event, that the **scaling itself was not
   helping** — or did you piece that together manually?

## 5. Show the concept (3–4 min) — *brief, read-only framing*
> "Here's what we'd add — nothing else. A read-only verdict per scale-out:
> **HELPING / NEUTRAL / NOT_HELPING**, plus a flag when an autoscaler keeps scaling
> while the metrics that matter don't improve — the **futile-runaway** pattern. Zero
> write permissions; it reads your Prometheus and never touches the cluster. It's a
> note in a report, not an action."

- [ ] Hand over `01_PARTNER_BRIEF.md`.

## 6. ⭐ The differentiation question (verbatim — the leading indicator) (3–4 min)
Ask it **open**, then stay silent and let them answer:

> **"Thinking about your existing tooling — Datadog/Grafana for *what happened*,
> Kubecost/CloudZero for *what it cost*, CAST AI/Karpenter for the *scaling actions* —
> would a verdict like this have told you something those did NOT: specifically, that a
> scale-out was *not helping*?"**

Follow-ups (only after their first answer):
- "Where would it have changed what you did, or how fast you did it?"
- "Or would you have seen it anyway, just from what you already run?"

**Score it (record in tracker as `differentiation`):**
- **YES** — unprompted, tied to a concrete episode where it would have told them
  something new / sooner. *(Leading indicator of pull.)*
- **NO** — "we'd have caught it anyway from existing tools." *(Pushes toward
  feature/acquisition; an honest, valuable answer — record it as-is.)*
- **UNSURE / coached** — couldn't separate it from existing tooling, or only agreed
  after we led. *(Do not score as YES.)*

## 7. Pull probes (5 min) — *posture only; do not negotiate*
Note each as **real-demand** vs **vanity** per the tracker rules:
1. **Keep / "very disappointed":** "If we ran this in shadow for two weeks and then
   removed it, how disappointed would you be — very / somewhat / not?" (Sean-Ellis)
2. **Expansion:** "If it were useful on this cluster, would you *want* it on others?"
   *(Counts only if later unprompted.)*
3. **Recommend mode:** "Would you want it to surface a recommendation into your
   incident/alert path — not act, just advise?"
4. **Actuation (future):** "Long-term, once it had a clean track record, could you see
   letting it *cap* a provably-futile runaway within strict bounds?"
5. **Willingness to pay:** "Is preventing this class of episode something a reliability
   budget would pay for — separate from your cost tools?" *(Verbal "probably" = vanity;
   only a paid pilot / LOI counts.)*

## 8. Data & next steps (3 min)
- [ ] Gauge willingness to share **6–12 mo Prometheus/HPA history** (the
      highest-leverage ask) and to name an **SRE adjudicator**.
- [ ] If warm → route to `03_DATA_REQUEST_NDA_CHECKLIST.md` (NDA **before** any data).
- [ ] Set a concrete next action + owner + date. Avoid "we'll be in touch."

## 9. Right after the call (5 min, solo)
- [ ] Write the **one or two concrete episodes** they described (for Track-B replay).
- [ ] Record `differentiation = yes / no / unsure` with the verbatim quote.
- [ ] Update the org's row in `05_PULL_SIGNAL_TRACKER.md`; classify each signal
      real-demand vs vanity. **Do not** log enthusiasm as pull.
- [ ] Note any commitment that belongs in the data-request checklist.

---
### Capture block (paste into the tracker / notes)
```
Org / cluster profile:           ____  (size, spiky?, dependency-heavy?, HPA/Karpenter?)
Concrete painful episode(s):     ____  (→ Track-B replay candidates)
Their frequency guess (NOT used as evidence): ____
What existing tooling told them: ____
DIFFERENTIATION (yes/no/unsure): ____  verbatim quote: "____"
"Very disappointed if removed":  very / somewhat / not
Recommend-mode interest:         yes / no
Actuation-someday posture:       yes / no / not-yet
Willingness to pay (LOI?):       ____  (verbal ≠ signal)
History + SRE adjudicator?:      yes / no  → NDA next?  yes / no
Next action / owner / date:      ____
```

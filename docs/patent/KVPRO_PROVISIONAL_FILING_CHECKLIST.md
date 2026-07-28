# KVPro Provisional — One‑Page Filing Checklist (for counsel)

> Hand this to a registered US patent attorney/agent. **Fees change — verify the current USPTO fee
> schedule (37 CFR 1.16) before paying; the figures below are approximate post‑Jan‑2025 amounts and
> may be stale.** Not legal advice.

## A. What a US provisional (35 U.S.C. §111(b)) actually requires
A provisional is deliberately lightweight. To get a filing date you need only:
1. **A written specification** that *describes and enables* the invention (35 U.S.C. §112(a)).
   → Use `KVPRO_PROVISIONAL_DRAFT_v1.md` (§11 prosecution note removed before filing).
2. **Drawings** where needed to understand the invention (§113).
   → Execute FIG. 1–8 from `KVPRO_PROVISIONAL_FIGURES_SPEC.md` as B/W line art.
3. **A provisional cover sheet** identifying the filing as provisional + naming the inventor(s)
   (USPTO form **SB/16**, or the Patent Center equivalent).
4. **The filing fee** (below).

**Not required for a provisional** (this is why it's fast): no claims, no oath/declaration, no
information disclosure statement (IDS), no formal drawings review. *(Including claims — as the draft
does — is fine and preserves scope; they simply aren't examined.)*

## B. Inventor & ownership (resolved)
- **Sole inventor** — one person conceived Concepts A–E; no co‑inventors. Provide **full legal name,
  residence, and citizenship** for the Application Data Sheet (ADS, form **AIA/14**).
- **Assignee:** Ugence Labs. Execute the **assignment** (inventor → Ugence Labs) and record it via
  the USPTO Assignment Center (recording is cheap/often no‑fee for electronic recordation).

## C. Entity status & fees (pick one — affects the fee ~4×)
Verify eligibility with counsel; the assignment to Ugence Labs matters here:
- **Micro entity** (75% discount): requires, among other things, the applicant's gross income under
  the USPTO threshold **and** ≤4 prior nonprovisional filings, **and** no assignment to an entity
  that itself fails the income test. If Ugence Labs has revenue/employees, micro may **not** apply.
  File cert **SB/15A** only if it genuinely qualifies. *(~$65 provisional filing fee if eligible.)*
- **Small entity** (60% discount): business with <500 employees, not obligated to assign to a
  large entity. Common for an early‑stage startup. *(~$130 provisional filing fee.)*
- **Undiscounted / large entity.** *(~$325 provisional filing fee.)*
- **Application size fee** only applies if the spec + drawings exceed **100 sheets** (they won't).
- **Do not over‑claim micro status** — a wrong micro certification can be treated as fraud on the
  Office. When unsure, file **small entity**.

## D. Filing mechanics
- File electronically via **USPTO Patent Center** (patentcenter.uspto.gov). No paper.
- Attach: (1) specification PDF, (2) drawings PDF, (3) SB/16 cover sheet, (4) ADS (recommended even
  though optional for a provisional — it cleanly captures inventor + any priority), (5) SB/15A if
  micro. Pay the 1.16(d) fee.
- You'll receive an **application number and filing date** immediately — that date is your priority
  anchor.

## E. The 12‑month clock (calendar this the day you file)
- Within **12 months** of the provisional's filing date you must file the **non‑provisional**
  (and/or a **PCT** for foreign rights) claiming priority to it — this deadline is **not
  extendable**. Miss it and the provisional expires with no benefit.
- Anything the provisional does **not** describe/enable gets **no** priority — so file it rich
  (the current draft is). Add any new embodiments now rather than relying on the non‑provisional.
- **Foreign rights:** the provisional preserves your Paris Convention priority for 12 months; decide
  PCT vs. direct national filings before the deadline.

## F. Pre‑filing hygiene (do these first)
- [ ] Confirm the **source repo is private** through filing (a public repo = public disclosure — see
      draft §13). If it was ever public, tell counsel the date.
- [ ] Keep the method **NDA‑only** — no posting/presenting/offering for sale before filing.
- [ ] Execute the **inventor→Ugence Labs assignment**.
- [ ] **Delete the §11 prosecution note** from the copy that gets filed (keep it in the attorney file).
- [ ] Have counsel run/scope a **prior‑art search** (KIVI, KVQuant, SAW‑INT4 [arXiv 2604.19157],
      CacheGen, GEAR, KVTuner, QuaRot, H2O, Atom, Marlin/QServe, vLLM prefix‑caching disclosures).
- [ ] Confirm inventor legal name/residence/citizenship for the ADS.

## G. What to hand counsel (the packet)
1. `KVPRO_PROVISIONAL_DRAFT_v1.md` (spec) — **minus §11**.
2. `KVPRO_PROVISIONAL_FIGURES_SPEC.md` → executed FIG. 1–8.
3. `KVPRO_PATENT_CLAIMS_ANALYSIS.md` (strategy/prior‑art context).
4. This checklist.
5. Inventor details + Ugence Labs assignment.

**Bottom line for counsel:** sole‑inventor provisional, no prior public disclosure by the inventor,
anchor claim = Concept E (static prefix‑compatible mask), file promptly (SAW‑INT4 prior‑art date
Apr 21 2026), small‑entity unless micro clearly qualifies, then calendar the non‑provisional/PCT at
+12 months.

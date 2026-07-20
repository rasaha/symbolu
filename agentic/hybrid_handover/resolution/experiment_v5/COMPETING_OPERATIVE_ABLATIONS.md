# COMPETING_OPERATIVE_ABLATIONS — Competing Operative Resolution Experiment v0.1

## Table 3 — C0–C4 aggregate (hidden). Discovery/classification identical (Table 2).

| condition | select | cover | govG | packP | false-ab | miss-ab | ab-recall | unsafe |
|---|---|---|---|---|---|---|---|---|
| C0_g3_control | 0.3860 | 0.9500 | 0.6000 | 0.5167 | 0.0000 | 0.2167 | 0.1875 | 2 |
| C1_extract | 0.3860 | 0.9500 | 0.6000 | 0.5167 | 0.0000 | 0.2167 | 0.1875 | 2 |
| C2_scope | 0.3860 | 0.9500 | 0.6000 | 0.5167 | 0.0000 | 0.2167 | 0.1875 | 2 |
| C3_classify | 0.3860 | 0.9500 | 0.6000 | 0.5167 | 0.0000 | 0.2167 | 0.1875 | 2 |
| C4_full | 0.3750 | 0.9333 | 0.6000 | 0.5167 | 0.0000 | 0.2000 | 0.2500 | 2 |

C0=C1=C2=C3: extraction, scope, and classification build the operative representation
without changing the decision. Only **C4** acts, and only via precise abstention. It
abstains on **one** additional case (coverage 0.95 → 0.9333), with false-abstention
held at 0 — the opposite of G4's failure.

## Historical comparators (diagnostic only)

| condition | select | cover | false-ab | note |
|---|---|---|---|---|
| frozen v0.2 | 0.2982 | 0.9500 | 0.0000 | pre-G3 baseline |
| C0 = G3 | 0.3860 | 0.9500 | 0.0000 | principal control |
| C4 (this) | 0.3750 | 0.9333 | 0.0000 | precise abstention |
| historical G4 | 0.5294 | 0.2833 | 0.5000 | coarse abstention (failed) |

The contrast with historical G4 is the point: G4 reached selective 0.5294 only by
collapsing coverage to 0.2833 and driving false-abstention to 0.5. C4 keeps coverage
at 0.9333 and false-abstention at 0 — it does **not** over-abstain — but on this pilot
it also finds no genuine conflict to exploit, so it adds no selective gain over G3.

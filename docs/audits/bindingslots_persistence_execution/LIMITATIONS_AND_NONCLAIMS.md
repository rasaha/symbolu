# Limitations and non-claims

This is a **bounded synthetic-task** experiment on one architecture (2M params, 32 slots, seq 160),
one retrieval task family, one distance suite (d16/d96/d220), five reserved seeds (23–27), under the
frozen merged protocol executed via the merged adaptive decision tree.

The result does **not** establish:

- natural-language transfer;
- production readiness;
- general language-modeling benefit;
- long-horizon retention beyond step 1200;
- transfer across slot count, sequence length, or model scale;
- KDA readiness or KDA superiority;
- any memory or speed benefit;
- architectural validation.

**Selected candidate ≠ proven superior to unrun candidates.** Under the adaptive plan, later arms are
omitted once an earlier arm fully passes. An unrun arm is `NOT_EVALUATED` — never failed or inferior.
A selected candidate proves only that it passed the frozen advancement gate on all five seeds and
that later intervention testing was unnecessary for this decision. It still requires an **independent
confirmatory replication** (a separate, later, un-started phase).

**KDA validation remains BLOCKED.** `READY_FOR_KDA_VALIDATION` is never emitted. Even on selection the
readiness is at most `KDA_VALIDATION_BLOCKED_PENDING_INDEPENDENT_CONFIRMATION`, and that confirmation
is not begun here.

Mechanistic statements (e.g., routing decay after withdrawal, address-independent shortcut) are
single-trajectory reads on five seeds and are phrased conservatively.

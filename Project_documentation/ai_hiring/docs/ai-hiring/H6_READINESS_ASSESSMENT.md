# H6 — Readiness Assessment

## Classification: `PACKAGE_READY_FOR_CONTROLLED_PILOT`

The AI Hiring product `0.6.0` is ready to be **installed, demonstrated, and used in a
controlled pilot** where no real hiring action is taken and no personal data leaves
the process. Every limitation below is a deliberate **scope boundary**, not a
correctness or governance-boundary defect.

### Why `PACKAGE_READY_FOR_CONTROLLED_PILOT` and not a higher tier

A production tier is deliberately **not** claimed. The package ships only
deterministic-simulation adapters and makes no production, scale, or
fairness/compliance certification. `version_info().production_certified` is hard-coded
`False`, and the config fails closed on any production execution mode.

### Why not `PACKAGE_READY_WITH_LIMITATIONS` or `NOT_READY`

- The package is coherent, **installable in a clean environment** (editable + wheel,
  verified from a non-repo cwd), **demonstrable** (`demo`/`report`/`verify`), and
  **maintainable** (typed config, documented API, changelog, versioning policy).
- Every product claim is backed by a test, runnable command, or verification tool
  (`PRODUCT_CLAIMS_AUDIT.md`).
- No correctness or governance-boundary defect exists; the frozen platform is
  byte-identical (freeze digest unchanged) with 0 dependency violations.

The limitations are all *absences of production scope* — appropriate for a controlled
pilot — rather than faults in what is shipped. `PACKAGE_READY_FOR_CONTROLLED_PILOT`
states exactly that.

## Evidence summary

| Dimension | Status | Evidence |
|---|---|---|
| Installs in clean env | ✅ | editable + wheel `verify` PASS from non-repo cwd |
| Demonstrable | ✅ | `python -m ai_hiring.product {demo,report,verify}` |
| Public API stable enough to pilot | ✅ (pre-1.0) | `API_REFERENCE.md`; `test_h6_product.py` |
| Config fail-closed | ✅ | `test_h6_product.py` config tests |
| No production effect | ✅ | `test_h6_boundary.py`; `verify` |
| No new governance/architecture | ✅ | boundary tests; freeze PASS; 0 dep violations |
| Accountability + redaction | ✅ | `test_h6_product.py` accountability tests |
| Claims audited | ✅ | `PRODUCT_CLAIMS_AUDIT.md` |
| Tests / battery | ✅ | 778 AI Hiring / 917 platform+app |

## Separated limitations (scope boundaries, not defects)

- No production integrations, offers, or rejections (`ISSUE_OFFER`/`SEND_REJECTION`
  unimplemented); deterministic simulation only.
- No scale/performance or fairness/compliance certification.
- In-memory persistence and static identity only.
- Whole-repository baseline is not clean (pre-existing, unrelated failures).

See `product/KNOWN_LIMITATIONS.md` for the authoritative list.

## Recommendation

Proceed to a **controlled pilot / evaluation** using the packaged product and its
accountability report. Any move toward production requires the deferred work in
`product/DEPLOYMENT.md` (production adapters, durable persistence, enterprise identity,
scale validation, and independent fairness/compliance review) and a re-classification.

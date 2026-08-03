# E2E Scenario Coverage (C1)

Four direct Playwright specs run against the REAL local P3B backend with live
frozen scenario data (no mocked eligibility, no test-only domain logic):

| Scenario | Flow | Result |
|---|---|---|
| Procurement | catalog → workflow → AI-agent role → role requirements → registry → eligibility → ineligible agent → reasons/evidence/fingerprints → maturity | pass |
| Customer Support | catalog → overview → workflow (node/edge accounting) → eligibility rows → one explanation (evidence/policy or empty) → synthetic + maturity | pass |
| Cybersecurity — Feasible | overview verification → workflow → complete role-agent accounting → eligible + ineligible explanations (no ranking/assignment language) → maturity | pass |
| Cybersecurity — No Feasible Team | eligibility failures visible → no empty-success → no preferred/assignment language → infeasibility is not an app error → maturity | pass |

Deterministic selectors (test ids, exact nav names, row filters). Browser
artifacts (`test-results/`, `playwright-report/`) are cleaned before commit and
gitignored.

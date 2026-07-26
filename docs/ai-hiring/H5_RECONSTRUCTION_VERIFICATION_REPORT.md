# H5 — Reconstruction Verification Report

## Method
`HiringActionReconstructionService` (H4) rebuilds the complete chain from an action
proposal back to origin; `GovernanceCaseReconstructionService` covers the governance leg.
H5 exercises reconstruction across every scenario (`test_h5_reconstruction.py`,
`test_h5_scenarios.py`).

## Verified for every executed scenario (§17)
tenant identity · candidate/application scope · requisition & job-definition versions ·
rubric version · evidence package (fingerprint) · structured claims · TAP assessments
(provider bindings) · recommendation version · reviewer/decision activity · DecisionCase ·
human decision · override record (when present) · action proposal · ActionGate request &
response (authorization record with constraints/obligations/expiry) · execution attempts ·
receipt · reconciliation · compensation/remediation (when present) · hiring audit · DGM
audit (by correlation) · provider records · correlation & causation chains.

## Defect detection (validated)
The validator detects and fails on: **broken links** (attempt→authorization mismatch —
`test_reconstruction_detects_broken_link`), **altered hashes / tampered audit chain**
(`test_tampered_audit_chain_detected`), **wrong tenant** (`test_cross_tenant_reconstruction_denied`),
action-without-a-decision and execution-without-authorization (prevented upstream by the
H4 gates; reconstruction confirms `links_intact` + `decision_cites_recommendation`),
receipt-without-attempt and reconciliation-without-evidence (structurally impossible —
attempts carry receipts; reconciliation references the attempt).

## Result
For all normal executed scenarios, `reconstructed == True` with
`hiring_hash_chain_valid`, `links_intact`, and `tenant_scope_consistent` all true. For
tamper/broken-link injections, `reconstructed == False` with the specific issue surfaced.

# Sanitized Enterprise Replay — Customer Data-Intake Package

This package lets a customer hand over **sanitized historical records** for the
account-takeover vertical slice so they can be normalized, linked, replayed, and
reviewed with the frozen Story Policy Pack. It is produced because **no valid
sanitized enterprise dataset is present** in the repository — see
`docs/replay/SANITIZED_ENTERPRISE_REPLAY_REPORT.md` (verdict:
`STOP — sanitized enterprise replay data required`).

Nothing here is enterprise data. `example_sanitized_record.json` is a **synthetic**
illustration of the record shape only.

## What to supply

| Artifact | Template | Notes |
|---|---|---|
| Replay manifest | `replay_manifest.template.json` | Immutable; includes data-use authorization reference. |
| Sanitized records | `replay_record.schema.json` | One JSON/JSONL record per event/proposal/approval/provider/receipt. |
| Source-event mapping | `source_event_mapping.template.json` | One entry per source event type; unmapped → reported, not dropped. |
| Trusted-provider mapping | `provider_mapping.template.json` | Provider failure may never map to ALLOW. |
| Policy-gap report | `policy_gap_report.template.md` | Confirms the reference pack fits the customer process. |
| Reviewer worksheet | `reviewer_worksheet.template.json` | Filled after replay by fraud-ops / risk. |

## Redaction guidance (required)

- **Never** transmit raw secrets, credentials, customer/legal names, account numbers,
  device serials, beneficiary names, IBANs, card numbers, or any PII.
- Replace every identifier (actor, account, device, beneficiary, destination) with a
  **stable redaction token**: `redacted:<first-16-hex of SHA-256(salt || value)>`. The
  salt stays with the customer; the same real value must map to the same token so
  same-account / same-device / same-beneficiary relationships survive (the mandatory
  StoryGraph edges depend on **exact token equality**, not fuzzy labels).
- Amounts may be bucketed or scaled consistently if raw values are sensitive; keep
  ordering and the amount-cap comparison meaningful.
- Set `redaction_status` per record; any `FAILED` record is quarantined and fails the
  data-quality gate.

## Secure handoff requirements

- Transfer over an encrypted channel to a tenant-isolated location; never paste
  records into issues, PRs, chat, or committed fixtures.
- Include the signed `data_use_authorization_reference` in the manifest; replay will
  not proceed without it.
- Provide per-file `source_file_digests` (SHA-256) so the manifest binds the exact
  bytes evaluated.
- One tenant per dataset (or a clearly-partitioned multi-tenant export); the runner
  rejects any record missing a tenant to prevent cross-tenant mixing.

## Data-quality bar (pre-registered)

The pre-registered minimums and R1–R9 acceptance gates
(`ugence_storygraph/policypack/replay_gates.py`, sealed digest recorded in the
phase report) must be met before findings are examined. Replay **stops visibly** when
missing/unreliable fields make a mandatory relationship impossible to evaluate.

## After handoff — the official run

1. **Commit A** — code + customer Policy Pack + source/provider mappings + replay
   manifest + frozen gates + normalization rules + runner. Record Commit A's hash.
2. Run the frozen replay once against Commit A.
3. **Commit B** — evidence-only record (`evaluation/evidence_chain.py`): evaluated
   Commit A hash, dataset/policy/config digests, raw + derived metrics, findings
   manifest, review results, verdict, evidence-record digest. Commit B changes no
   algorithm, mapping, policy, threshold, or dataset input (path-verified).

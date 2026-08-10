# Trace fixtures — provenance

These are **small real slices** of the Azure Public Dataset, committed only so the
replay adapters have deterministic unit-test inputs. They are NOT the full traces.

| fixture | source file (Azure/AzurePublicDataset) | full rows | slice rows |
|---|---|---|---|
| `azure_llm_conv_sample.csv` | `data/AzureLLMInferenceTrace_conv.csv` | 19,366 | 800 |
| `azure_llm_code_sample.csv` | `data/AzureLLMInferenceTrace_code.csv` | 8,819 | 800 |
| `azure_vm_noise_sample.csv` | `vm-noise-data/.../unit=MiB_s.csv` | ~6,946 | 400 |

**License:** Azure Public Dataset is released under **CC-BY-4.0** (Attribution 4.0
International). Schemas: LLM traces `TIMESTAMP,ContextTokens,GeneratedTokens`;
VM-noise `value,runtime,starttime,VM_id`.

Fetch the FULL traces with `scripts/fetch_real_traces.sh` (writes to
`data/cloud_traces/`, gitignored). Replay numbers in the artifacts are computed on
the FULL traces, not these slices.

## Schema fixtures (NOT real data)

`alibaba_msresource_SCHEMA_FIXTURE.csv` and `google_borg_task_usage_SCHEMA_FIXTURE.csv`
are **synthetic rows in the real column schema**, committed ONLY so the Alibaba and
Google adapters (status PENDING_DATA) have a deterministic parser test. They are
**not** real Alibaba/Google data and produce **no** reported number.

`partner_prometheus_SCHEMA_FIXTURE.csv` + `partner_incidents_SCHEMA_FIXTURE.csv` are
**synthetic rows in the partner Prometheus/HPA export schema**, committed ONLY to
validate the **Tier-A detector tooling** (`cloud_controller/replay/tier_a.py`,
`PartnerPrometheusAdapter`, status PENDING_DATA). The metrics trace contains a
capacity-bound HELPING stretch and a planted futile-runaway stretch (latency high /
utilization collapsing while replicas climb past M=20) overlapping the committed
incident window — exercising every classification branch. They are **not** real
partner data and produce **no market number**: any Tier-A count or APCY computed on
them is a *tooling self-test*, and the pre-registered coverage trip-wire
(`Project_documentation/governance/docs/cloud_scaling_real_validation/TIER_A_DETECTOR_SPEC.md` §5c) deliberately refuses
to report it as evidence. Real partner runs are labelled `real-trace-replay (estimate
pending live adjudication)` and gated on SRE adjudication.

// Bring Your Workflow (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §22, BW-1 to BW-5).
//
// The one screen on which the operator's own document enters the studio: Ugence
// Workflow IR JSON, pasted or chosen from a local file, gated in the browser by
// gate.ts and then handed to exactly three operations of the frozen v1 contract:
// validate, adapt, compare-adaptations. It stores nothing (no server write exists for
// it, no browser storage is touched), fetches no URL, executes nothing, never touches
// the scenario catalog, and accepts no code, YAML, archive, credential or
// framework-native object. Results live in component state and leave only as a local
// download. The guided example is the procurement compiled workflow the catalog
// itself serves, bundled with this screen, never fetched.
import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import { adaptWorkflow, ApiClientError, compareAdaptations, validateWorkflow } from "@/api/client";
import type { ApiResponseEnvelope } from "@/api/types";
import type { AdaptWorkflowResult, CompareAdaptationsResult, ValidateWorkflowResult } from "@/api/types-bring";
import { Card, Field, Fingerprint, Section } from "@/design-system/primitives";
import { clientDigest, gateWorkflowText, LIMITS, SUPPORTED_CONTRACTS, type GateResult } from "./gate";
import exampleWorkflowIrV1 from "./example-workflow-ir.v1.json";

export const SCREEN_NAME = "Bring Your Workflow";
export const SCREEN_TAGLINE = "Validate and adapt an existing agentic workflow for Ugence governance.";
export const DISCLAIMER = "Accepts Ugence Workflow IR JSON. It does not execute, publish or persist the submitted workflow.";
export const MATURITY = "REFERENCE_GRADE";

type Envelope<T> = ApiResponseEnvelope<T>;

interface Outcome {
  validation: Envelope<ValidateWorkflowResult> | null;
  adaptation: Envelope<AdaptWorkflowResult> | null;
  comparison: Envelope<CompareAdaptationsResult> | null;
}

const EMPTY: Outcome = { validation: null, adaptation: null, comparison: null };

async function readLocalFile(file: File): Promise<string> {
  if (typeof file.text === "function") return file.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

function downloadJson(name: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function describeError(err: unknown): { code: string; message: string } {
  if (err instanceof ApiClientError) return { code: err.code, message: err.message };
  if (err instanceof Error) return { code: err.name, message: err.message };
  return { code: "unknown", message: String(err) };
}

function shortDigest(value: string | null | undefined) {
  return <Fingerprint value={value} />;
}

function Counts({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts).sort();
  if (!entries.length) return <span className="text-ink-3">none</span>;
  return (
    <ul className="flex flex-wrap gap-1">
      {entries.map(([k, n]) => (
        <li key={k} className="rounded border border-surface-border bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-ink-2">
          {k} × {n}
        </li>
      ))}
    </ul>
  );
}

function Names({ names }: { names: string[] }) {
  if (!names.length) return <span className="text-ink-3">none declared</span>;
  return <span className="font-mono text-[11px]">{names.join(", ")}</span>;
}

function Diagnostics({ items, testId }: { items: Array<Record<string, unknown>>; testId: string }) {
  if (!items.length) return <p className="text-xs text-ink-3" data-testid={testId}>no diagnostics</p>;
  return (
    <ul className="space-y-1 text-xs" data-testid={testId}>
      {items.map((d, i) => (
        <li key={i} className="rounded border border-surface-border bg-surface-2/60 px-2 py-1">
          <span className="font-mono text-[11px] text-ink-2">{String(d.code ?? d.severity ?? "diagnostic")}</span>{" "}
          <span className="text-ink-1">{String(d.message ?? JSON.stringify(d))}</span>
          {typeof d.field_path === "string" && d.field_path ? <span className="text-ink-3"> at {d.field_path}</span> : null}
        </li>
      ))}
    </ul>
  );
}

function DocumentInput({
  id,
  label,
  text,
  onText,
  gate,
  testPrefix,
}: {
  id: string;
  label: string;
  text: string;
  onText: (t: string) => void;
  gate: GateResult | null;
  testPrefix: string;
}) {
  const [fileNote, setFileNote] = useState<string | null>(null);
  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > LIMITS.document_bytes) {
      setFileNote(`${file.name}: ${file.size} bytes exceed the limit of ${LIMITS.document_bytes} (1 MiB); not read`);
      return;
    }
    const content = await readLocalFile(file);
    setFileNote(`${file.name} (${file.size} bytes) read locally; nothing was uploaded until you act below`);
    onText(content);
  };
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-xs font-semibold uppercase tracking-wide text-ink-2">
        {label}
      </label>
      <textarea
        id={id}
        value={text}
        onChange={(e) => onText(e.target.value)}
        spellCheck={false}
        rows={10}
        placeholder='{ "ir_version": "workflow_ir.v2", ... }'
        className="w-full rounded border border-surface-border bg-surface-0 p-2 font-mono text-[11px] text-ink-1"
        data-testid={`${testPrefix}-text`}
      />
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <label className="text-ink-2">
          or choose a local JSON file{" "}
          <input
            type="file"
            accept="application/json,.json"
            onChange={onFile}
            aria-label={`${label} file`}
            className="text-[11px]"
            data-testid={`${testPrefix}-file`}
          />
        </label>
        {fileNote ? <span className="text-ink-3">{fileNote}</span> : null}
      </div>
      {gate && !gate.ok ? (
        <p role="alert" className="rounded border border-danger/40 bg-danger/10 p-2 text-xs text-ink-1" data-testid={`${testPrefix}-refusal`}>
          <span className="font-mono text-[11px]">{gate.code}</span> · {gate.message}
        </p>
      ) : null}
    </div>
  );
}

export function BringYourWorkflowScreen() {
  const [text, setText] = useState("");
  const [secondText, setSecondText] = useState("");
  const [digest, setDigest] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome>(EMPTY);
  const [busy, setBusy] = useState<"validate" | "adapt" | "compare" | null>(null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  const gate = useMemo(() => (text.trim() ? gateWorkflowText(text) : null), [text]);
  const secondGate = useMemo(() => (secondText.trim() ? gateWorkflowText(secondText) : null), [secondText]);

  // A result describes exactly one document: any edit clears every result and error.
  useEffect(() => {
    setOutcome(EMPTY);
    setError(null);
  }, [text, secondText]);

  useEffect(() => {
    let live = true;
    setDigest(null);
    if (gate?.ok) {
      clientDigest(gate.document).then((d) => {
        if (live) setDigest(d);
      });
    }
    return () => {
      live = false;
    };
  }, [gate]);

  const ready = !!gate?.ok && busy === null;
  const comparePair = useMemo(() => {
    if (!gate?.ok || !secondGate?.ok) return null;
    if (gate.declaredVersion === secondGate.declaredVersion) return null;
    const v1 = gate.declaredVersion === "workflow_ir.v1" ? gate.document : secondGate.document;
    const v2 = gate.declaredVersion === "workflow_ir.v2" ? gate.document : secondGate.document;
    return { v1, v2 };
  }, [gate, secondGate]);
  const compareNote =
    gate?.ok && secondGate?.ok && gate.declaredVersion === secondGate.declaredVersion
      ? `comparison needs one ${SUPPORTED_CONTRACTS[0]} and one ${SUPPORTED_CONTRACTS[1]} document; both declare ${gate.declaredVersion}`
      : null;

  const run = async (kind: "validate" | "adapt" | "compare") => {
    if (!gate?.ok) return;
    setBusy(kind);
    setError(null);
    try {
      if (kind === "validate") {
        const validation = await validateWorkflow(gate.document, gate.declaredVersion, digest ?? undefined);
        setOutcome((o) => ({ ...o, validation }));
      } else if (kind === "adapt") {
        const adaptation = await adaptWorkflow(gate.document, gate.declaredVersion);
        setOutcome((o) => ({ ...o, adaptation }));
      } else if (comparePair) {
        const comparison = await compareAdaptations(comparePair.v1, comparePair.v2);
        setOutcome((o) => ({ ...o, comparison }));
      }
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(null);
    }
  };

  const report = () => {
    if (!gate?.ok) return;
    downloadJson("ugence-bring-your-workflow-report.json", {
      schema: "governance_studio.bring-your-workflow.report.v1",
      screen: SCREEN_NAME,
      maturity: MATURITY,
      disclaimer: DISCLAIMER,
      input: {
        declared_contract_version: gate.declaredVersion,
        bytes: gate.bytes,
        measures: gate.measures,
        client_canonical_digest: digest,
        summary: gate.summary,
      },
      validate: outcome.validation,
      adapt: outcome.adaptation,
      compare: outcome.comparison,
    });
  };

  const envelope = () => {
    if (!outcome.adaptation) return;
    downloadJson("ugence-adapted-workflow-envelope.json", outcome.adaptation.result.adaptation_envelope);
  };

  const anyResult = !!(outcome.validation || outcome.adaptation || outcome.comparison);

  return (
    <div className="space-y-4" data-testid="bring-your-workflow">
      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-ink-0">{SCREEN_NAME}</h2>
          <span className="rounded border border-surface-border bg-surface-2 px-2 py-0.5 font-mono text-[11px] text-ink-2" title="maturity">
            {MATURITY}
          </span>
          <span className="rounded border border-surface-border bg-surface-2 px-2 py-0.5 text-[11px] text-ink-2">ephemeral · no execution</span>
        </div>
        <p className="text-sm text-ink-2">{SCREEN_TAGLINE}</p>
        <p className="rounded border border-surface-border bg-surface-2/50 p-3 text-xs text-ink-1" data-testid="bring-disclaimer">
          {DISCLAIMER}
        </p>
      </header>

      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="btn-action px-3 py-1.5 text-xs"
            onClick={() => setText(JSON.stringify(exampleWorkflowIrV1, null, 2))}
            data-testid="bring-load-example"
          >
            Load the guided example
          </button>
          <button
            type="button"
            className="rounded border border-surface-border px-3 py-1.5 text-xs text-ink-2 hover:bg-surface-2"
            onClick={() => {
              setText("");
              setSecondText("");
            }}
            data-testid="bring-clear"
          >
            Clear
          </button>
          <span className="text-xs text-ink-3">
            The guided example is the procurement compiled workflow the scenario catalog serves, bundled with this screen.
          </span>
        </div>
        <DocumentInput id="bring-workflow" label="Workflow IR JSON" text={text} onText={setText} gate={gate} testPrefix="bring" />
      </Card>

      {gate?.ok ? (
        <Card className="p-4" data-testid="bring-summary">
          <Section title="What the document declares">
            <dl>
              <Field label="declared version">
                <span className="font-mono text-[11px]">{gate.declaredVersion}</span>
              </Field>
              <Field label="size">
                {gate.bytes} bytes · depth {gate.measures.depth} · {gate.measures.elements} values
              </Field>
              <Field label="nodes / edges">
                <span data-testid="bring-node-count">{gate.summary.nodeCount}</span> nodes · <span data-testid="bring-edge-count">{gate.summary.edgeCount}</span> edges
              </Field>
              <Field label="node kinds">
                <Counts counts={gate.summary.kinds} />
              </Field>
              <Field label="declared dispositions">
                <Counts counts={gate.summary.dispositions} />
              </Field>
              <Field label="human review required">
                <Names names={gate.summary.humanReviewNodes} />
              </Field>
              <Field label="human authority required">
                <Names names={gate.summary.humanAuthorityNodes} />
              </Field>
              <Field label="required tool refs">
                <Names names={gate.summary.toolRefs} />
              </Field>
              <Field label="referenced capabilities">
                <Names names={gate.summary.capabilityRefs} />
              </Field>
              <Field label="policy pack">{gate.summary.policyPack ?? <span className="text-ink-3">none declared</span>}</Field>
              <Field label="declared fingerprint">{shortDigest(gate.summary.workflowFingerprint)}</Field>
              <Field label="canonical digest (client)">
                {digest ? shortDigest(digest) : <span className="text-ink-3">unavailable in this browser; the server's digest stands</span>}
              </Field>
            </dl>
          </Section>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-action px-3 py-1.5 text-xs" disabled={!ready} onClick={() => run("validate")} data-testid="bring-validate">
              {busy === "validate" ? "Validating…" : "Validate"}
            </button>
            <button type="button" className="btn-action px-3 py-1.5 text-xs" disabled={!ready} onClick={() => run("adapt")} data-testid="bring-adapt">
              {busy === "adapt" ? "Adapting…" : "Adapt"}
            </button>
            <span className="text-xs text-ink-3">Each sends the document once, to one operation of the frozen v1 contract, and keeps nothing.</span>
          </div>
        </Card>
      ) : null}

      {gate?.ok ? (
        <Card className="p-4">
          <Section title="Compare adaptation alternatives">
            <p className="mb-2 text-xs text-ink-2">
              Provide the same workflow in the other contract version; the server adapts both and reports whether the adaptations are
              equivalent.
            </p>
            <DocumentInput
              id="bring-second-workflow"
              label="Second Workflow IR JSON, for comparison"
              text={secondText}
              onText={setSecondText}
              gate={secondGate}
              testPrefix="bring-second"
            />
            {compareNote ? (
              <p role="alert" className="mt-2 rounded border border-surface-border bg-surface-2/60 p-2 text-xs text-ink-1" data-testid="bring-compare-note">
                {compareNote}
              </p>
            ) : null}
            <button
              type="button"
              className="btn-action mt-2 px-3 py-1.5 text-xs"
              disabled={!ready || !comparePair}
              onClick={() => run("compare")}
              data-testid="bring-compare"
            >
              {busy === "compare" ? "Comparing…" : "Compare adaptations"}
            </button>
          </Section>
        </Card>
      ) : null}

      {error ? (
        <p role="alert" className="rounded border border-danger/40 bg-danger/10 p-3 text-xs text-ink-1" data-testid="bring-server-refusal">
          The server refused: <span className="font-mono text-[11px]">{error.code}</span> · {error.message}
        </p>
      ) : null}

      {outcome.validation ? (
        <Card className="p-4" data-testid="bring-validation-result">
          <Section title="Validation">
            <dl>
              <Field label="state">
                <span className="font-mono text-[11px]" data-testid="bring-validation-state">
                  {outcome.validation.result.validation_state}
                </span>
              </Field>
              <Field label="declared version">
                <span className="font-mono text-[11px]">{outcome.validation.result.declared_contract_version}</span>
              </Field>
              <Field label="supported">
                {outcome.validation.result.supported_version ? "yes" : "no"} (server supports {outcome.validation.result.supported_contracts.join(", ")})
              </Field>
              <Field label="integrity">
                {outcome.validation.result.integrity.checked ? (
                  <span data-testid="bring-integrity">
                    client {shortDigest(outcome.validation.result.integrity.source_digest)} · server{" "}
                    {shortDigest(outcome.validation.result.integrity.computed_digest)} ·{" "}
                    {outcome.validation.result.integrity.match ? "match" : "differ; the server's canonical digest is the one of record"}
                  </span>
                ) : (
                  <span className="text-ink-3">not checked; no client digest was available to send</span>
                )}
              </Field>
              <Field label="request">
                <span className="font-mono text-[11px]">{outcome.validation.request_id}</span> · awc {outcome.validation.awc_version}
              </Field>
            </dl>
            <Diagnostics items={outcome.validation.result.diagnostics} testId="bring-validation-diagnostics" />
          </Section>
        </Card>
      ) : null}

      {outcome.adaptation ? (
        <Card className="p-4" data-testid="bring-adaptation-result">
          <Section title="Adaptation">
            <dl>
              <Field label="adapter mode">
                <span className="font-mono text-[11px]" data-testid="bring-adapter-mode">
                  {outcome.adaptation.result.adapter_mode}
                </span>
              </Field>
              <Field label="ok">{outcome.adaptation.result.ok ? "yes" : "no"}</Field>
              <Field label="adaptation fingerprint">{shortDigest(outcome.adaptation.result.adaptation_fingerprint)}</Field>
              <Field label="envelope fingerprint">{shortDigest(outcome.adaptation.result.adaptation_envelope_fingerprint)}</Field>
              <Field label="input digest (server)">{shortDigest(outcome.adaptation.input_digests.workflow)}</Field>
            </dl>
          </Section>
          <Section title="Node dispositions" count={outcome.adaptation.result.node_dispositions.length}>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-ink-3">
                    <th className="py-1 pr-2">node</th>
                    <th className="py-1 pr-2">kind</th>
                    <th className="py-1 pr-2">disposition</th>
                    <th className="py-1 pr-2">agent role</th>
                    <th className="py-1">reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {outcome.adaptation.result.node_dispositions.map((d) => (
                    <tr key={d.node_id} className="border-t border-surface-border/50">
                      <td className="py-1 pr-2 font-mono text-[11px]">{d.node_id}</td>
                      <td className="py-1 pr-2 font-mono text-[11px]">{d.source_node_kind}</td>
                      <td className="py-1 pr-2 font-mono text-[11px]">{d.disposition}</td>
                      <td className="py-1 pr-2">{d.is_agent_role ? d.role_id || "yes" : "no"}</td>
                      <td className="py-1 font-mono text-[11px] text-ink-2">{d.reason_codes.join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
          <Section title="Role requirements" count={outcome.adaptation.result.role_requirements.length}>
            {outcome.adaptation.result.role_requirements.length ? (
              <ul className="space-y-1 text-xs">
                {outcome.adaptation.result.role_requirements.map((r) => (
                  <li key={r.role_id} className="rounded border border-surface-border bg-surface-2/60 px-2 py-1">
                    <span className="font-mono text-[11px]">{r.role_id}</span> · {r.role_name} · from {r.source_node_id} ({r.source_node_kind}) · needs{" "}
                    <span className="font-mono text-[11px]">{r.required_capabilities.join(", ") || "nothing declared"}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-ink-3">no agent role derived</p>
            )}
          </Section>
          <Diagnostics items={outcome.adaptation.result.diagnostics} testId="bring-adaptation-diagnostics" />
        </Card>
      ) : null}

      {outcome.comparison ? (
        <Card className="p-4" data-testid="bring-comparison-result">
          <Section title="Comparison of adaptations">
            <dl>
              <Field label="equivalence">
                <span className="font-mono text-[11px]" data-testid="bring-equivalence-state">
                  {outcome.comparison.result.equivalence_state}
                </span>
              </Field>
              <Field label="v1 adaptation">{shortDigest(outcome.comparison.result.v1_adaptation_fingerprint)}</Field>
              <Field label="v2 adaptation">{shortDigest(outcome.comparison.result.v2_adaptation_fingerprint)}</Field>
              <Field label="report">
                <pre className="max-h-64 overflow-auto rounded bg-surface-2/60 p-2 font-mono text-[11px]">
                  {JSON.stringify(outcome.comparison.result.report, null, 2)}
                </pre>
              </Field>
            </dl>
          </Section>
        </Card>
      ) : null}

      {anyResult ? (
        <Card className="p-4">
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-action px-3 py-1.5 text-xs" onClick={report} data-testid="bring-download-report">
              Download report
            </button>
            <button
              type="button"
              className="btn-action px-3 py-1.5 text-xs"
              disabled={!outcome.adaptation}
              onClick={envelope}
              data-testid="bring-download-envelope"
            >
              Download adapted envelope
            </button>
            <span className="text-xs text-ink-3">Both are written by your browser to your device. Nothing is kept anywhere else.</span>
          </div>
        </Card>
      ) : null}

      <Card className="p-4">
        <Section title="What this surface never does">
          <ul className="list-disc space-y-1 pl-5 text-xs text-ink-2">
            <li>Execute, simulate, publish or persist the document. There is no server write for it and no browser storage is used.</li>
            <li>Fetch a URL, read a repository or open an archive. The document is the pasted text or the chosen file, and nothing else.</li>
            <li>Accept code, YAML, a framework-native agent object or a credential. A value shaped like one is refused before anything is sent.</li>
            <li>Add to or change the scenario catalog. The pinned scenarios are untouched by anything done here.</li>
            <li>
              Convert from LangGraph, CrewAI, AutoGen, n8n or BPMN in the browser. Conversion is an offline command-line tool: today the
              n8n and BPMN 2.0 converters emit a DRAFT policy pack, a conversion report and a preview Workflow IR labelled
              PREVIEW_UNAPPROVED that this screen inspects; LangGraph, CrewAI and AutoGen wait for a declarative export.
            </li>
          </ul>
        </Section>
      </Card>
    </div>
  );
}

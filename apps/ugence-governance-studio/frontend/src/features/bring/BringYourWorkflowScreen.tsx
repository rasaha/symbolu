// Bring Your Workflow (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §22, BW-1 to BW-5; §24,
// BW-3A for phase 3A drafts).
//
// The one screen on which the operator's own document enters the studio: Ugence
// Workflow IR JSON, pasted or chosen from a local file, gated in the browser by
// gate.ts and then handed to exactly three operations of the frozen v1 contract
// (validate, adapt, compare-adaptations) and, since phase 3A, to the three draft
// operations of the v2 contract (save, list, read). A draft is the one thing this
// screen may keep: the server validates the document again and keeps its canonical
// encoding as an unapproved DRAFT for the deployment's own tenant, never the pasted
// text, never under a tenant the browser names. Nothing here approves, compiles,
// publishes, exports or executes; no browser storage is touched; no URL is fetched;
// the scenario catalog is never touched; no code, YAML, archive, credential or
// framework-native object is accepted. Results live in component state and leave
// only as a local download. The guided example is the procurement compiled workflow
// the catalog itself serves, bundled with this screen, never fetched.
import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import { adaptWorkflow, ApiClientError, compareAdaptations, validateWorkflow } from "@/api/client";
import { listWorkflowDrafts, readWorkflowDraft, saveWorkflowDraft } from "@/api/client-v2";
import { decodeDraftRefusal, decodeWorkflowDraftListing, decodeWorkflowDraftRead, decodeWorkflowDraftSaved } from "@/api/decoders";
import type { ApiResponseEnvelope } from "@/api/types";
import type {
  AdaptWorkflowResult,
  CompareAdaptationsResult,
  DraftRefusal,
  ValidateWorkflowResult,
  WorkflowDraftListing,
  WorkflowDraftSaved,
} from "@/api/types-bring";
import { isUnavailable, type Unavailable } from "@/api/types-v2";
import { Card, Field, Fingerprint, Section } from "@/design-system/primitives";
import { clientDigest, gateWorkflowText, LIMITS, SUPPORTED_CONTRACTS, type GateResult } from "./gate";
import exampleWorkflowIrV1 from "./example-workflow-ir.v1.json";

export const SCREEN_NAME = "Bring Your Workflow";
export const SCREEN_TAGLINE = "Validate and adapt an existing agentic workflow for Ugence governance.";
export const DISCLAIMER =
  "Accepts Ugence Workflow IR JSON. It does not execute, compile, approve or publish the submitted workflow. A validated document may be kept only as an unapproved DRAFT for this deployment's tenant.";
export const MATURITY = "REFERENCE_GRADE";
/** BW-3A: what any claimed owner on a draft is worth. Named the same in the contract. */
export const CLAIMED_OWNER_ASSURANCE = "PRESENTED_UNPROVEN";

type Envelope<T> = ApiResponseEnvelope<T>;

interface Outcome {
  validation: Envelope<ValidateWorkflowResult> | null;
  adaptation: Envelope<AdaptWorkflowResult> | null;
  comparison: Envelope<CompareAdaptationsResult> | null;
}

const EMPTY: Outcome = { validation: null, adaptation: null, comparison: null };

type DraftAnswer = { kind: "saved"; saved: WorkflowDraftSaved } | { kind: "refused"; refusal: DraftRefusal } | { kind: "gap"; gap: Unavailable };
type DraftsAnswer = { kind: "listed"; listing: WorkflowDraftListing } | { kind: "refused"; refusal: DraftRefusal } | { kind: "gap"; gap: Unavailable };

interface DraftForm {
  title: string;
  claimedOwnerRef: string;
  registrationRef: string;
  registrationDigest: string;
  supersedes: string;
  notes: string;
}

const EMPTY_DRAFT_FORM: DraftForm = { title: "", claimedOwnerRef: "", registrationRef: "", registrationDigest: "", supersedes: "", notes: "" };

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

function TextInput({
  id,
  label,
  value,
  onChange,
  hint,
  required,
  testId,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
  required?: boolean;
  testId: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-[11px] text-ink-2">
        {label}
        {required ? " *" : ""}
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        className="w-full rounded border border-surface-border bg-surface-0 px-2 py-1 font-mono text-[11px] text-ink-0"
        data-testid={testId}
      />
      {hint ? <p className="mt-1 text-[10px] text-ink-3">{hint}</p> : null}
    </div>
  );
}

function GapText({ gap }: { gap: Unavailable }) {
  return (
    <p role="status" className="rounded border border-surface-border bg-surface-2/60 p-2 text-xs text-ink-1" data-testid="bring-draft-gap">
      Not available in this deployment: <span className="font-mono text-[11px]">{gap.capability}</span> · {gap.reason}
    </p>
  );
}

function RefusalText({ refusal, testId }: { refusal: DraftRefusal; testId: string }) {
  return (
    <p role="alert" className="rounded border border-danger/40 bg-danger/10 p-2 text-xs text-ink-1" data-testid={testId}>
      The server refused: <span className="font-mono text-[11px]">{refusal.code}</span> · {refusal.reason}
    </p>
  );
}

export function BringYourWorkflowScreen() {
  const [text, setText] = useState("");
  const [secondText, setSecondText] = useState("");
  const [digest, setDigest] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome>(EMPTY);
  const [busy, setBusy] = useState<"validate" | "adapt" | "compare" | null>(null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  // Phase 3A (BW-3A): the draft form and the server's answer to it. Cleared, like every
  // other result, by any edit of the document.
  const [draftForm, setDraftForm] = useState<DraftForm>(EMPTY_DRAFT_FORM);
  const [draftAnswer, setDraftAnswer] = useState<DraftAnswer | null>(null);
  const [draftBusy, setDraftBusy] = useState(false);
  const [draftsAnswer, setDraftsAnswer] = useState<DraftsAnswer | null>(null);
  const [includeSuperseded, setIncludeSuperseded] = useState(false);
  const [draftsBusy, setDraftsBusy] = useState(false);
  const [loadedDraft, setLoadedDraft] = useState<string | null>(null);

  const gate = useMemo(() => (text.trim() ? gateWorkflowText(text) : null), [text]);
  const secondGate = useMemo(() => (secondText.trim() ? gateWorkflowText(secondText) : null), [secondText]);

  // A result describes exactly one document: any edit clears every result and error.
  useEffect(() => {
    setOutcome(EMPTY);
    setError(null);
    setDraftAnswer(null);
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

  const setDraftField = (key: keyof DraftForm) => (value: string) => setDraftForm((f) => ({ ...f, [key]: value }));

  const keepDraft = async () => {
    if (!gate?.ok) return;
    setDraftBusy(true);
    setError(null);
    try {
      const answer = await saveWorkflowDraft({
        workflow: gate.document,
        contract_version: gate.declaredVersion,
        title: draftForm.title,
        claimed_owner_ref: draftForm.claimedOwnerRef,
        registration_ref: draftForm.registrationRef,
        registration_digest: draftForm.registrationDigest,
        supersedes: draftForm.supersedes,
        notes: draftForm.notes,
        source_digest: digest ?? undefined,
      });
      if (isUnavailable(answer)) setDraftAnswer({ kind: "gap", gap: answer });
      else {
        const refusal = decodeDraftRefusal(answer);
        setDraftAnswer(refusal ? { kind: "refused", refusal } : { kind: "saved", saved: decodeWorkflowDraftSaved(answer) });
      }
    } catch (err) {
      setError(describeError(err));
    } finally {
      setDraftBusy(false);
    }
  };

  const showDrafts = async (all: boolean) => {
    setDraftsBusy(true);
    setError(null);
    try {
      const answer = await listWorkflowDrafts(all);
      if (isUnavailable(answer)) setDraftsAnswer({ kind: "gap", gap: answer });
      else {
        const refusal = decodeDraftRefusal(answer);
        setDraftsAnswer(refusal ? { kind: "refused", refusal } : { kind: "listed", listing: decodeWorkflowDraftListing(answer) });
      }
    } catch (err) {
      setError(describeError(err));
    } finally {
      setDraftsBusy(false);
    }
  };

  const loadDraft = async (draftId: string) => {
    setDraftsBusy(true);
    setError(null);
    try {
      const answer = await readWorkflowDraft(draftId);
      if (isUnavailable(answer)) {
        setDraftsAnswer({ kind: "gap", gap: answer });
        return;
      }
      const read = decodeWorkflowDraftRead(answer);
      if (read.found && read.record) {
        // The kept document enters the editor exactly as the server kept it, through
        // the same gate as anything pasted; revising it is a new draft that supersedes
        // this one, so the form is pre-filled with that lineage.
        setText(JSON.stringify(read.record.workflow, null, 2));
        setDraftForm({
          title: read.record.draft.title,
          claimedOwnerRef: read.record.draft.claimed_owner_ref,
          registrationRef: read.record.draft.registration_ref,
          registrationDigest: read.record.draft.registration_digest,
          supersedes: read.record.draft.draft_id,
          notes: read.record.draft.notes,
        });
        setLoadedDraft(read.record.draft.draft_id);
      } else {
        setDraftsAnswer({ kind: "refused", refusal: { refused: true, code: "draft_not_found", reason: `no draft ${read.draft_id} is kept for this deployment's tenant` } });
      }
    } catch (err) {
      setError(describeError(err));
    } finally {
      setDraftsBusy(false);
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

      {gate?.ok ? (
        <Card className="p-4" data-testid="bring-draft">
          <Section title="Keep as an unapproved draft (phase 3A)">
            <p className="mb-2 text-xs text-ink-2">
              The server validates the document again and keeps its canonical form, with its digest, as a DRAFT for this
              deployment&apos;s own tenant. It never keeps the pasted text, and a draft is never approved, compiled, published or
              exported from here. A revision is a new draft that supersedes its predecessor; nothing is edited in place.
            </p>
            {loadedDraft ? (
              <p className="mb-2 text-xs text-ink-3" data-testid="bring-draft-loaded">
                Loaded from draft <span className="font-mono text-[11px]">{loadedDraft}</span>; keeping it again records a revision that supersedes it.
              </p>
            ) : null}
            <div className="grid gap-2 md:grid-cols-2">
              <TextInput id="bring-draft-title" label="Title" value={draftForm.title} onChange={setDraftField("title")} required testId="bring-draft-title" />
              <TextInput
                id="bring-draft-owner"
                label={`Claimed owner (recorded as ${CLAIMED_OWNER_ASSURANCE})`}
                value={draftForm.claimedOwnerRef}
                onChange={setDraftField("claimedOwnerRef")}
                hint="An opaque handle, recorded as a claim. It confers no read, write, approval or execution authority; a verified owner is phase 3B, behind AP-3."
                testId="bring-draft-owner"
              />
              <TextInput
                id="bring-draft-registration-ref"
                label="AI-system registration id"
                value={draftForm.registrationRef}
                onChange={setDraftField("registrationRef")}
                hint="Optional. A link is a reference plus the digest of the record it names; the server matches both against this tenant's own registry."
                testId="bring-draft-registration-ref"
              />
              <TextInput
                id="bring-draft-registration-digest"
                label="Registration record digest"
                value={draftForm.registrationDigest}
                onChange={setDraftField("registrationDigest")}
                testId="bring-draft-registration-digest"
              />
              <TextInput
                id="bring-draft-supersedes"
                label="Supersedes (draft id)"
                value={draftForm.supersedes}
                onChange={setDraftField("supersedes")}
                hint="Optional. The draft this revision replaces; it must be the head of its lineage."
                testId="bring-draft-supersedes"
              />
              <TextInput id="bring-draft-notes" label="Notes" value={draftForm.notes} onChange={setDraftField("notes")} testId="bring-draft-notes" />
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="btn-action px-3 py-1.5 text-xs"
                disabled={!ready || draftBusy || !draftForm.title.trim()}
                onClick={keepDraft}
                data-testid="bring-draft-save"
              >
                {draftBusy ? "Keeping…" : "Keep as draft"}
              </button>
              <span className="text-xs text-ink-3">Sends the document once, to the one draft write of the v2 contract. The tenant is the server&apos;s, never this browser&apos;s.</span>
            </div>
            {draftAnswer?.kind === "gap" ? <div className="mt-2"><GapText gap={draftAnswer.gap} /></div> : null}
            {draftAnswer?.kind === "refused" ? <div className="mt-2"><RefusalText refusal={draftAnswer.refusal} testId="bring-draft-refusal" /></div> : null}
            {draftAnswer?.kind === "saved" ? (
              <dl className="mt-2" data-testid="bring-draft-saved">
                <Field label="draft id">
                  <span className="font-mono text-[11px]" data-testid="bring-draft-id">{draftAnswer.saved.draft_id}</span>
                </Field>
                <Field label="lifecycle">
                  <span className="font-mono text-[11px]" data-testid="bring-draft-lifecycle">{draftAnswer.saved.lifecycle}</span> · {draftAnswer.saved.lifecycle_note}
                </Field>
                <Field label="kept digest">{shortDigest(draftAnswer.saved.workflow_digest)}</Field>
                <Field label="record digest">{shortDigest(draftAnswer.saved.record_digest)}</Field>
                <Field label="integrity">
                  {draftAnswer.saved.integrity.checked
                    ? `client ${draftAnswer.saved.integrity.source_digest === draftAnswer.saved.integrity.computed_digest ? "and server agree" : "and server differ; the server's canonical digest is the one of record"}`
                    : "not checked; no client digest was available to send"}
                </Field>
                <Field label="claimed owner">
                  {draftAnswer.saved.record.draft.claimed_owner_ref || <span className="text-ink-3">none claimed</span>} ·{" "}
                  <span className="font-mono text-[11px]" data-testid="bring-draft-owner-status">{draftAnswer.saved.claimed_owner_status}</span>
                </Field>
                <Field label="supersedes">{draftAnswer.saved.record.draft.supersedes || <span className="text-ink-3">none; the first of its lineage</span>}</Field>
                <Field label="registration link">
                  {draftAnswer.saved.record.draft.registration_ref ? (
                    <span className="font-mono text-[11px]">{draftAnswer.saved.record.draft.registration_ref}</span>
                  ) : (
                    <span className="text-ink-3">none</span>
                  )}
                </Field>
                <Field label="recorded by">
                  <span className="font-mono text-[11px]">{draftAnswer.saved.recorded_by}</span> · validated by{" "}
                  <span className="font-mono text-[11px]">{draftAnswer.saved.validated_by}</span>
                </Field>
                <Field label="confers">
                  <span data-testid="bring-draft-confers">{draftAnswer.saved.confers}</span>
                </Field>
              </dl>
            ) : null}
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

      <Card className="p-4" data-testid="bring-drafts">
        <Section title="Drafts this deployment keeps">
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-action px-3 py-1.5 text-xs" disabled={draftsBusy} onClick={() => showDrafts(includeSuperseded)} data-testid="bring-drafts-show">
              {draftsBusy ? "Reading…" : "Show kept drafts"}
            </button>
            <label className="flex items-center gap-1 text-xs text-ink-2">
              <input type="checkbox" checked={includeSuperseded} onChange={(e) => setIncludeSuperseded(e.target.checked)} data-testid="bring-drafts-all" />
              include superseded revisions
            </label>
            <span className="text-xs text-ink-3">Read on request, never on load. Only this deployment&apos;s tenant is ever answered.</span>
          </div>
          {draftsAnswer?.kind === "gap" ? <div className="mt-2"><GapText gap={draftsAnswer.gap} /></div> : null}
          {draftsAnswer?.kind === "refused" ? <div className="mt-2"><RefusalText refusal={draftsAnswer.refusal} testId="bring-drafts-refusal" /></div> : null}
          {draftsAnswer?.kind === "listed" ? (
            <div className="mt-2" data-testid="bring-drafts-list">
              <p className="mb-1 text-xs text-ink-3">
                <span data-testid="bring-drafts-count">{draftsAnswer.listing.count}</span> draft{draftsAnswer.listing.count === 1 ? "" : "s"} · lifecycle DRAFT ·
                claimed owners {draftsAnswer.listing.claimed_owner_status} · confers {draftsAnswer.listing.confers}
              </p>
              {draftsAnswer.listing.result.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-ink-3">
                        <th className="py-1 pr-2">title</th>
                        <th className="py-1 pr-2">draft id</th>
                        <th className="py-1 pr-2">contract</th>
                        <th className="py-1 pr-2">digest</th>
                        <th className="py-1 pr-2">claimed owner</th>
                        <th className="py-1 pr-2">supersedes</th>
                        <th className="py-1 pr-2">superseded by</th>
                        <th className="py-1">
                          <span className="sr-only">load</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {draftsAnswer.listing.result.map((row) => (
                        <tr key={row.draft_id} className="border-t border-surface-border/50" data-testid="bring-drafts-row">
                          <td className="py-1 pr-2">{row.title}</td>
                          <td className="py-1 pr-2 font-mono text-[11px]">{row.draft_id}</td>
                          <td className="py-1 pr-2 font-mono text-[11px]">{row.contract_version}</td>
                          <td className="py-1 pr-2">{shortDigest(row.workflow_digest)}</td>
                          <td className="py-1 pr-2 font-mono text-[11px]">{row.claimed_owner_ref || "—"}</td>
                          <td className="py-1 pr-2 font-mono text-[11px]">{row.supersedes || "—"}</td>
                          <td className="py-1 pr-2 font-mono text-[11px]">{row.superseded_by || "—"}</td>
                          <td className="py-1">
                            <button type="button" className="rounded border border-surface-border px-2 py-0.5 text-[11px] text-ink-2 hover:bg-surface-2" disabled={draftsBusy} onClick={() => loadDraft(row.draft_id)} data-testid="bring-drafts-load">
                              Load
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-ink-3">none kept</p>
              )}
            </div>
          ) : null}
        </Section>
      </Card>

      <Card className="p-4">
        <Section title="What this surface never does">
          <ul className="list-disc space-y-1 pl-5 text-xs text-ink-2">
            <li>
              Execute, simulate, compile, approve, publish or export the document. The one write is a DRAFT the server keeps for its
              own tenant (phase 3A); a claimed owner is a claim, and submitting for approval waits for phase 3B behind AP-3. No
              browser storage is used.
            </li>
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

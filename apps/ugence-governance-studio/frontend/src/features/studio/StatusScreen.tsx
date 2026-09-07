// Status panel (ADR_UGENCE_MODULE_ADMINISTRATION_SCOPING.md MA-2 as amended by MS-1 to
// MS-5).
//
// One read, and a read of one thing: what the deployment attested about itself before
// its port bound. The deployment's fail-closed integrity gate computes the six seam
// states, the checks and the pins; the report is handed to the studio once at
// composition (MS-2) and this panel renders it as it was handed.
//
// What this panel is not. It is not a module registry: the console's nine module rows
// cannot reach the studio under any current ruling and are struck from MA-2 (MS-1). It
// is not a live probe: a seam that reads "configured" was writable when the gate ran,
// and that says nothing about whether any engine is reachable now (§15.4). It is not
// an administration screen: nothing here can be changed, and no route beside this one
// exists (MA-1).
import { GapNotice } from "./GapNotice";
import { Panel, ScreenFrame } from "./ScreenFrame";
import { useDeploymentStatus } from "./hooks";
import { LoadingState, QueryError } from "@/design-system/states";
import { isUnavailable, type Available } from "@/api/types-v2";

const SEAM_LABEL: Record<string, string> = {
  constitution_registry: "Constitution registry (seam 1)",
  authority_reads: "Authority reads (seam 2)",
  simulation_provider: "Simulation provider (seam 3)",
  system_registry: "System registry (seam 5)",
  data_use_declarations: "Data-use declarations (seam 8)",
  vendor_declarations: "Vendor declarations (seam 9)",
};

function rec(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {};
}

function SeamState({ state }: { state: string }) {
  const cls =
    state === "configured"
      ? "border-emerald-300 bg-emerald-50 text-emerald-950"
      : state === "unwritable"
        ? "border-rose-300 bg-rose-50 text-rose-950"
        : "border-surface-border bg-surface-2 text-ink-2";
  return <span className={`rounded border px-1.5 py-0.5 font-mono text-[11px] ${cls}`}>{state}</span>;
}

function Attestation({ data }: { data: Available }) {
  const result = rec(data.result);
  const seams = rec(result.seams);
  const checks = rec(result.checks);
  const pins = rec(result.pins);
  const excluded = Array.isArray(data.excluded_fields) ? (data.excluded_fields as string[]) : [];
  return (
    <div className="space-y-3">
      <div
        role="note"
        aria-label="startup attestation ceiling"
        className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-[12px] text-amber-950"
      >
        <div className="font-semibold">What this is evidence of</div>
        <p className="mt-1 leading-relaxed">{String(data.ceiling ?? "")}</p>
      </div>

      <Panel title="Gate result">
        <p role="status" aria-label="gate result" className="text-[12px] text-ink-1">
          <span className="font-mono">{String(result.result ?? "")}</span>
          {" · "}
          <span className="font-mono">{String(result.failure_code ?? "")}</span>
        </p>
      </Panel>

      <Panel title="Seam states, as the gate attested them">
        <dl data-testid="status-seams" className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-[12px]">
          {Object.entries(seams).map(([name, state]) => (
            <div key={name} className="contents">
              <dt className="text-ink-2">
                {SEAM_LABEL[name] ?? name} <span className="font-mono text-[11px] text-ink-3">{name}</span>
              </dt>
              <dd>
                <SeamState state={String(state)} />
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-2 text-[11px] text-ink-3">
          &ldquo;configured&rdquo; means the seam&rsquo;s file or flag was present and writable when the
          gate ran. It is not a statement that any engine is reachable now.
        </p>
      </Panel>

      <Panel title="Integrity checks">
        <ul aria-label="integrity checks" className="space-y-0.5 text-[12px]">
          {Object.entries(checks).map(([name, ok]) => (
            <li key={name} className="flex items-center gap-2">
              <span className={`font-mono text-[11px] ${ok ? "text-emerald-800" : "text-rose-800"}`}>
                {ok ? "passed" : "failed"}
              </span>
              <span className="font-mono text-[11px] text-ink-2">{name}</span>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Pins">
        <dl data-testid="status-pins" className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[11px]">
          {Object.entries(pins).map(([name, value]) => (
            <div key={name} className="contents">
              <dt className="font-mono text-ink-3">{name}</dt>
              <dd className="break-all font-mono text-ink-1">{value === null || value === undefined ? "—" : String(value)}</dd>
            </div>
          ))}
        </dl>
        {excluded.length > 0 ? (
          <p className="mt-2 text-[11px] text-ink-3">
            Not shown by ruling MS-4: <span className="font-mono">{excluded.join(", ")}</span>.
          </p>
        ) : null}
      </Panel>
    </div>
  );
}

export function StatusScreen() {
  const status = useDeploymentStatus();
  return (
    <ScreenFrame
      title="Status"
      subtitle="What this deployment attested about itself before its port bound: the six front-door seam states, the integrity checks and the pinned identities, handed to the studio once at composition."
      neverDoes="This panel probes nothing, changes nothing, and lists no module registry. A configured seam is not a reachable engine, and nothing here is read at request time."
    >
      {status.isPending ? <LoadingState label="Reading the startup attestation…" /> : null}
      {status.isError ? <QueryError error={status.error} /> : null}
      {status.data ? (
        isUnavailable(status.data) ? <GapNotice gap={status.data} /> : <Attestation data={status.data} />
      ) : null}
    </ScreenFrame>
  );
}

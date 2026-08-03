// Replay Explorer (§22) + deterministic export (§26). Replay verifies deterministic
// plan reconstruction — it does not rerun agent execution. A mismatch is a
// prominent integrity state and is never suppressed.
import { useState } from "react";
import { useParams } from "react-router-dom";
import { CheckCircle2, XCircle, Download } from "lucide-react";
import { useReplay, useScenarioExport, useVersion } from "@/hooks/queries";
import { PlanningNote } from "@/components/MaturityBanner";
import { Card, Field, Fingerprint, Section } from "@/design-system/primitives";
import { LoadingState, QueryError } from "@/design-system/states";

export function ReplayScreen() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const replay = useReplay(scenarioId, true);
  const version = useVersion();
  const [exportOn, setExportOn] = useState(false);
  const exportQuery = useScenarioExport(scenarioId, exportOn);

  if (replay.isLoading) return <LoadingState label="Replaying plan…" />;
  if (replay.error) return <QueryError error={replay.error} />;
  const r = replay.data!;

  const download = () => {
    if (!exportQuery.data) return;
    const blob = new Blob([JSON.stringify(exportQuery.data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `governance-studio-${scenarioId}-export.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportManifest = exportQuery.data?.fingerprint_manifest as Record<string, unknown> | undefined;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold text-ink-0">Replay</h1>
      </header>
      <PlanningNote />
      <p className="rounded border border-surface-border bg-surface-2/50 p-3 text-xs text-ink-2">
        Replay verifies deterministic plan reconstruction. It does not rerun or replay agent execution.
      </p>

      <Card className={"p-4 " + (r.match ? "" : "border-state-ineligible/50")} data-testid="replay-result">
        <div className="mb-3 flex items-center gap-2" role="status" aria-live="polite">
          {r.match ? (
            <CheckCircle2 className="h-5 w-5 text-state-eligible" aria-hidden="true" />
          ) : (
            <XCircle className="h-5 w-5 text-state-ineligible" aria-hidden="true" />
          )}
          <span className="text-sm font-semibold text-ink-0">
            {r.match ? "Plan replayed deterministically (fingerprints match)" : "REPLAY MISMATCH — integrity check failed"}
          </span>
        </div>
        <dl>
          <Field label="Expected fingerprint"><Fingerprint value={r.expected_plan_fingerprint} label="expected" /></Field>
          <Field label="Replayed fingerprint"><Fingerprint value={r.replayed_plan_fingerprint} label="replayed" /></Field>
          <Field label="Plan state">{r.plan_state}</Field>
          <Field label="AWC version">{version.data?.awc_distribution_version ?? "—"}</Field>
          <Field label="API contract">{version.data?.api_contract_version ?? "—"}</Field>
          {r.diagnostics.length > 0 && (
            <Field label="Diagnostics">{r.diagnostics.map((d) => d.message).join("; ")}</Field>
          )}
        </dl>
      </Card>

      <Card className="p-4">
        <Section title="Deterministic export">
          <p className="mb-2 text-sm text-ink-2">
            The export bundle is the API's deterministic artifact set (manifest, workflow, registry,
            policies, plan, replay record and fingerprints). Synthetic data only — no source code,
            secrets or local paths.
          </p>
          {!exportOn ? (
            <button type="button" onClick={() => setExportOn(true)} className="rounded border border-surface-border bg-surface-2 px-3 py-2 text-sm text-ink-0 hover:bg-surface-3">
              Load export manifest
            </button>
          ) : exportQuery.isLoading ? (
            <LoadingState label="Loading export…" />
          ) : exportQuery.error ? (
            <QueryError error={exportQuery.error} />
          ) : (
            <>
              <dl>
                <Field label="Scenario">{String(exportQuery.data?.scenario_id ?? scenarioId)}</Field>
                <Field label="Plan fingerprint"><Fingerprint value={exportManifest?.plan_fingerprint as string} label="plan" /></Field>
                <Field label="Replay fingerprint"><Fingerprint value={exportManifest?.replay_fingerprint as string} label="replay" /></Field>
                <Field label="Synthetic-data notice">Synthetic demonstration data — planning only.</Field>
              </dl>
              <button type="button" onClick={download} className="mt-3 inline-flex items-center gap-2 rounded border border-surface-border bg-surface-2 px-3 py-2 text-sm text-ink-0 hover:bg-surface-3" data-testid="export-download">
                <Download className="h-4 w-4" aria-hidden="true" /> Download export bundle
              </button>
            </>
          )}
        </Section>
      </Card>
    </div>
  );
}

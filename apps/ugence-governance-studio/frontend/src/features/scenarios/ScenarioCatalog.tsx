// Screen 1 — Scenario catalog (§11).
import { Link } from "react-router-dom";
import { ArrowRight, FlaskConical, Star } from "lucide-react";
import { useScenarios } from "@/hooks/queries";
import { Badge, Card } from "@/design-system/primitives";
import { LoadingState, QueryError, EmptyState } from "@/design-system/states";

const RECOMMENDED = "procurement";
const P3C_VIEWS = ["Overview", "Workflow", "Roles", "Registry", "Eligibility"];

export function ScenarioCatalog() {
  const { data, isLoading, error } = useScenarios();

  if (isLoading) return <LoadingState label="Loading scenarios…" />;
  if (error) return <QueryError error={error} />;
  if (!data || data.scenarios.length === 0)
    return <EmptyState title="No scenarios available" detail="The backend returned no scenarios." />;

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-semibold text-ink-0">Scenario catalog</h1>
        <p
          className="mt-2 flex items-start gap-2 rounded border border-state-indeterminate/30 bg-state-indeterminate/10 p-3 text-sm text-ink-1"
          role="note"
        >
          <FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-state-indeterminate" aria-hidden="true" />
          These scenarios use synthetic demonstration data. They do not represent measured production
          performance, live enterprise data or pilot validation.
        </p>
      </div>

      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-2">
        {data.scenarios.map((s) => {
          const recommended = s.scenario_id === RECOMMENDED;
          return (
            <li key={s.scenario_id}>
              <Card className="flex h-full flex-col p-4">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="text-xs uppercase tracking-wide text-ink-3">{s.domain}</span>
                  <div className="flex items-center gap-1.5">
                    {s.synthetic_data && <Badge tone="indeterminate">Synthetic data</Badge>}
                    {recommended && (
                      <Badge tone="authority">
                        <Star className="mr-1 h-3 w-3" aria-hidden="true" />
                        Recommended demo
                      </Badge>
                    )}
                  </div>
                </div>
                <h2 className="text-base font-semibold text-ink-0">{s.title}</h2>
                <p className="mt-1 flex-1 text-sm text-ink-2">{s.description}</p>

                <dl className="mt-3 grid grid-cols-2 gap-y-1 text-xs">
                  <dt className="text-ink-3">Workflow contract</dt>
                  <dd className="font-mono text-ink-1">{s.workflow_contract_version}</dd>
                  <dt className="text-ink-3">Expected state</dt>
                  <dd className="text-ink-1">{s.expected_plan_state}</dd>
                </dl>

                <div className="mt-3 flex flex-wrap gap-1">
                  {P3C_VIEWS.map((v) => (
                    <span key={v} className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-ink-2">
                      {v}
                    </span>
                  ))}
                </div>

                <Link
                  to={`/scenarios/${s.scenario_id}`}
                  className="mt-4 inline-flex items-center justify-center gap-1.5 rounded border border-surface-border bg-surface-2 px-3 py-2 text-sm font-medium text-ink-0 hover:bg-surface-3"
                  data-testid={`open-${s.scenario_id}`}
                >
                  Open scenario
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </Link>
              </Card>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

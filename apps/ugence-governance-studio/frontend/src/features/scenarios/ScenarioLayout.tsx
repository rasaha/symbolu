// Scenario-scoped three-panel shell (§22): left navigation, center content
// (routed outlet). Detail/provenance/explanation panels live inside each screen.
import { NavLink, Outlet, useParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { clsx } from "clsx";
import { useScenario } from "@/hooks/queries";

const NAV = [
  { to: "", label: "Overview", end: true },
  { to: "workflow", label: "Workflow" },
  { to: "registry", label: "Registry" },
  { to: "eligibility", label: "Eligibility" },
  { to: "ranking", label: "Ranking" },
  { to: "composition", label: "Composition" },
  { to: "permissions", label: "Permissions" },
  { to: "fallbacks", label: "Fallbacks" },
  { to: "replay", label: "Replay" },
  { to: "compare", label: "Comparison" },
  { to: "what-if", label: "What-If" },
];

export function ScenarioLayout() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const { data } = useScenario(scenarioId);

  return (
    <div className="grid gap-5 lg:grid-cols-[200px_1fr]">
      <nav aria-label="Scenario sections" className="lg:sticky lg:top-4 lg:self-start">
        <Link to="/scenarios" className="mb-3 inline-flex items-center gap-1 text-xs text-ink-2 hover:text-ink-0">
          <ChevronLeft className="h-3.5 w-3.5" aria-hidden="true" />
          All scenarios
        </Link>
        <p className="mb-3 text-sm font-semibold text-ink-0">{data?.metadata.title ?? scenarioId}</p>
        <ul className="flex gap-1 overflow-x-auto lg:flex-col lg:gap-0.5">
          {NAV.map((item) => (
            <li key={item.label}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  clsx(
                    "block rounded px-3 py-1.5 text-sm",
                    isActive ? "bg-surface-3 font-medium text-ink-0" : "text-ink-2 hover:bg-surface-2",
                  )
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="min-w-0">
        <Outlet />
      </div>
    </div>
  );
}

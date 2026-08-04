// React Query hooks (§26, §28). Immutable scenario responses are cached per
// scenario id; results are never re-keyed across scenarios. Nothing here computes
// a domain outcome — each hook is a thin wrapper over a typed client call.
import { useQuery } from "@tanstack/react-query";
import {
  explainEligibility,
  getScenario,
  getScenarioEligibility,
  getScenarioRegistry,
  getScenarioWorkflow,
  getVersion,
  listScenarios,
} from "@/api/client";

export const useVersion = () =>
  useQuery({ queryKey: ["version"], queryFn: getVersion, staleTime: 60_000 });

// Scenario responses are immutable (frozen fixtures) → cache indefinitely.
const IMMUTABLE = { staleTime: Infinity, gcTime: Infinity } as const;

export const useScenarios = () =>
  useQuery({ queryKey: ["scenarios"], queryFn: listScenarios, ...IMMUTABLE });

export const useScenario = (id: string | undefined) =>
  useQuery({ queryKey: ["scenario", id], queryFn: () => getScenario(id!), enabled: !!id, ...IMMUTABLE });

export const useWorkflow = (id: string | undefined) =>
  useQuery({ queryKey: ["workflow", id], queryFn: () => getScenarioWorkflow(id!), enabled: !!id, ...IMMUTABLE });

export const useRegistry = (id: string | undefined) =>
  useQuery({ queryKey: ["registry", id], queryFn: () => getScenarioRegistry(id!), enabled: !!id, ...IMMUTABLE });

export const useEligibility = (id: string | undefined) =>
  useQuery({ queryKey: ["eligibility", id], queryFn: () => getScenarioEligibility(id!, true), enabled: !!id, ...IMMUTABLE });

export const useEligibilityExplanation = (id: string | undefined, roleId: string | undefined) =>
  useQuery({
    queryKey: ["explain", id, roleId ?? null],
    queryFn: () => explainEligibility(id!, roleId),
    enabled: !!id,
    ...IMMUTABLE,
  });

// -- P3D planning hooks (immutable per scenario/params) --------------------
import {
  comparePlans,
  explainPlan,
  getScenarioPlan,
  getScenarioRanking,
  replayPlan,
  scenarioWhatIf,
  getScenarioExport,
  type PlanSource,
} from "@/api/client";

export const useRanking = (id: string | undefined) =>
  useQuery({ queryKey: ["ranking", id], queryFn: () => getScenarioRanking(id!), enabled: !!id, ...IMMUTABLE });

export const usePlan = (id: string | undefined) =>
  useQuery({ queryKey: ["plan", id], queryFn: () => getScenarioPlan(id!), enabled: !!id, ...IMMUTABLE });

export const useExplainPlan = (id: string | undefined) =>
  useQuery({ queryKey: ["explainplan", id], queryFn: () => explainPlan(id!), enabled: !!id, ...IMMUTABLE });

export const useReplay = (id: string | undefined, enabled: boolean) =>
  useQuery({ queryKey: ["replay", id], queryFn: () => replayPlan(id!), enabled: !!id && enabled, ...IMMUTABLE });

export const useCompare = (left: PlanSource | null, right: PlanSource | null) =>
  useQuery({
    queryKey: ["compare", left, right],
    queryFn: () => comparePlans(left!, right!),
    enabled: !!left && !!right,
    ...IMMUTABLE,
  });

export const useWhatIf = (id: string | undefined, op: string | null, params: Record<string, unknown> | null) =>
  useQuery({
    queryKey: ["whatif", id, op, params],
    queryFn: () => scenarioWhatIf(id!, op!, params ?? {}),
    enabled: !!id && !!op && !!params,
    ...IMMUTABLE,
  });

export const useScenarioExport = (id: string | undefined, enabled: boolean) =>
  useQuery({ queryKey: ["export", id], queryFn: () => getScenarioExport(id!), enabled: !!id && enabled, ...IMMUTABLE });

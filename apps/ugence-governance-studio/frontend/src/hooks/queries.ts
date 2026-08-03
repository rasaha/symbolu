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

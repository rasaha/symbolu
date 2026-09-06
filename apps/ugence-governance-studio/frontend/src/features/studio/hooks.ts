// React Query hooks for the six screens.
//
// Every hook returns a `GapAware` result — the client narrows through `decodeGap`
// before it ever reaches a component — so a screen cannot read a field off a result
// the backend reported as unavailable.
import { useMutation, useQuery } from "@tanstack/react-query";

import * as v2 from "@/api/client-v2";
import type {
  ConstitutionPreflightBody,
  ConstitutionValidateBody,
  PolicyCompileBody,
  PolicyPackBody,
  PublishShadowBody,
  DataUseDeclareBody,
  VendorDeclareBody,
  RegistryRegisterBody,
  ReviewDecisionBody,
  ReviewStartShadowRunBody,
  SimulateRunBody,
} from "@/api/types-v2";

const RETRY = 0; // a governance answer is not retried: a refusal is the answer

export const useValidateConstitution = () =>
  useMutation({ mutationFn: (b: ConstitutionValidateBody) => v2.validateConstitution(b) });

export const usePreflightConstitution = () =>
  useMutation({ mutationFn: (b: ConstitutionPreflightBody) => v2.preflightConstitution(b) });

export const useValidatePolicyPack = () =>
  useMutation({ mutationFn: (b: PolicyPackBody) => v2.validatePolicyPack(b) });

export const useSynthesizePolicyPack = () =>
  useMutation({ mutationFn: (b: PolicyPackBody) => v2.synthesizePolicyPack(b) });

export const useCompilePolicyPack = () =>
  useMutation({ mutationFn: (b: PolicyCompileBody) => v2.compilePolicyPack(b) });

export const useAuthorityPolicies = () =>
  useQuery({ queryKey: ["v2", "authority", "policies"], queryFn: v2.listAuthorityPolicies, retry: RETRY });

export const useRunSimulation = () =>
  useMutation({ mutationFn: (b: SimulateRunBody) => v2.runSimulation(b) });

export const usePublishShadow = () =>
  useMutation({ mutationFn: (b: PublishShadowBody) => v2.publishShadow(b) });

export const useAuditCorrelationIds = () =>
  useQuery({ queryKey: ["v2", "observe", "audit"], queryFn: v2.listAuditCorrelationIds, retry: RETRY });

export const useAuditChain = (correlationId: string | null) =>
  useQuery({
    queryKey: ["v2", "observe", "audit", correlationId],
    queryFn: () => v2.readAuditChain(correlationId as string),
    enabled: correlationId !== null && correlationId !== "",
    retry: RETRY,
  });

// -- 6b · Observe over the worker's ledger (front-door seam 7, FD-11) --------
export const useLedgerChain = (correlationId: string | null) =>
  useQuery({
    queryKey: ["v2", "observe", "ledger", correlationId],
    queryFn: () => v2.readLedgerChain(correlationId as string),
    enabled: correlationId !== null && correlationId !== "",
    retry: RETRY,
  });

// -- 7 · Review (GAS-7 HR-D) ------------------------------------------------
export const useReviewQueue = (requiredRole = "") =>
  useQuery({
    queryKey: ["v2", "review", "queue", requiredRole],
    queryFn: () => v2.listReviewQueue(requiredRole),
    retry: RETRY,
  });

export const useReviewRun = (instanceId: string | null) =>
  useQuery({
    queryKey: ["v2", "review", "run", instanceId],
    queryFn: () => v2.readReviewRun(instanceId as string),
    enabled: instanceId !== null && instanceId !== "",
    retry: RETRY,
  });

export const useReviewRunEvents = (instanceId: string | null) =>
  useQuery({
    queryKey: ["v2", "review", "run", instanceId, "events"],
    queryFn: () => v2.readReviewRunEvents(instanceId as string),
    enabled: instanceId !== null && instanceId !== "",
    retry: RETRY,
  });

export const useReviewApproval = (approvalId: string | null) =>
  useQuery({
    queryKey: ["v2", "review", "approval", approvalId],
    queryFn: () => v2.readReviewApproval(approvalId as string),
    enabled: approvalId !== null && approvalId !== "",
    retry: RETRY,
  });

export const useSubmitReviewDecision = () =>
  useMutation({
    mutationFn: ({ body, proof }: { body: ReviewDecisionBody; proof?: string }) =>
      v2.submitReviewDecision(body, proof ?? ""),
  });

// -- 4b · The worker shadow-run relay (front-door seam 6, FD-10) -------------
export const useStartWorkerShadowRun = () =>
  useMutation({ mutationFn: (b: ReviewStartShadowRunBody) => v2.startWorkerShadowRun(b) });

// -- 8 · Registration (front-door seam 5, FD-9) ------------------------------
export const useRegisterSystem = () =>
  useMutation({ mutationFn: (b: RegistryRegisterBody) => v2.registerSystem(b) });

export const useRegistrations = (asOf = "") =>
  useQuery({
    queryKey: ["v2", "registry", "registrations", asOf],
    queryFn: () => v2.listRegistrations(asOf),
    retry: RETRY,
  });

// Front-door seam 8 (FD-12): typed data-use declarations. Declare is the only write.
export const useDeclareDataUse = () =>
  useMutation({ mutationFn: (b: DataUseDeclareBody) => v2.declareDataUse(b) });

export const useDataUseDeclarations = (asOf = "") =>
  useQuery({
    queryKey: ["v2", "data-use", "declarations", asOf],
    queryFn: () => v2.listDataUseDeclarations(asOf),
    retry: RETRY,
  });

// Front-door seam 9 (FD-13): typed vendor declarations. Declare is the only write.
export const useDeclareVendorDependency = () =>
  useMutation({ mutationFn: (b: VendorDeclareBody) => v2.declareVendorDependency(b) });

export const useVendorDeclarations = (asOf = "") =>
  useQuery({
    queryKey: ["v2", "vendor", "declarations", asOf],
    queryFn: () => v2.listVendorDeclarations(asOf),
    retry: RETRY,
  });

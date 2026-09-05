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
  ReviewDecisionBody,
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
  useMutation({ mutationFn: (b: ReviewDecisionBody) => v2.submitReviewDecision(b) });

/**
 * React Query hooks binding the typed endpoints to server state. Server state is
 * kept here; local UI state stays in components; secure auth state lives in the
 * AuthContext. The client never duplicates backend authorization as a security
 * boundary — it only reflects backend responses.
 */
import { useMutation, useQuery, useQueryClient, type UseMutationResult, type UseQueryResult } from "@tanstack/react-query";

import { BirthProfileApi, CoupleApi, UserApi } from "@/api/endpoints";
import { ApiError } from "@/api/errors";
import { useAuth } from "@/auth/AuthContext";
import type { BirthProfileCreateRequest, BirthProfileResponse, CoupleResponse, InvitationCreateResponse, UserMeResponse } from "@/api/types";

export const qk = {
  me: ["me"] as const,
  birthProfile: ["birthProfile"] as const,
  couple: ["couple"] as const,
};

export function useMe(): UseQueryResult<UserMeResponse, ApiError> {
  const { client, status } = useAuth();
  return useQuery({
    queryKey: qk.me,
    queryFn: () => UserApi.me(client),
    enabled: status === "signed-in",
  });
}

export function useBirthProfile(): UseQueryResult<BirthProfileResponse | null, ApiError> {
  const { client, status } = useAuth();
  return useQuery({
    queryKey: qk.birthProfile,
    enabled: status === "signed-in",
    queryFn: async () => {
      try {
        return await BirthProfileApi.get(client);
      } catch (e) {
        // A 404-style "no profile yet" is a normal empty state, not an error.
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
  });
}

export function useSaveBirthProfile(): UseMutationResult<BirthProfileResponse, ApiError, { body: BirthProfileCreateRequest; exists: boolean }> {
  const { client } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ body, exists }) => (exists ? BirthProfileApi.update(client, body) : BirthProfileApi.create(client, body)),
    onSuccess: (data) => {
      qc.setQueryData(qk.birthProfile, data);
    },
  });
}

export function useCurrentCouple(): UseQueryResult<CoupleResponse | null, ApiError> {
  const { client, status } = useAuth();
  return useQuery({
    queryKey: qk.couple,
    enabled: status === "signed-in",
    queryFn: async () => {
      try {
        return await CoupleApi.current(client);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
  });
}

export function useCreateInvitation(): UseMutationResult<InvitationCreateResponse, ApiError, void> {
  const { client } = useAuth();
  return useMutation({ mutationFn: () => CoupleApi.createInvitation(client) });
}

export function useAcceptInvitation(): UseMutationResult<CoupleResponse, ApiError, string> {
  const { client } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => CoupleApi.acceptInvitation(client, token),
    onSuccess: (data) => {
      qc.setQueryData(qk.couple, data);
    },
  });
}

export function useUnpair(): UseMutationResult<void, ApiError, string> {
  const { client } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (coupleId: string) => CoupleApi.unpair(client, coupleId),
    onSuccess: () => {
      qc.setQueryData(qk.couple, null);
      void qc.invalidateQueries({ queryKey: qk.couple });
    },
  });
}

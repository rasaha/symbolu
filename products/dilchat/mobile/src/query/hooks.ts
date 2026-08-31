/**
 * React Query hooks binding the typed endpoints to server state. Server state is
 * kept here; local UI state stays in components; secure auth state lives in the
 * AuthContext. The client never duplicates backend authorization as a security
 * boundary — it only reflects backend responses.
 */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData, type UseInfiniteQueryResult, type UseMutationResult, type UseQueryResult } from "@tanstack/react-query";

import { BirthProfileApi, ChatApi, CoupleApi, UserApi } from "@/api/endpoints";
import { ApiError } from "@/api/errors";
import { useAuth } from "@/auth/AuthContext";
import type { BirthProfileCreateRequest, BirthProfileResponse, ConversationResponse, CoupleResponse, InvitationCreateResponse, MessageCreateRequest, MessageListResponse, MessageResponse, ReadStateResponse, UserMeResponse } from "@/api/types";

export const qk = {
  me: ["me"] as const,
  birthProfile: ["birthProfile"] as const,
  couple: ["couple"] as const,
  conversation: ["conversation"] as const,
  messages: (conversationId: string) => ["messages", conversationId] as const,
};

/** Poll cadence for chat freshness. Polling (not WebSocket/push) is the ratified
 * Phase 3D transport; correctness never depends on it — a refetch only surfaces
 * what the backend already committed. */
export const CHAT_POLL_MS = 5000;

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
      // Unpair revokes the conversation server-side; drop cached chat state too.
      qc.setQueryData(qk.conversation, null);
      void qc.invalidateQueries({ queryKey: qk.conversation });
    },
  });
}

// --- Secure 1:1 chat (Phase 3D) -------------------------------------------- //

export function useCurrentConversation(): UseQueryResult<ConversationResponse | null, ApiError> {
  const { client, status } = useAuth();
  return useQuery({
    queryKey: qk.conversation,
    enabled: status === "signed-in",
    queryFn: async () => {
      try {
        return await ChatApi.current(client);
      } catch (e) {
        // 404 = no active conversation (unpaired, or revoked): a normal empty
        // state mirroring useCurrentCouple, not an error.
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
  });
}

/**
 * Message history as a forward-paged infinite query (ascending server_sequence;
 * the backend mints opaque cursors, so paging always starts at the oldest
 * message). Poll-refreshed: react-query refetches every loaded page, so new
 * messages appear on the last page without any client-minted cursor.
 */
export function useMessages(
  conversationId: string | undefined,
): UseInfiniteQueryResult<InfiniteData<MessageListResponse>, ApiError> {
  const { client, status } = useAuth();
  return useInfiniteQuery({
    queryKey: conversationId ? qk.messages(conversationId) : ["messages", "none"],
    enabled: status === "signed-in" && !!conversationId,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => ChatApi.listMessages(client, conversationId as string, pageParam),
    getNextPageParam: (last) => (last.has_more && last.next_cursor ? last.next_cursor : undefined),
    refetchInterval: CHAT_POLL_MS,
  });
}

export function useSendMessage(
  conversationId: string | undefined,
): UseMutationResult<MessageResponse, ApiError, MessageCreateRequest> {
  const { client } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MessageCreateRequest) =>
      ChatApi.sendMessage(client, conversationId as string, body),
    onSuccess: () => {
      // Refetch so the confirmed message (with its server_sequence) replaces the
      // screen's pending entry, which is keyed by the same client_message_id.
      if (conversationId) void qc.invalidateQueries({ queryKey: qk.messages(conversationId) });
    },
  });
}

export function useUpdateReadState(
  conversationId: string | undefined,
): UseMutationResult<ReadStateResponse, ApiError, number> {
  const { client } = useAuth();
  return useMutation({
    mutationFn: (lastReadSequence: number) =>
      ChatApi.updateReadState(client, conversationId as string, lastReadSequence),
  });
}

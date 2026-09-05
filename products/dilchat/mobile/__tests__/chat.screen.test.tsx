import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import Chat from "../app/(app)/chat";
import { isValidClientMessageId } from "@/chat/clientMessageId";
import type { MessageResponse } from "@/api/types";

const mockSendMutate = jest.fn();
const mockReadMutate = jest.fn();
const mockFetchNextPage = jest.fn();
const mockConvRefetch = jest.fn().mockResolvedValue(undefined);
const mockMsgRefetch = jest.fn().mockResolvedValue(undefined);

let mockMe: { data: unknown; isLoading: boolean };
let mockConversation: { data: unknown; isLoading: boolean; error: unknown; refetch: jest.Mock; isRefetching: boolean };
let mockMessages: {
  data: unknown;
  isLoading: boolean;
  error: unknown;
  refetch: jest.Mock;
  isRefetching: boolean;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: jest.Mock;
};

jest.mock("@/query/hooks", () => ({
  useMe: () => mockMe,
  useCurrentConversation: () => mockConversation,
  useMessages: () => mockMessages,
  useSendMessage: () => ({ mutate: mockSendMutate, isPending: false }),
  useUpdateReadState: () => ({ mutate: mockReadMutate, isPending: false }),
}));

jest.mock("expo-router", () => {
  const ReactActual = require("react");
  return {
    useRouter: () => ({ replace: jest.fn(), push: jest.fn(), back: jest.fn() }),
    Link: ({ children }: { children: React.ReactNode }) =>
      ReactActual.createElement(ReactActual.Fragment, null, children),
  };
});

const CONV = {
  conversation_id: "conv1",
  couple_id: "c1",
  status: "ACTIVE",
  created_at: "2026-01-01T00:00:00Z",
  latest_sequence: 2,
  last_read_sequence: 0,
  member_user_ids: ["u1", "u2"],
};

function serverMsg(over: Partial<MessageResponse>): MessageResponse {
  return {
    message_id: "m1",
    conversation_id: "conv1",
    sender_user_id: "u2",
    client_message_id: "cid-1",
    server_sequence: 1,
    body: "hi from partner",
    created_at: "2026-01-01T00:00:01Z",
    deleted: false,
    deleted_at: null,
    ...over,
  };
}

function withMessages(list: MessageResponse[]): void {
  mockMessages.data = { pages: [{ messages: list, next_cursor: null, has_more: false }], pageParams: [null] };
}

describe("Chat screen", () => {
  beforeEach(() => {
    mockSendMutate.mockReset();
    mockReadMutate.mockReset();
    mockFetchNextPage.mockReset();
    mockConvRefetch.mockClear();
    mockMsgRefetch.mockClear();
    mockMe = { data: { id: "u1", email: "a@example.com", status: "ACTIVE", created_at: "x" }, isLoading: false };
    mockConversation = { data: CONV, isLoading: false, error: null, refetch: mockConvRefetch, isRefetching: false };
    mockMessages = {
      data: { pages: [{ messages: [], next_cursor: null, has_more: false }], pageParams: [null] },
      isLoading: false,
      error: null,
      refetch: mockMsgRefetch,
      isRefetching: false,
      hasNextPage: false,
      isFetchingNextPage: false,
      fetchNextPage: mockFetchNextPage,
    };
  });

  it("renders history with tombstones as a neutral placeholder, never the deleted body", () => {
    withMessages([
      serverMsg({ message_id: "m1", client_message_id: "cid-1", server_sequence: 1 }),
      serverMsg({
        message_id: "m2",
        client_message_id: "cid-2",
        server_sequence: 2,
        sender_user_id: "u1",
        body: null,
        deleted: true,
        deleted_at: "2026-01-01T01:00:00Z",
      }),
    ]);
    const { getByText, queryByText, getByTestId } = render(<Chat />);
    expect(getByText("hi from partner")).toBeTruthy();
    expect(getByTestId("message-cid-2")).toBeTruthy();
    expect(getByText("Message deleted")).toBeTruthy();
    // A tombstone never leaks content; only metadata remains.
    expect(queryByText(/null/)).toBeNull();
  });

  it("shows the empty state when there are no messages", () => {
    const { getByTestId } = render(<Chat />);
    expect(getByTestId("chat-empty")).toBeTruthy();
  });

  it("shows the not-connected state when there is no conversation", () => {
    mockConversation = { data: null, isLoading: false, error: null, refetch: mockConvRefetch, isRefetching: false };
    const { getByText, queryByTestId } = render(<Chat />);
    expect(getByText("Chat opens once you are connected with a partner.")).toBeTruthy();
    expect(queryByTestId("composer-input")).toBeNull();
  });

  it("shows a retryable error state when the conversation fails to load", () => {
    mockConversation = {
      data: undefined,
      isLoading: false,
      error: Object.assign(new Error("boom"), { kind: "network" }),
      refetch: mockConvRefetch,
      isRefetching: false,
    };
    const { getByTestId } = render(<Chat />);
    fireEvent.press(getByTestId("retry-conversation"));
    expect(mockConvRefetch).toHaveBeenCalled();
  });

  it("sends optimistically with a valid client_message_id and shows a pending bubble", () => {
    const { getByTestId, getByText } = render(<Chat />);
    fireEvent.changeText(getByTestId("composer-input"), "  hello there  ");
    fireEvent.press(getByTestId("send-message"));
    expect(mockSendMutate).toHaveBeenCalledTimes(1);
    const [payload] = mockSendMutate.mock.calls[0];
    expect(payload.body).toBe("hello there"); // trimmed
    expect(isValidClientMessageId(payload.client_message_id)).toBe(true);
    expect(getByText("hello there")).toBeTruthy();
    expect(getByText("Sending…")).toBeTruthy();
  });

  it("marks a failed send Not sent and retries with the SAME client_message_id", async () => {
    const { getByTestId, getByText } = render(<Chat />);
    fireEvent.changeText(getByTestId("composer-input"), "resend me");
    fireEvent.press(getByTestId("send-message"));
    const [payload, options] = mockSendMutate.mock.calls[0];
    options.onError(Object.assign(new Error("timeout"), { kind: "timeout" }));
    await waitFor(() => expect(getByText("Not sent")).toBeTruthy());

    fireEvent.press(getByTestId(`retry-${payload.client_message_id}`));
    expect(mockSendMutate).toHaveBeenCalledTimes(2);
    const [retryPayload] = mockSendMutate.mock.calls[1];
    // Idempotent replay: identical key and body, so the backend can never duplicate.
    expect(retryPayload.client_message_id).toBe(payload.client_message_id);
    expect(retryPayload.body).toBe(payload.body);
  });

  it("can discard a failed send", async () => {
    const { getByTestId, queryByText } = render(<Chat />);
    fireEvent.changeText(getByTestId("composer-input"), "oops");
    fireEvent.press(getByTestId("send-message"));
    const [payload, options] = mockSendMutate.mock.calls[0];
    options.onError(Object.assign(new Error("down"), { kind: "network" }));
    await waitFor(() => expect(getByTestId(`discard-${payload.client_message_id}`)).toBeTruthy());
    fireEvent.press(getByTestId(`discard-${payload.client_message_id}`));
    expect(queryByText("oops")).toBeNull();
  });

  it("pushes forward-only read state for the latest loaded sequence", async () => {
    withMessages([
      serverMsg({ message_id: "m1", client_message_id: "cid-1", server_sequence: 1 }),
      serverMsg({ message_id: "m2", client_message_id: "cid-2", server_sequence: 2 }),
    ]);
    render(<Chat />);
    await waitFor(() => expect(mockReadMutate).toHaveBeenCalledWith(2));
    expect(mockReadMutate).toHaveBeenCalledTimes(1);
  });

  it("does NOT push read state backward when everything is already read", async () => {
    mockConversation = {
      data: { ...CONV, last_read_sequence: 2 },
      isLoading: false,
      error: null,
      refetch: mockConvRefetch,
      isRefetching: false,
    };
    withMessages([
      serverMsg({ message_id: "m1", client_message_id: "cid-1", server_sequence: 1 }),
      serverMsg({ message_id: "m2", client_message_id: "cid-2", server_sequence: 2 }),
    ]);
    render(<Chat />);
    await waitFor(() => expect(mockReadMutate).not.toHaveBeenCalled());
  });

  it("waits for the full history before marking read (no premature read state)", async () => {
    mockMessages.hasNextPage = true;
    withMessages([serverMsg({ server_sequence: 1 })]);
    render(<Chat />);
    // Still paging: read state must not fire, but the next page must be requested.
    await waitFor(() => expect(mockFetchNextPage).toHaveBeenCalled());
    expect(mockReadMutate).not.toHaveBeenCalled();
  });
});

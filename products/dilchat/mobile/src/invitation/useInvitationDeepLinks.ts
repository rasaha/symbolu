/**
 * Deep-link interceptor for invitation links.
 *
 * Mounted once at the root. It:
 *  1. reads the initial URL (cold start / terminated) and subsequent URLs
 *     (foreground / background resume) via expo-linking;
 *  2. parses each with the versioned, allowlisted parser — a link that is not a
 *     valid invitation is IGNORED (never navigated to), foreclosing open-redirect
 *     and arbitrary-route jumps;
 *  3. stores only the minimum context (token + version) in the in-memory pending
 *     store;
 *  4. drives navigation via the pure policy: signed-out → sign-in (context
 *     preserved and resumed after auth); signed-in → the CONSENT review screen
 *     (never a direct accept).
 *
 * It never logs the URL or token. A rejected non-empty link surfaces a neutral,
 * token-free reason via the optional callback.
 */
import { useCallback, useEffect, useRef } from "react";
import * as Linking from "expo-linking";
import { useRouter } from "expo-router";

import { useAuth } from "@/auth/AuthContext";
import { parseDeepLink, reasonMessage, type DeepLinkRejectReason } from "@/deeplink/parse";
import {
  clearPendingInvitation,
  setPendingInvitation,
  usePendingInvitation,
} from "@/invitation/pendingInvitation";
import { decideInvitationNav } from "@/invitation/router";

export interface UseInvitationDeepLinksOptions {
  /** Called with a neutral, token-free message when a non-empty link is rejected. */
  onRejected?: (message: string, reason: DeepLinkRejectReason) => void;
}

export function useInvitationDeepLinks(opts: UseInvitationDeepLinksOptions = {}): void {
  const { status } = useAuth();
  const router = useRouter();
  const pending = usePendingInvitation();
  const onRejected = opts.onRejected;
  // The URL of the last link we consumed, so foreground re-delivery of the same
  // OS URL is not reprocessed (the pending store also dedupes by token).
  const lastUrl = useRef<string | null>(null);
  // Guards a single navigation per (action, token) so we do not re-navigate on
  // every render while status/pending are stable.
  const lastNav = useRef<string>("");

  const handleUrl = useCallback(
    (url: string | null) => {
      if (!url || url === lastUrl.current) return;
      lastUrl.current = url;
      const parsed = parseDeepLink(url);
      if (parsed.kind === "invitation") {
        setPendingInvitation({ token: parsed.token, version: parsed.version });
      } else if (parsed.reason !== "empty") {
        onRejected?.(reasonMessage(parsed.reason), parsed.reason);
      }
    },
    [onRejected],
  );

  // Initial URL (cold start from a terminated state).
  useEffect(() => {
    let active = true;
    void Linking.getInitialURL().then((url) => {
      if (active) handleUrl(url);
    });
    return () => {
      active = false;
    };
  }, [handleUrl]);

  // Subsequent URLs (app already running, foreground/background resume).
  useEffect(() => {
    const sub = Linking.addEventListener("url", (e: { url: string }) => handleUrl(e.url));
    return () => sub.remove();
  }, [handleUrl]);

  // Drive navigation from the pure policy whenever status/pending change.
  useEffect(() => {
    const action = decideInvitationNav(status, pending);
    const key = action.type === "to-consent" ? `consent:${action.token}` : action.type;
    if (key === lastNav.current) return;
    if (action.type === "none") {
      lastNav.current = "";
      return;
    }
    lastNav.current = key;
    if (action.type === "to-sign-in") {
      router.replace("/(auth)/sign-in");
    } else if (action.type === "to-consent") {
      router.replace({ pathname: "/(app)/consent", params: { token: action.token, source: "deeplink" } });
    }
  }, [status, pending, router]);

  // If the pending invitation is cleared (accept/reject/sign-out), reset the nav
  // guard so a fresh link later re-navigates.
  useEffect(() => {
    if (!pending) lastNav.current = "";
  }, [pending]);

  // Clear any stale nav bookkeeping on unmount; the store itself is cleared by
  // the auth/consent flows.
  useEffect(() => {
    return () => {
      lastUrl.current = null;
    };
  }, []);

  // Exposed for callers that want to explicitly drop context (kept internal).
  void clearPendingInvitation;
}

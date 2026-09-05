/** Root layout: providers (React Query + Auth) and the navigation stack. Also
 * mounts the invitation deep-link interceptor and the app-switcher privacy
 * shield. */
import React from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { Stack } from "expo-router";

import { AuthProvider } from "@/auth/AuthContext";
import { makeQueryClient } from "@/query/queryClient";
import { useInvitationDeepLinks } from "@/invitation/useInvitationDeepLinks";
import { AppSwitcherShield } from "@/privacy/AppSwitcherShield";

const queryClient = makeQueryClient();

/** Owns invitation deep links: parses, preserves context through auth, and
 * routes through the consent gate. Renders nothing. */
function InvitationDeepLinkBridge(): null {
  useInvitationDeepLinks();
  return null;
}

export default function RootLayout(): React.ReactElement {
  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <AppSwitcherShield>
            <StatusBar style="dark" />
            <InvitationDeepLinkBridge />
            <Stack screenOptions={{ headerShown: false }} />
          </AppSwitcherShield>
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

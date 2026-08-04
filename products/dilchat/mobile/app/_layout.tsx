/** Root layout: providers (React Query + Auth) and the navigation stack. */
import React from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { Stack } from "expo-router";

import { AuthProvider } from "@/auth/AuthContext";
import { makeQueryClient } from "@/query/queryClient";

const queryClient = makeQueryClient();

export default function RootLayout(): React.ReactElement {
  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <StatusBar style="dark" />
          <Stack screenOptions={{ headerShown: false }} />
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

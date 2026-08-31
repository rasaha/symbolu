import React from "react";
import { Redirect, Stack } from "expo-router";
import { useAuth } from "@/auth/AuthContext";
import { Loading, Screen } from "@/ui/components";

/** Authenticated area. Unauthenticated users are sent to sign-in; an expired
 * session (detected by the client) flips status to signed-out and redirects. */
export default function AppLayout(): React.ReactElement {
  const { status } = useAuth();
  if (status === "loading") {
    return (
      <Screen scroll={false}>
        <Loading />
      </Screen>
    );
  }
  if (status === "signed-out") return <Redirect href="/(auth)/sign-in" />;
  return (
    <Stack screenOptions={{ headerShown: true, headerBackTitle: "Back" }}>
      <Stack.Screen name="home" options={{ title: "DilChat", headerShown: false }} />
      <Stack.Screen name="profile" options={{ title: "Birth profile" }} />
      <Stack.Screen name="invite" options={{ title: "Invite a partner" }} />
      <Stack.Screen name="accept" options={{ title: "Accept invitation" }} />
      <Stack.Screen name="consent" options={{ title: "Before you connect" }} />
      <Stack.Screen name="paired" options={{ title: "Your connection" }} />
      <Stack.Screen name="chat" options={{ title: "Chat" }} />
      <Stack.Screen name="privacy" options={{ title: "Privacy" }} />
      <Stack.Screen name="settings" options={{ title: "Settings" }} />
      <Stack.Screen name="compatibility" options={{ title: "Compatibility" }} />
    </Stack>
  );
}

import React from "react";
import { Redirect, Stack } from "expo-router";
import { useAuth } from "@/auth/AuthContext";

/** Auth-area layout. Signed-in users are redirected away from auth screens. */
export default function AuthLayout(): React.ReactElement {
  const { status } = useAuth();
  if (status === "signed-in") return <Redirect href="/(app)/home" />;
  return <Stack screenOptions={{ headerShown: false }} />;
}

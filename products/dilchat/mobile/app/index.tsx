/** Launch / session-loading screen. Restores the session then routes to the
 * authenticated area or the sign-in screen. */
import React from "react";
import { Redirect } from "expo-router";

import { useAuth } from "@/auth/AuthContext";
import { Loading, Screen } from "@/ui/components";

export default function Index(): React.ReactElement {
  const { status } = useAuth();
  if (status === "loading") {
    return (
      <Screen scroll={false}>
        <Loading label="Loading your session…" />
      </Screen>
    );
  }
  return status === "signed-in" ? <Redirect href="/(app)/home" /> : <Redirect href="/(auth)/sign-in" />;
}

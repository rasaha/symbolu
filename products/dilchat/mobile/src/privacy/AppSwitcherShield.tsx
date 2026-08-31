/**
 * App-switcher / background privacy shield.
 *
 * On iOS the OS captures a snapshot of the foreground screen when the app becomes
 * inactive/backgrounded and shows it in the app switcher; on Android the same
 * surface can appear in Recents. Those snapshots can expose birth-profile values,
 * an invitation token/link, the account email, or pairing state.
 *
 * This component renders an opaque, content-free cover OVER the app whenever the
 * app is not active, so the snapshot the OS captures shows only a neutral cover —
 * never sensitive content. It is removed the instant the app becomes active
 * again, so there is no permanent blank/broken state after resume.
 *
 * Notes:
 * - This complements (does not replace) platform capture flags. It works on both
 *   platforms without disabling screenshots globally.
 * - The cover shows only the app name and a neutral line; no user data.
 */
import React, { useEffect, useRef, useState } from "react";
import { AppState, type AppStateStatus, StyleSheet, Text, View } from "react-native";

export function AppSwitcherShield({ children }: { children: React.ReactNode }): React.ReactElement {
  const [covered, setCovered] = useState(false);
  const appState = useRef<AppStateStatus>(AppState.currentState);

  useEffect(() => {
    const sub = AppState.addEventListener("change", (next: AppStateStatus) => {
      // Cover as soon as we leave "active" (iOS reports "inactive" during the
      // app-switcher transition and snapshot); uncover only when fully active.
      setCovered(next !== "active");
      appState.current = next;
    });
    // Initialize from the current state (e.g., launched into background).
    setCovered(AppState.currentState !== "active");
    return () => sub.remove();
  }, []);

  return (
    <View style={styles.root}>
      {children}
      {covered ? (
        <View
          testID="app-switcher-shield"
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
          style={styles.cover}
          pointerEvents="none"
        >
          <Text style={styles.brand}>DilChat</Text>
          <Text style={styles.sub}>Locked while in the background</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  cover: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#2a2540",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  brand: { color: "#ffffff", fontSize: 22, fontWeight: "700" },
  sub: { color: "#d8d6de", fontSize: 14 },
});

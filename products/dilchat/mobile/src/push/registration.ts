/**
 * Config-gated push registration (Phase 3C mobile slice, DILCHAT-D3C-M2).
 *
 * The whole pipeline is an OPTIONAL delivery enhancement: push availability
 * never determines messaging correctness, and every failure path degrades to
 * REST + the existing polling. Ratified gates, in order:
 *
 *   EAS project id configured  →  signed-in caller  →  permission granted
 *       →  Expo token acquisition  →  authenticated POST /v1/devices
 *
 * - No EAS project id: NO acquisition attempt, no fake token, no placeholder
 *   registration, no startup failure, no warning loop — a silent
 *   "skipped_no_config" (distinguishable from transport failure in the
 *   returned status, without ever exposing a token).
 * - Permission: prompted at most once per app launch, only when the OS reports
 *   "undetermined", via the platform-native dialog. A user who declined is
 *   never re-prompted here.
 * - The push token is SENSITIVE: never logged, never displayed, never treated
 *   as an authentication credential. Device revocation on logout/logout-all is
 *   the BACKEND's contract (session-associated registrations); the client does
 *   not duplicate it.
 */

import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { DeviceApi } from "@/api/endpoints";
import type { HttpClient } from "@/api/client";
import type { DevicePlatform } from "@/api/types";

export type PushRegistrationStatus =
  | "registered"
  | "skipped_no_config" // deployment config absent — NOT a transport failure
  | "skipped_permission" // user declined or prompt not allowed this launch
  | "failed_transport"; // acquisition/registration failed; polling continues

/** Deployment configuration, never user data: the EAS project id, resolved
 * through the established Expo config mechanism. Absent => push is off. */
export function getEasProjectId(): string | null {
  const extra = (Constants.expoConfig?.extra ?? {}) as {
    eas?: { projectId?: unknown };
  };
  const id = extra.eas?.projectId;
  return typeof id === "string" && id.length > 0 ? id : null;
}

export function devicePlatform(): DevicePlatform {
  if (Platform.OS === "ios") return "IOS";
  if (Platform.OS === "android") return "ANDROID";
  return "UNKNOWN";
}

// At most one native permission prompt per app launch (a declined user is
// never re-prompted at all — only "undetermined" may prompt).
let promptedThisLaunch = false;

/** Test-only reset for the per-launch prompt guard. */
export function resetPromptGuardForTests(): void {
  promptedThisLaunch = false;
}

export async function maybeRegisterForPush(client: HttpClient): Promise<PushRegistrationStatus> {
  const projectId = getEasProjectId();
  if (!projectId) return "skipped_no_config";

  try {
    // The notification APIs (and the native permission machinery behind them)
    // are only CALLED once the deployment configuration says push is in play.
    let { status } = await Notifications.getPermissionsAsync();
    if (status === "undetermined" && !promptedThisLaunch) {
      promptedThisLaunch = true;
      status = (await Notifications.requestPermissionsAsync()).status;
    }
    if (status !== "granted") return "skipped_permission";

    const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
    if (!token) return "failed_transport";
    await DeviceApi.register(client, { push_token: token, platform: devicePlatform() });
    return "registered";
  } catch {
    // Permission APIs, token acquisition, or the registration call failed.
    // Deliberately silent (no token, no provider payload ever logged); the
    // app keeps working on REST + polling and may succeed on a later launch.
    return "failed_transport";
  }
}

/**
 * Node stub for `expo-constants`, used only by the live-backend integration
 * config so the production API modules import cleanly outside the Expo runtime.
 * The integration test constructs HttpClient with an explicit base URL, so the
 * configured `extra.apiBaseUrl` is intentionally empty here.
 */
export default { expoConfig: { extra: {} } };

/* Test setup: mock expo-secure-store with an in-memory store so auth-storage
   tests run without a device keychain. No real credentials are used. The store
   variable is `mock`-prefixed so Jest allows the factory to reference it. */

/* Default per-test timeout. The RN/expo/jest-expo module graph is transformed
   lazily on first use, so whichever behavioral suite renders the full provider
   tree first on a *cold* Jest cache pays a one-time transform cost that can
   exceed Jest's 5s default (observed ~8-10s on a cold CI runner, <0.5s warm).
   Raising the default absorbs that cold-start cost without masking a genuine
   hang — the app code has no unbounded waits, and the CI job-level timeout is
   the real backstop. Behavior assertions are unchanged. */
jest.setTimeout(20000);

const mockSecureStoreMem = new Map<string, string>();

jest.mock("expo-secure-store", () => ({
  WHEN_UNLOCKED_THIS_DEVICE_ONLY: "WHEN_UNLOCKED_THIS_DEVICE_ONLY",
  setItemAsync: async (k: string, v: string) => {
    mockSecureStoreMem.set(k, v);
  },
  getItemAsync: async (k: string) =>
    mockSecureStoreMem.has(k) ? mockSecureStoreMem.get(k)! : null,
  deleteItemAsync: async (k: string) => {
    mockSecureStoreMem.delete(k);
  },
}));

beforeEach(() => {
  mockSecureStoreMem.clear();
});

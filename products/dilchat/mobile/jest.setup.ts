/* Test setup: mock expo-secure-store with an in-memory store so auth-storage
   tests run without a device keychain. No real credentials are used. The store
   variable is `mock`-prefixed so Jest allows the factory to reference it. */
const mockSecureStoreMem = new Map<string, string>();

jest.mock("expo-secure-store", () => ({
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

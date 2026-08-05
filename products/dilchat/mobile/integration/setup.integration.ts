/* Integration setup: the production env module references the RN `__DEV__`
   global. In this Node harness we set it false — the integration test always
   passes an explicit base URL, so the dev fallback is never taken. */
(globalThis as unknown as { __DEV__: boolean }).__DEV__ = false;

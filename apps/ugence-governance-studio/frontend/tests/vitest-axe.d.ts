import "vitest";

// vitest-axe augments expect at runtime via extend-expect; declare the matcher
// so TypeScript recognises it in the test suite.
declare module "vitest" {
  interface Assertion<T = unknown> {
    toHaveNoViolations(): T;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): void;
  }
}

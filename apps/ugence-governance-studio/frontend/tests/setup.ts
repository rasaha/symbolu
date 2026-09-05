import "@testing-library/jest-dom/vitest";
import { afterEach, expect } from "vitest";
import { cleanup } from "@testing-library/react";
import * as axeMatchers from "vitest-axe/matchers";

expect.extend(axeMatchers);

afterEach(() => cleanup());

// jsdom lacks matchMedia; provide a reduced-motion-aware stub.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}

// jsdom implements neither ResizeObserver nor DOMMatrixReadOnly, and React Flow
// measures its viewport with both. Polyfilled here rather than mocked away in each
// test so the canvas renders its real component tree — a mocked-out canvas would let
// a broken node registry pass the screen tests.
class ResizeObserverPolyfill {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === "undefined") {
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver = ResizeObserverPolyfill;
}
if (typeof (globalThis as { DOMMatrixReadOnly?: unknown }).DOMMatrixReadOnly === "undefined") {
  class DOMMatrixReadOnlyPolyfill {
    m22 = 1;
    constructor(_transform?: string) {}
  }
  (globalThis as { DOMMatrixReadOnly?: unknown }).DOMMatrixReadOnly = DOMMatrixReadOnlyPolyfill;
}
if (typeof Element !== "undefined") {
  if (!Element.prototype.getBoundingClientRect.toString().includes("polyfilled")) {
    // React Flow reads a non-zero size before it will render nodes.
    Element.prototype.getBoundingClientRect = function polyfilled() {
      return { x: 0, y: 0, width: 800, height: 600, top: 0, left: 0, bottom: 600, right: 800, toJSON: () => ({}) } as DOMRect;
    };
  }
}

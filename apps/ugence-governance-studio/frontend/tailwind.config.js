/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Enterprise research-lab neutral surfaces + precise status hues.
        surface: {
          0: "#0b0e14",
          1: "#111621",
          2: "#161c2a",
          3: "#1e2636",
          border: "#2a3244",
        },
        ink: {
          0: "#f5f7fa",
          1: "#c7cedb",
          2: "#8b95a7",
          3: "#727d90",
        },
        state: {
          // Brightened to meet WCAG 2.2 AA on the app's dark tinted surfaces
          // (verified by scripts/verify-contrast.mjs).
          eligible: "#3ecf8e",
          ineligible: "#f0685c",
          indeterminate: "#d9a441",
          invalid: "#a78bfa",
          authority: "#5aa2e0",
          review: "#cf8ccf",
          governance: "#4fc4cd",
          deterministic: "#8b95a7",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

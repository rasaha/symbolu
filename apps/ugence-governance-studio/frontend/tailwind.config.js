/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // White surfaces, black ink, red actions (owner direction, 2026-09-06).
        // Every pair is verified by scripts/verify-contrast.mjs against WCAG 2.2 AA.
        surface: {
          0: "#ffffff",
          1: "#ffffff",
          2: "#f4f4f4",
          3: "#e8e8e8",
          border: "#cfcfcf",
        },
        ink: {
          0: "#000000",
          1: "#000000",
          2: "#1f1f1f",
          3: "#333333",
        },
        // The one action colour: red buttons carry white labels (6.47:1).
        action: {
          DEFAULT: "#b91c1c",
          hover: "#991b1b",
        },
        state: {
          // Darkened to meet WCAG 2.2 AA on white and on their own 10% tints
          // (verified by scripts/verify-contrast.mjs).
          eligible: "#166534",
          ineligible: "#b91c1c",
          indeterminate: "#92400e",
          invalid: "#6d28d9",
          authority: "#1d4ed8",
          review: "#a21caf",
          governance: "#155e75",
          deterministic: "#4b5563",
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

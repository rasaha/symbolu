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
          3: "#5c6678",
        },
        state: {
          eligible: "#1f9d6b",
          ineligible: "#c2453a",
          indeterminate: "#c08a2e",
          invalid: "#7a5cd0",
          authority: "#2f6fb0",
          review: "#b06fb0",
          governance: "#3a8f96",
          deterministic: "#6b7280",
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

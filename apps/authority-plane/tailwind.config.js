/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // White surfaces, black ink, red actions: the owner's direction for every
        // React screen (2026-09-06). #b91c1c carries a white label at 6.47:1.
        action: { DEFAULT: "#b91c1c", hover: "#991b1b" },
      },
    },
  },
  plugins: [],
};

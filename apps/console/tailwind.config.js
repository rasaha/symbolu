/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ugence: {
          primary: '#4f46e5',
          accent: '#06b6d4',
        },
        verdict: {
          allow: '#22c55e',
          hold: '#f59e0b',
          block: '#ef4444',
          neutral: '#64748b',
        },
      },
    },
  },
  plugins: [],
};

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ugence: {
          primary: '#b91c1c',
          accent: '#7f1d1d',
        },
        verdict: {
          allow: '#166534',
          hold: '#b45309',
          block: '#b91c1c',
          neutral: '#4b5563',
        },
      },
    },
  },
  plugins: [],
};

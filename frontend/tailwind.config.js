/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      animation: {
        'pulse-fast': 'pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      boxShadow: {
        'glow-red': '0 0 15px rgba(239, 68, 68, 0.6)',
        'glow-green': '0 0 15px rgba(34, 197, 94, 0.6)',
      }
    },
  },
  plugins: [],
}

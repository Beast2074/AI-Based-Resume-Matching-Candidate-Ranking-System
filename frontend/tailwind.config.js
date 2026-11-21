/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0A0F1E",
        textPrimary: "#E8ECF8",
        textMuted: "#8B95B0",
        accentIndigo: "#6366F1",
        accentCyan: "#22D3EE",
        scoreRed: "#EF4444",
        scoreAmber: "#F59E0B",
        scoreCyan: "#22D3EE",
        scoreGreen: "#10B981"
      },
      fontFamily: {
        heading: ["Space Grotesk", "sans-serif"],
        sans: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"]
      }
    },
  },
  plugins: [],
}

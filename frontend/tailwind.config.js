/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        nm: {
          bg:       "#0f1117",
          surface:  "#1a1d27",
          border:   "#2a2d3a",
          accent:   "#6366f1",
          accent2:  "#22d3ee",
          text:     "#e2e8f0",
          muted:    "#64748b",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // DayZ-inspired palette
        bg: {
          DEFAULT: "#0d0f0e",
          panel: "#161918",
          elevated: "#1f2322",
        },
        accent: {
          DEFAULT: "#3a8c5a",
          dim: "#1f4d2e",
          bright: "#52b073",
        },
        warn: "#d4a72c",
        err: "#c64545",
        ok: "#3a8c5a",
        muted: "#7a807d",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

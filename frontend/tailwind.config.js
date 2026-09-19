/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Vercel Dark Mode Colors
        background: "#000000",
        surface: "#0a0a0a",
        "surface-elevated": "#111111",
        "surface-hover": "#171717",
        "surface-active": "#1f1f1f",
        
        // Vercel Borders
        border: "#1f1f1f",
        "border-light": "#2e2e2e",
        "border-hover": "#444444",
        
        // Vercel Typography
        "text-primary": "#ededed",
        "text-secondary": "#888888",
        "text-muted": "#a1a1a1",
        "text-dim": "#555555",
        
        // Vercel Accents
        "vercel-blue": "#0070f3",
        "vercel-blue-subtle": "rgba(0, 112, 243, 0.15)",
        "vercel-green": "#00e599",
        "vercel-green-subtle": "rgba(0, 229, 153, 0.15)",
        "vercel-red": "#ff0055",
        "vercel-red-subtle": "rgba(255, 0, 85, 0.15)",
        "vercel-amber": "#f5a623",
      },
      fontFamily: {
        sans: ["Geist", "Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["Geist Mono", "JetBrains Mono", "monospace"],
      },
      borderRadius: {
        DEFAULT: "6px",
        md: "6px",
        lg: "8px",
        xl: "12px",
      }
    },
  },
  plugins: [],
}

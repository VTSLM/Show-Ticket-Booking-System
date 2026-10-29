/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        cinema: {
          950: "#050711",
          900: "#090d1a",
          850: "#0d1326",
          800: "#131b34",
          700: "#1d284a",
          blue: {
            DEFAULT: "#2563eb",
            glow: "#3b82f6",
            electric: "#1d4ed8",
            dark: "#1e40af",
          },
        },
      },
      boxShadow: {
        glow: "0 0 30px -5px rgba(37, 99, 235, 0.4)",
        glowSm: "0 0 15px -2px rgba(59, 130, 246, 0.35)",
        card: "0 20px 40px -15px rgba(0, 0, 0, 0.7)",
      },
      borderRadius: {
        "3xl": "24px",
        "4xl": "32px",
      },
    },
  },
  plugins: [],
};

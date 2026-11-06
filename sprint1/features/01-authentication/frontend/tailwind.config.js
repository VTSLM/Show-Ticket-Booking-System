/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#fdf4ff",
          100: "#fae8ff",
          200: "#f3d0fe",
          300: "#e9a8fd",
          400: "#d872fa",
          500: "#c44df0",
          600: "#a82cd6",
          700: "#8b1eb0",
          800: "#731c8f",
          900: "#5f1a74",
          950: "#3e0650",
        },
      },
    },
  },
  plugins: [],
};

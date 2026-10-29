import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './features/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0B0F19',
        surface: {
          DEFAULT: '#111827',
          card: '#161F30',
          hover: '#1F293D',
          border: 'rgba(255, 255, 255, 0.08)',
        },
        seat: {
          selected: '#3B82F6',
          selectedHover: '#2563EB',
          available: '#10B981',
          availableHover: '#059669',
          held: '#F59E0B',
          taken: '#374151',
          takenBorder: '#4B5563',
          reserved: '#475569',
        },
      },
      boxShadow: {
        'glow-screen': '0 10px 40px -10px rgba(96, 165, 250, 0.45)',
        'glow-seat': '0 0 12px rgba(59, 130, 246, 0.6)',
        'glow-available': '0 0 10px rgba(16, 185, 129, 0.3)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
};

export default config;

import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#09090B',
        surface: '#111113',
        'surface-card': 'rgba(255,255,255,0.05)',
        border: 'rgba(255,255,255,0.08)',
        foreground: '#FFFFFF',
        'foreground-muted': '#B6B6C2',
        primary: '#FF8A3D',
        'primary-hover': '#FF9B57',
        accent: '#FFC857',
        danger: '#ef4444',
        warning: '#f59e0b',
        success: '#22c55e',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'premium': '0 20px 40px -10px rgba(0,0,0,0.5)',
        'premium-hover': '0 30px 60px -15px rgba(0,0,0,0.6)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'hero-glow': 'radial-gradient(circle at 50% 50%, rgba(255,138,61,0.15) 0%, transparent 50%)',
      },
    },
  },
  plugins: [],
};

export default config;
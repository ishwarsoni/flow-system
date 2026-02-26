/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Solo Leveling palette
        sl: {
          bg: '#02050f',
          navy: '#040d1c',
          cyan: '#00d4ff',
          blue: '#0062ff',
          purple: '#7c3aed',
          red: '#ff2040',
          green: '#00ff88',
          gold: '#ffd700',
        },
        // Keep legacy aliases
        primary: {
          DEFAULT: '#0062ff',
          400: '#3b85ff',
          500: '#0062ff',
          600: '#0050cc',
        },
        accent: {
          DEFAULT: '#00d4ff',
          400: '#33ddff',
          500: '#00d4ff',
          600: '#00a8cc',
        },
        success: {
          DEFAULT: '#00ff88',
          400: '#33ffaa',
          500: '#00ff88',
        },
        danger: {
          DEFAULT: '#ff2040',
          400: '#ff5068',
          500: '#ff2040',
        },
        warning: {
          DEFAULT: '#ffd700',
          400: '#ffdf33',
          500: '#ffd700',
        },
        surface: {
          DEFAULT: '#040d1c',
          700: '#071528',
          800: '#040d1c',
          900: '#02050f',
          950: '#010208',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        system: ['Orbitron', 'Share Tech Mono', 'monospace'],
      },
      animation: {
        'sl-appear': 'sl-appear 0.35s ease-out',
        'sl-pulse': 'sl-glow-pulse 3s ease-in-out infinite',
        'sl-flicker': 'sl-flicker 9s ease-in-out infinite',
        'spin': 'spin 1s linear infinite',
      },
      keyframes: {
        'sl-appear': {
          '0%': { opacity: '0', transform: 'translateY(-10px) scale(0.97)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'sl-glow-pulse': {
          '0%,100%': { boxShadow: '0 0 10px rgba(0,212,255,0.15)' },
          '50%': { boxShadow: '0 0 28px rgba(0,212,255,0.45)' },
        },
        'sl-flicker': {
          '0%,89%,91%,93%,100%': { opacity: '1' },
          '90%': { opacity: '0.7' },
          '92%': { opacity: '0.9' },
        },
        spin: { to: { transform: 'rotate(360deg)' } },
      },
    },
  },
  plugins: [],
}


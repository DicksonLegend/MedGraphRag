/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Theme A (Clinical Calm - Light) & Theme B (Vital Monitor - Dark) CSS variable mappings
        canvas: 'var(--color-canvas)',
        card: {
          DEFAULT: 'var(--color-card)',
          hover: 'var(--color-card-hover)',
          border: 'var(--color-card-border)',
        },
        ink: {
          DEFAULT: 'var(--color-ink)',
          muted: 'var(--color-ink-muted)',
          subtle: 'var(--color-ink-subtle)',
        },
        brand: {
          DEFAULT: 'var(--color-brand)',
          hover: 'var(--color-brand-hover)',
          surface: 'var(--color-brand-surface)',
          border: 'var(--color-brand-border)',
          secondary: 'var(--color-brand-secondary)',
        },
        status: {
          success: 'var(--color-status-success)',
          'success-bg': 'var(--color-status-success-bg)',
          caution: 'var(--color-status-caution)',
          'caution-bg': 'var(--color-status-caution-bg)',
          danger: 'var(--color-status-danger)',
          'danger-bg': 'var(--color-status-danger-bg)',
          info: 'var(--color-status-info)',
          'info-bg': 'var(--color-status-info-bg)',
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
        heading: ['Sora', '"Space Grotesk"', 'sans-serif'],
      },
      borderRadius: {
        card: '14px',
        subtle: '8px',
      },
      animation: {
        'ecg-pulse': 'ecgPulse 2.4s ease-in-out infinite',
        'code-blue': 'codeBluePulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.25s ease-out forwards',
      },
      keyframes: {
        ecgPulse: {
          '0%': { strokeDashoffset: '1000' },
          '100%': { strokeDashoffset: '0' },
        },
        codeBluePulse: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.94', transform: 'scale(0.998)' },
        },
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}

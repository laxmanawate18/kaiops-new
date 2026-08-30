import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

/**
 * KaiOPS design system.
 *
 * Every colour is an HSL triplet in a CSS variable so Tailwind's `/alpha`
 * modifier works everywhere (`bg-surface/60`) and so themes can be swapped
 * without a rebuild. Raw hex values do not belong in components.
 */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // — Structural ————————————————————————————————
        canvas: 'hsl(var(--canvas) / <alpha-value>)',
        surface: {
          DEFAULT: 'hsl(var(--surface) / <alpha-value>)',
          raised: 'hsl(var(--surface-raised) / <alpha-value>)',
          overlay: 'hsl(var(--surface-overlay) / <alpha-value>)',
          sunken: 'hsl(var(--surface-sunken) / <alpha-value>)',
        },
        line: {
          DEFAULT: 'hsl(var(--line) / <alpha-value>)',
          strong: 'hsl(var(--line-strong) / <alpha-value>)',
        },
        content: {
          DEFAULT: 'hsl(var(--content) / <alpha-value>)',
          muted: 'hsl(var(--content-muted) / <alpha-value>)',
          subtle: 'hsl(var(--content-subtle) / <alpha-value>)',
          inverse: 'hsl(var(--content-inverse) / <alpha-value>)',
        },

        // — Brand ————————————————————————————————————
        brand: {
          50: 'hsl(var(--brand-50) / <alpha-value>)',
          100: 'hsl(var(--brand-100) / <alpha-value>)',
          200: 'hsl(var(--brand-200) / <alpha-value>)',
          300: 'hsl(var(--brand-300) / <alpha-value>)',
          400: 'hsl(var(--brand-400) / <alpha-value>)',
          500: 'hsl(var(--brand-500) / <alpha-value>)',
          600: 'hsl(var(--brand-600) / <alpha-value>)',
          700: 'hsl(var(--brand-700) / <alpha-value>)',
          800: 'hsl(var(--brand-800) / <alpha-value>)',
          900: 'hsl(var(--brand-900) / <alpha-value>)',
          DEFAULT: 'hsl(var(--brand-500) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent) / <alpha-value>)',
          soft: 'hsl(var(--accent-soft) / <alpha-value>)',
        },

        // — Semantic / status ————————————————————————
        // Deliberately distinguishable without relying on hue alone:
        // each pairs with a distinct icon and label in the UI.
        ok: {
          DEFAULT: 'hsl(var(--ok) / <alpha-value>)',
          soft: 'hsl(var(--ok-soft) / <alpha-value>)',
        },
        warn: {
          DEFAULT: 'hsl(var(--warn) / <alpha-value>)',
          soft: 'hsl(var(--warn-soft) / <alpha-value>)',
        },
        danger: {
          DEFAULT: 'hsl(var(--danger) / <alpha-value>)',
          soft: 'hsl(var(--danger-soft) / <alpha-value>)',
        },
        info: {
          DEFAULT: 'hsl(var(--info) / <alpha-value>)',
          soft: 'hsl(var(--info-soft) / <alpha-value>)',
        },
        neutral: {
          DEFAULT: 'hsl(var(--neutral) / <alpha-value>)',
          soft: 'hsl(var(--neutral-soft) / <alpha-value>)',
        },

        // — Severity (incident priority) ————————————
        sev: {
          p0: 'hsl(var(--sev-p0) / <alpha-value>)',
          p1: 'hsl(var(--sev-p1) / <alpha-value>)',
          p2: 'hsl(var(--sev-p2) / <alpha-value>)',
          p3: 'hsl(var(--sev-p3) / <alpha-value>)',
        },

        // — Categorical series (charts) ————————————
        // 8-step qualitative ramp, ordered by perceptual separation.
        series: {
          1: 'hsl(var(--series-1) / <alpha-value>)',
          2: 'hsl(var(--series-2) / <alpha-value>)',
          3: 'hsl(var(--series-3) / <alpha-value>)',
          4: 'hsl(var(--series-4) / <alpha-value>)',
          5: 'hsl(var(--series-5) / <alpha-value>)',
          6: 'hsl(var(--series-6) / <alpha-value>)',
          7: 'hsl(var(--series-7) / <alpha-value>)',
          8: 'hsl(var(--series-8) / <alpha-value>)',
        },

        ring: 'hsl(var(--ring) / <alpha-value>)',
      },

      fontFamily: {
        sans: ['InterVariable', 'Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },

      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.02em' }],
      },

      spacing: {
        // Control height that sits between h-9 and h-10 — the default row size.
        '9.5': '2.375rem',
      },

      borderRadius: {
        xs: '0.25rem',
        sm: '0.375rem',
        DEFAULT: '0.5rem',
        md: '0.625rem',
        lg: '0.75rem',
        xl: '1rem',
        '2xl': '1.25rem',
        '3xl': '1.75rem',
      },

      boxShadow: {
        // Layered, low-opacity shadows read better on near-black than one big blur.
        subtle: '0 1px 2px 0 hsl(var(--shadow) / 0.3)',
        raised: '0 2px 4px -1px hsl(var(--shadow) / 0.35), 0 4px 12px -2px hsl(var(--shadow) / 0.3)',
        float: '0 8px 16px -4px hsl(var(--shadow) / 0.4), 0 16px 40px -8px hsl(var(--shadow) / 0.35)',
        overlay: '0 16px 32px -8px hsl(var(--shadow) / 0.5), 0 32px 80px -16px hsl(var(--shadow) / 0.45)',
        glow: '0 0 0 1px hsl(var(--brand-500) / 0.2), 0 0 24px -4px hsl(var(--brand-500) / 0.35)',
        'glow-danger': '0 0 0 1px hsl(var(--danger) / 0.25), 0 0 24px -4px hsl(var(--danger) / 0.4)',
      },

      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        // Two-tone breathing pulse for live/streaming indicators.
        breathe: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.55', transform: 'scale(0.92)' },
        },
        // Radar sweep used on the "investigating" state.
        sweep: {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
        'draw-line': {
          from: { strokeDashoffset: '1' },
          to: { strokeDashoffset: '0' },
        },
        'caret-blink': {
          '0%, 70%, 100%': { opacity: '1' },
          '20%, 50%': { opacity: '0' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.2s ease-out',
        'slide-up': 'slide-up 0.28s cubic-bezier(0.22, 1, 0.36, 1)',
        shimmer: 'shimmer 1.8s infinite',
        breathe: 'breathe 2.4s ease-in-out infinite',
        sweep: 'sweep 3s linear infinite',
        'caret-blink': 'caret-blink 1.25s ease-out infinite',
      },

      transitionTimingFunction: {
        // A single easing curve used app-wide keeps motion feeling authored.
        emphasis: 'cubic-bezier(0.22, 1, 0.36, 1)',
        exit: 'cubic-bezier(0.4, 0, 1, 1)',
      },

      backgroundImage: {
        'grid-fade':
          'linear-gradient(to bottom, hsl(var(--canvas) / 0), hsl(var(--canvas) / 1))',
      },
    },
  },
  plugins: [animate],
} satisfies Config

import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{ts,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          0: 'var(--bg-0)',
          1: 'var(--bg-1)',
          2: 'var(--bg-2)',
          3: 'var(--bg-3)',
        },
        text: {
          0: 'var(--text-0)',
          1: 'var(--text-1)',
          2: 'var(--text-2)',
          3: 'var(--text-3)',
        },
        line: {
          DEFAULT: 'var(--line)',
          strong: 'var(--line-strong)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          soft: 'var(--accent-soft)',
          line: 'var(--accent-line)',
        },
        gold: {
          DEFAULT: 'var(--gold)',
          soft: 'var(--gold-soft)',
        },
        ok: 'var(--ok)',
        warn: 'var(--warn)',
        bad: {
          DEFAULT: 'var(--bad)',
          soft: 'var(--bad-soft)',
        },
      },
      borderRadius: {
        s: 'var(--radius-s)',
        m: 'var(--radius-m)',
        l: 'var(--radius-l)',
      },
      fontFamily: {
        ui: 'var(--font-ui)',
        mono: 'var(--font-mono)',
      },
      keyframes: {
        pulseDot: {
          '0%': { transform: 'scale(1)', opacity: '0.7' },
          '100%': { transform: 'scale(3.2)', opacity: '0' },
        },
        badgePulse: {
          '0%, 100%': {
            boxShadow:
              '0 0 calc(8px * var(--glow)) oklch(0.68 0.21 25 / calc(0.40 * var(--glow))), inset 0 0 calc(8px * var(--glow)) oklch(0.68 0.21 25 / calc(0.15 * var(--glow)))',
          },
          '50%': {
            boxShadow:
              '0 0 calc(18px * var(--glow)) oklch(0.68 0.21 25 / calc(0.65 * var(--glow))), inset 0 0 calc(10px * var(--glow)) oklch(0.68 0.21 25 / calc(0.20 * var(--glow)))',
          },
        },
        tickerScroll: {
          from: { transform: 'translateX(0)' },
          to: { transform: 'translateX(-50%)' },
        },
      },
      animation: {
        'pulse-dot': 'pulseDot 2s ease-out infinite',
        'badge-pulse': 'badgePulse 2.4s ease-in-out infinite',
        'ticker-scroll': 'tickerScroll 60s linear infinite',
      },
    },
  },
  plugins: [],
};

export default config;

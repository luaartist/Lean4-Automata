import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          primary: 'var(--bg-primary)',
          secondary: 'var(--bg-secondary)',
          surface: 'var(--bg-surface)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
        },
        border: {
          DEFAULT: 'var(--border-default)',
        },
        accent: {
          primary: 'var(--accent-primary)',
          hover: 'var(--accent-hover)',
        },
        status: {
          error: 'var(--status-error)',
          warning: 'var(--status-warning)',
          success: 'var(--status-success)',
        },
        edge: {
          direct: 'var(--edge-direct)',
          import: 'var(--edge-import)',
          implicit: 'var(--edge-implicit)',
          indirect: 'var(--edge-indirect)',
        },
      },
      spacing: {
        '4': '4px',
        '8': '8px',
        '12': '12px',
        '16': '16px',
        '24': '24px',
        '32': '32px',
        '48': '48px',
        '64': '64px',
        '96': '96px',
      },
      fontSize: {
        xs: ['12px', '16px'],
        sm: ['14px', '20px'],
        base: ['16px', '24px'],
        lg: ['18px', '28px'],
        xl: ['24px', '32px'],
        '2xl': ['30px', '36px'],
        mono: ['14px', '20px'],
      },
      fontWeight: {
        normal: '400',
        medium: '500',
        semibold: '600',
        bold: '700',
      },
      screens: {
        mobile: { max: '639px' },
        tablet: { min: '640px', max: '1023px' },
        desktop: { min: '1024px' },
      },
    },
  },
  plugins: [],
};

export default config;

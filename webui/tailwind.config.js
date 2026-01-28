/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark theme colors (matching existing CSS variables)
        bg: {
          DEFAULT: '#101114',
          surface: '#1b1e22',
        },
        surface: {
          DEFAULT: '#1b1e22',
          hover: 'rgba(122, 162, 247, 0.05)',
        },
        text: {
          DEFAULT: '#eaeef2',
          secondary: '#9aa3ac',
        },
        primary: {
          DEFAULT: '#7aa2f7',
          variant: '#3b82f6',
          light: 'rgba(122, 162, 247, 0.15)',
        },
        success: {
          DEFAULT: '#22c55e',
          light: 'rgba(34, 197, 94, 0.15)',
        },
        danger: {
          DEFAULT: '#ef4444',
          light: 'rgba(239, 68, 68, 0.15)',
        },
        warning: {
          DEFAULT: '#facc15',
          light: 'rgba(250, 204, 21, 0.15)',
        },
        border: {
          DEFAULT: '#2a2f36',
          hover: 'rgba(122, 162, 247, 0.3)',
        },
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          '"Helvetica Neue"',
          'Arial',
          '"Noto Sans"',
          'sans-serif',
          '"Apple Color Emoji"',
          '"Segoe UI Emoji"',
          '"Segoe UI Symbol"',
        ],
      },
      borderRadius: {
        card: '14px',
        button: '8px',
      },
      boxShadow: {
        card: '0 2px 8px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06)',
        'card-dark': '0 8px 24px rgba(0, 0, 0, 0.25), 0 2px 4px rgba(0, 0, 0, 0.3)',
        'card-hover': '0 16px 40px rgba(0, 0, 0, 0.12), 0 4px 8px rgba(0, 0, 0, 0.08)',
        'card-hover-dark': '0 12px 32px rgba(0, 0, 0, 0.35), 0 4px 8px rgba(0, 0, 0, 0.4)',
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.3s ease',
        'slide-in': 'slideIn 0.2s ease',
        'pulse-slow': 'pulse 1.5s ease-in-out infinite',
      },
      keyframes: {
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(-10px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [],
  // Important: Tailwind shouldn't override Mantine's styles
  corePlugins: {
    preflight: false, // Disable Tailwind's base reset since we have custom CSS
  },
}

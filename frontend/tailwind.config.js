/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        gh: {
          canvas: '#F6F8FA',
          surface: '#FFFFFF',
          fg: '#24292F',
          muted: '#57606A',
          border: '#D0D7DE',
          selected: '#EFF2F5',
          accent: '#0969DA',
          accentSubtle: '#DDF4FF',
          accentBorder: '#54AEFF',
          success: '#1A7F37',
          successSubtle: '#DAFBE1',
          successBorder: '#4AC26B',
          warning: '#9A6700',
          warningSubtle: '#FFF8C5',
          warningBorder: '#D4A72C',
          danger: '#CF222E',
          dangerSubtle: '#FFEBE9',
          dangerBorder: '#FF8182',
        },
      },
    },
  },
  plugins: [],
}

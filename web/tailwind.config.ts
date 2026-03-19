import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/app/**/*.{js,ts,jsx,tsx}", "./src/components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "var(--color-ink)",
        mist: "var(--color-mist)",
        panel: "var(--color-panel)",
        accent: "var(--color-accent)",
        signal: "var(--color-signal)",
        warn: "var(--color-warn)",
        good: "var(--color-good)"
      },
      fontFamily: {
        headline: ["var(--font-headline)"],
        body: ["var(--font-body)"],
        mono: ["var(--font-mono)"]
      },
      boxShadow: {
        panel: "0 20px 40px rgba(14, 27, 39, 0.09)"
      }
    }
  },
  plugins: []
};

export default config;


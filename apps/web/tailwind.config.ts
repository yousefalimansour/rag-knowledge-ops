import type { Config } from "tailwindcss";

// Project palette — dark glass-morphism, locked in step 01.
// Source aesthetic: Uiverse Priyanshu02020 login card.
// These tokens are the project's design language; all subsequent screens
// (dashboard, documents, copilot, insights) compose from them.
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surface scale — from page background up to elevated cards.
        surface: {
          900: "#1a1a1a", // page background
          800: "#222222", // card / panel resting
          700: "#272727", // card / login-box (Uiverse `--login-box-color`)
          600: "#2f2f2f", // hover / focus lift
        },
        // Interactive controls.
        control: {
          DEFAULT: "#373737", // button (Uiverse `--button-color`)
          input: "#3a3a3a", // input field (Uiverse `--input-color`)
        },
        // Text scale.
        ink: {
          DEFAULT: "#ffffff",
          muted: "rgba(255, 255, 255, 0.7)",
          subtle: "rgba(255, 255, 255, 0.5)", // Uiverse `--footer-color`
          faint: "rgba(255, 255, 255, 0.12)", // dividers, hairlines
        },
        // Brand accent — used sparingly for active state, links, focus rings.
        accent: {
          DEFAULT: "#7c8cff",
          soft: "rgba(124, 140, 255, 0.18)",
        },
      },
      boxShadow: {
        // Match Uiverse login-box outer + inset combo.
        card:
          "0 4px 8px rgba(0,0,0,0.2), 0 8px 16px rgba(0,0,0,0.2), 0 0 8px rgba(255,255,255,0.1), 0 0 16px rgba(255,255,255,0.08)",
        inset:
          "inset 0 40px 60px -8px rgba(255,255,255,0.12), inset 4px 0 12px -6px rgba(255,255,255,0.12), inset 0 0 12px -4px rgba(255,255,255,0.12)",
        button:
          "inset 0 3px 6px -4px rgba(255,255,255,0.6), inset 0 -3px 6px -2px rgba(0,0,0,0.8)",
      },
    },
  },
  plugins: [],
} satisfies Config;

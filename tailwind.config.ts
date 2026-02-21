import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                background: "var(--background)",
                foreground: "var(--foreground)",
                neon: {
                    green: "#00FF41", // Long / Bullish
                    red: "#FF003C",   // Short / Bearish
                    cyan: "#00E5FF",  // Neutral / Math / Support
                    slate: "#1A1A1A", // Paneles Glassmorphism
                }
            },
            backgroundImage: {
                'glass-gradient': 'linear-gradient(180deg, rgba(26, 26, 26, 0.70) 0%, rgba(10, 10, 10, 0.90) 100%)',
            }
        },
    },
    plugins: [],
};

export default config;

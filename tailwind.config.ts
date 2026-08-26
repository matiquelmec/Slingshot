import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ["var(--font-sans)", "Inter", "sans-serif"],
                mono: ["var(--font-mono)", "JetBrains Mono", "monospace"],
            },
            colors: {
                background: "var(--background)",
                foreground: "var(--foreground)",
                cyber: {
                    dark: "#030712",
                    slate: "#0B132B",
                    card: "rgba(15, 23, 42, 0.65)",
                    border: "rgba(255, 255, 255, 0.08)",
                },
                neon: {
                    green: "#10B981", // Long / Esmeralda Cuantitativo
                    red: "#F43F5E",   // Short / Carmesí Institucional
                    cyan: "#06B6D4",  // Fast BE / Soporte Matemático
                    blue: "#38BDF8",  // Ticker / Telemetría
                    gold: "#F59E0B",  // Élite / Oro / Institucional
                    purple: "#8B5CF6",// IA / Nemotron / SMC
                    slate: "#1E293B", // Paneles Glassmorphism
                }
            },
            backgroundImage: {
                'glass-gradient': 'linear-gradient(180deg, rgba(30, 41, 59, 0.70) 0%, rgba(15, 23, 42, 0.90) 100%)',
                'cyber-grid': 'radial-gradient(circle, rgba(255, 255, 255, 0.03) 1px, transparent 1px)',
                'neon-radial': 'radial-gradient(circle at 50% 0%, rgba(6, 182, 212, 0.15) 0%, transparent 70%)',
            },
            boxShadow: {
                'glow-cyan': '0 0 20px -5px rgba(6, 182, 212, 0.3)',
                'glow-green': '0 0 20px -5px rgba(16, 185, 129, 0.3)',
                'glow-red': '0 0 20px -5px rgba(244, 63, 94, 0.3)',
                'glow-gold': '0 0 20px -5px rgba(245, 158, 11, 0.3)',
            }
        },
    },
    plugins: [],
};

export default config;

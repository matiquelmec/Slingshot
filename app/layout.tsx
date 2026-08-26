import type { Metadata } from "next";
import { Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const plusJakarta = Plus_Jakarta_Sans({
    subsets: ["latin"],
    variable: "--font-sans",
    display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
    subsets: ["latin"],
    variable: "--font-mono",
    display: "swap",
});

export const metadata: Metadata = {
    title: "SLINGSHOT APEX | Institutional Trading Terminal",
    description: "Capa 5: Quantitative & Algorithmic Execution System",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en" suppressHydrationWarning className={`${plusJakarta.variable} ${jetbrainsMono.variable}`}>
            <body suppressHydrationWarning className="antialiased font-sans bg-background text-foreground h-screen w-screen overflow-hidden selection:bg-neon-cyan/20 selection:text-neon-cyan">
                {children}
            </body>
        </html>
    );
}

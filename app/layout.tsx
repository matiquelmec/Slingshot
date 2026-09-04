import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
    title: "SLINGSHOT APEX | Institutional Trading Terminal",
    description: "Capa 5: Quantitative & Algorithmic Execution System",
};

export const viewport: Viewport = {
    width: "device-width",
    initialScale: 1,
    maximumScale: 1,
    userScalable: false,
    viewportFit: "cover",
    themeColor: "#02040A",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en" suppressHydrationWarning>
            <head>
                <link rel="preconnect" href="https://fonts.googleapis.com" />
                <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
                <link 
                    href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,300..800;1,300..800&family=Plus+Jakarta+Sans:ital,wght@0,300..800;1,300..800&display=swap" 
                    rel="stylesheet" 
                />
            </head>
            <body suppressHydrationWarning className="antialiased font-sans bg-background text-foreground min-h-screen w-full selection:bg-neon-cyan/20 selection:text-neon-cyan">
                {children}
            </body>
        </html>
    );
}

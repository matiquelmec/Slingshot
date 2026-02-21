import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
    title: "SLINGSHOT | Telescopic Sight",
    description: "Capa 5: Institutional Algorithmic Trading Interface",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en" suppressHydrationWarning>
            <body suppressHydrationWarning className="antialiased bg-background text-foreground h-screen w-screen overflow-hidden">
                {children}
            </body>
        </html>
    );
}

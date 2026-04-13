'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { 
    LayoutDashboard, Radio, Terminal, BarChart2, Activity, Database, 
    Crosshair, ShieldCheck 
} from 'lucide-react';
import { useTelemetryStore } from '../store/telemetryStore';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const router = useRouter();
    const { isConnected, connect } = useTelemetryStore();
    const hasInitialized = React.useRef(false);

    // Auto-Conexión Global con persistencia de moneda
    useEffect(() => {
        if (!hasInitialized.current) {
            hasInitialized.current = true;
            const savedSymbol = typeof window !== 'undefined' ? localStorage.getItem('slingshot_symbol') : null;
            const savedTimeframe = typeof window !== 'undefined' ? localStorage.getItem('slingshot_timeframe') : null;
            const { activeSymbol, activeTimeframe } = useTelemetryStore.getState();
            connect(savedSymbol || activeSymbol, (savedTimeframe as any) || activeTimeframe);
        }
    }, [connect]);

    const navItems = [
        { name: 'Overview', href: '/', icon: LayoutDashboard },
        { name: 'Radar Center', href: '/radar', icon: Radio },
        { name: 'Signal Terminal', href: '/signals', icon: Terminal },
        { name: 'Trading Chart', href: '/chart', icon: BarChart2 },
        { name: 'Liquidity Heatmap', href: '/heatmap', icon: Activity },
        { name: 'Session Log', href: '/history', icon: Database },
    ];

    return (
        <div className="h-screen w-full flex flex-col bg-[#02040A] text-foreground font-mono relative overflow-hidden selection:bg-neon-cyan/30">
            {/* Background */}
            <div className="absolute inset-0 z-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-[#111A2C] via-[#02040A] to-[#010204] pointer-events-none" />
            <div
                className="absolute inset-0 z-0 opacity-[0.04] pointer-events-none"
                style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)', backgroundSize: '50px 50px' }}
            />

            {/* Header */}
            <motion.header
                initial={{ y: -50, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                className="h-16 border-b border-white/5 bg-black/30 backdrop-blur-2xl flex items-center justify-between px-6 z-20 shadow-[0_4px_40px_rgba(0,0,0,0.6)] flex-shrink-0"
            >
                <div className="flex items-center gap-5">
                    <div className="flex items-center justify-center bg-gradient-to-br from-neon-cyan/20 to-transparent p-2.5 rounded-xl border border-neon-cyan/30 shadow-[0_0_15px_rgba(0,229,255,0.2)]">
                        <Crosshair className="text-neon-cyan" size={20} />
                    </div>
                    <div className="flex flex-col">
                        <h1 className="text-base font-black tracking-[0.2em] text-white/90 drop-shadow-[0_0_10px_rgba(0,229,255,0.4)] flex items-center uppercase">
                            SLINGSHOT <span className="text-neon-cyan ml-2 text-sm">CORE</span>
                        </h1>
                        <p className="text-[10px] text-neon-cyan/60 tracking-[0.3em] font-semibold mt-0.5 uppercase">ESTRATEGIA CUANTITATIVA INSTITUCIONAL</p>
                    </div>
                </div>

                <div className="flex items-center space-x-5 text-xs font-bold tracking-wider uppercase">
                    <div className="flex items-center gap-2.5 text-white/40">
                        <Radio size={14} className={isConnected ? "text-neon-green" : "text-white/20 animate-pulse"} />
                        <span>DATOS: <span className={isConnected ? "text-neon-green" : "text-white/20"}>{isConnected ? 'LIVE SYNC' : 'WAITING'}</span></span>
                    </div>
                    <div className="flex items-center gap-2.5 text-blue-400/80">
                        <Database size={14} />
                        <span>ESTADO: <span className="text-blue-400 drop-shadow-[0_0_5px_rgba(96,165,250,0.5)]">LOCAL MASTER v5.7</span></span>
                    </div>
                    <div className="flex items-center gap-2.5 bg-neon-green/10 px-3 py-1.5 rounded-full border border-neon-green/20">
                        <ShieldCheck size={14} className="text-neon-green" />
                        <span className="text-neon-green drop-shadow-[0_0_8px_rgba(0,255,65,0.8)]">SYSTEM ONLINE</span>
                    </div>
                </div>
            </motion.header>

            <div className="flex flex-1 overflow-hidden z-10">
                {/* Sidebar Navigation */}
                <motion.nav
                    initial={{ x: -100, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    className="w-64 border-r border-white/5 bg-black/20 backdrop-blur-xl p-4 flex flex-col gap-2 relative z-20 shadow-[4px_0_40px_rgba(0,0,0,0.3)] flex-shrink-0"
                >
                    <div className="text-[10px] font-bold tracking-[0.2em] text-white/40 mb-4 px-2 uppercase">HERRAMIENTAS</div>
                    {navItems.map((item) => {
                        const isActive = pathname === item.href || (pathname !== '/' && item.href !== '/' && pathname.startsWith(item.href));
                        const Icon = item.icon;
                        return (
                            <Link key={item.name} href={item.href}>
                                <div className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all hover:scale-[1.02] ${isActive ? 'bg-neon-cyan/10 border border-neon-cyan/30 text-neon-cyan shadow-[0_0_15px_rgba(0,229,255,0.15)]' : 'border border-transparent text-white/50 hover:bg-white/5 hover:text-white/90'}`}>
                                    <Icon size={18} />
                                    <span className="text-xs font-bold tracking-wider uppercase">{item.name}</span>
                                </div>
                            </Link>
                        );
                    })}
                </motion.nav>

                {/* Main Content Area — Scrollable v5.7.155 Master Gold */}
                <main className="flex-1 overflow-y-auto custom-scrollbar relative bg-black/10 flex flex-col">
                    <div className="flex-1 h-full">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
}

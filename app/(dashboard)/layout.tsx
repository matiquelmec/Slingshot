'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { 
    LayoutDashboard, Radio, Terminal, BarChart2, Activity, Database, 
    Crosshair, ShieldCheck, Menu, X, ChevronRight, Zap
} from 'lucide-react';
import { useTelemetryStore } from '../store/telemetryStore';
import OnboardingModal from '@/app/components/setup/OnboardingModal';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const { isConnected, connect, connectionStatus } = useTelemetryStore();
    const hasInitialized = React.useRef(false);
    const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

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

    // Cerrar drawer automáticamente al cambiar de ruta
    useEffect(() => {
        setMobileDrawerOpen(false);
    }, [pathname]);

    const navItems = [
        { name: 'Overview', href: '/', icon: LayoutDashboard },
        { name: 'Radar Center', href: '/radar', icon: Radio },
        { name: 'Signal Terminal', href: '/signals', icon: Terminal },
        { name: 'FTMO MT5', href: '/ftmo', icon: ShieldCheck },
        { name: 'Trading Chart', href: '/chart', icon: BarChart2 },
        { name: 'Liquidity Heatmap', href: '/heatmap', icon: Activity },
        { name: 'Session Log', href: '/history', icon: Database },
    ];

    const mobileBottomTabs = [
        { name: 'Overview', href: '/', icon: LayoutDashboard },
        { name: 'Radar', href: '/radar', icon: Radio },
        { name: 'Signals', href: '/signals', icon: Terminal },
        { name: 'Chart', href: '/chart', icon: BarChart2 },
        { name: 'FTMO', href: '/ftmo', icon: ShieldCheck },
    ];

    return (
        <div className="min-h-screen lg:h-screen w-full flex flex-col bg-[#02040A] text-foreground font-mono relative selection:bg-neon-cyan/30">
            {/* Background */}
            <div className="absolute inset-0 z-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-[#111A2C] via-[#02040A] to-[#010204] pointer-events-none" />
            <div
                className="absolute inset-0 z-0 opacity-[0.04] pointer-events-none"
                style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)', backgroundSize: '50px 50px' }}
            />

            {/* Header Adaptativo (Desktop & Mobile) */}
            <header className="h-16 border-b border-white/5 bg-black/40 backdrop-blur-2xl flex items-center justify-between px-4 lg:px-6 z-30 shadow-[0_4px_40px_rgba(0,0,0,0.6)] flex-shrink-0 sticky top-0">
                {/* Brand Title */}
                <div className="flex items-center gap-3 lg:gap-5">
                    <div className="flex items-center justify-center bg-gradient-to-br from-neon-cyan/20 to-transparent p-2 lg:p-2.5 rounded-xl border border-neon-cyan/30 shadow-[0_0_15px_rgba(0,229,255,0.2)]">
                        <Crosshair className="text-neon-cyan" size={18} />
                    </div>
                    <div className="flex flex-col">
                        <h1 className="text-sm lg:text-base font-black tracking-[0.15em] lg:tracking-[0.2em] text-white/90 drop-shadow-[0_0_10px_rgba(0,229,255,0.4)] flex items-center uppercase">
                            SLINGSHOT <span className="text-neon-cyan ml-1.5 lg:ml-2 text-xs lg:text-sm">CORE</span>
                        </h1>
                        <p className="hidden md:block text-[10px] text-neon-cyan/60 tracking-[0.3em] font-semibold mt-0.5 uppercase">
                            ESTRATEGIA CUANTITATIVA INSTITUCIONAL
                        </p>
                    </div>
                </div>

                {/* Status Badges - Desktop */}
                <div className="hidden lg:flex items-center space-x-5 text-xs font-bold tracking-wider uppercase">
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

                {/* Mobile Controls (Latency Pill + Hamburger Menu Button) */}
                <div className="flex lg:hidden items-center gap-2.5">
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-[10px] font-bold">
                        <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-neon-green animate-pulse' : 'bg-neon-red'}`} />
                        <span className="text-white/70">{isConnected ? 'LIVE' : 'SYNC'}</span>
                    </div>

                    <button
                        onClick={() => setMobileDrawerOpen(prev => !prev)}
                        className="p-2 rounded-xl bg-white/5 border border-white/10 hover:border-neon-cyan/50 text-white/80 hover:text-white transition-all cursor-pointer"
                        aria-label="Abrir menú de navegación"
                    >
                        {mobileDrawerOpen ? <X size={20} className="text-neon-cyan" /> : <Menu size={20} />}
                    </button>
                </div>
            </header>

            {/* Mobile Drawer (Slide-Over Menu) */}
            <AnimatePresence>
                {mobileDrawerOpen && (
                    <>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setMobileDrawerOpen(false)}
                            className="fixed inset-0 z-40 bg-black/80 backdrop-blur-sm lg:hidden"
                        />
                        <motion.aside
                            initial={{ x: '-100%' }}
                            animate={{ x: 0 }}
                            exit={{ x: '-100%' }}
                            transition={{ type: 'spring', damping: 25, stiffness: 260 }}
                            className="fixed top-0 bottom-0 left-0 z-50 w-72 max-w-[85vw] bg-[#050B14]/98 border-r border-white/10 p-5 flex flex-col justify-between shadow-2xl lg:hidden overflow-y-auto"
                        >
                            <div>
                                <div className="flex items-center justify-between pb-4 mb-4 border-b border-white/10">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-neon-cyan/10 border border-neon-cyan/30">
                                            <Zap size={18} className="text-neon-cyan" />
                                        </div>
                                        <div>
                                            <h2 className="text-xs font-black tracking-widest text-white">SLINGSHOT APEX</h2>
                                            <p className="text-[9px] text-neon-cyan font-bold tracking-wider">INSTITUTIONAL v5.7</p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => setMobileDrawerOpen(false)}
                                        className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/5"
                                    >
                                        <X size={18} />
                                    </button>
                                </div>

                                <div className="text-[10px] font-bold tracking-[0.2em] text-white/40 mb-3 px-2 uppercase">
                                    HERRAMIENTAS QUANT
                                </div>
                                <div className="flex flex-col gap-1.5">
                                    {navItems.map((item) => {
                                        const isActive = pathname === item.href || (pathname !== '/' && item.href !== '/' && pathname.startsWith(item.href));
                                        const Icon = item.icon;
                                        return (
                                            <Link key={item.name} href={item.href} onClick={() => setMobileDrawerOpen(false)}>
                                                <div className={`flex items-center justify-between px-3.5 py-3 rounded-xl transition-all ${isActive ? 'bg-neon-cyan/15 border border-neon-cyan/30 text-neon-cyan shadow-[0_0_15px_rgba(0,229,255,0.15)] font-bold' : 'border border-transparent text-white/60 hover:bg-white/5 hover:text-white'}`}>
                                                    <div className="flex items-center gap-3">
                                                        <Icon size={18} />
                                                        <span className="text-xs tracking-wider uppercase">{item.name}</span>
                                                    </div>
                                                    <ChevronRight size={14} className={isActive ? 'text-neon-cyan' : 'text-white/20'} />
                                                </div>
                                            </Link>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Drawer Footer Status */}
                            <div className="pt-4 border-t border-white/10 mt-6 flex flex-col gap-2 text-[10px] font-mono text-white/40">
                                <div className="flex items-center justify-between">
                                    <span>CONEXIÓN:</span>
                                    <span className={isConnected ? 'text-neon-green font-bold' : 'text-neon-red font-bold'}>
                                        {isConnected ? 'LIVE SYNC' : 'OFFLINE'}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span>MOTOR:</span>
                                    <span className="text-neon-cyan font-bold">LOCAL MASTER v5.7</span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span>STATUS:</span>
                                    <span className="text-neon-green font-bold">{connectionStatus}</span>
                                </div>
                            </div>
                        </motion.aside>
                    </>
                )}
            </AnimatePresence>

            <div className="flex flex-1 overflow-hidden z-10 relative">
                {/* Desktop Sidebar Navigation (Hidden on Mobile) */}
                <motion.nav
                    initial={{ x: -100, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    className="hidden lg:flex w-64 border-r border-white/5 bg-black/20 backdrop-blur-xl p-4 flex-col gap-2 relative z-20 shadow-[4px_0_40px_rgba(0,0,0,0.3)] flex-shrink-0"
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

                {/* Main Content Area — Scrollable with extra bottom padding on mobile for BottomNav */}
                <main className="flex-1 overflow-y-auto custom-scrollbar relative bg-black/10 flex flex-col pb-20 lg:pb-0 min-w-0">
                    <div className="flex-1 h-full w-full min-w-0">
                        {children}
                    </div>
                </main>
            </div>

            {/* Mobile Bottom Navigation Dock (Fixed at bottom on mobile screens) */}
            <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-[#050B14]/95 backdrop-blur-2xl border-t border-white/10 px-2 py-1.5 flex items-center justify-around pb-safe shadow-[0_-8px_30px_rgba(0,0,0,0.8)]">
                {mobileBottomTabs.map((tab) => {
                    const isActive = pathname === tab.href || (pathname !== '/' && tab.href !== '/' && pathname.startsWith(tab.href));
                    const Icon = tab.icon;
                    return (
                        <Link key={tab.name} href={tab.href} className="flex-1 py-1">
                            <div className={`flex flex-col items-center justify-center gap-1 transition-all ${isActive ? 'text-neon-cyan scale-105' : 'text-white/40 hover:text-white/80'}`}>
                                <div className={`p-1.5 rounded-xl transition-colors ${isActive ? 'bg-neon-cyan/15 border border-neon-cyan/30 shadow-[0_0_10px_rgba(0,229,255,0.3)]' : 'border border-transparent'}`}>
                                    <Icon size={18} />
                                </div>
                                <span className={`text-[9px] font-mono tracking-tight font-bold ${isActive ? 'text-neon-cyan' : 'text-white/40'}`}>
                                    {tab.name}
                                </span>
                            </div>
                        </Link>
                    );
                })}
            </nav>

            {/* Asistente de Configuración Inicial (Onboarding Wizard) */}
            <OnboardingModal />
        </div>
    );
}

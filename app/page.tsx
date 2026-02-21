'use client';

import React, { useState, useEffect, useRef } from 'react';


import { motion, AnimatePresence } from 'framer-motion';
import {
    Crosshair, Activity, Cpu, Terminal, ShieldCheck, Database,
    Radio, ChevronRight, BarChart2, Plus, X
} from 'lucide-react';
import dynamic from 'next/dynamic';
import { useTelemetryStore, Timeframe } from './store/telemetryStore';
import { useIndicatorsStore } from './store/indicatorsStore';

const TradingChart = dynamic(() => import('./components/ui/TradingChart'), { ssr: false });

// === WATCHLIST: Agrega o quita activos aquí. El backend soporta CUALQUIER par de Binance ===
const DEFAULT_WATCHLIST = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
    'DOGEUSDT', 'AVAXUSDT', 'ADAUSDT', 'LINKUSDT', 'DOTUSDT'
];

const TIMEFRAMES: Timeframe[] = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '8h', '1d', '1w', '1M'];



export default function Dashboard() {
    const [mounted, setMounted] = useState(false);
    const [showIndicators, setShowIndicators] = useState(false);
    const [watchlist, setWatchlist] = useState<string[]>(DEFAULT_WATCHLIST);
    const { indicators, toggleIndicator } = useIndicatorsStore();
    const [addingSymbol, setAddingSymbol] = useState(false);
    const [newSymbol, setNewSymbol] = useState('');

    const indicatorsPanelRef = useRef<HTMLDivElement>(null);

    const { isConnected, activeSymbol, activeTimeframe, latestPrice, mlProjection, tacticalDecision, connect, setTimeframe } = useTelemetryStore();

    useEffect(() => {
        setMounted(true);
        connect('BTCUSDT', '15m');
    }, []);

    // Close indicators panel on outside click (uses 'click', not 'mousedown',
    // so toggle buttons inside fire their onClick first then stop propagation)
    useEffect(() => {
        if (!showIndicators) return;
        const handler = (e: MouseEvent) => {
            if (indicatorsPanelRef.current && !indicatorsPanelRef.current.contains(e.target as Node)) {
                setShowIndicators(false);
            }
        };
        document.addEventListener('click', handler);
        return () => document.removeEventListener('click', handler);
    }, [showIndicators]);

    if (!mounted) return null;

    const handleSymbolClick = (symbol: string) => {
        if (symbol !== activeSymbol) {
            connect(symbol);
        }
    };

    const handleTimeframeClick = (tf: Timeframe) => {
        if (tf !== activeTimeframe) {
            setTimeframe(tf);
        }
    };

    const handleAddSymbol = () => {
        const sym = newSymbol.trim().toUpperCase();
        if (sym && !watchlist.includes(sym)) {
            setWatchlist(prev => [...prev, sym]);
        }
        setNewSymbol('');
        setAddingSymbol(false);
    };

    const handleRemoveSymbol = (sym: string) => {
        if (sym === activeSymbol) return; // No puedes quitar el activo activo
        setWatchlist(prev => prev.filter(s => s !== sym));
    };

    const containerVariants = {
        hidden: { opacity: 0 },
        show: { opacity: 1, transition: { staggerChildren: 0.12 } }
    };
    const itemVariants = {
        hidden: { opacity: 0, scale: 0.97, y: 15 },
        show: { opacity: 1, scale: 1, y: 0, transition: { type: 'spring', stiffness: 250, damping: 22 } }
    };

    const enabledCount = indicators.filter(i => i.enabled).length;

    return (
        <div className="h-full w-full flex flex-col bg-[#02040A] text-foreground font-mono relative overflow-hidden selection:bg-neon-cyan/30">

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
                className="h-16 border-b border-white/5 bg-black/30 backdrop-blur-2xl flex items-center justify-between px-6 z-20 shadow-[0_4px_40px_rgba(0,0,0,0.6)]"
            >
                <div className="flex items-center gap-5">
                    <div className="flex items-center justify-center bg-gradient-to-br from-neon-cyan/20 to-transparent p-2.5 rounded-xl border border-neon-cyan/30 shadow-[0_0_15px_rgba(0,229,255,0.2)]">
                        <Crosshair className="text-neon-cyan" size={20} />
                    </div>
                    <div className="flex flex-col">
                        <h1 className="text-base font-black tracking-[0.2em] text-white/90 drop-shadow-[0_0_10px_rgba(0,229,255,0.4)] flex items-center">
                            SLINGSHOT <span className="text-neon-cyan ml-2 text-sm">CORE</span>
                        </h1>
                        <p className="text-[10px] text-neon-cyan/60 tracking-[0.3em] font-semibold mt-0.5">ESTRATEGIA CUANTITATIVA INSTITUCIONAL</p>
                    </div>
                </div>

                <div className="flex items-center space-x-8 text-xs font-bold tracking-wider">
                    <div className="flex items-center gap-2.5 text-white/40">
                        <Radio size={14} className={isConnected ? "text-neon-green" : "text-white/20 animate-pulse"} />
                        <span>DATOS: <span className={isConnected ? "text-neon-green" : "text-white/20"}>{isConnected ? 'LIVE SYNC' : 'WAITING'}</span></span>
                    </div>
                    <div className="flex items-center gap-2.5 text-blue-400/80">
                        <Database size={14} />
                        <span>CACHE: <span className="text-blue-400 drop-shadow-[0_0_5px_rgba(96,165,250,0.5)]">REDIS OK</span></span>
                    </div>
                    <div className="flex items-center gap-2.5 bg-neon-green/10 px-4 py-1.5 rounded-full border border-neon-green/20">
                        <ShieldCheck size={14} className="text-neon-green" />
                        <span className="text-neon-green drop-shadow-[0_0_8px_rgba(0,255,65,0.8)]">SYSTEM ONLINE</span>
                    </div>
                </div>
            </motion.header>

            {/* Main Grid */}
            <motion.main
                variants={containerVariants}
                initial="hidden"
                animate="show"
                className="flex-1 grid grid-cols-12 gap-5 p-5 z-10 overflow-hidden"
            >
                {/* Left: Command Center */}
                <motion.section variants={itemVariants} className="col-span-3 flex flex-col gap-5 overflow-hidden">

                    {/* Watchlist / Radar */}
                    <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl flex flex-col flex-1 relative overflow-hidden">
                        <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none" />
                        <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                            <div className="flex items-center gap-2.5">
                                <Activity size={16} className="text-neon-cyan" />
                                <h2 className="text-xs font-bold text-white/90 tracking-widest">CONTROL DE RADARES</h2>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="relative flex h-2 w-2">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neon-cyan opacity-40" />
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-neon-cyan/80" />
                                </span>
                                <button
                                    onClick={() => setAddingSymbol(v => !v)}
                                    className="ml-1 text-white/30 hover:text-neon-cyan transition-colors"
                                    title="Añadir símbolo"
                                >
                                    <Plus size={14} />
                                </button>
                            </div>
                        </div>

                        {/* Add symbol input */}
                        <AnimatePresence>
                            {addingSymbol && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: 'auto', opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    className="overflow-hidden px-4 pt-3"
                                >
                                    <div className="flex gap-2">
                                        <input
                                            autoFocus
                                            type="text"
                                            placeholder="BTCUSDT..."
                                            value={newSymbol}
                                            onChange={e => setNewSymbol(e.target.value)}
                                            onKeyDown={e => e.key === 'Enter' && handleAddSymbol()}
                                            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white placeholder-white/20 focus:outline-none focus:border-neon-cyan/50"
                                        />
                                        <button onClick={handleAddSymbol} className="bg-neon-cyan/15 border border-neon-cyan/30 text-neon-cyan text-xs px-3 py-1.5 rounded-lg hover:bg-neon-cyan/25 transition-all">
                                            +
                                        </button>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        <div className="p-4 flex flex-col gap-2 overflow-y-auto flex-1">
                            {watchlist.map((ticker) => {
                                const isActive = ticker === activeSymbol;
                                return (
                                    <div
                                        key={ticker}
                                        onClick={() => handleSymbolClick(ticker)}
                                        className={`group flex justify-between items-center text-xs p-3 rounded-lg border transition-all cursor-pointer hover:-translate-y-0.5 ${isActive
                                            ? 'bg-neon-cyan/10 border-neon-cyan/30 shadow-[0_0_20px_rgba(0,229,255,0.1)]'
                                            : 'bg-white/[0.02] border-white/5 hover:border-white/20 hover:bg-white/[0.05]'
                                            }`}
                                    >
                                        <span className={`font-bold tracking-wider ${isActive ? 'text-neon-cyan' : 'text-white/70 group-hover:text-white'}`}>
                                            {ticker}
                                        </span>
                                        <div className="flex items-center gap-2">
                                            {isActive && latestPrice && (
                                                <span className="text-neon-green font-bold text-[10px] tracking-wider">
                                                    ${latestPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                                                </span>
                                            )}
                                            {!isActive && (
                                                <button
                                                    onClick={e => { e.stopPropagation(); handleRemoveSymbol(ticker); }}
                                                    className="opacity-0 group-hover:opacity-100 transition-opacity text-white/20 hover:text-red-400"
                                                >
                                                    <X size={10} />
                                                </button>
                                            )}
                                            <span className={`h-2 w-2 rounded-full ${isActive ? 'bg-neon-cyan shadow-[0_0_8px_rgba(0,229,255,0.8)]' : 'bg-neon-green/40'}`} />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Tactical Decision */}
                    <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl flex-1 flex flex-col relative overflow-hidden" style={{ maxHeight: '40%' }}>
                        <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                            <div className="flex items-center gap-2.5">
                                <Cpu size={16} className={`${tacticalDecision.strategy === 'STANDBY' ? 'text-white/40' : 'text-neon-green'}`} />
                                <h2 className="text-xs font-bold text-white/90 tracking-widest">DECISIÓN TÁCTICA</h2>
                            </div>
                        </div>
                        <div className="p-5 flex flex-col gap-4 overflow-y-auto">

                            <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                                <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] mb-1.5 block">RÉGIMEN DE MERCADO</span>
                                <span className={`text-sm font-black tracking-wider ${tacticalDecision.regime.includes('BULLISH') ? 'text-neon-green' : tacticalDecision.regime.includes('BEARISH') ? 'text-neon-red' : 'text-neon-cyan'}`}>{tacticalDecision.regime}</span>
                            </div>

                            <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                                <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] mb-1.5 block">ESTRATEGIA ENRUTADA</span>
                                <div className="flex items-center gap-2">
                                    <span className={`h-2 w-2 rounded-full ${tacticalDecision.strategy !== 'STANDBY' ? 'bg-neon-green shadow-[0_0_8px_rgba(0,255,65,0.8)]' : 'bg-white/20'}`} />
                                    <span className="text-white/90 font-bold text-xs tracking-wide">{tacticalDecision.strategy}</span>
                                </div>
                            </div>

                            <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3 relative overflow-hidden">
                                <div className="absolute left-0 top-0 bottom-0 w-1 bg-white/20" />
                                <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] mb-1.5 block pl-3">RAZONAMIENTO ML</span>
                                <span className="text-[11px] text-white/70 font-mono leading-relaxed pl-3 block">
                                    {tacticalDecision.reasoning}
                                </span>
                            </div>

                        </div>
                    </div>
                </motion.section>

                {/* Center: Trading Chart */}
                <motion.section variants={itemVariants} className="col-span-6 bg-[#010204]/80 backdrop-blur-3xl rounded-2xl border border-white/10 relative flex flex-col overflow-hidden shadow-[inset_0_0_100px_rgba(0,0,0,1)]">

                    {/* Watermark */}
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none overflow-hidden">
                        <span className="text-[12rem] font-black text-white/[0.015] tracking-tighter transform rotate-12 scale-150">SLINGSHOT</span>
                    </div>

                    {/* Chart Toolbar — z-20 so it sits above the chart canvas */}
                    <div className="h-12 border-b border-white/5 bg-gradient-to-r from-white/[0.03] to-transparent flex items-center px-5 gap-6 z-20 relative">

                        {/* Timeframe Selector */}
                        <div className="flex gap-1.5">
                            {TIMEFRAMES.map(tf => {
                                const isActiveTf = tf === activeTimeframe;
                                return (
                                    <button
                                        key={tf}
                                        onClick={() => handleTimeframeClick(tf)}
                                        className={`text-[11px] font-bold px-3 py-1.5 rounded-md transition-all ${isActiveTf
                                            ? 'bg-neon-cyan/15 text-neon-cyan border border-neon-cyan/40 shadow-[0_0_10px_rgba(0,229,255,0.2)]'
                                            : 'text-white/40 hover:text-white/90 hover:bg-white/5 border border-transparent'
                                            }`}
                                    >
                                        {tf}
                                    </button>
                                );
                            })}
                        </div>

                        <div className="h-4 w-px bg-white/10" />

                        {/* Active Symbol Display */}
                        <span className="text-xs font-bold text-white/60 tracking-widest">{activeSymbol}</span>

                        <div className="h-4 w-px bg-white/10" />

                        {/* Indicators Button */}
                        <div className="relative" ref={indicatorsPanelRef}>
                            <button
                                onClick={() => setShowIndicators(v => !v)}
                                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border transition-all ${showIndicators
                                    ? 'text-neon-cyan bg-neon-cyan/10 border-neon-cyan/30'
                                    : 'text-white/40 border-transparent hover:text-white/90 hover:bg-white/5'
                                    }`}
                            >
                                <BarChart2 size={14} />
                                <span>Indicadores</span>
                                {enabledCount > 0 && (
                                    <span className="bg-neon-cyan/20 text-neon-cyan text-[10px] font-bold px-1.5 py-0.5 rounded-full border border-neon-cyan/30">
                                        {enabledCount}
                                    </span>
                                )}
                            </button>

                            {/* Indicators Dropdown */}
                            <AnimatePresence>
                                {showIndicators && (
                                    <motion.div
                                        initial={{ opacity: 0, y: -8, scale: 0.97 }}
                                        animate={{ opacity: 1, y: 0, scale: 1 }}
                                        exit={{ opacity: 0, y: -8, scale: 0.97 }}
                                        transition={{ duration: 0.15 }}
                                        className="absolute top-full mt-2 left-0 w-64 bg-[#06101A]/95 backdrop-blur-2xl border border-white/10 rounded-xl shadow-2xl z-[200] overflow-hidden"
                                        onClick={e => e.stopPropagation()}
                                    >
                                        <div className="p-3 border-b border-white/5">
                                            <p className="text-[10px] text-white/40 font-bold tracking-widest">INDICADORES TÉCNICOS</p>
                                        </div>
                                        <div className="p-2 flex flex-col gap-1">
                                            {indicators.map(ind => (
                                                <button
                                                    key={ind.id}
                                                    onClick={() => toggleIndicator(ind.id)}
                                                    className={`flex items-center justify-between w-full px-3 py-2.5 rounded-lg transition-all text-left ${ind.enabled ? 'bg-white/5' : 'hover:bg-white/[0.03]'}`}
                                                >
                                                    <div className="flex items-center gap-3">
                                                        <div
                                                            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                                                            style={{ backgroundColor: ind.color, boxShadow: ind.enabled ? `0 0 6px ${ind.color}` : 'none' }}
                                                        />
                                                        <div>
                                                            <p className={`text-xs font-bold ${ind.enabled ? 'text-white/90' : 'text-white/30'}`}>{ind.label}</p>
                                                            <p className="text-[10px] text-white/25">{ind.sublabel}</p>
                                                        </div>
                                                    </div>
                                                    <div className={`w-8 h-4 rounded-full flex items-center px-0.5 transition-all duration-200 flex-shrink-0 ${ind.enabled ? 'bg-neon-green/20 border border-neon-green/30' : 'bg-black border border-white/10'}`}>
                                                        <motion.div
                                                            layout
                                                            className={`w-3 h-3 rounded-full ${ind.enabled ? 'bg-neon-green' : 'bg-white/20'}`}
                                                            animate={{ x: ind.enabled ? 14 : 0 }}
                                                            transition={{ type: "spring", stiffness: 500, damping: 30 }}
                                                        />
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    </div>


                    {/* Chart — z-0 so toolbar (z-20) always sits above the canvas */}
                    <div className="flex-1 w-full h-full relative z-0">
                        <TradingChart />
                    </div>
                </motion.section>

                {/* Right: AI Advisor */}
                <motion.section variants={itemVariants} className="col-span-3 flex flex-col gap-5 overflow-hidden">

                    <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] flex-1 flex flex-col overflow-hidden relative">
                        <div className="p-4 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-neon-cyan/10 to-transparent">
                            <div className="flex items-center gap-2.5">
                                <Terminal size={16} className="text-neon-cyan" />
                                <h2 className="text-xs font-bold text-white/90 tracking-widest drop-shadow-[0_0_8px_rgba(0,229,255,0.5)]">FLUJO NEURAL</h2>
                            </div>
                        </div>

                        <div className="p-5 flex flex-col gap-5 overflow-y-auto text-[11.5px] leading-relaxed font-mono">
                            {useTelemetryStore.getState().neuralLogs.length === 0 ? (
                                <div className="text-white/40 italic">Esperando inicialización del motor neural...</div>
                            ) : (
                                useTelemetryStore.getState().neuralLogs.map((log) => (
                                    <div
                                        key={log.id}
                                        className={`relative pl-4 ${log.type === 'ALERT' ? 'bg-neon-red/5 p-3 rounded-xl border border-neon-red/10' : ''}`}
                                    >
                                        <div className={`absolute left-0 top-${log.type === 'ALERT' ? '0' : '1.5'} bottom-0 w-${log.type === 'ALERT' ? '1' : '0.5'} ${log.type === 'ALERT' ? 'bg-neon-red rounded-l-xl shadow-[0_0_10px_rgba(255,0,60,0.5)]' :
                                            log.type === 'SYSTEM' ? 'bg-gradient-to-b from-blue-500 to-transparent' :
                                                'bg-gradient-to-b from-white/30 to-transparent'
                                            }`} />

                                        <span className={`block mb-1 font-${log.type === 'ALERT' ? 'bold' : 'semibold'} flex items-center gap-2 ${log.type === 'ALERT' ? 'text-neon-red' :
                                            log.type === 'SYSTEM' ? 'text-blue-400' :
                                                'text-white/40'
                                            }`}>
                                            [{log.timestamp}] <ChevronRight size={12} /> {log.type}
                                        </span>
                                        <span className={`${log.type === 'ALERT' ? 'text-white/90 font-medium' : 'text-white/60'}`}>
                                            {log.message}
                                        </span>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* ML Projection */}
                    <div className="h-36 bg-gradient-to-br from-[#050B14] to-black backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl flex flex-col justify-between p-5 relative overflow-hidden">
                        <div className={`absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(${mlProjection.direction === 'ALCISTA' ? '0,255,65' : '255,0,60'},0.1),transparent_50%)] pointer-events-none transition-colors duration-1000`} />

                        <div className="flex justify-between items-start z-10">
                            <p className="text-[10px] text-white/50 tracking-[0.2em] font-bold">PROYECCIÓN IA (XGBOOST)</p>
                            <Activity size={14} className={`${mlProjection.direction === 'ALCISTA' ? 'text-neon-green' : 'text-neon-red'} opacity-50`} />
                        </div>

                        <div className="z-10">
                            <div className="flex items-baseline gap-3">
                                <span className={`text-4xl font-black ${mlProjection.direction === 'ALCISTA' ? 'text-neon-green drop-shadow-[0_0_15px_rgba(0,255,65,0.5)]' : 'text-neon-red drop-shadow-[0_0_15px_rgba(255,0,60,0.5)]'} tracking-tighter`}>
                                    {mlProjection.probability}%
                                </span>
                                <span className={`text-xs ${mlProjection.direction === 'ALCISTA' ? 'text-neon-green/80' : 'text-neon-red/80'} font-semibold tracking-wider`}>
                                    {mlProjection.direction} ({activeTimeframe})
                                </span>
                            </div>
                            <div className="h-2 w-full bg-black rounded-full mt-4 overflow-hidden border border-white/5">
                                <motion.div
                                    animate={{ width: `${mlProjection.probability}%` }}
                                    transition={{ duration: 1.5, ease: [0.16, 1, 0.3, 1] }}
                                    className={`h-full bg-gradient-to-r ${mlProjection.direction === 'ALCISTA' ? 'from-green-600 to-neon-green shadow-[0_0_15px_rgba(0,255,65,0.8)]' : 'from-red-600 to-neon-red shadow-[0_0_15px_rgba(255,0,60,0.8)]'} relative`}
                                >
                                    <div className="absolute top-0 right-0 bottom-0 w-4 bg-white/30 rounded-full blur-[2px]" />
                                </motion.div>
                            </div>
                        </div>
                    </div>

                </motion.section>
            </motion.main>
        </div>
    );
}

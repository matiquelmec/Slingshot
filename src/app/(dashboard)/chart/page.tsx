'use client';

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    BarChart2,
    ChevronDown,
    Maximize2,
    Minimize2,
    RotateCcw,
    Search,
    Sparkles,
} from 'lucide-react';
import dynamic from 'next/dynamic';
import {
    useTelemetryStore,
    Timeframe,
    MASTER_WATCHLIST,
    getAssetExecutionBadge,
} from '../../store/telemetryStore';
import {
    useIndicatorsStore,
    CHART_PRESETS,
    ChartPresetId,
    IndicatorCategory,
} from '../../store/indicatorsStore';
import { formatPrice } from '@/shared';

const TradingChart = dynamic(() => import('../../components/ui/TradingChart'), { ssr: false });

const TIMEFRAMES: Timeframe[] = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '8h', '1d', '1w', '1M'];
const PRIMARY_TIMEFRAMES = new Set<Timeframe>(['15m', '1h', '4h', '1d']);

const CATEGORY_META: Record<IndicatorCategory, { title: string }> = {
    SSOT_CORE: { title: 'TENDENCIA & EJECUCIÓN SSoT' },
    STRUCTURE: { title: 'ESTRUCTURA SMC & SESIONES' },
    LIQUIDITY: { title: 'LIQUIDEZ & MICROESTRUCTURA' },
};

const PRESET_ORDER: ChartPresetId[] = ['CLEAN', 'SSOT_STRATEGY', 'LIQUIDITY_FLOW', 'FULL_AUDIT'];

export default function ChartPage() {
    const [mounted, setMounted] = useState(false);
    const [showIndicators, setShowIndicators] = useState(false);
    const [showSymbolMenu, setShowSymbolMenu] = useState(false);
    const [symbolQuery, setSymbolQuery] = useState('');
    const [isLogScale, setIsLogScale] = useState(false);
    const [isAutoScale, setIsAutoScale] = useState(true);
    const [fitTrigger, setFitTrigger] = useState(0);
    const [isFullscreen, setIsFullscreen] = useState(false);

    const { indicators, activePreset, hydrate, toggleIndicator, applyPreset } = useIndicatorsStore();
    const indicatorsPanelRef = useRef<HTMLDivElement>(null);
    const symbolPanelRef = useRef<HTMLDivElement>(null);
    const chartRootRef = useRef<HTMLDivElement>(null);

    const {
        activeSymbol,
        activeTimeframe,
        setTimeframe,
        connect,
        marketSummary,
        latestPrices,
        latestPrice,
    } = useTelemetryStore();

    useEffect(() => {
        setMounted(true);
        hydrate();
    }, [hydrate]);

    // Close popovers on outside click
    useEffect(() => {
        if (!showIndicators && !showSymbolMenu) return;
        const handler = (e: MouseEvent) => {
            const target = e.target as Node;
            if (showIndicators && indicatorsPanelRef.current && !indicatorsPanelRef.current.contains(target)) {
                setShowIndicators(false);
            }
            if (showSymbolMenu && symbolPanelRef.current && !symbolPanelRef.current.contains(target)) {
                setShowSymbolMenu(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [showIndicators, showSymbolMenu]);

    // Sync fullscreen state with browser API
    useEffect(() => {
        const onFsChange = () => {
            setIsFullscreen(Boolean(document.fullscreenElement));
        };
        document.addEventListener('fullscreenchange', onFsChange);
        return () => document.removeEventListener('fullscreenchange', onFsChange);
    }, []);

    const handleToggleFullscreen = useCallback(async () => {
        try {
            if (!document.fullscreenElement && chartRootRef.current) {
                await chartRootRef.current.requestFullscreen();
            } else if (document.fullscreenElement) {
                await document.exitFullscreen();
            }
        } catch {
            // Ignore browser fullscreen restrictions
        }
    }, []);

    const handleFitContent = useCallback(() => {
        setFitTrigger((n) => n + 1);
    }, []);

    const handleSelectSymbol = useCallback(
        (symbol: string) => {
            if (symbol !== activeSymbol) {
                connect(symbol, activeTimeframe);
            }
            setShowSymbolMenu(false);
            setSymbolQuery('');
        },
        [activeSymbol, activeTimeframe, connect]
    );

    // Keyboard shortcuts: [ / ] cycle canonical symbol, R fit zoom, F fullscreen
    useEffect(() => {
        const onKeyDown = (e: KeyboardEvent) => {
            const tag = (e.target as HTMLElement | null)?.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.ctrlKey || e.metaKey || e.altKey) {
                return;
            }
            if (e.key === '[' || e.key === ']') {
                const idx = MASTER_WATCHLIST.indexOf(activeSymbol);
                const safeIdx = idx === -1 ? 0 : idx;
                const nextIdx =
                    e.key === ']'
                        ? (safeIdx + 1) % MASTER_WATCHLIST.length
                        : (safeIdx - 1 + MASTER_WATCHLIST.length) % MASTER_WATCHLIST.length;
                connect(MASTER_WATCHLIST[nextIdx], activeTimeframe);
            } else if (e.key === 'r' || e.key === 'R') {
                handleFitContent();
            } else if (e.key === 'f' || e.key === 'F') {
                handleToggleFullscreen();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [activeSymbol, activeTimeframe, connect, handleFitContent, handleToggleFullscreen]);

    const filteredSymbols = useMemo(() => {
        const q = symbolQuery.trim().toUpperCase();
        if (!q) return MASTER_WATCHLIST;
        return MASTER_WATCHLIST.filter((s) => s.includes(q));
    }, [symbolQuery]);

    const groupedIndicators = useMemo(() => {
        return (['SSOT_CORE', 'STRUCTURE', 'LIQUIDITY'] as IndicatorCategory[]).map((category) => ({
            category,
            title: CATEGORY_META[category].title,
            items: indicators.filter((ind) => ind.category === category),
        }));
    }, [indicators]);

    if (!mounted) return null;

    const handleTimeframeClick = (tf: Timeframe) => {
        if (tf !== activeTimeframe) setTimeframe(tf);
    };

    const enabledCount = indicators.filter((i) => i.enabled).length;
    const activeBadge = getAssetExecutionBadge(activeSymbol || 'BTCUSDT');
    const displayPrice = latestPrice ?? latestPrices?.[activeSymbol] ?? marketSummary?.[activeSymbol]?.price ?? null;

    return (
        <div
            ref={chartRootRef}
            className="h-full w-full bg-[#010204]/90 backdrop-blur-3xl rounded-2xl border border-white/10 relative flex flex-col overflow-hidden shadow-[inset_0_0_100px_rgba(0,0,0,1)]"
        >
            {/* Watermark */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none overflow-hidden">
                <span className="text-[10rem] md:text-[12rem] font-black text-white/[0.015] tracking-tighter transform rotate-12 scale-150">
                    SLINGSHOT
                </span>
            </div>

            {/* Institutional Chart Toolbar (8-Point Grid, >= 44px touch targets) */}
            <div className="min-h-[56px] border-b border-white/10 bg-gradient-to-r from-white/[0.04] to-transparent flex flex-wrap md:flex-nowrap items-center px-2 md:px-4 py-2 gap-2 md:gap-4 z-30 relative">
                {/* Canonical 13-Asset Symbol Selector */}
                <div className="relative shrink-0" ref={symbolPanelRef}>
                    <button
                        type="button"
                        onClick={() => {
                            setShowSymbolMenu((v) => !v);
                            setShowIndicators(false);
                        }}
                        aria-haspopup="listbox"
                        aria-expanded={showSymbolMenu}
                        aria-label="Seleccionar par canónico"
                        className="min-h-[44px] px-3 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/15 hover:border-neon-cyan/40 flex items-center gap-2 transition-all cursor-pointer"
                    >
                        <div className="flex flex-col items-start text-left">
                            <div className="flex items-center gap-2">
                                <span className="text-xs font-black text-white font-mono tracking-wider">
                                    {activeSymbol || 'BTCUSDT'}
                                </span>
                                <span
                                    className={`text-[9px] font-bold font-mono px-1.5 py-0.5 rounded border ${
                                        activeBadge.isExecutable
                                            ? 'text-neon-cyan bg-neon-cyan/15 border-neon-cyan/40'
                                            : 'text-slate-300 bg-white/10 border-white/20'
                                    }`}
                                >
                                    {activeBadge.label}
                                </span>
                            </div>
                            <span className="text-[11px] font-mono text-slate-300 leading-tight">
                                {displayPrice != null ? `$${formatPrice(displayPrice)}` : 'Sincronizando...'}
                            </span>
                        </div>
                        <ChevronDown
                            size={16}
                            className={`text-slate-300 transition-transform ${showSymbolMenu ? 'rotate-180 text-neon-cyan' : ''}`}
                        />
                    </button>

                    <AnimatePresence>
                        {showSymbolMenu && (
                            <motion.div
                                initial={{ opacity: 0, y: -8, scale: 0.98 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: -8, scale: 0.98 }}
                                transition={{ duration: 0.14 }}
                                className="absolute top-full mt-2 left-0 w-72 sm:w-80 bg-[#06101A]/98 backdrop-blur-2xl border border-white/15 rounded-xl shadow-2xl z-[220] overflow-hidden"
                            >
                                <div className="p-2 border-b border-white/10">
                                    <div className="relative flex items-center">
                                        <Search size={14} className="absolute left-3 text-slate-400 pointer-events-none" />
                                        <input
                                            type="text"
                                            value={symbolQuery}
                                            onChange={(e) => setSymbolQuery(e.target.value)}
                                            placeholder="Buscar en 13 pares canónicos..."
                                            className="w-full min-h-[44px] pl-9 pr-3 rounded-lg bg-black/50 border border-white/10 text-xs text-white placeholder:text-slate-400 focus:outline-none focus:border-neon-cyan/50 font-mono"
                                            autoFocus
                                        />
                                    </div>
                                </div>
                                <div className="max-h-72 overflow-y-auto p-2 flex flex-col gap-1" role="listbox">
                                    {filteredSymbols.map((sym) => {
                                        const isCurrent = sym === activeSymbol;
                                        const badge = getAssetExecutionBadge(sym);
                                        const summary = marketSummary?.[sym];
                                        const symPrice = latestPrices?.[sym] ?? summary?.price ?? null;
                                        return (
                                            <button
                                                key={sym}
                                                type="button"
                                                role="option"
                                                aria-selected={isCurrent}
                                                onClick={() => handleSelectSymbol(sym)}
                                                className={`min-h-[44px] w-full px-3 py-2 rounded-lg flex items-center justify-between transition-all cursor-pointer ${
                                                    isCurrent
                                                        ? 'bg-neon-cyan/15 border border-neon-cyan/40'
                                                        : 'hover:bg-white/[0.06] border border-transparent'
                                                }`}
                                            >
                                                <div className="flex flex-col items-start">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-xs font-bold font-mono text-white">{sym}</span>
                                                        <span
                                                            className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                                                                badge.isExecutable
                                                                    ? 'bg-neon-cyan/15 text-neon-cyan'
                                                                    : 'bg-white/10 text-slate-300'
                                                            }`}
                                                        >
                                                            {badge.label}
                                                        </span>
                                                    </div>
                                                    <span className="text-[10px] text-slate-400 font-mono">
                                                        {summary?.regime || 'UNIVERSO CANÓNICO'}
                                                    </span>
                                                </div>
                                                <span className="text-xs font-mono font-semibold text-slate-200">
                                                    {symPrice != null ? `$${formatPrice(symPrice)}` : '—'}
                                                </span>
                                            </button>
                                        );
                                    })}
                                    {filteredSymbols.length === 0 && (
                                        <p className="text-xs text-slate-400 text-center py-4 font-mono">
                                            Sin coincidencias en Universo Canónico
                                        </p>
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                <div className="hidden md:block h-6 w-px bg-white/10 shrink-0" />

                {/* Timeframe Selector */}
                <div className="flex items-center gap-1 min-w-0 flex-1 overflow-x-auto no-scrollbar">
                    {TIMEFRAMES.map((tf) => {
                        const isActiveTf = tf === activeTimeframe;
                        const isPrimary = PRIMARY_TIMEFRAMES.has(tf);
                        return (
                            <button
                                key={tf}
                                type="button"
                                onClick={() => handleTimeframeClick(tf)}
                                className={`min-h-[44px] md:min-h-[36px] min-w-[40px] px-2.5 rounded-lg text-xs font-mono font-bold transition-all shrink-0 flex items-center justify-center gap-1 cursor-pointer ${
                                    isActiveTf
                                        ? 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/50 shadow-[0_0_10px_rgba(0,229,255,0.2)]'
                                        : isPrimary
                                            ? 'text-slate-200 hover:text-white hover:bg-white/10 border border-white/10'
                                            : 'text-slate-400 hover:text-slate-100 hover:bg-white/5 border border-transparent'
                                }`}
                            >
                                {tf}
                            </button>
                        );
                    })}
                </div>

                <div className="hidden md:block h-6 w-px bg-white/10 shrink-0" />

                {/* Indicators & Presets Dropdown */}
                <div className="relative shrink-0" ref={indicatorsPanelRef}>
                    <button
                        type="button"
                        onClick={() => {
                            setShowIndicators((v) => !v);
                            setShowSymbolMenu(false);
                        }}
                        aria-expanded={showIndicators}
                        className={`min-h-[44px] md:min-h-[36px] px-3 rounded-lg border text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer ${
                            showIndicators
                                ? 'text-neon-cyan bg-neon-cyan/15 border-neon-cyan/40'
                                : 'text-slate-200 bg-white/[0.03] border-white/10 hover:text-white hover:bg-white/10'
                        }`}
                    >
                        <BarChart2 size={15} />
                        <span>Indicadores</span>
                        <span className="bg-neon-cyan/20 text-neon-cyan text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-full border border-neon-cyan/30">
                            {enabledCount}
                        </span>
                    </button>

                    <AnimatePresence>
                        {showIndicators && (
                            <motion.div
                                initial={{ opacity: 0, y: -8, scale: 0.98 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: -8, scale: 0.98 }}
                                transition={{ duration: 0.14 }}
                                className="absolute top-full mt-2 right-0 w-80 sm:w-96 bg-[#06101A]/98 backdrop-blur-2xl border border-white/15 rounded-xl shadow-2xl z-[220] overflow-hidden"
                            >
                                {/* 1-Click Presets */}
                                <div className="p-3 border-b border-white/10 bg-white/[0.02]">
                                    <div className="flex items-center gap-1.5 mb-2">
                                        <Sparkles size={13} className="text-neon-cyan" />
                                        <p className="text-[11px] text-slate-200 font-bold tracking-wider uppercase">
                                            Presets Institucionales
                                        </p>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2">
                                        {PRESET_ORDER.map((presetId) => {
                                            const preset = CHART_PRESETS[presetId];
                                            const isSelected = activePreset === presetId;
                                            return (
                                                <button
                                                    key={presetId}
                                                    type="button"
                                                    onClick={() => applyPreset(presetId)}
                                                    className={`min-h-[44px] px-2.5 py-1.5 rounded-lg text-left border transition-all cursor-pointer ${
                                                        isSelected
                                                            ? 'bg-neon-cyan/15 border-neon-cyan/50 text-neon-cyan'
                                                            : 'bg-black/40 border-white/10 text-slate-200 hover:bg-white/10'
                                                    }`}
                                                >
                                                    <p className="text-xs font-bold leading-tight">{preset.label}</p>
                                                    <p className="text-[10px] text-slate-400 truncate">{preset.description}</p>
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>

                                {/* Categorized Indicator Toggles */}
                                <div className="max-h-80 overflow-y-auto p-2 flex flex-col gap-3">
                                    {groupedIndicators.map((group) => (
                                        <div key={group.category} className="flex flex-col gap-1">
                                            <p className="px-2 text-[10px] font-bold tracking-widest text-slate-400">
                                                {group.title}
                                            </p>
                                            {group.items.map((ind) => (
                                                <button
                                                    key={ind.id}
                                                    type="button"
                                                    onClick={() => toggleIndicator(ind.id)}
                                                    className={`min-h-[44px] flex items-center justify-between w-full px-3 py-2 rounded-lg transition-all text-left cursor-pointer ${
                                                        ind.enabled
                                                            ? 'bg-white/[0.07] border border-white/10'
                                                            : 'hover:bg-white/[0.04] border border-transparent'
                                                    }`}
                                                >
                                                    <div className="flex items-center gap-3 min-w-0">
                                                        <div
                                                            className="w-2.5 h-2.5 rounded-full shrink-0"
                                                            style={{
                                                                backgroundColor: ind.color,
                                                                boxShadow: ind.enabled ? `0 0 8px ${ind.color}` : 'none',
                                                            }}
                                                        />
                                                        <div className="min-w-0">
                                                            <p
                                                                className={`text-xs font-bold truncate ${
                                                                    ind.enabled ? 'text-white' : 'text-slate-300'
                                                                }`}
                                                            >
                                                                {ind.label}
                                                            </p>
                                                            <p className="text-[10px] text-slate-400 truncate">{ind.sublabel}</p>
                                                        </div>
                                                    </div>
                                                    <div
                                                        className={`w-9 h-5 rounded-full flex items-center px-0.5 transition-all duration-200 shrink-0 ${
                                                            ind.enabled
                                                                ? 'bg-neon-green/25 border border-neon-green/50'
                                                                : 'bg-black/70 border border-white/20'
                                                        }`}
                                                    >
                                                        <motion.div
                                                            layout
                                                            className={`w-3.5 h-3.5 rounded-full ${
                                                                ind.enabled ? 'bg-neon-green' : 'bg-slate-400'
                                                            }`}
                                                            animate={{ x: ind.enabled ? 16 : 0 }}
                                                            transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                                                        />
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    ))}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Scale & View Controls */}
                <div className="flex items-center gap-2 shrink-0">
                    <button
                        type="button"
                        onClick={() => setIsLogScale((v) => !v)}
                        title="Alternar escala logarítmica"
                        className={`min-h-[44px] md:min-h-[36px] min-w-[44px] px-2.5 rounded-lg text-[11px] font-mono font-bold border transition-all cursor-pointer ${
                            isLogScale
                                ? 'bg-neon-cyan/20 text-neon-cyan border-neon-cyan/50'
                                : 'bg-white/[0.03] text-slate-300 border-white/10 hover:text-white hover:bg-white/10'
                        }`}
                    >
                        LOG
                    </button>
                    <button
                        type="button"
                        onClick={() => setIsAutoScale((v) => !v)}
                        title="Alternar auto-escala vertical"
                        className={`min-h-[44px] md:min-h-[36px] min-w-[44px] px-2.5 rounded-lg text-[11px] font-mono font-bold border transition-all cursor-pointer ${
                            isAutoScale
                                ? 'bg-neon-cyan/20 text-neon-cyan border-neon-cyan/50'
                                : 'bg-white/[0.03] text-slate-300 border-white/10 hover:text-white hover:bg-white/10'
                        }`}
                    >
                        AUTO
                    </button>
                    <button
                        type="button"
                        onClick={handleFitContent}
                        title="Encuadrar gráfico (Atajo: R)"
                        aria-label="Encuadrar gráfico"
                        className="min-h-[44px] md:min-h-[36px] min-w-[44px] md:min-w-[36px] rounded-lg bg-white/[0.03] text-slate-200 border border-white/10 hover:text-white hover:bg-white/10 flex items-center justify-center transition-all cursor-pointer"
                    >
                        <RotateCcw size={15} />
                    </button>
                    <button
                        type="button"
                        onClick={handleToggleFullscreen}
                        title="Pantalla completa (Atajo: F)"
                        aria-label="Pantalla completa"
                        className="min-h-[44px] md:min-h-[36px] min-w-[44px] md:min-w-[36px] rounded-lg bg-white/[0.03] text-slate-200 border border-white/10 hover:text-white hover:bg-white/10 flex items-center justify-center transition-all cursor-pointer"
                    >
                        {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                    </button>
                </div>
            </div>

            {/* Chart Area */}
            <div className="flex-1 w-full relative z-0 min-h-0">
                <TradingChart
                    isLogScale={isLogScale}
                    isAutoScale={isAutoScale}
                    fitTrigger={fitTrigger}
                />
            </div>
        </div>
    );
}

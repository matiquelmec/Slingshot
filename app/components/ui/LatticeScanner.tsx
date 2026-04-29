'use client';

import React, { useState, useMemo, useRef } from 'react';
import { motion } from 'framer-motion';
import { Activity, Zap, ShieldCheck, Search } from 'lucide-react';
import { useTelemetryStore, MASTER_WATCHLIST } from '../../store/telemetryStore';
import { formatCurrency } from '../../utils/formatters';

const ROW_HEIGHT = 44;
const VISIBLE_ROWS = 12;

export default function LatticeScanner() {
    const marketSummary = useTelemetryStore((state) => state.marketSummary);
    const activeSymbol = useTelemetryStore((state) => state.activeSymbol);
    const activeTimeframe = useTelemetryStore((state) => state.activeTimeframe);
    const connect = useTelemetryStore((state) => state.connect);
    const [filter, setFilter] = useState('');
    const [scrollTop, setScrollTop] = useState(0);
    const containerRef = useRef<HTMLDivElement>(null);

    // Construir lista de pares reales desde el marketSummary del backend
    const pairs = useMemo(() => {
        const entries = { ...marketSummary };
        
        // 🛡️ OMEGA STABILITY: Asegurar que los Master siempre existan en el mapa visual
        MASTER_WATCHLIST.forEach(symbol => {
            if (!entries[symbol]) {
                entries[symbol] = { asset: symbol, price: 0, regime: 'SYNCING...', strategy: 'STANDBY', bias: 'NEUTRAL', trend: 0 };
            }
        });

        return Object.values(entries)
            .filter(p => p.asset && p.asset.endsWith('USDT'))
            .sort((a, b) => {
                // Prioridad 1: Master Watchlist al principio (Orden Estricto según MASTER_WATCHLIST)
                const indexA = MASTER_WATCHLIST.indexOf(a.asset);
                const indexB = MASTER_WATCHLIST.indexOf(b.asset);
                
                if (indexA !== -1 && indexB !== -1) return indexA - indexB;
                if (indexA !== -1) return -1;
                if (indexB !== -1) return 1;
                
                // Prioridad 2: Orden por precio para el resto
                return (b.price || 0) - (a.price || 0);
            });
    }, [marketSummary]);

    // Filtrar por búsqueda
    const filteredPairs = useMemo(() => {
        if (!filter.trim()) return pairs;
        const term = filter.toUpperCase();
        return pairs.filter(p => p.asset.includes(term));
    }, [pairs, filter]);

    const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
        setScrollTop(e.currentTarget.scrollTop);
    };

    const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT));
    const endIndex = Math.min(filteredPairs.length, startIndex + VISIBLE_ROWS + 5);
    const visiblePairs = filteredPairs.slice(startIndex, endIndex);

    const handlePairClick = (asset: string) => {
        connect(asset, activeTimeframe);
    };

    return (
        <div className="bg-[#05111B]/40 backdrop-blur-xl border border-white/5 rounded-2xl flex flex-col h-full overflow-hidden">
            {/* Header Scanner */}
            <div className="p-3 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
                <div className="flex items-center gap-2">
                    <Activity size={14} className="text-neon-cyan animate-pulse" />
                    <h2 className="text-[10px] font-black tracking-[0.15em] text-white">LATTICE SCANNER</h2>
                    <span className="text-[8px] font-bold text-white/20 bg-white/5 px-1.5 py-0.5 rounded">
                        {pairs.length} PARES
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[8px] font-bold text-neon-cyan/40 tracking-widest">LIVE</span>
                </div>
            </div>

            {/* Search Bar */}
            <div className="px-3 py-2 border-b border-white/5">
                <div className="relative">
                    <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-white/20" />
                    <input
                        placeholder="Buscar par..."
                        className="w-full bg-white/[0.03] border border-white/5 rounded-lg py-1.5 pl-8 pr-3 text-[9px] font-mono font-bold text-white/70 focus:border-neon-cyan/30 outline-none transition-all uppercase placeholder:normal-case placeholder:text-white/15"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                    />
                </div>
            </div>

            {/* List Header */}
            <div className="grid grid-cols-12 px-4 py-1.5 border-b border-white/5 text-[7px] font-black text-white/15 tracking-wider uppercase">
                <div className="col-span-4">SÍMBOLO</div>
                <div className="col-span-3 text-center">RÉGIMEN</div>
                <div className="col-span-2 text-center">SESGO</div>
                <div className="col-span-3 text-right">PRECIO</div>
            </div>

            {/* Virtualized Container */}
            {pairs.length === 0 ? (
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                        <Activity size={24} className="text-white/10 mx-auto mb-2 animate-pulse" />
                        <p className="text-[9px] text-white/20 font-bold tracking-widest">SINCRONIZANDO BROADCASTERS...</p>
                        <p className="text-[8px] text-white/10 mt-1">Los pares se cargan automáticamente</p>
                    </div>
                </div>
            ) : (
                <div 
                    ref={containerRef}
                    onScroll={handleScroll}
                    className="flex-1 overflow-y-auto custom-scrollbar relative"
                >
                    <div style={{ height: filteredPairs.length * ROW_HEIGHT }} className="relative w-full">
                        {visiblePairs.map((pair, idx) => {
                            const actualIndex = startIndex + idx;
                            const isActive = pair.asset === activeSymbol;
                            const biasColor = pair.bias === 'BULLISH' ? 'text-neon-green' 
                                : pair.bias === 'BEARISH' ? 'text-neon-red' : 'text-white/30';
                            const regimeColor = pair.regime === 'MARKUP' || pair.regime === 'ACCUMULATION' 
                                ? 'text-neon-green/70' 
                                : pair.regime === 'MARKDOWN' || pair.regime === 'DISTRIBUTION' 
                                    ? 'text-neon-red/70' 
                                    : pair.regime === 'CHOPPY' ? 'text-purple-400/70' : 'text-white/30';

                            return (
                                <div 
                                    key={pair.asset}
                                    onClick={() => handlePairClick(pair.asset)}
                                    className={`absolute left-0 w-full grid grid-cols-12 px-4 items-center cursor-pointer transition-all duration-150 ${
                                        isActive 
                                            ? 'bg-neon-cyan/10 border-l-2 border-neon-cyan' 
                                            : 'border-b border-white/[0.02] hover:bg-white/[0.04]'
                                    }`}
                                    style={{ 
                                        height: ROW_HEIGHT, 
                                        top: actualIndex * ROW_HEIGHT,
                                    }}
                                >
                                    {/* Symbol */}
                                    <div className="col-span-4 flex items-center gap-1.5">
                                        <span className={`text-[10px] font-black font-mono ${isActive ? 'text-neon-cyan' : 'text-white/60'}`}>
                                            {pair.asset.replace('USDT', '')}
                                        </span>
                                        <span className="text-[7px] text-white/15 font-bold">/USDT</span>
                                    </div>

                                    {/* Regime */}
                                    <div className="col-span-3 flex items-center justify-center">
                                        <span className={`text-[8px] font-bold tracking-wider ${regimeColor}`}>
                                            {pair.regime || '—'}
                                        </span>
                                    </div>

                                    {/* Bias */}
                                    <div className="col-span-2 flex items-center justify-center gap-1">
                                        <span className={`w-1 h-1 rounded-full ${pair.bias === 'BULLISH' ? 'bg-neon-green' : pair.bias === 'BEARISH' ? 'bg-neon-red' : 'bg-white/20'}`} />
                                        <span className={`text-[8px] font-bold ${biasColor}`}>
                                            {pair.bias?.slice(0, 4) || '—'}
                                        </span>
                                    </div>

                                    {/* Price */}
                                    <div className="col-span-3 text-right">
                                        <span className="text-[10px] font-black font-mono text-white/70">
                                            {formatCurrency(pair.price)}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Footer */}
            <div className="px-3 py-1.5 border-t border-white/5 bg-black/20 flex items-center justify-between">
                <div className="flex items-center gap-3 text-[7px] font-black text-white/15 tracking-widest uppercase">
                    <div className="flex items-center gap-1">
                        <div className="w-1 h-1 rounded-full bg-neon-green" />
                        <span>SMC</span>
                    </div>
                    <div className="flex items-center gap-1">
                        <div className="w-1 h-1 rounded-full bg-neon-cyan shadow-[0_0_4px_cyan]" />
                        <span>C++ BRIDGE</span>
                    </div>
                </div>
                <div className="flex items-center gap-1 text-[7px] font-black text-white/20 tracking-widest uppercase">
                    <ShieldCheck size={8} className="text-neon-green/50" />
                    <span>RISK: LOCKED</span>
                </div>
            </div>
        </div>
    );
}

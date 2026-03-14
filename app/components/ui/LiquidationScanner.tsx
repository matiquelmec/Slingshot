'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Skull, TrendingDown, TrendingUp, Info } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';

export default function LiquidationScanner() {
    const { liquidations, latestPrice } = useTelemetryStore();

    if (!latestPrice) return null;

    // Clasificar liquidaciones por tipo
    const shortLiqs = liquidations
        .filter(l => l.type === 'SHORT_LIQ')
        .sort((a, b) => a.price - b.price); // De más cercana a más lejana (arriba)

    const longLiqs = liquidations
        .filter(l => l.type === 'LONG_LIQ')
        .sort((a, b) => b.price - a.price); // De más cercana a más lejana (abajo)

    return (
        <div className="flex flex-col h-full overflow-hidden bg-black/20">
            <div className="p-4 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-neon-red/10 to-transparent">
                <div className="flex items-center gap-2.5">
                    <Skull size={16} className="text-neon-red" />
                    <h2 className="text-xs font-bold text-white/90 tracking-widest drop-shadow-[0_0_8px_rgba(255,0,60,0.5)]">ESCÁNER DE LIQUIDACIONES</h2>
                </div>
                <div className="group relative">
                    <Info size={12} className="text-white/20 hover:text-white/60 cursor-help" />
                    <div className="absolute right-0 top-6 w-48 p-2 bg-black/90 border border-white/10 rounded-lg text-[9px] text-white/60 leading-tight opacity-0 group-hover:opacity-100 transition-opacity z-50 pointer-events-none">
                        Zonas de "Safe Stops" y alta liquidez donde el mercado suele buscar "combustible" para reversiones.
                    </div>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-4">
                {/* SHORT LIQUIDATIONS (SELL STOPS / BUY LIQS) - ARRIBA DEL PRECIO */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2 px-1">
                        <TrendingUp size={12} className="text-neon-cyan" />
                        <span className="text-[9px] font-black text-neon-cyan/80 tracking-widest uppercase">Magnetismo Superior (Shorts)</span>
                    </div>
                    <div className="space-y-1.5">
                        <AnimatePresence initial={false}>
                            {shortLiqs.length > 0 ? (
                                shortLiqs.slice(0, 5).map((liq, idx) => (
                                    <LiquidationRow key={`short-${idx}`} liq={liq} currentPrice={latestPrice} />
                                ))
                            ) : (
                                <p className="text-[10px] text-white/10 italic text-center py-2">Sin clusters detectados...</p>
                            )}
                        </AnimatePresence>
                    </div>
                </div>

                {/* CURRENT PRICE DIVIDER */}
                <div className="relative py-2 flex items-center justify-center">
                    <div className="absolute inset-0 flex items-center">
                        <div className="w-full border-t border-white/5 border-dashed" />
                    </div>
                    <div className="relative bg-[#0A0F1D] px-3 py-1 rounded-full border border-white/10">
                        <span className="text-[10px] font-mono font-bold text-white/60">
                            ${latestPrice.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </span>
                    </div>
                </div>

                {/* LONG LIQUIDATIONS (BUY STOPS / SELL LIQS) - ABAJO DEL PRECIO */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2 px-1">
                        <TrendingDown size={12} className="text-neon-purple" />
                        <span className="text-[9px] font-black text-neon-purple/80 tracking-widest uppercase">Magnetismo Inferior (Longs)</span>
                    </div>
                    <div className="space-y-1.5">
                        <AnimatePresence initial={false}>
                            {longLiqs.length > 0 ? (
                                longLiqs.slice(0, 5).map((liq, idx) => (
                                    <LiquidationRow key={`long-${idx}`} liq={liq} currentPrice={latestPrice} />
                                ))
                            ) : (
                                <p className="text-[10px] text-white/10 italic text-center py-2">Sin clusters detectados...</p>
                            )}
                        </AnimatePresence>
                    </div>
                </div>
            </div>
            
            <div className="p-2 border-t border-white/5 bg-black/40">
                <div className="flex justify-between items-center text-[8px] font-mono text-white/20 uppercase tracking-tighter">
                    <span>Inferencia: Estructural</span>
                    <span>Tolerancia: 0.15%</span>
                </div>
            </div>
        </div>
    );
}

function LiquidationRow({ liq, currentPrice }: { liq: any, currentPrice: number }) {
    const dist = ((liq.price - currentPrice) / currentPrice) * 100;
    const isAbove = liq.type === 'SHORT_LIQ';
    
    return (
        <motion.div
            initial={{ opacity: 0, x: isAbove ? 10 : -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="relative group h-9 flex items-center bg-white/[0.02] hover:bg-white/[0.05] border border-white/5 rounded-lg transition-all overflow-hidden"
        >
            {/* Intensity Bar Overlay */}
            <div 
                className={`absolute inset-y-0 left-0 ${isAbove ? 'bg-neon-cyan/10' : 'bg-neon-purple/10'} transition-all duration-1000`}
                style={{ width: `${liq.strength}%` }}
            />
            
            <div className="relative z-10 w-full flex items-center justify-between px-3">
                <div className="flex flex-col">
                    <span className={`text-[11px] font-mono font-black ${isAbove ? 'text-neon-cyan' : 'text-neon-purple'}`}>
                        ${liq.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                    <span className="text-[8px] text-white/30 font-bold">
                        MODO: {liq.leverage}x
                    </span>
                </div>
                
                <div className="text-right flex flex-col items-end">
                    <span className={`text-[9px] font-bold ${Math.abs(dist) < 0.5 ? 'text-white animate-pulse' : 'text-white/40'}`}>
                        {dist > 0 ? '+' : ''}{dist.toFixed(2)}%
                    </span>
                    <div className="flex gap-0.5 mt-0.5">
                        {[...Array(5)].map((_, i) => (
                            <div 
                                key={i} 
                                className={`w-1 h-1 rounded-full ${i < (liq.strength / 20) ? (isAbove ? 'bg-neon-cyan/50' : 'bg-neon-purple/50') : 'bg-white/5'}`} 
                            />
                        ))}
                    </div>
                </div>
            </div>
            
            {/* Hover Glow */}
            <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-r from-transparent ${isAbove ? 'via-neon-cyan/5' : 'via-neon-purple/5'} to-transparent`} />
        </motion.div>
    );
}

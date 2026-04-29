'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, ShieldAlert, Crosshair, StopCircle, Lock, ServerCog, Activity, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';
import { formatCurrency, formatPrice } from '../../utils/formatters';

export default function OmegaCentinelPanel() {
    // Estado simulado para la integración posterior con WebSocket OMEGA
    const [isShieldLocked, setIsShieldLocked] = useState(false);
    const [dailyDrawdown, setDailyDrawdown] = useState(0.00); // 0%
    const maxDrawdown = -3.50;

    const activeSymbol = useTelemetryStore(state => state.activeSymbol);
    const latestPrices = useTelemetryStore(state => state.latestPrices);
    const signalHistory = useTelemetryStore(state => state.signalHistory);
    const signalIds = useTelemetryStore(state => state.signalIds);
    const viewMode = useTelemetryStore(state => state.viewMode);
    
    // Helper para formateo de precios profesional
    // Using formatPrice from utils/formatters

    // Obtener señales en ejecución o pendientes
    // [v8.3.2] Clean up signalIds to prevent duplicate keys in React (Set conversion)
    const activeExecutionSignals = Array.from(new Set(signalIds))
        .map(id => signalHistory[id])
        .filter(sig => sig && (viewMode === 'GLOBAL' || sig.asset === activeSymbol) && ['ACTIVE', 'FILLED', 'SHIELD_ACTIVATED', 'TP1_HIT', 'SHIELDED'].includes(sig.status || ''));

    const activeOrders = activeExecutionSignals.map(sig => {
        const symbol = sig.asset || 'UNKNOWN';
        const currentPrice = latestPrices[symbol] || sig.current_price || sig.price;
        
        return {
            id: sig.id,
            asset: symbol,
            type: sig.signal_type || (sig.type?.includes('LONG') ? 'LONG' : 'SHORT'),
            status: sig.status,
            entry: sig.price,
            sl: sig.sl_dynamic || sig.stop_loss,
            tp1: sig.tp1,
            tp2: sig.tp2,
            tp3: sig.tp3 || sig.take_profit_3r,
            shield_active: sig.shield_active || false,
            profit_locked: sig.profit_locked || false,
            current_price: currentPrice
        };
    });

    const drawdownPct = Math.min((dailyDrawdown / maxDrawdown) * 100, 100);

    return (
        <div className="h-full flex flex-col pt-2 p-4 bg-gradient-to-b from-[#0a0f18] to-black text-white">
            {/* OMEGA Header & Daily Status */}
            <div className="flex-none flex items-center justify-between mb-4 border-b border-white/10 pb-4">
                <div className="flex items-center gap-3">
                    <div className="relative">
                        <Shield className={`text-${isShieldLocked ? 'red-500' : 'neon-cyan'} w-6 h-6`} />
                        {!isShieldLocked && (
                            <motion.div
                                animate={{ scale: [1, 1.2, 1], opacity: [0.8, 0, 0.8] }}
                                transition={{ repeat: Infinity, duration: 2 }}
                                className="absolute inset-0 border border-neon-cyan/50 rounded-full"
                            />
                        )}
                    </div>
                    <div>
                        <h2 className="text-xs font-black tracking-widest text-white/90">OMEGA CENTINEL</h2>
                        <h3 className="text-[9px] font-mono tracking-[0.2em] text-white/40 uppercase">Execution & Risk Shield</h3>
                    </div>
                </div>

                <div className="flex flex-col items-end gap-1">
                    <span className="text-[10px] font-bold tracking-widest text-white/50 uppercase">DAILY PNL LIMIT</span>
                    <div className="flex items-center gap-2">
                        <span className={`text-xs font-black tracking-wider ${dailyDrawdown < 0 ? 'text-red-400' : 'text-green-400'}`}>
                            {dailyDrawdown.toFixed(2)}%
                        </span>
                        <span className="text-[10px] font-bold text-white/20">/ {maxDrawdown.toFixed(2)}%</span>
                    </div>
                </div>
            </div>

            {/* Limit Bar */}
            <div className="flex-none mb-6 relative">
                <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                    <motion.div
                        className={`h-full ${isShieldLocked ? 'bg-red-500' : 'bg-neon-cyan'}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${drawdownPct}%` }}
                    />
                </div>
                {isShieldLocked && (
                    <div className="absolute -top-1 -right-1 bg-red-500 rounded-full p-0.5 animate-pulse">
                        <Lock size={10} className="text-white" />
                    </div>
                )}
            </div>

            {/* Active Execution Grid */}
            <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar flex flex-col gap-3">
                <div className="flex items-center justify-between mb-2 px-1">
                    <h4 className="text-[10px] font-bold tracking-widest text-white/60">ACTIVE POSITIONS</h4>
                    <span className="text-[9px] px-2 py-0.5 rounded bg-white/5 text-white/50 font-mono">
                        {activeOrders.length} RUNNING
                    </span>
                </div>

                {activeOrders.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center gap-3 border border-dashed border-white/10 rounded-xl bg-white/[0.02]">
                        <ServerCog size={28} className="text-white/20" />
                        <p className="text-[10px] tracking-[0.3em] font-mono text-white/30 text-center uppercase leading-relaxed">
                            No active orders
                            <br />
                            Awaiting Gateway Triggers
                        </p>
                    </div>
                ) : (
                    <AnimatePresence mode="popLayout">
                        {activeOrders.map((order: any, idx: number) => (
                            <motion.div
                                key={order.id || `order-${order.asset}-${idx}`}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                                className={`flex flex-col border ${order.shield_active ? 'border-neon-cyan/40 bg-neon-cyan/5' : order.profit_locked ? 'border-neon-green/40 bg-neon-green/5' : 'border-white/10 bg-black/40'} rounded-xl p-3 relative overflow-hidden`}
                            >
                                {/* Header */}
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-2">
                                        <Activity size={14} className={order.type === 'LONG' ? 'text-neon-green' : 'text-red-500'} />
                                        <span className="text-sm font-black tracking-widest text-white">{order.asset}</span>
                                        <span className={`text-[9px] px-1.5 py-0.5 rounded ${order.type === 'LONG' ? 'bg-neon-green/20 text-neon-green' : 'bg-red-500/20 text-red-500'} font-bold`}>
                                            {order.type}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {(order.status === 'PENDING' || order.status === 'ACTIVE') && (
                                            <span className="text-[9px] font-mono text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded animate-pulse">
                                                PENDING ENTRY
                                            </span>
                                        )}
                                        {order.status === 'FILLED' && (
                                            <span className="text-[9px] font-mono text-neon-cyan bg-neon-cyan/10 px-2 py-0.5 rounded font-black">
                                                EXECUTING
                                            </span>
                                        )}
                                    </div>
                                </div>

                                {/* Body */}
                                <div className="grid grid-cols-3 gap-2 text-[9px] font-mono mb-3">
                                    <div className="flex flex-col gap-1">
                                        <span className="text-white/30">ENTRY</span>
                                        <span className="text-white font-bold">{formatCurrency(order.entry)}</span>
                                    </div>
                                    <div className="flex flex-col gap-1">
                                        <span className="text-white/30">PnL %</span>
                                        <span className={`font-black ${
                                            order.status === 'FILLED' ? 
                                            (order.type === 'LONG' ? (order.current_price > order.entry ? 'text-neon-green' : 'text-red-400') : (order.current_price < order.entry ? 'text-neon-green' : 'text-red-400')) : 
                                            'text-white/20'
                                        }`}>
                                            {order.status === 'FILLED' ? 
                                                `${(order.type === 'LONG' ? (order.current_price / order.entry - 1) * 100 : (order.entry / order.current_price - 1) * 100).toFixed(2)}%` : 
                                                '--'
                                            }
                                        </span>
                                    </div>
                                    <div className="flex flex-col gap-1">
                                        <span className="text-white/30">STOP LOSS</span>
                                        <span className={`font-bold ${order.shield_active ? 'text-neon-cyan' : 'text-red-400'}`}>
                                            {order.shield_active ? '🛡️ BE' : formatCurrency(order.sl)}
                                        </span>
                                    </div>
                                    <div className="flex flex-col gap-1">
                                        <span className="text-neon-cyan/50">TP1</span>
                                        <span className="text-neon-cyan font-bold">{formatCurrency(order.tp1)}</span>
                                    </div>
                                    <div className="flex flex-col gap-1">
                                        <span className="text-neon-cyan/50">TP2</span>
                                        <span className="text-neon-cyan font-bold">{formatCurrency(order.tp2)}</span>,StartLine:188,TargetContent:
                                    </div>
                                    <div className="flex flex-col gap-1">
                                        <span className="text-neon-cyan/50">TP3</span>
                                        <span className="text-neon-cyan font-bold">{formatCurrency(order.tp3)}</span>
                                    </div>
                                </div>

                                {/* Shield Status Injectors */}
                                {order.shield_active && !order.profit_locked && (
                                    <div className="mt-2 flex items-center justify-center gap-2 bg-neon-cyan/20 border border-neon-cyan/40 p-1.5 rounded uppercase tracking-widest text-[9px] font-black text-neon-cyan">
                                        <ShieldAlert size={12} />
                                        SHIELD ACTIVATED: RISK FREE
                                    </div>
                                )}
                                {order.profit_locked && (
                                    <div className="mt-2 flex items-center justify-center gap-2 bg-neon-green/20 border border-neon-green/40 p-1.5 rounded uppercase tracking-widest text-[9px] font-black text-neon-green">
                                        <CheckCircle2 size={12} />
                                        PROFITS LOCKED (TP1 MET)
                                    </div>
                                )}
                            </motion.div>
                        ))}
                    </AnimatePresence>
                )}
            </div>
            
            {/* Disclaimer */}
            <div className="flex-none mt-4 text-[8px] text-white/20 text-center tracking-widest uppercase font-mono border-t border-white/5 pt-3">
                SECURE BRIDGE CONNECTION REQUIRED FOR LIVE TELEMETRY
            </div>
        </div>
    );
}

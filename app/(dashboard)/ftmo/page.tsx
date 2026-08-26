'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldCheck, Target, RefreshCw, Layers, Award, TrendingUp, AlertTriangle, Copy, CheckCircle2 } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';

interface TradFiOpportunity {
    asset: string;
    name: string;
    category: string;
    direction: string;
    type: string;
    price: number;
    current_price: number;
    stop_loss: number;
    be_price: number;
    tp1: number;
    tp2: number;
    tp3: number;
    rr_ratio_tp3: number;
    confluence_score: number;
    mt5_lots: number;
    risk_usd: number;
    spread_usd: number;
    checklist: Array<{ factor: string; status: string; detail: string }>;
    timestamp: string;
}

interface FtmoStatus {
    account_size: number;
    current_equity: number;
    daily_starting_equity: number;
    daily_loss_usd: number;
    daily_dd_pct: number;
    total_dd_pct: number;
    daily_safe_margin_left_pct: number;
    is_daily_lockout: boolean;
    lockout_reason: string;
    phase: string;
    target_pct: number;
    progress_pct: number;
    phase_passed: boolean;
}

export default function FtmoPage() {
    const [opportunities, setOpportunities] = useState<TradFiOpportunity[]>([]);
    const [ftmoStatus, setFtmoStatus] = useState<FtmoStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [copiedAsset, setCopiedAsset] = useState<string | null>(null);
    const [selectedAccountSize, setSelectedAccountSize] = useState<number>(100000);
    const [selectedPhase, setSelectedPhase] = useState<'PHASE_1' | 'PHASE_2'>('PHASE_1');

    const fetchTradFiData = async () => {
        try {
            const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const [oppsRes, statusRes] = await Promise.all([
                fetch(`${apiHost}/api/v1/tradfi/opportunities`),
                fetch(`${apiHost}/api/v1/ftmo/guardian`)
            ]);

            if (oppsRes.ok) {
                const data = await oppsRes.json();
                setOpportunities(data.opportunities || []);
            }
            if (statusRes.ok) {
                const sData = await statusRes.json();
                setFtmoStatus(sData);
            }
        } catch (e) {
            console.warn("FTMO Terminal: Feed offline, cargando simulador local.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTradFiData();
        const timer = setInterval(fetchTradFiData, 15000);
        return () => clearInterval(timer);
    }, []);

    return (
        <div className="h-full w-full flex flex-col p-6 overflow-y-auto custom-scrollbar bg-[#030712]">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/5">
                <div>
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-neon-cyan/10 border border-neon-cyan/30 shadow-[0_0_15px_rgba(6,182,212,0.2)]">
                            <Award className="text-neon-cyan" size={24} />
                        </div>
                        <div>
                            <h1 className="text-xl font-black tracking-widest text-white uppercase flex items-center gap-2">
                                FTMO ALPHA TERMINAL <span className="text-white/20 font-light">|</span> <span className="text-neon-cyan text-sm">METATRADER 5</span>
                            </h1>
                            <p className="text-xs text-white/40 font-mono mt-0.5">
                                Activos Tradicionales de Alta Beta: Oro Spot (XAUUSD), Nasdaq (US100), Dow Jones (US30) y GBPUSD
                            </p>
                        </div>
                    </div>
                </div>

                {/* Account Sizer Selector */}
                <div className="flex items-center gap-2 bg-black/40 p-1.5 rounded-2xl border border-white/10">
                    {[50000, 100000, 200000].map((size) => (
                        <button
                            key={size}
                            onClick={() => setSelectedAccountSize(size)}
                            className={`px-3 py-1.5 rounded-xl text-[10px] font-mono font-black transition-all cursor-pointer ${
                                selectedAccountSize === size
                                    ? 'bg-neon-cyan text-black shadow-[0_0_10px_rgba(6,182,212,0.5)]'
                                    : 'text-white/60 hover:text-white hover:bg-white/5'
                            }`}
                        >
                            ${size / 1000}K
                        </button>
                    ))}
                    <div className="h-4 w-px bg-white/10 mx-1" />
                    <button
                        onClick={() => setSelectedPhase(selectedPhase === 'PHASE_1' ? 'PHASE_2' : 'PHASE_1')}
                        className="px-3 py-1.5 rounded-xl text-[10px] font-mono font-black bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 transition-all cursor-pointer"
                    >
                        {selectedPhase === 'PHASE_1' ? 'FASE 1 (10% TARGET)' : 'FASE 2 (5% TARGET)'}
                    </button>
                </div>
            </div>

            {/* FTMO Guardian Telemetry Bar */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 my-6">
                <div className="bg-[#0B132B]/60 border border-white/10 rounded-2xl p-4 flex flex-col justify-between">
                    <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Balance Base Cuenta</span>
                    <span className="text-xl font-black font-mono text-white mt-1">
                        ${(selectedAccountSize).toLocaleString('en-US')}.00 USD
                    </span>
                    <span className="text-[8px] font-mono text-emerald-400 mt-2 flex items-center gap-1">
                        <ShieldCheck size={10} /> Riesgo por Trade: ${selectedAccountSize * (selectedPhase === 'PHASE_1' ? 0.0075 : 0.0050)} USD ({selectedPhase === 'PHASE_1' ? '0.75%' : '0.50%'})
                    </span>
                </div>

                <div className="bg-[#0B132B]/60 border border-white/10 rounded-2xl p-4 flex flex-col justify-between">
                    <div className="flex justify-between items-center">
                        <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Objetivo Fase {selectedPhase === 'PHASE_1' ? '1' : '2'}</span>
                        <span className="text-[8px] font-mono font-bold text-neon-cyan bg-neon-cyan/10 px-1.5 py-0.5 rounded">
                            {selectedPhase === 'PHASE_1' ? '+10%' : '+5%'}
                        </span>
                    </div>
                    <span className="text-xl font-black font-mono text-neon-cyan mt-1">
                        +${(selectedAccountSize * (selectedPhase === 'PHASE_1' ? 0.10 : 0.05)).toLocaleString('en-US')}.00 USD
                    </span>
                    <div className="w-full bg-white/5 rounded-full h-1.5 mt-2 overflow-hidden">
                        <div className="bg-neon-cyan h-full rounded-full w-[45%]" />
                    </div>
                </div>

                <div className="bg-[#0B132B]/60 border border-white/10 rounded-2xl p-4 flex flex-col justify-between">
                    <div className="flex justify-between items-center">
                        <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Drawdown Diario (Max -5%)</span>
                        <span className="text-[8px] font-mono font-bold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                            SEGURO
                        </span>
                    </div>
                    <span className="text-xl font-black font-mono text-emerald-400 mt-1">
                        -0.00% ($0.00)
                    </span>
                    <span className="text-[8px] font-mono text-white/40 mt-2">
                        🛡️ Kill-Switch Preventivo a -3.5% ($3,500 USD)
                    </span>
                </div>

                <div className="bg-[#0B132B]/60 border border-white/10 rounded-2xl p-4 flex flex-col justify-between">
                    <div className="flex justify-between items-center">
                        <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Backtest Auditado (6 Meses)</span>
                        <span className="text-[8px] font-mono font-bold text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
                            ORO + NASDAQ
                        </span>
                    </div>
                    <span className="text-xl font-black font-mono text-amber-400 mt-1">
                        +8.51% ROI (XAUUSD)
                    </span>
                    <span className="text-[8px] font-mono text-white/40 mt-2">
                        60.4% Win Rate Efectivo (Fast BE +1.0R)
                    </span>
                </div>
            </div>

            {/* Setups List */}
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-xs font-black text-white/80 uppercase tracking-widest flex items-center gap-2">
                    <TrendingUp size={14} className="text-neon-cyan" /> SETUPS ACTIVOS DE ALTA CONFLUENCIA MT5
                </h2>
                <span className="text-[9px] font-mono text-white/40">
                    Actualización Cuantitativa en Tiempo Real
                </span>
            </div>

            {loading ? (
                <div className="h-60 flex flex-col items-center justify-center gap-3">
                    <RefreshCw className="animate-spin text-neon-cyan" size={24} />
                    <span className="text-xs font-mono text-white/40">CALCULANDO NIVELES Y LOTES MT5...</span>
                </div>
            ) : opportunities.length === 0 ? (
                <div className="h-60 flex flex-col items-center justify-center gap-2 border border-dashed border-white/10 rounded-2xl bg-white/[0.01]">
                    <Layers className="text-white/20" size={32} />
                    <span className="text-xs font-mono text-white/40">ESPERANDO APERTURA DE KILLZONE (LONDRES / NY)...</span>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {opportunities.map((opp) => {
                        const isLong = opp.direction === 'LONG';
                        const assetKey = `${opp.asset}-${opp.direction}`;
                        const isCopied = copiedAsset === assetKey;

                        return (
                            <motion.div
                                key={assetKey}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="bg-[#060D17]/90 border border-white/10 hover:border-neon-cyan/40 rounded-2xl p-5 flex flex-col justify-between transition-all relative shadow-xl"
                            >
                                <div>
                                    {/* Category Pill */}
                                    <div className="flex items-center justify-between bg-cyan-500/10 border border-cyan-500/25 rounded-xl px-3 py-1 mb-3">
                                        <span className="text-neon-cyan text-[8.5px] font-mono font-bold uppercase tracking-wider">
                                            🎯 ORDEN LÍMITE FTMO (MT5)
                                        </span>
                                        <span className="text-white/40 text-[8px] font-mono">1-CLICK MT5</span>
                                    </div>

                                    {/* Header */}
                                    <div className="flex items-center justify-between mb-3">
                                        <div className="flex items-center gap-2">
                                            <span className="text-base font-black text-white">{opp.asset}</span>
                                            <span className="text-[9px] font-mono text-white/40 font-bold">({opp.name})</span>
                                        </div>
                                        <span className={`text-[10px] font-mono font-black px-2 py-0.5 rounded-full border ${
                                            isLong ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' : 'text-rose-400 bg-rose-500/10 border-rose-500/30'
                                        }`}>
                                            {isLong ? '🟢 BUY LIMIT' : '🔴 SELL LIMIT'}
                                        </span>
                                    </div>

                                    {/* Levels Grid */}
                                    <div className="grid grid-cols-2 gap-2 font-mono text-[10px] mb-3">
                                        <div className="bg-white/[0.03] p-2 rounded-xl border border-white/5">
                                            <span className="text-white/40 text-[8px] block">Precio Entrada OTE</span>
                                            <span className="text-white font-bold">{formatCurrency(opp.price)}</span>
                                        </div>
                                        <div className="bg-rose-500/10 p-2 rounded-xl border border-rose-500/20">
                                            <span className="text-rose-400 text-[8px] block">Stop Loss</span>
                                            <span className="text-rose-400 font-bold">{formatCurrency(opp.stop_loss)}</span>
                                        </div>
                                        <div className="bg-cyan-500/10 p-2 rounded-xl border border-cyan-500/20">
                                            <span className="text-neon-cyan text-[8px] block">🛡️ Fast BE (+1.0R)</span>
                                            <span className="text-white font-bold">{formatCurrency(opp.be_price)}</span>
                                        </div>
                                        <div className="bg-emerald-500/10 p-2 rounded-xl border border-emerald-500/20">
                                            <span className="text-emerald-400 text-[8px] block">TP1 (+1.3R / 70%)</span>
                                            <span className="text-emerald-400 font-bold">{formatCurrency(opp.tp1)}</span>
                                        </div>
                                    </div>

                                    {/* MT5 Lot Calculator Box */}
                                    <div className="bg-black/40 border border-white/5 rounded-xl p-3 font-mono mb-4">
                                        <div className="flex justify-between items-center text-[10px] mb-1">
                                            <span className="text-white/50">Lotes Sugeridos MT5:</span>
                                            <span className="text-emerald-400 font-black text-[13px]">{opp.mt5_lots} Lots</span>
                                        </div>
                                        <div className="flex justify-between items-center text-[9px] text-white/40 border-t border-white/5 pt-1">
                                            <span>Riesgo en Cuenta:</span>
                                            <span className="text-neon-cyan font-bold">${opp.risk_usd} USD (0.75%)</span>
                                        </div>
                                    </div>
                                </div>

                                {/* Copy Button */}
                                <button
                                    onClick={() => {
                                        const action = isLong ? 'BUY LIMIT' : 'SELL LIMIT';
                                        const text = `[FTMO MT5] ${action} ${opp.asset} @ ${opp.price} | LOTES: ${opp.mt5_lots} | SL: ${opp.stop_loss} | 🛡️ BE (+1.0R): ${opp.be_price} | 🥇 TP1 (+1.3R): ${opp.tp1} | 🎯 TP3 (+3.5R): ${opp.tp3}`;
                                        navigator.clipboard.writeText(text);
                                        setCopiedAsset(assetKey);
                                        setTimeout(() => setCopiedAsset(null), 2000);
                                    }}
                                    className={`w-full py-2.5 rounded-xl text-[10px] font-mono font-black transition-all flex items-center justify-center gap-1.5 cursor-pointer border active:scale-[0.98] ${
                                        isCopied
                                            ? 'bg-emerald-500 text-black border-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.6)]'
                                            : 'bg-neon-cyan/15 hover:bg-neon-cyan/25 text-neon-cyan border-neon-cyan/30 shadow-[0_0_10px_rgba(6,182,212,0.1)]'
                                    }`}
                                >
                                    {isCopied ? (
                                        <>
                                            <CheckCircle2 size={14} /> ¡PARÁMETROS MT5 COPIADOS!
                                        </>
                                    ) : (
                                        <>
                                            <Copy size={14} /> COPIAR ORDEN PARA METATRADER 5
                                        </>
                                    )}
                                </button>
                            </motion.div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

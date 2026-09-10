'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldCheck, Target, RefreshCw, Layers, Award, TrendingUp, AlertTriangle, Copy, CheckCircle2, Activity, ArrowUpRight, ArrowDownRight, Clock, Zap } from 'lucide-react';
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

interface Mt5Position {
    ticket: number;
    symbol: string;
    side: 'LONG' | 'SHORT';
    volume: number;
    entry_price: number;
    cur_price: number;
    sl: number;
    tp: number;
    profit: number;
    magic: number;
    comment: string;
}

interface Mt5PendingOrder {
    ticket: number;
    symbol: string;
    type: string;
    volume: number;
    price: number;
    sl: number;
    tp: number;
    comment: string;
}

interface Mt5SpreadItem {
    symbol: string;
    bid: number;
    ask: number;
    spread_raw: number;
    spread_points: number;
    digits: number;
    is_spike: boolean;
    status: 'NORMAL' | 'ELEVATED';
}

interface Mt5TelemetryData {
    connected: boolean;
    account_login: number;
    balance: number;
    equity: number;
    margin?: number;
    margin_free?: number;
    currency?: string;
    leverage?: number;
    total_floating_pnl: number;
    positions_count: number;
    positions: Mt5Position[];
    pending_orders: Mt5PendingOrder[];
    spreads: Record<string, Mt5SpreadItem>;
}

import { getApiBaseUrl } from '../../utils/apiUrl';

export default function FtmoPage() {
    const [opportunities, setOpportunities] = useState<TradFiOpportunity[]>([]);
    const [ftmoStatus, setFtmoStatus] = useState<FtmoStatus | null>(null);
    const [mt5Data, setMt5Data] = useState<Mt5TelemetryData | null>(null);
    const [loading, setLoading] = useState(true);
    const [copiedAsset, setCopiedAsset] = useState<string | null>(null);
    const [selectedAccountSize, setSelectedAccountSize] = useState<number>(100000);
    const [selectedPhase, setSelectedPhase] = useState<'PHASE_1' | 'PHASE_2'>('PHASE_1');

    const fetchTradFiData = async () => {
        try {
            const apiHost = getApiBaseUrl();
            const [oppsRes, statusRes, mt5Res] = await Promise.all([
                fetch(`${apiHost}/api/v1/tradfi/opportunities`),
                fetch(`${apiHost}/api/v1/ftmo/guardian`),
                fetch(`${apiHost}/api/v1/ftmo/positions`)
            ]);

            if (oppsRes.ok) {
                const data = await oppsRes.json();
                setOpportunities(data.opportunities || []);
            }
            if (statusRes.ok) {
                const sData = await statusRes.json();
                setFtmoStatus(sData);
            }
            if (mt5Res.ok) {
                const mData = await mt5Res.json();
                setMt5Data(mData);
            }
        } catch (e) {
            console.warn("FTMO Terminal: Feed offline, cargando simulador local.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTradFiData();
        const timer = setInterval(fetchTradFiData, 5000);
        return () => clearInterval(timer);
    }, []);

    return (
        <div className="h-full w-full flex flex-col p-3 lg:p-6 overflow-y-auto custom-scrollbar bg-[#030712]">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 lg:pb-6 border-b border-white/5">
                <div>
                    <div className="flex items-center gap-3">
                        <div className="p-2 lg:p-2.5 rounded-xl bg-neon-cyan/10 border border-neon-cyan/30 shadow-[0_0_15px_rgba(6,182,212,0.2)]">
                            <Award className="text-neon-cyan" size={22} />
                        </div>
                        <div>
                            <h1 className="text-base lg:text-xl font-black tracking-wider lg:tracking-widest text-white uppercase flex items-center gap-2">
                                FTMO ALPHA TERMINAL <span className="text-white/20 font-light hidden sm:inline">|</span> <span className="text-neon-cyan text-xs lg:text-sm hidden sm:inline">METATRADER 5</span>
                            </h1>
                            <p className="text-[10px] lg:text-xs text-white/40 font-mono mt-0.5">
                                Activos Tradicionales: Oro Spot (XAUUSD), Nasdaq (US100), Dow Jones (US30) y GBPUSD
                            </p>
                        </div>
                    </div>
                </div>

                {/* Account Sizer Selector */}
                <div className="flex flex-wrap items-center gap-2 bg-black/40 p-1.5 rounded-2xl border border-white/10">
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
                    <div className="h-4 w-px bg-white/10 mx-1 hidden sm:block" />
                    <button
                        onClick={() => setSelectedPhase(selectedPhase === 'PHASE_1' ? 'PHASE_2' : 'PHASE_1')}
                        className="px-3 py-1.5 rounded-xl text-[10px] font-mono font-black bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 transition-all cursor-pointer"
                    >
                        {selectedPhase === 'PHASE_1' ? 'FASE 1 (10% TARGET)' : 'FASE 2 (5% TARGET)'}
                    </button>
                </div>
            </div>

            {/* FTMO Guardian Telemetry Bar */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-4 my-4 lg:my-6">
                <div className="bg-[#0B132B]/60 border border-white/10 rounded-2xl p-4 flex flex-col justify-between">
                    <div className="flex justify-between items-center">
                        <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Balance en Vivo (MT5)</span>
                        {mt5Data?.account_login && (
                            <span className="text-[8px] font-mono font-bold text-neon-cyan bg-neon-cyan/10 px-1.5 py-0.5 rounded border border-neon-cyan/20">
                                #{mt5Data.account_login}
                            </span>
                        )}
                    </div>
                    <span className="text-xl font-black font-mono text-white mt-1">
                        ${(mt5Data?.balance ?? selectedAccountSize).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {mt5Data?.currency || 'USD'}
                    </span>
                    <span className="text-[8px] font-mono text-emerald-400 mt-2 flex items-center gap-1">
                        <ShieldCheck size={10} /> Equidad: ${(mt5Data?.equity ?? selectedAccountSize).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (Margen Libre: ${(mt5Data?.margin_free ?? 0).toLocaleString('en-US')})
                    </span>
                </div>

                <div className="bg-[#0B132B]/60 border border-white/10 rounded-2xl p-4 flex flex-col justify-between">
                    <div className="flex justify-between items-center">
                        <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Objetivo Fase {ftmoStatus?.phase === 'PHASE_2' ? '2' : '1'}</span>
                        <span className="text-[8px] font-mono font-bold text-neon-cyan bg-neon-cyan/10 px-1.5 py-0.5 rounded">
                            +{ftmoStatus?.target_pct ?? 10}%
                        </span>
                    </div>
                    <span className="text-xl font-black font-mono text-neon-cyan mt-1">
                        +${((ftmoStatus?.account_size ?? selectedAccountSize) * ((ftmoStatus?.target_pct ?? 10) / 100)).toLocaleString('en-US')}.00 USD
                    </span>
                    <div className="w-full bg-white/5 rounded-full h-1.5 mt-2 overflow-hidden">
                        <div 
                            className="bg-neon-cyan h-full rounded-full transition-all duration-500" 
                            style={{ width: `${Math.min(100, Math.max(0, ftmoStatus?.progress_pct ?? 0))}%` }} 
                        />
                    </div>
                    <span className="text-[8px] font-mono text-white/40 mt-1">
                        Progreso actual: {(ftmoStatus?.progress_pct ?? 0).toFixed(1)}% {ftmoStatus?.phase_passed ? '🎉 FASE APROBADA' : ''}
                    </span>
                </div>

                <div className="bg-[#0B132B]/60 border border-white/10 rounded-2xl p-4 flex flex-col justify-between">
                    <div className="flex justify-between items-center">
                        <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Drawdown Diario (Max -5%)</span>
                        <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded ${
                            ftmoStatus?.is_daily_lockout 
                                ? 'text-rose-400 bg-rose-500/20 animate-pulse' 
                                : (ftmoStatus?.daily_dd_pct ?? 0) > 2.0 
                                    ? 'text-amber-400 bg-amber-500/10' 
                                    : 'text-emerald-400 bg-emerald-500/10'
                        }`}>
                            {ftmoStatus?.is_daily_lockout ? 'LOCKOUT' : (ftmoStatus?.daily_dd_pct ?? 0) > 2.0 ? 'PRECAUCIÓN' : 'SEGURO'}
                        </span>
                    </div>
                    <span className={`text-xl font-black font-mono mt-1 ${(ftmoStatus?.daily_dd_pct ?? 0) > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                        -{(ftmoStatus?.daily_dd_pct ?? 0).toFixed(2)}% (-${(ftmoStatus?.daily_loss_usd ?? 0).toFixed(2)})
                    </span>
                    <span className="text-[8px] font-mono text-white/40 mt-2">
                        🛡️ Kill-Switch a -3.5% | Margen restante: {(ftmoStatus?.daily_safe_margin_left_pct ?? 3.5).toFixed(2)}%
                    </span>
                </div>

                <div className="bg-[#0B132B]/60 border border-white/10 rounded-2xl p-4 flex flex-col justify-between">
                    <div className="flex justify-between items-center">
                        <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Flotante Neto Actual</span>
                        <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded ${(mt5Data?.total_floating_pnl ?? 0) >= 0 ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'}`}>
                            {(mt5Data?.total_floating_pnl ?? 0) >= 0 ? 'PROFIT' : 'DRAWDOWN'}
                        </span>
                    </div>
                    <span className={`text-xl font-black font-mono mt-1 ${(mt5Data?.total_floating_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {(mt5Data?.total_floating_pnl ?? 0) >= 0 ? '+' : ''}${(mt5Data?.total_floating_pnl ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
                    </span>
                    <span className="text-[8px] font-mono text-white/40 mt-2">
                        Apalancamiento: 1:{mt5Data?.leverage ?? 30} | {mt5Data?.positions_count ?? 0} posición(es) viva(s)
                    </span>
                </div>
            </div>

            {/* 1. Real-Time Spread Monitor (Tier A) */}
            {mt5Data?.spreads && Object.keys(mt5Data.spreads).length > 0 && (
                <div className="mb-6 bg-[#050B14]/70 border border-white/10 rounded-2xl p-4 backdrop-blur-xl">
                    <div className="flex items-center justify-between mb-3 border-b border-white/5 pb-2">
                        <span className="text-xs font-black text-white/90 uppercase tracking-widest flex items-center gap-2">
                            <Activity size={14} className="text-neon-cyan animate-pulse" /> SPREAD INSTITUCIONAL EN VIVO (MT5 TICKER)
                        </span>
                        <span className="text-[9px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                            🛡️ SPREAD SPIKE GUARD ACTIVO
                        </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
                        {Object.entries(mt5Data.spreads).map(([sym, item]) => {
                            const isElevated = item.is_spike || item.status === 'ELEVATED';
                            return (
                                <div key={sym} className={`p-2.5 rounded-xl border transition-all ${
                                    isElevated ? 'bg-rose-500/10 border-rose-500/30' : 'bg-black/30 border-white/5'
                                }`}>
                                    <div className="flex justify-between items-center mb-1">
                                        <span className="text-[11px] font-black text-white">{sym.replace('.cash', '')}</span>
                                        <span className={`text-[8px] font-bold px-1.5 py-0.2 rounded ${
                                            isElevated ? 'bg-rose-500 text-black font-black' : 'text-emerald-400 bg-emerald-500/15'
                                        }`}>
                                            {isElevated ? 'ELEVADO' : 'NORMAL'}
                                        </span>
                                    </div>
                                    <div className="flex justify-between items-baseline text-[10px]">
                                        <span className="text-white/40">Spread:</span>
                                        <span className={`font-black ${isElevated ? 'text-rose-400' : 'text-neon-cyan'}`}>
                                            {item.spread_raw} ({item.spread_points} pts)
                                        </span>
                                    </div>
                                    <div className="flex justify-between items-baseline text-[8.5px] text-white/30 mt-0.5">
                                        <span>B: {item.bid}</span>
                                        <span>A: {item.ask}</span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* 2. Live Active Positions in MT5 */}
            <div className="mb-6 bg-[#050B14]/80 border border-white/10 rounded-2xl p-4 backdrop-blur-xl">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3 border-b border-white/5 pb-2">
                    <div className="flex items-center gap-2">
                        <Zap size={14} className="text-neon-green" />
                        <h2 className="text-xs font-black text-white/90 uppercase tracking-widest">
                            POSICIONES ACTIVAS EN METATRADER 5 (EN EJECUCIÓN)
                        </h2>
                        <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-white/5 text-white/60 border border-white/10">
                            {mt5Data?.positions?.length || 0} Abiertas
                        </span>
                    </div>
                    {mt5Data?.total_floating_pnl !== undefined && (
                        <div className="flex items-center gap-2 font-mono text-xs">
                            <span className="text-white/40 text-[10px]">Flotante Neto:</span>
                            <span className={`font-black px-2 py-0.5 rounded-lg border ${
                                mt5Data.total_floating_pnl >= 0 
                                    ? 'text-neon-green bg-neon-green/10 border-neon-green/30' 
                                    : 'text-rose-400 bg-rose-500/10 border-rose-500/30'
                            }`}>
                                {mt5Data.total_floating_pnl >= 0 ? `+$${mt5Data.total_floating_pnl.toFixed(2)}` : `-$${Math.abs(mt5Data.total_floating_pnl).toFixed(2)}`} USD
                            </span>
                        </div>
                    )}
                </div>

                {(!mt5Data?.positions || mt5Data.positions.length === 0) ? (
                    <div className="py-6 flex flex-col items-center justify-center text-center">
                        <ShieldCheck size={28} className="text-emerald-400/40 mb-2" />
                        <p className="text-xs font-mono font-bold text-white/60">SIN POSICIONES EN RIESGO ABIERTO</p>
                        <p className="text-[10px] font-mono text-white/30 mt-0.5">Capital 100% blindado esperando confluencia ≥ 75% en Killzone</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 font-mono">
                        {mt5Data.positions.map((pos) => {
                            const isProfit = pos.profit >= 0;
                            const isLong = pos.side === 'LONG';
                            return (
                                <div key={pos.ticket} className="bg-black/40 border border-white/10 rounded-xl p-3.5 flex flex-col justify-between hover:border-white/20 transition-all">
                                    <div className="flex justify-between items-start mb-2">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm font-black text-white">{pos.symbol}</span>
                                                <span className={`text-[9px] font-black px-2 py-0.5 rounded-md flex items-center gap-0.5 ${
                                                    isLong ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                                                }`}>
                                                    {isLong ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />} {pos.side}
                                                </span>
                                                <span className="text-[9px] text-white/40">#{pos.ticket}</span>
                                            </div>
                                            <p className="text-[9px] text-neon-cyan/70 mt-0.5">{pos.comment || 'Slingshot FTMO'}</p>
                                        </div>
                                        <div className="text-right">
                                            <span className={`text-base font-black tracking-tight ${isProfit ? 'text-neon-green drop-shadow-[0_0_8px_rgba(0,255,65,0.4)]' : 'text-rose-400'}`}>
                                                {isProfit ? `+$${pos.profit.toFixed(2)}` : `-$${Math.abs(pos.profit).toFixed(2)}`} USD
                                            </span>
                                            <span className="text-[9px] block text-white/40">{pos.volume} Lotes</span>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-4 gap-1.5 pt-2 border-t border-white/5 text-[9px]">
                                        <div className="bg-white/[0.02] p-1.5 rounded-lg border border-white/5">
                                            <span className="text-white/40 block">Entrada</span>
                                            <span className="text-white font-bold">{pos.entry_price}</span>
                                        </div>
                                        <div className="bg-white/[0.02] p-1.5 rounded-lg border border-white/5">
                                            <span className="text-white/40 block">Actual</span>
                                            <span className="text-white font-bold">{pos.cur_price}</span>
                                        </div>
                                        <div className="bg-rose-500/10 p-1.5 rounded-lg border border-rose-500/20">
                                            <span className="text-rose-400/70 block">Stop Loss</span>
                                            <span className="text-rose-400 font-bold">{pos.sl || '---'}</span>
                                        </div>
                                        <div className="bg-emerald-500/10 p-1.5 rounded-lg border border-emerald-500/20">
                                            <span className="text-emerald-400/70 block">Take Profit</span>
                                            <span className="text-emerald-400 font-bold">{pos.tp || '---'}</span>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* 3. Pending Limit Orders in MT5 */}
            {mt5Data?.pending_orders && mt5Data.pending_orders.length > 0 && (
                <div className="mb-6 bg-[#050B14]/80 border border-white/10 rounded-2xl p-4 backdrop-blur-xl">
                    <div className="flex items-center justify-between mb-3 border-b border-white/5 pb-2">
                        <div className="flex items-center gap-2">
                            <Clock size={14} className="text-amber-400" />
                            <h2 className="text-xs font-black text-white/90 uppercase tracking-widest">
                                ÓRDENES LÍMITE PENDIENTES (MT5 OTE)
                            </h2>
                            <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-amber-400/10 text-amber-400 border border-amber-400/20 font-bold">
                                {mt5Data.pending_orders.length} Órdenes
                            </span>
                        </div>
                        <span className="text-[9px] font-mono text-white/40">
                            Cosecha Escalonada 50 / 30 / 20 Activa
                        </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono">
                        {mt5Data.pending_orders.map((ord) => (
                            <div key={ord.ticket} className="bg-black/30 border border-amber-500/20 rounded-xl p-3 flex flex-col justify-between">
                                <div className="flex justify-between items-center mb-1.5">
                                    <span className="text-xs font-black text-white">{ord.symbol}</span>
                                    <span className="text-[9px] font-bold text-amber-400 bg-amber-500/15 px-2 py-0.5 rounded-md border border-amber-500/30">
                                        {ord.type}
                                    </span>
                                </div>
                                <div className="text-[10px] text-white/70 space-y-0.5 my-1">
                                    <div className="flex justify-between">
                                        <span className="text-white/40">Precio Entrada:</span>
                                        <span className="text-white font-bold">{ord.price}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-white/40">Volumen:</span>
                                        <span className="text-emerald-400 font-bold">{ord.volume} Lotes</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-white/40">SL / TP:</span>
                                        <span>{ord.sl} / {ord.tp}</span>
                                    </div>
                                </div>
                                <div className="text-[8px] text-white/30 border-t border-white/5 pt-1 mt-1 flex justify-between">
                                    <span>#{ord.ticket}</span>
                                    <span className="text-neon-cyan/70">{ord.comment}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

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

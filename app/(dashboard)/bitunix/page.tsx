'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
    Zap, ShieldCheck, Activity, RefreshCw, AlertTriangle, ArrowUpRight, ArrowDownRight, 
    Lock, CheckCircle2, DollarSign, Crosshair, Layers, HelpCircle
} from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';
import { getApiBaseUrl } from '../../utils/apiUrl';

interface ActiveStopLoss {
    price: number | null;
    order_id: string | null;
    is_protected: boolean;
}

interface TakeProfitItem {
    order_id: string;
    price: number;
    qty: number;
    ctime?: string;
}

interface BitunixPosition {
    symbol: string;
    position_id: string;
    side: 'LONG' | 'SHORT';
    qty: number;
    entry_price: number;
    mark_price: number;
    leverage: number;
    isolated_margin: number;
    unrealized_pnl: number;
    unrealized_pnl_pct: number;
    active_sl: ActiveStopLoss;
    take_profits: TakeProfitItem[];
}

interface BitunixPendingOrder {
    order_id: string;
    symbol: string;
    side: string;
    trade_side: string;
    order_type: string;
    price: number;
    qty: number;
    reduce_only: boolean;
    ctime?: string;
}

interface BitunixRiskConfig {
    risk_pct: number;
    risk_pct_display: string;
    risk_usd_per_trade: number;
    max_notional_mult: number;
    sop_protocol: string;
}

interface BitunixTelemetryData {
    account_label: string;
    connected: boolean;
    latency_ms: number;
    equity: number;
    available_balance: number;
    net_available_balance: number;
    used_margin: number;
    frozen_margin: number;
    total_floating_pnl: number;
    risk_config: BitunixRiskConfig;
    positions_count: number;
    positions: BitunixPosition[];
    pending_orders_count: number;
    pending_orders: BitunixPendingOrder[];
}

export default function BitunixPage() {
    const [data, setData] = useState<BitunixTelemetryData | null>(null);
    const [loading, setLoading] = useState(true);
    const [simEntry, setSimEntry] = useState<number>(0);
    const [simSl, setSimSl] = useState<number>(0);

    const fetchBitunixData = async () => {
        try {
            const apiHost = getApiBaseUrl();
            const res = await fetch(`${apiHost}/api/v1/bitunix/telemetry`);
            if (res.ok) {
                const json = await res.json();
                setData(json);
            }
        } catch (e) {
            console.warn("Bitunix Terminal: Error consultando telemetría en vivo:", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchBitunixData();
        const interval = setInterval(fetchBitunixData, 3000);
        return () => clearInterval(interval);
    }, []);

    // Cálculo interactivo del simulador de riesgo (SOP-41 2.50%)
    const simRiskUsd = data?.risk_config?.risk_usd_per_trade ?? ((data?.equity ?? 648.83) * 0.025);
    const simSlDist = Math.abs(simEntry - simSl);
    const simContracts = (simEntry > 0 && simSlDist > 0) ? (simRiskUsd / simSlDist) : 0;
    const simNotional = simContracts * simEntry;
    const isExceedingNotional = simNotional > ((data?.equity ?? 648.83) * 5.0);

    return (
        <div className="h-full w-full flex flex-col p-3 lg:p-6 overflow-y-auto custom-scrollbar bg-[#02040A]">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 lg:pb-6 border-b border-white/5">
                <div>
                    <div className="flex items-center gap-3">
                        <div className="p-2 lg:p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 shadow-[0_0_15px_rgba(245,158,11,0.2)]">
                            <Zap className="text-amber-400" size={22} />
                        </div>
                        <div>
                            <h1 className="text-base lg:text-xl font-black tracking-wider lg:tracking-widest text-white uppercase flex items-center gap-2">
                                BITUNIX MASTER TERMINAL <span className="text-white/20 font-light hidden sm:inline">|</span> <span className="text-amber-400 text-xs lg:text-sm hidden sm:inline">FUTUROS CRIPTO</span>
                            </h1>
                            <p className="text-[10px] lg:text-xs text-white/40 font-mono mt-0.5">
                                Cuenta Principal Institucional: Futuros Perpetuos con Margen Aislado y Reglas SOP-41 / SOP-58
                            </p>
                        </div>
                    </div>
                </div>

                {/* Status Badges */}
                <div className="flex flex-wrap items-center gap-2 font-mono text-[10px]">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-black/40 border border-white/10 text-white/70">
                        <span className={`w-2 h-2 rounded-full ${data?.connected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'}`} />
                        <span>API: {data?.connected ? 'CONECTADO' : 'OFFLINE'} ({data?.latency_ms ?? 0}ms)</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-300">
                        <Zap size={12} className="text-purple-400 animate-pulse" />
                        <span>AI: NVIDIA NIM (NEMOTRON 3.5)</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                        <ShieldCheck size={12} />
                        <span>SOP-58 AUTO-HEALING ACTIVO</span>
                    </div>
                </div>
            </div>

            {/* Telemetry Bar (4 Tarjetas) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-4 my-4 lg:my-6">
                {/* 1. Balance Disponible */}
                <div className="bg-[#0A0F1D]/80 border border-white/10 rounded-2xl p-4 flex flex-col justify-between backdrop-blur-xl">
                    <div className="flex justify-between items-center">
                        <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Balance Total (USDT)</span>
                        <span className="text-[8px] font-mono font-bold text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">
                            FUTUROS
                        </span>
                    </div>
                    <span className="text-xl font-black font-mono text-white mt-1">
                        ${(data?.equity ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT
                    </span>
                    <span className="text-[8px] font-mono text-white/40 mt-2 flex items-center justify-between">
                        <span>Disponible: <strong className="text-emerald-400">${(data?.available_balance ?? 0).toFixed(2)}</strong></span>
                        <span>Congelado: ${(data?.frozen_margin ?? 0).toFixed(2)}</span>
                    </span>
                </div>

                {/* 2. Riesgo Institucional SOP-41 (2.50%) */}
                <div className="bg-[#0A0F1D]/80 border border-white/10 rounded-2xl p-4 flex flex-col justify-between backdrop-blur-xl">
                    <div className="flex justify-between items-center">
                        <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Riesgo Canónico por Trade</span>
                        <span className="text-[8px] font-mono font-bold text-neon-cyan bg-neon-cyan/10 px-1.5 py-0.5 rounded border border-neon-cyan/20">
                            SOP-41 (2.50%)
                        </span>
                    </div>
                    <span className="text-xl font-black font-mono text-neon-cyan mt-1">
                        ${(data?.risk_config?.risk_usd_per_trade ?? 0).toFixed(2)} USDT
                    </span>
                    <span className="text-[8px] font-mono text-white/40 mt-2">
                        🛡️ Techo Nocional Máx: 5.0x (${((data?.equity ?? 0) * 5).toFixed(2)} USDT)
                    </span>
                </div>

                {/* 3. Flotante Neto Cripto */}
                <div className="bg-[#0A0F1D]/80 border border-white/10 rounded-2xl p-4 flex flex-col justify-between backdrop-blur-xl">
                    <div className="flex justify-between items-center">
                        <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Flotante No Realizado</span>
                        <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded ${(data?.total_floating_pnl ?? 0) >= 0 ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'}`}>
                            {(data?.total_floating_pnl ?? 0) >= 0 ? 'PROFIT' : 'DRAWDOWN'}
                        </span>
                    </div>
                    <span className={`text-xl font-black font-mono mt-1 ${(data?.total_floating_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {(data?.total_floating_pnl ?? 0) >= 0 ? '+' : ''}${(data?.total_floating_pnl ?? 0).toFixed(2)} USDT
                    </span>
                    <span className="text-[8px] font-mono text-white/40 mt-2">
                        Margen Utilizado: ${(data?.used_margin ?? 0).toFixed(2)} USDT
                    </span>
                </div>

                {/* 4. Posiciones y Órdenes Activas */}
                <div className="bg-[#0A0F1D]/80 border border-white/10 rounded-2xl p-4 flex flex-col justify-between backdrop-blur-xl">
                    <div className="flex justify-between items-center">
                        <span className="text-[9px] font-mono font-bold text-white/40 uppercase">Exposición Activa</span>
                        <span className="text-[8px] font-mono font-bold text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded border border-purple-500/20">
                            HEDGE ISOLATED
                        </span>
                    </div>
                    <span className="text-xl font-black font-mono text-purple-300 mt-1">
                        {data?.positions_count ?? 0} Posición(es)
                    </span>
                    <span className="text-[8px] font-mono text-white/40 mt-2">
                        {data?.pending_orders_count ?? 0} Órdenes Límite / TPs en exchange
                    </span>
                </div>
            </div>

            {/* Módulo 1: Posiciones Abiertas Vivas en Bitunix */}
            <div className="mb-6 bg-[#060B14]/80 border border-white/10 rounded-2xl p-4 backdrop-blur-xl shadow-xl">
                <div className="flex items-center justify-between mb-4 border-b border-white/5 pb-3">
                    <span className="text-xs font-black text-white/90 uppercase tracking-widest flex items-center gap-2">
                        <Activity size={14} className="text-amber-400 animate-pulse" /> POSICIONES ACTIVAS EN BITUNIX (FUTUROS EN EJECUCIÓN)
                    </span>
                    <span className="text-[9px] font-mono text-white/40">
                        Sincronización API cada 3 segundos
                    </span>
                </div>

                {(!data?.positions || data.positions.length === 0) ? (
                    <div className="py-8 flex flex-col items-center justify-center text-center border border-dashed border-white/5 rounded-xl bg-black/20">
                        <ShieldCheck size={32} className="text-emerald-400/40 mb-2" />
                        <p className="text-xs font-mono font-bold text-white/70">SIN POSICIONES ABIERTAS EN BITUNIX</p>
                        <p className="text-[10px] font-mono text-white/30 mt-0.5">Capital 100% disponible esperando señales de confluencia institucional</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 font-mono">
                        {data.positions.map((pos) => {
                            const isProfit = pos.unrealized_pnl >= 0;
                            const isLong = pos.side === 'LONG';
                            return (
                                <div key={pos.position_id || pos.symbol} className="bg-black/50 border border-white/10 hover:border-amber-500/30 rounded-xl p-4 flex flex-col justify-between transition-all shadow-lg">
                                    {/* Top Line */}
                                    <div className="flex justify-between items-start mb-3">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-base font-black text-white">{pos.symbol}</span>
                                                <span className={`text-[9px] font-black px-2 py-0.5 rounded-md flex items-center gap-0.5 ${
                                                    isLong ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                                                }`}>
                                                    {isLong ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />} {pos.side}
                                                </span>
                                                <span className="text-[8px] font-mono text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">
                                                    {pos.leverage}x
                                                </span>
                                            </div>
                                            <p className="text-[9px] text-white/40 mt-0.5">PosId: #{pos.position_id || 'N/A'}</p>
                                        </div>

                                        <div className="text-right">
                                            <span className={`text-base font-black tracking-tight ${isProfit ? 'text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]' : 'text-rose-400'}`}>
                                                {isProfit ? `+$${pos.unrealized_pnl.toFixed(2)}` : `-$${Math.abs(pos.unrealized_pnl).toFixed(2)}`} USDT
                                            </span>
                                            <span className={`text-[9px] block font-bold ${isProfit ? 'text-emerald-400/80' : 'text-rose-400/80'}`}>
                                                ({isProfit ? '+' : ''}{pos.unrealized_pnl_pct.toFixed(2)}% ROI)
                                            </span>
                                        </div>
                                    </div>

                                    {/* Metrics Grid */}
                                    <div className="grid grid-cols-4 gap-2 py-2 border-t border-b border-white/5 text-[9px] mb-3">
                                        <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                                            <span className="text-white/40 block">Contratos</span>
                                            <span className="text-white font-bold">{pos.qty}</span>
                                        </div>
                                        <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                                            <span className="text-white/40 block">Entrada</span>
                                            <span className="text-white font-bold">${pos.entry_price.toFixed(4)}</span>
                                        </div>
                                        <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                                            <span className="text-white/40 block">Mark Actual</span>
                                            <span className="text-amber-400 font-bold">${pos.mark_price.toFixed(4)}</span>
                                        </div>
                                        <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                                            <span className="text-white/40 block">Margen Aislado</span>
                                            <span className="text-white font-bold">${pos.isolated_margin.toFixed(2)}</span>
                                        </div>
                                    </div>

                                    {/* Protection Section: SL y TPs */}
                                    <div className="space-y-2 text-[9px]">
                                        {/* Stop Loss Banner */}
                                        <div className={`p-2 rounded-lg flex items-center justify-between border ${
                                            pos.active_sl?.is_protected 
                                                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
                                                : 'bg-rose-500/20 border-rose-500/40 text-rose-300 animate-pulse'
                                        }`}>
                                            <span className="flex items-center gap-1 font-bold">
                                                <ShieldCheck size={12} /> STOP LOSS CONDICIONAL:
                                            </span>
                                            <span className="font-mono font-black text-[11px]">
                                                {pos.active_sl?.price ? `$${pos.active_sl.price.toFixed(4)} USDT` : '⚠️ SIN STOP LOSS (VULNERABLE)'}
                                            </span>
                                        </div>

                                        {/* Take Profits en Libro */}
                                        {pos.take_profits && pos.take_profits.length > 0 && (
                                            <div className="bg-white/[0.02] border border-white/5 rounded-lg p-2">
                                                <span className="text-[8px] font-bold text-white/40 uppercase block mb-1">
                                                    🎯 Órdenes de Take Profit en Exchange ({pos.take_profits.length} tramos):
                                                </span>
                                                <div className="grid grid-cols-3 gap-1">
                                                    {pos.take_profits.map((tp, idx) => (
                                                        <div key={tp.order_id} className="bg-black/40 border border-white/5 p-1 rounded text-center">
                                                            <span className="text-[7.5px] text-neon-cyan block">TP{idx+1} ({tp.qty} cts)</span>
                                                            <span className="text-emerald-400 font-bold">${tp.price.toFixed(4)}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Módulo 2: Órdenes Límite Pendientes en Bitunix */}
            <div className="mb-6 bg-[#060B14]/80 border border-white/10 rounded-2xl p-4 backdrop-blur-xl shadow-xl">
                <div className="flex items-center justify-between mb-4 border-b border-white/5 pb-3">
                    <span className="text-xs font-black text-white/90 uppercase tracking-widest flex items-center gap-2">
                        <Layers size={14} className="text-neon-cyan" /> ÓRDENES PENDIENTES EN EXCHANGE ({data?.pending_orders_count ?? 0})
                    </span>
                    <span className="text-[9px] font-mono text-white/40">
                        Órdenes de Entrada (OPEN) y Salidas Programadas (CLOSE)
                    </span>
                </div>

                {(!data?.pending_orders || data.pending_orders.length === 0) ? (
                    <div className="py-6 text-center text-white/30 font-mono text-[10px]">
                        No hay órdenes pendientes en el libro de Bitunix.
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left font-mono text-[10px]">
                            <thead>
                                <tr className="border-b border-white/5 text-white/40 uppercase text-[8px]">
                                    <th className="py-2 px-3">ID Orden</th>
                                    <th className="py-2 px-3">Par</th>
                                    <th className="py-2 px-3">Lado</th>
                                    <th className="py-2 px-3">Tipo</th>
                                    <th className="py-2 px-3">Precio Límite</th>
                                    <th className="py-2 px-3">Contratos</th>
                                    <th className="py-2 px-3">Objetivo</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {data.pending_orders.map((ord) => {
                                    const isClose = ord.trade_side === 'CLOSE' || ord.reduce_only;
                                    return (
                                        <tr key={ord.order_id} className="hover:bg-white/[0.02] transition-all">
                                            <td className="py-2 px-3 text-white/50">#{ord.order_id}</td>
                                            <td className="py-2 px-3 font-bold text-white">{ord.symbol}</td>
                                            <td className="py-2 px-3">
                                                <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold ${
                                                    ord.side === 'BUY' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                                                }`}>
                                                    {ord.side}
                                                </span>
                                            </td>
                                            <td className="py-2 px-3 text-white/70">{ord.order_type}</td>
                                            <td className="py-2 px-3 font-bold text-amber-400">${ord.price.toFixed(4)}</td>
                                            <td className="py-2 px-3 text-white">{ord.qty}</td>
                                            <td className="py-2 px-3">
                                                <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold ${
                                                    isClose ? 'bg-purple-500/10 text-purple-300 border border-purple-500/20' : 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/20'
                                                }`}>
                                                    {isClose ? '🎯 TAKE PROFIT' : '🚀 ENTRADA OTE'}
                                                </span>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Módulo 3: Simulador / Calculadora Canónica SOP-41 (2.50%) */}
            <div className="bg-[#060B14]/80 border border-white/10 rounded-2xl p-4 backdrop-blur-xl shadow-xl font-mono">
                <div className="flex items-center justify-between mb-3 border-b border-white/5 pb-2">
                    <span className="text-xs font-black text-white/90 uppercase tracking-widest flex items-center gap-2">
                        <Crosshair size={14} className="text-emerald-400" /> CALCULADORA DE RIESGO INSTITUCIONAL (SOP-41 2.50%)
                    </span>
                    <span className="text-[9px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                        MAX LOSS: ${simRiskUsd.toFixed(2)} USDT
                    </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                    <div>
                        <label className="text-[9px] text-white/40 block mb-1">Precio de Entrada Proyectado (USDT):</label>
                        <input 
                            type="number" 
                            step="0.001"
                            placeholder="Ej: 7.962"
                            value={simEntry || ''}
                            onChange={(e) => setSimEntry(parseFloat(e.target.value) || 0)}
                            className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-amber-400 focus:outline-none"
                        />
                    </div>
                    <div>
                        <label className="text-[9px] text-white/40 block mb-1">Precio Stop Loss Técnico (USDT):</label>
                        <input 
                            type="number" 
                            step="0.001"
                            placeholder="Ej: 7.683"
                            value={simSl || ''}
                            onChange={(e) => setSimSl(parseFloat(e.target.value) || 0)}
                            className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:border-rose-400 focus:outline-none"
                        />
                    </div>
                    <div className="bg-black/30 border border-white/5 rounded-xl p-2.5 flex flex-col justify-between">
                        <span className="text-[8px] text-white/40 uppercase">Contratos Sugeridos:</span>
                        <span className="text-lg font-black text-emerald-400">
                            {simContracts > 0 ? `${simContracts.toFixed(1)} Contratos` : '---'}
                        </span>
                        <span className="text-[7.5px] text-white/40">
                            Nocional: ${simNotional.toFixed(2)} USDT {isExceedingNotional ? '⚠️ (Excede 5x cap)' : '✅ (Seguro)'}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}

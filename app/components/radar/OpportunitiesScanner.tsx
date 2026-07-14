'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, ShieldCheck, Zap, ArrowUpRight, ArrowDownRight, RefreshCw, Layers } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';

interface ChecklistItem {
    factor: string;
    status: string;
    detail: string;
}

interface Opportunity {
    asset: string;
    direction: string;
    type: string;
    price: number;
    stop_loss: number;
    tp1: number;
    tp2: number;
    tp3: number;
    rr_ratio_tp3: number;
    confluence_score: number;
    checklist: ChecklistItem[];
    is_active_trigger: boolean;
    ote_chasing?: boolean;
    session?: string;
}

export default function OpportunitiesScanner() {
    const [activeTab, setActiveTab] = useState<'scalp' | 'swing'>('scalp');
    const [opportunities, setOpportunities] = useState<{ scalp: Opportunity[]; swing: Opportunity[] }>({
        scalp: [],
        swing: []
    });
    const [expandedAsset, setExpandedAsset] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const fetchOpps = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/v1/scanner/opportunities');
            if (res.ok) {
                const data = await res.json();
                setOpportunities({
                    scalp: data.scalp || [],
                    swing: data.swing || []
                });
            }
        } catch (err) {
            console.error("Error fetching scanner opportunities:", err);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchOpps();
        const interval = setInterval(fetchOpps, 15000); // Refresco automático cada 15 segundos
        return () => clearInterval(interval);
    }, []);

    const handleManualRefresh = () => {
        setRefreshing(true);
        fetchOpps();
    };

    const currentOpps = activeTab === 'scalp' ? opportunities.scalp : opportunities.swing;

    const toggleExpand = (assetKey: string) => {
        if (expandedAsset === assetKey) {
            setExpandedAsset(null);
        } else {
            setExpandedAsset(assetKey);
        }
    };

    const getSessionBadge = (session?: string) => {
        switch (session) {
            case 'LONDON':    return { label: '🇬🇧 LONDON',   color: 'text-blue-400 border-blue-400/20 bg-blue-400/5' };
            case 'NEW_YORK':  return { label: '🗽 NEW YORK',  color: 'text-purple-400 border-purple-400/20 bg-purple-400/5' };
            case 'ASIA':      return { label: '🌏 ASIA',      color: 'text-amber-400 border-amber-400/20 bg-amber-400/5' };
            case 'OFF_HOURS': return { label: '🌙 OFF-HOURS', color: 'text-white/30 border-white/5 bg-white/[0.02]' };
            case 'LIVE_SIGNAL': return { label: '🔥 TRIGGER', color: 'text-neon-green border-neon-green/20 bg-neon-green/5' };
            default:          return null;
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status.toUpperCase()) {
            case 'CONFIRMADO':
            case 'ELITE':
            case 'ACTIVO':
            case 'APROBADO':
            case 'FRESCO':
            case 'FAVORABLE':
            case 'ALINEADO':
            case 'INSTITUCIONAL':
                return '✓';
            case 'PARCIAL':
            case 'VOLÁTIL':
            case 'DECAYENDO':
            case 'PRECAUCIÓN':
            case 'ALERTA':
                return '◑';
            default:
                return '✗';
        }
    };

    const getStatusColor = (status: string) => {
        switch (status.toUpperCase()) {
            case 'CONFIRMADO':
            case 'ELITE':
            case 'ACTIVO':
            case 'APROBADO':
            case 'FRESCO':
            case 'FAVORABLE':
            case 'ALINEADO':
            case 'INSTITUCIONAL':
                return 'text-neon-green bg-neon-green/10 border-neon-green/20';
            case 'PARCIAL':
            case 'VOLÁTIL':
            case 'DECAYENDO':
            case 'PRECAUCIÓN':
            case 'ALERTA':
                return 'text-amber-400 bg-amber-400/10 border-amber-400/20';
            default:
                return 'text-white/30 bg-white/5 border-white/5';
        }
    };

    return (
        <div className="w-full bg-[#050B14]/40 border border-white/5 rounded-3xl overflow-hidden backdrop-blur-md">
            {/* Header Area */}
            <div className="p-6 border-b border-white/5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-neon-cyan/15 rounded-xl border border-neon-cyan/20">
                        <Activity size={18} className="text-neon-cyan animate-pulse" />
                    </div>
                    <div>
                        <h2 className="text-sm font-bold text-white uppercase tracking-widest">
                            Escáner de Oportunidades
                        </h2>
                        <p className="text-[10px] text-white/40 font-mono mt-0.5">
                            ANÁLISIS MULTITEMPORAL DE 20 ACTIVOS EN VIVO
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {/* Timeframe Selector tabs */}
                    <div className="flex bg-[#070E18] p-1 rounded-xl border border-white/5">
                        <button
                            onClick={() => { setActiveTab('scalp'); setExpandedAsset(null); }}
                            className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                                activeTab === 'scalp'
                                    ? 'bg-neon-cyan/15 text-neon-cyan border border-neon-cyan/25'
                                    : 'text-white/50 hover:text-white border border-transparent'
                            }`}
                        >
                            Scalp (15m)
                        </button>
                        <button
                            onClick={() => { setActiveTab('swing'); setExpandedAsset(null); }}
                            className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                                activeTab === 'swing'
                                    ? 'bg-neon-cyan/15 text-neon-cyan border border-neon-cyan/25'
                                    : 'text-white/50 hover:text-white border border-transparent'
                            }`}
                        >
                            Swing (4h)
                        </button>
                    </div>

                    <button
                        onClick={handleManualRefresh}
                        disabled={refreshing}
                        className="p-2 bg-[#070E18] hover:bg-white/5 border border-white/5 rounded-xl text-white/70 hover:text-white transition-all disabled:opacity-50"
                    >
                        <RefreshCw size={14} className={refreshing ? "animate-spin text-neon-cyan" : ""} />
                    </button>
                </div>
            </div>

            {/* List / Cards Container */}
            <div className="p-6">
                {loading ? (
                    <div className="h-60 flex flex-col justify-center items-center gap-3">
                        <RefreshCw size={24} className="animate-spin text-neon-cyan" />
                        <span className="text-xs text-white/40 font-mono">BARRIDA INICIAL DE CONFLUENCIA EN CURSO...</span>
                    </div>
                ) : currentOpps.length === 0 ? (
                    <div className="h-60 flex flex-col justify-center items-center gap-2 border border-dashed border-white/5 rounded-2xl bg-white/[0.01]">
                        <Layers size={32} className="text-white/10" />
                        <span className="text-xs text-white/40 font-mono">CALIBRANDO SETUPS DE MERCADO...</span>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        <AnimatePresence mode="popLayout">
                            {currentOpps.map((opp, idx) => {
                                const assetKey = `${opp.asset}-${opp.direction}-${idx}`;
                                const isExpanded = expandedAsset === assetKey;
                                const isLong = opp.direction.toUpperCase() === 'LONG';
                                
                                return (
                                    <motion.div
                                        key={assetKey}
                                        layout
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, scale: 0.95 }}
                                        transition={{ duration: 0.2 }}
                                        className={`bg-[#060D17]/80 border rounded-2xl p-5 hover:border-white/15 transition-all overflow-hidden flex flex-col justify-between ${
                                            opp.is_active_trigger
                                                ? 'border-neon-green/30 shadow-[0_0_15px_rgba(16,185,129,0.05)]'
                                                : opp.ote_chasing
                                                ? 'border-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.04)]'
                                                : 'border-white/5'
                                        }`}
                                    >
                                        <div>
                                            {/* OTE Watchdog Alert Banner */}
                                            {opp.ote_chasing && (
                                                <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2 mb-3">
                                                    <span className="text-amber-400 text-[10px]">⚠️</span>
                                                    <span className="text-amber-400 text-[9px] font-mono font-bold uppercase tracking-wider">OTE Watchdog: Persiguiendo Precio</span>
                                                </div>
                                            )}

                                            {/* Top Line */}
                                            <div className="flex items-center justify-between mb-4">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm font-black text-white tracking-tight">{opp.asset}</span>
                                                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                                                        isLong 
                                                            ? 'text-neon-green bg-neon-green/10 border border-neon-green/20'
                                                            : 'text-neon-red bg-neon-red/10 border border-neon-red/20'
                                                    }`}>
                                                        {opp.direction}
                                                    </span>
                                                </div>

                                                <div className="flex items-center gap-1.5">
                                                    {/* Session Badge */}
                                                    {(() => { const sb = getSessionBadge(opp.session); return sb ? (
                                                        <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded border ${sb.color}`}>
                                                            {sb.label}
                                                        </span>
                                                    ) : null; })()}
                                                    <span className={`text-[9px] font-mono px-2 py-0.5 rounded border ${
                                                        opp.is_active_trigger
                                                            ? 'text-neon-green bg-neon-green/5 border-neon-green/20 font-bold'
                                                            : 'text-white/40 bg-white/5 border-white/5'
                                                    }`}>
                                                        {opp.is_active_trigger ? '🔥 TRIGGER ACTIVO' : 'VIRTUAL SETUP'}
                                                    </span>
                                                </div>
                                            </div>

                                            {/* Score and Stats */}
                                            <div className="grid grid-cols-2 gap-4 mb-4 bg-white/[0.02] border border-white/5 rounded-xl p-3">
                                                <div>
                                                    <span className="block text-[9px] text-white/40 uppercase font-mono">Confluencia</span>
                                                    <span className="text-lg font-black text-white font-mono">{opp.confluence_score}%</span>
                                                    {/* Progress bar */}
                                                    <div className="w-full bg-white/5 h-1 rounded-full mt-1.5 overflow-hidden">
                                                        <div 
                                                            className={`h-full rounded-full ${isLong ? 'bg-neon-green' : 'bg-neon-red'}`}
                                                            style={{ width: `${opp.confluence_score}%` }}
                                                        />
                                                    </div>
                                                </div>

                                                <div>
                                                    <span className="block text-[9px] text-white/40 uppercase font-mono">R:R Proyectado</span>
                                                    <span className="text-lg font-black text-white font-mono text-neon-cyan">{opp.rr_ratio_tp3}:1</span>
                                                    <span className="block text-[8px] text-white/30 font-mono mt-0.5">TARGET TP3</span>
                                                </div>
                                            </div>

                                            {/* Levels */}
                                            <div className="space-y-1 text-xs font-mono mb-4 border-t border-white/5 pt-3">
                                                <div className="flex justify-between">
                                                    <span className="text-white/40">Entrada:</span>
                                                    <span className="text-white/80 font-bold">${formatCurrency(opp.price)}</span>
                                                </div>
                                                <div className="flex justify-between">
                                                    <span className="text-white/40">Stop Loss:</span>
                                                    <span className="text-neon-red">${formatCurrency(opp.stop_loss)}</span>
                                                </div>
                                                <div className="flex justify-between">
                                                    <span className="text-white/40">TP1 (Cobertura):</span>
                                                    <span className="text-neon-cyan">${formatCurrency(opp.tp1)}</span>
                                                </div>
                                                <div className="flex justify-between">
                                                    <span className="text-white/40">TP3 (Estructural):</span>
                                                    <span className="text-neon-green">${formatCurrency(opp.tp3)}</span>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Toggle button and checklist accordion */}
                                        <div className="mt-2 border-t border-white/5 pt-3">
                                            <button
                                                onClick={() => toggleExpand(assetKey)}
                                                className="w-full text-center py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-all text-[10px] font-bold uppercase tracking-wider font-mono flex items-center justify-center gap-1.5"
                                            >
                                                {isExpanded ? 'Ocultar Confluencias' : 'Ver Checklist Confluencia'}
                                                {opp.direction.toUpperCase() === 'LONG' ? (
                                                    <ArrowUpRight size={10} className="text-neon-green" />
                                                ) : (
                                                    <ArrowDownRight size={10} className="text-neon-red" />
                                                )}
                                            </button>

                                            <AnimatePresence>
                                                {isExpanded && (
                                                    <motion.div
                                                        initial={{ height: 0, opacity: 0 }}
                                                        animate={{ height: 'auto', opacity: 1 }}
                                                        exit={{ height: 0, opacity: 0 }}
                                                        className="overflow-hidden mt-3 space-y-1.5"
                                                    >
                                                        {opp.checklist.map((item, cIdx) => (
                                                            <div 
                                                                key={cIdx} 
                                                                className={`flex items-start justify-between p-2 rounded border text-[10px] font-mono leading-tight ${getStatusColor(item.status)}`}
                                                            >
                                                                <div className="flex-1 pr-2">
                                                                    <span className="block font-bold">{item.factor}</span>
                                                                    <span className="opacity-70 text-[9px]">{item.detail}</span>
                                                                </div>
                                                                <span className="font-bold">{getStatusIcon(item.status)}</span>
                                                            </div>
                                                        ))}
                                                    </motion.div>
                                                )}
                                            </AnimatePresence>
                                        </div>
                                    </motion.div>
                                );
                            })}
                        </AnimatePresence>
                    </div>
                )}
            </div>
        </div>
    );
}

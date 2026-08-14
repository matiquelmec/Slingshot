'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, ShieldCheck, Zap, ArrowUpRight, ArrowDownRight, RefreshCw, Layers } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';
import { AccountProfileSelector, PROFILES_CONFIG } from '../signals/AccountProfileSelector';
import { FtmoShieldWidget } from '../signals/FtmoShieldWidget';
import { AccountProfileType, FtmoPhase } from '../../types/signal';
import { calculateMt5Lots, MarketCategory, getAssetMarketCategory } from '../../utils/ftmoSpecs';

interface ChecklistItem {
    factor: string;
    status: string;
    detail: string;
}

interface AssetHealth {
    ker: number;
    status: string;
    is_quarantined: boolean;
}

interface Opportunity {
    asset: string;
    direction: string;
    type: string;
    price: number;
    stop_loss: number;
    sl_dist_pct?: number;
    position_size_usdt?: number;
    tp1: number;
    tp2: number;
    tp3: number;
    rr_ratio_tp3: number;
    confluence_score: number;
    checklist: ChecklistItem[];
    is_active_trigger: boolean;
    ote_chasing?: boolean;
    session?: string;
    asset_health?: AssetHealth;
}

const EDUCATIONAL_NOTES: Record<string, string> = {
    "Salud de Activo (KER)": "El indicador KER mide si el precio tiene mechas erráticas. Si es < 0.22, entra en Cuarentena y exige ≥ 65% de confluencia para proteger tu capital.",
    "Alineación Macro BTC": "Filtro V12 Sovereign: Evita operar Altcoins si van en dirección opuesta a la tendencia macro de Bitcoin para prevenir trampas.",
    "Narrativa SMC": "Estructura Institucional CHoCH/BOS. Valida que el impulso siga el flujo de volumen principal.",
    "Zonas POI": "Point of Interest (Order Blocks o FVGs). Zonas con bloques de órdenes institucionales pendientes.",
    "Yosh Order Flow": "Detección de trampas de liquidez y ventana de oro (Golden Window 10:00 - 11:30 AM EST).",
    "Liquidez": "Barrido de liquidez (Liquidity Sweep). Los creadores de mercado sacan a los minoristas antes del movimiento verdadero.",
    "Huella RVOL": "Volumen Relativo > 1.5x. Confirma la entrada de volumen transaccional de bancos e instituciones.",
    "Golden Pocket": "Zona Fibonacci 61.8% - 78.6% (OTE). Área de máxima probabilidad de reacción del precio.",
    "SMT Divergence": "Divergencia entre activos correlacionados (ej. BTC vs ETH) que revela acumulación u ocultamiento del Smart Money.",
    "Order Flow Delta": "Presión neta de compradores agresivos (Takers) vs vendedores agresivos en el libro de órdenes.",
    "Tendencia Macro EMA 200": "Confirma que la entrada no opere en contra de la tendencia promedio de las últimas 200 velas."
};

export default function OpportunitiesScanner() {
    const [activeTab, setActiveTab] = useState<'scalp' | 'swing'>('scalp');
    const [opportunities, setOpportunities] = useState<{ scalp: Opportunity[]; swing: Opportunity[] }>({
        scalp: [],
        swing: []
    });
    const [filterHighConfluence, setFilterHighConfluence] = useState(false);
    const [filterAdaptiveKER, setFilterAdaptiveKER] = useState(true);
    const [marketCategoryFilter, setMarketCategoryFilter] = useState<MarketCategory>('ALL');
    const [expandedAsset, setExpandedAsset] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [accountProfile, setAccountProfile] = useState<AccountProfileType>('FTMO_100K');
    const [ftmoPhase, setFtmoPhase] = useState<FtmoPhase>('PHASE_1');
    const [copiedAsset, setCopiedAsset] = useState<string | null>(null);

    const activeProfileConfig = PROFILES_CONFIG[accountProfile](ftmoPhase);

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

    const currentOppsRaw = activeTab === 'scalp' ? opportunities.scalp : opportunities.swing;
    
    let filteredOpps = currentOppsRaw;
    
    // Filtro por Categoría de Mercado (FTMO Institucional vs Altcoins)
    if (marketCategoryFilter === 'FTMO_INSTITUTIONAL') {
        filteredOpps = filteredOpps.filter(o => getAssetMarketCategory(o.asset) === 'FTMO_INSTITUTIONAL');
    } else if (marketCategoryFilter === 'CRYPTO_ALTCOINS') {
        filteredOpps = filteredOpps.filter(o => getAssetMarketCategory(o.asset) === 'CRYPTO_ALTCOINS');
    }

    if (filterHighConfluence) {
        filteredOpps = filteredOpps.filter(o => o.confluence_score >= 50);
    }
    
    if (filterAdaptiveKER) {
        const HIGH_NOISE_ASSETS = ['BNBUSDT', 'XRPUSDT', 'SOLUSDT', 'LINKUSDT'];
        // En modo adaptativo KER, bloquea activos ruidosos o en cuarentena a menos que alcancen confluencia ELITE (>= 65%)
        filteredOpps = filteredOpps.filter(o => {
            const assetUpper = (o.asset || '').toUpperCase();
            const isQuarantined = o.asset_health?.is_quarantined || o.asset_health?.status === 'QUARANTINED';
            const isKnownHighNoise = HIGH_NOISE_ASSETS.includes(assetUpper);
            
            if (isQuarantined || isKnownHighNoise) {
                return o.confluence_score >= 65; // Exige 65%+ para salir del filtro antiruido
            }
            return o.confluence_score >= 45;
        });
    }
    
    // Ordenar de mayor a menor confluencia (Prioridad Máxima Primero)
    const currentOpps = [...filteredOpps].sort((a, b) => b.confluence_score - a.confluence_score);

    const toggleExpand = (assetKey: string) => {
        if (expandedAsset === assetKey) {
            setExpandedAsset(null);
        } else {
            setExpandedAsset(assetKey);
        }
    };

    const getSessionBadge = (session?: string) => {
        if (!session) return null;
        const s = session.toUpperCase();
        if (s.includes('NEW_YORK') || s.includes('NY')) {
            return { label: '🗽 NEW YORK', color: 'text-purple-400 border-purple-400/20 bg-purple-400/5' };
        }
        if (s.includes('LONDON')) {
            return { label: '🇬🇧 LONDON', color: 'text-blue-400 border-blue-400/20 bg-blue-400/5' };
        }
        if (s.includes('ASIA')) {
            return { label: '🌏 ASIA', color: 'text-amber-400 border-amber-400/20 bg-amber-400/5' };
        }
        if (s.includes('OFF_HOURS')) {
            return { label: '🌙 OFF-HOURS', color: 'text-white/30 border-white/5 bg-white/[0.02]' };
        }
        if (s.includes('LIVE_SIGNAL') || s.includes('TRIGGER')) {
            return { label: '🔥 TRIGGER', color: 'text-neon-green border-neon-green/20 bg-neon-green/5' };
        }
        return { label: `🌐 ${s}`, color: 'text-white/40 border-white/10 bg-white/5' };
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
                    {/* KER Adaptive Filter Toggle */}
                    <button
                        onClick={() => setFilterAdaptiveKER(!filterAdaptiveKER)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all border flex items-center gap-1.5 ${
                            filterAdaptiveKER
                                ? 'bg-neon-cyan/20 text-neon-cyan border-neon-cyan/40 shadow-[0_0_12px_rgba(6,182,212,0.2)]'
                                : 'bg-[#070E18] text-white/50 border-white/5 hover:text-white hover:border-white/10'
                        }`}
                        title="Filtro Adaptativo Inteligente de Ruido con Kaufman Efficiency Ratio (KER)"
                    >
                        <Zap size={13} className={filterAdaptiveKER ? "text-neon-cyan animate-pulse" : ""} />
                        <span>Filtro Adaptativo KER</span>
                    </button>

                    {/* High Confluence Filter Toggle */}
                    <button
                        onClick={() => setFilterHighConfluence(!filterHighConfluence)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all border flex items-center gap-1.5 ${
                            filterHighConfluence
                                ? 'bg-neon-green/20 text-neon-green border-neon-green/40 shadow-[0_0_12px_rgba(16,185,129,0.2)]'
                                : 'bg-[#070E18] text-white/50 border-white/5 hover:text-white hover:border-white/10'
                        }`}
                        title="Filtra oportunidades con >50% confluencia alineadas a la EMA 200 (Profit Factor 3.00)"
                    >
                        <ShieldCheck size={13} className={filterHighConfluence ? "text-neon-green" : ""} />
                        <span>Solo &ge; 50% Confluencia</span>
                    </button>

                    {/* Market Category Selector Tabs (FTMO vs Altcoins) */}
                    <div className="flex bg-[#070E18] p-1 rounded-xl border border-white/5 text-xs font-mono">
                        <button
                            onClick={() => setMarketCategoryFilter('ALL')}
                            className={`px-3 py-1.5 rounded-lg font-bold transition-all ${
                                marketCategoryFilter === 'ALL'
                                    ? 'bg-white/15 text-white border border-white/20'
                                    : 'text-white/40 hover:text-white border border-transparent'
                            }`}
                        >
                            🌐 Todos
                        </button>
                        <button
                            onClick={() => setMarketCategoryFilter('FTMO_INSTITUTIONAL')}
                            className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
                                marketCategoryFilter === 'FTMO_INSTITUTIONAL'
                                    ? 'bg-neon-green/20 text-neon-green border border-neon-green/40 shadow-[0_0_10px_rgba(16,185,129,0.2)]'
                                    : 'text-white/40 hover:text-neon-green border border-transparent'
                            }`}
                        >
                            🏛️ FTMO (Oro, BTC, ETH)
                        </button>
                        <button
                            onClick={() => setMarketCategoryFilter('CRYPTO_ALTCOINS')}
                            className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
                                marketCategoryFilter === 'CRYPTO_ALTCOINS'
                                    ? 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/40 shadow-[0_0_10px_rgba(6,182,212,0.2)]'
                                    : 'text-white/40 hover:text-neon-cyan border border-transparent'
                            }`}
                        >
                            ⚡ Altcoins (Bitunix)
                        </button>
                    </div>

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

            {/* Selector de Perfil de Cuenta & Escudo FTMO en el Escáner */}
            <div className="px-6 py-4 border-b border-white/5 bg-black/40 flex flex-col gap-2.5">
                <AccountProfileSelector
                    currentProfile={accountProfile}
                    currentPhase={ftmoPhase}
                    onProfileChange={(p) => setAccountProfile(p)}
                    onPhaseChange={(ph) => setFtmoPhase(ph)}
                />
                {activeProfileConfig.isFtmo && (
                    <FtmoShieldWidget
                        config={activeProfileConfig}
                        currentProfitUsd={0}
                        dailyLossUsd={0}
                    />
                )}
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
                                        className={`bg-[#060D17]/80 border rounded-2xl p-5 hover:border-white/20 transition-all flex flex-col justify-between relative ${
                                            opp.confluence_score >= 60
                                                ? 'border-neon-green/40 shadow-[0_0_20px_rgba(16,185,129,0.15)] ring-1 ring-neon-green/20'
                                                : opp.confluence_score >= 50
                                                ? 'border-neon-cyan/35 shadow-[0_0_12px_rgba(6,182,212,0.1)]'
                                                : opp.is_active_trigger
                                                ? 'border-neon-green/30 shadow-[0_0_15px_rgba(16,185,129,0.05)]'
                                                : opp.ote_chasing
                                                ? 'border-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.04)]'
                                                : 'border-white/5 opacity-80 hover:opacity-100'
                                        }`}
                                    >
                                        <div>
                                            {/* Insignia de Categoría Institucional */}
                                            <div className="flex items-center justify-between bg-cyan-500/10 border border-cyan-500/25 rounded-xl px-3 py-1 mb-2.5">
                                                <span className="text-neon-cyan text-[8.5px] font-mono font-bold uppercase tracking-wider flex items-center gap-1.5">
                                                    <span>🎯 ORDEN LÍMITE PENDIENTE (ENTRADA SMC)</span>
                                                </span>
                                                <span className="text-white/40 text-[8px] font-mono">COPIAR AL EXCHANGE</span>
                                            </div>
                                            {/* Priority Banner for High Confluence */}
                                            {opp.confluence_score >= 60 ? (
                                                <div className="flex items-center justify-between bg-neon-green/10 border border-neon-green/25 rounded-xl px-3 py-1.5 mb-3">
                                                    <span className="text-neon-green text-[9px] font-mono font-black uppercase tracking-wider flex items-center gap-1">
                                                        <span>👑 PRIORIDAD ELITE</span>
                                                        <span className="text-white/40">|</span>
                                                        <span>PROFIT FACTOR 3.00</span>
                                                    </span>
                                                    <span className="text-neon-green text-[8px] font-mono font-bold bg-neon-green/20 px-1.5 py-0.5 rounded">R:R 1:3.0+</span>
                                                </div>
                                            ) : opp.confluence_score >= 50 ? (
                                                <div className="flex items-center justify-between bg-neon-cyan/10 border border-neon-cyan/20 rounded-xl px-3 py-1.5 mb-3">
                                                    <span className="text-neon-cyan text-[9px] font-mono font-bold uppercase tracking-wider flex items-center gap-1">
                                                        <span>🎯 ALTA EXPECTATIVA</span>
                                                        <span className="text-white/40">|</span>
                                                        <span>ALINEADO EMA 200</span>
                                                    </span>
                                                    <span className="text-neon-cyan text-[8px] font-mono font-bold bg-neon-cyan/20 px-1.5 py-0.5 rounded">PASO 1 OK</span>
                                                </div>
                                            ) : null}

                                            {/* OTE Watchdog Alert Banner */}
                                            {opp.ote_chasing && (
                                                <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2 mb-3">
                                                    <span className="text-amber-400 text-[10px]">⚠️</span>
                                                    <span className="text-amber-400 text-[9px] font-mono font-bold uppercase tracking-wider">OTE Watchdog: Persiguiendo Precio</span>
                                                </div>
                                            )}

                                            {/* Top Line */}
                                            <div className="flex items-center justify-between mb-4">
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    <span className="text-sm font-black text-white tracking-tight">{opp.asset}</span>
                                                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                                                        isLong 
                                                            ? 'text-neon-green bg-neon-green/10 border border-neon-green/20'
                                                            : 'text-neon-red bg-neon-red/10 border border-neon-red/20'
                                                    }`}>
                                                        {opp.direction}
                                                    </span>

                                                    {/* Health KER Badge con Nota Educativa */}
                                                    {opp.asset_health && (
                                                        <div className="relative group/ker cursor-help">
                                                            <span className={`text-[9px] px-2 py-0.5 rounded-md font-mono font-bold border transition-all flex items-center gap-1 ${
                                                                opp.asset_health.is_quarantined || opp.asset_health.status === 'QUARANTINED'
                                                                    ? 'text-rose-400 bg-rose-500/15 border-rose-500/30'
                                                                    : opp.asset_health.status === 'OPTIMAL'
                                                                    ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                                                                    : 'text-amber-400 bg-amber-500/10 border-amber-500/20'
                                                            }`}>
                                                                {opp.asset_health.is_quarantined || opp.asset_health.status === 'QUARANTINED'
                                                                    ? `🔴 CUARENTENA (KER ${opp.asset_health.ker})`
                                                                    : opp.asset_health.status === 'OPTIMAL'
                                                                    ? `🟢 KER ${opp.asset_health.ker}`
                                                                    : `🟡 KER ${opp.asset_health.ker}`}
                                                            </span>
                                                            <div className="absolute left-0 bottom-full mb-1 hidden group-hover/ker:block z-50 w-64 p-2 bg-neutral-900/95 backdrop-blur-md border border-rose-500/30 rounded-lg shadow-xl text-[9px] text-white/90 font-mono leading-relaxed">
                                                                <span className="font-bold text-rose-400 block mb-0.5">📚 Nota Educativa (KER):</span>
                                                                {opp.asset_health.is_quarantined 
                                                                    ? "Activo con alto ruido y mechas erráticas. Se exige confluencia ≥ 65% para filtrar falsas rupturas de mercado."
                                                                    : "Estructura de precio limpia con baja mecha de ruido. Operativa ideal."}
                                                            </div>
                                                        </div>
                                                    )}
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
                                            <div className="space-y-1.5 text-xs font-mono mb-4 border-t border-white/5 pt-3">
                                                <div className="flex justify-between items-center group/level">
                                                    <span className="text-white/40">Entrada:</span>
                                                    <span 
                                                        onClick={() => {
                                                            navigator.clipboard.writeText(opp.price.toString());
                                                            // Efecto visual rápido
                                                            const el = document.getElementById(`copy-entry-${assetKey}`);
                                                            if (el) { el.innerText = "COPIADO"; setTimeout(() => el.innerText = "COPIAR", 1000); }
                                                        }}
                                                        className="text-white/80 font-bold cursor-pointer hover:text-neon-cyan flex items-center gap-1.5 active:scale-95 transition-all select-all"
                                                        title="Haz clic para copiar precio"
                                                    >
                                                        <span>{formatCurrency(opp.price)}</span>
                                                        <span id={`copy-entry-${assetKey}`} className="text-[7px] text-white/20 border border-white/10 px-1 py-0.5 rounded opacity-0 group-hover/level:opacity-100 transition-opacity font-sans">COPIAR</span>
                                                    </span>
                                                </div>
                                                <div className="flex justify-between items-center group/level">
                                                    <span className="text-white/40">Stop Loss:</span>
                                                    <span 
                                                        onClick={() => {
                                                            navigator.clipboard.writeText(opp.stop_loss.toString());
                                                            const el = document.getElementById(`copy-sl-${assetKey}`);
                                                            if (el) { el.innerText = "COPIADO"; setTimeout(() => el.innerText = "COPIAR", 1000); }
                                                        }}
                                                        className="text-neon-red font-bold cursor-pointer hover:text-neon-cyan flex items-center gap-1.5 active:scale-95 transition-all select-all"
                                                        title="Haz clic para copiar Stop Loss"
                                                    >
                                                        <span>{formatCurrency(opp.stop_loss)} <span className="text-[9px] opacity-70">(-{opp.sl_dist_pct ? opp.sl_dist_pct.toFixed(2) : ((Math.abs(opp.price - opp.stop_loss)/opp.price)*100).toFixed(2)}%)</span></span>
                                                        <span id={`copy-sl-${assetKey}`} className="text-[7px] text-white/20 border border-white/10 px-1 py-0.5 rounded opacity-0 group-hover/level:opacity-100 transition-opacity font-sans">COPIAR</span>
                                                    </span>
                                                </div>
                                                <div className="flex justify-between items-center group/level">
                                                    <span className="text-white/40">TP1 (Cobertura):</span>
                                                    <span 
                                                        onClick={() => {
                                                            navigator.clipboard.writeText(opp.tp1.toString());
                                                            const el = document.getElementById(`copy-tp1-${assetKey}`);
                                                            if (el) { el.innerText = "COPIADO"; setTimeout(() => el.innerText = "COPIAR", 1000); }
                                                        }}
                                                        className="text-neon-cyan font-bold cursor-pointer hover:text-white flex items-center gap-1.5 active:scale-95 transition-all select-all"
                                                        title="Haz clic para copiar TP1"
                                                    >
                                                        <span>{formatCurrency(opp.tp1)}</span>
                                                        <span id={`copy-tp1-${assetKey}`} className="text-[7px] text-white/20 border border-white/10 px-1 py-0.5 rounded opacity-0 group-hover/level:opacity-100 transition-opacity font-sans">COPIAR</span>
                                                    </span>
                                                </div>
                                                {opp.tp2 && (
                                                    <div className="flex justify-between items-center group/level">
                                                        <span className="text-white/40">TP2 (Equilibrio):</span>
                                                        <span 
                                                            onClick={() => {
                                                                navigator.clipboard.writeText(opp.tp2.toString());
                                                                const el = document.getElementById(`copy-tp2-${assetKey}`);
                                                                if (el) { el.innerText = "COPIADO"; setTimeout(() => el.innerText = "COPIAR", 1000); }
                                                            }}
                                                            className="text-yellow-400 font-bold cursor-pointer hover:text-white flex items-center gap-1.5 active:scale-95 transition-all select-all"
                                                            title="Haz clic para copiar TP2"
                                                        >
                                                            <span>{formatCurrency(opp.tp2)}</span>
                                                            <span id={`copy-tp2-${assetKey}`} className="text-[7px] text-white/20 border border-white/10 px-1 py-0.5 rounded opacity-0 group-hover/level:opacity-100 transition-opacity font-sans">COPIAR</span>
                                                        </span>
                                                    </div>
                                                )}
                                                <div className="flex justify-between items-center group/level">
                                                    <span className="text-white/40">TP3 (Estructural):</span>
                                                    <span 
                                                        onClick={() => {
                                                            navigator.clipboard.writeText(opp.tp3.toString());
                                                            const el = document.getElementById(`copy-tp3-${assetKey}`);
                                                            if (el) { el.innerText = "COPIADO"; setTimeout(() => el.innerText = "COPIAR", 1000); }
                                                        }}
                                                        className="text-neon-green font-bold cursor-pointer hover:text-neon-cyan flex items-center gap-1.5 active:scale-95 transition-all select-all"
                                                        title="Haz clic para copiar TP3"
                                                    >
                                                        <span>{formatCurrency(opp.tp3)}</span>
                                                        <span id={`copy-tp3-${assetKey}`} className="text-[7px] text-white/20 border border-white/10 px-1 py-0.5 rounded opacity-0 group-hover/level:opacity-100 transition-opacity font-sans">COPIAR</span>
                                                    </span>
                                                </div>
                                                {/* Dynamic MT5 / Account Lot Size & 1-Click Copy */}
                                                <div className="flex flex-col gap-1.5 pt-2 border-t border-white/5 font-mono">
                                                    <div className="flex justify-between items-center text-[10px]">
                                                        <span className="text-neon-cyan/80 font-bold">
                                                            {activeProfileConfig.isFtmo ? `🎯 Lotes MT5 (${activeProfileConfig.name.split(' ')[0]}):` : 'Pos Size Bitunix:'}
                                                        </span>
                                                        <span className="text-neon-green font-black text-[12px]">
                                                            {(() => {
                                                                const risk = activeProfileConfig.riskUsd;
                                                                const dist = Math.abs(opp.price - opp.stop_loss);
                                                                const lots = calculateMt5Lots(opp.asset, risk, dist);
                                                                return activeProfileConfig.isFtmo ? `${lots.toFixed(2)} Lots` : `$${formatCurrency(opp.position_size_usdt || 12500)} USDT`;
                                                            })()}
                                                        </span>
                                                    </div>
                                                    <div className="flex justify-between items-center text-[9px] text-white/40">
                                                        <span>Riesgo en Cuenta:</span>
                                                        <span className="text-neon-cyan font-bold">${activeProfileConfig.riskUsd} USD ({activeProfileConfig.riskPct}%)</span>
                                                    </div>
                                                    <button
                                                        onClick={() => {
                                                            const action = opp.direction.toUpperCase() === 'LONG' ? 'BUY LIMIT' : 'SELL LIMIT';
                                                            const sym = opp.asset.replace('USDT', 'USD');
                                                            const risk = activeProfileConfig.riskUsd;
                                                            const dist = Math.abs(opp.price - opp.stop_loss);
                                                            const lots = calculateMt5Lots(opp.asset, risk, dist);
                                                            const text = `[${activeProfileConfig.isFtmo ? 'FTMO MT5' : 'BITUNIX'}] ${action} ${sym} @ ${opp.price} | LOTES: ${lots.toFixed(2)} | SL: ${opp.stop_loss} | TP1: ${opp.tp1} | TP3: ${opp.tp3}`;
                                                            navigator.clipboard.writeText(text);
                                                            setCopiedAsset(assetKey);
                                                            setTimeout(() => setCopiedAsset(null), 2000);
                                                        }}
                                                        className={`w-full py-1.5 rounded-lg text-[9px] font-mono font-black transition-all flex items-center justify-center gap-1 cursor-pointer border ${
                                                            copiedAsset === assetKey
                                                                ? 'bg-neon-green text-black border-neon-green shadow-[0_0_10px_rgba(16,185,129,0.5)]'
                                                                : 'bg-neon-green/15 hover:bg-neon-green/25 text-neon-green border-neon-green/30'
                                                        }`}
                                                    >
                                                        {copiedAsset === assetKey ? '✅ ¡ORDEN COPIADA!' : '📋 COPIAR ORDEN MT5'}
                                                    </button>
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
                                                        className="mt-3 space-y-2"
                                                    >
                                                        {opp.checklist.map((item, cIdx) => {
                                                            const eduNote = EDUCATIONAL_NOTES[item.factor];
                                                            return (
                                                                <div 
                                                                    key={cIdx} 
                                                                    className={`flex flex-col p-2.5 rounded-xl border text-[10px] font-mono leading-tight space-y-1 ${getStatusColor(item.status)}`}
                                                                >
                                                                    <div className="flex items-start justify-between">
                                                                        <div className="flex-1 pr-2">
                                                                            <span className="block font-bold text-white/90">{item.factor}</span>
                                                                            <span className="opacity-80 text-[9px]">{item.detail}</span>
                                                                        </div>
                                                                        <span className="font-bold">{getStatusIcon(item.status)}</span>
                                                                    </div>
                                                                    {eduNote && (
                                                                        <div className="bg-[#02060D] border border-cyan-500/25 rounded-lg p-2 mt-1 text-[9px] text-cyan-200/90 leading-relaxed font-sans shadow-inner">
                                                                            <span className="font-bold text-cyan-400 block mb-0.5 font-mono text-[8.5px] uppercase tracking-wider">📚 Nota Educativa:</span>
                                                                            <span className="text-white/80">{eduNote}</span>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            );
                                                        })}
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

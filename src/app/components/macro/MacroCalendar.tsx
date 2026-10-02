
'use client';

import React, { useEffect, useMemo, useState, memo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
    Calendar, 
    AlertTriangle, 
    Activity, 
    Clock, 
    ChevronRight, 
    Globe, 
    Flame, 
    Timer,
    History,
    Zap,
    Target,
    ShieldAlert
} from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';
import { EconomicEvent } from '../../types/signal';

const MacroCalendar: React.FC = () => {
    const { economicEvents, fetchEconomicEvents } = useTelemetryStore();
    const [filter, setFilter] = useState<'ALL' | 'HIGH'>('HIGH');

    useEffect(() => {
        fetchEconomicEvents();
        const interval = setInterval(fetchEconomicEvents, 1000 * 60 * 15); // Cada 15 min
        return () => clearInterval(interval);
    }, [fetchEconomicEvents]);

    const processedEvents = useMemo(() => {
        const now = new Date();
        const LIVE_WINDOW_MS = 60 * 60 * 1000; // 1 hora como Live (intermitencia)
        const RECENT_WINDOW_MS = 12 * 60 * 60 * 1000; // 12 horas como "Reciente"
        
        return economicEvents
            .map(event => {
                const eventDate = new Date(event.date);
                const diffMs = eventDate.getTime() - now.getTime();
                const isPast = diffMs < 0;
                
                // Un evento es "Crítico" si es Futuro O si pasó hace menos de 12 horas y es High Impact
                const isLive = isPast && Math.abs(diffMs) < LIVE_WINDOW_MS;
                const isRecentCritical = isPast && Math.abs(diffMs) < RECENT_WINDOW_MS && event.impact === 'High';
                
                const diffMinutes = Math.abs(Math.round(diffMs / 60000));
                
                let timeLabel = '';
                if (isLive) {
                    timeLabel = `LIVE / HACE ${diffMinutes}m`;
                } else if (isRecentCritical) {
                    timeLabel = diffMinutes < 60 ? `hace ${diffMinutes}m` : `HACE ${Math.floor(diffMinutes/60)}h ${diffMinutes%60}m`;
                } else if (isPast) {
                    timeLabel = diffMinutes < 60 ? `hace ${diffMinutes}m` : `finalizado`;
                } else {
                    const diffHours = Math.floor(diffMinutes / 60);
                    const remMins = diffMinutes % 60;
                    if (diffHours >= 24) {
                        const diffDays = Math.floor(diffHours / 24);
                        timeLabel = `en ${diffDays}d ${diffHours % 24}h`;
                    } else {
                        timeLabel = diffHours > 0 ? `en ${diffHours}h ${remMins}m` : `en ${diffMinutes}m`;
                    }
                }

                return {
                    ...event,
                    isPast: isPast && !isLive && !isRecentCritical, // Mantenemos como "No Pasado" si es Crítico Reciente
                    isActualPast: isPast,
                    isLive,
                    isRecentCritical,
                    timeLabel,
                    diffMinutes,
                    rawDate: eventDate
                };
            })
            .sort((a, b) => a.rawDate.getTime() - b.rawDate.getTime());
    }, [economicEvents]);

    const upcomingEvents = useMemo(() => {
        return processedEvents.filter(e => !e.isPast);
    }, [processedEvents]);

    const criticalEvent = useMemo(() => {
        // Encontrar el primer evento de alto impacto futuro o LIVE
        return upcomingEvents.find(e => e.impact === 'High');
    }, [upcomingEvents]);

    const relevantList = useMemo(() => {
        return processedEvents.filter(e => filter === 'ALL' || e.impact === 'High');
    }, [processedEvents, filter]);

    const getImpactStyles = (impact: string) => {
        switch (impact) {
            case 'High':
                return 'text-neon-red bg-neon-red/10 border-neon-red/20 shadow-[0_0_10px_rgba(255,0,60,0.15)]';
            case 'Medium':
                return 'text-amber-500 bg-amber-500/10 border-amber-500/20';
            default:
                return 'text-white/40 bg-white/5 border-white/5';
        }
    };

    return (
        <div className="h-full flex flex-col overflow-hidden bg-[#050B14]/40 select-none">
            {/* ── HEADER ── */}
            <div className="p-4 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-amber-500/10 via-transparent to-transparent">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20 shadow-[0_0_20px_rgba(245,158,11,0.05)]">
                        <Calendar size={15} className="text-amber-500" />
                    </div>
                    <div>
                        <h2 className="text-[11px] font-black text-white tracking-[0.2em] drop-shadow-[0_0_8px_rgba(245,158,11,0.4)]">MACRO INTELLIGENCE</h2>
                        <div className="flex items-center gap-2 mt-0.5">
                            <Activity size={10} className="text-amber-500/50" />
                            <span className="text-[8px] text-white/30 font-mono font-bold tracking-tighter uppercase underline decoration-amber-500/20 underline-offset-2">Escaneo de Ciclos Fundamentales</span>
                        </div>
                    </div>
                </div>

                <div className="flex bg-black/40 p-1 rounded-lg border border-white/5">
                    <button 
                        onClick={() => setFilter('HIGH')}
                        className={`px-2 py-1 rounded-md text-[8px] font-black transition-all ${filter === 'HIGH' ? 'bg-amber-500/20 text-amber-500' : 'text-white/20 hover:text-white/40'}`}
                    >
                        CRÍTICOS
                    </button>
                    <button 
                        onClick={() => setFilter('ALL')}
                        className={`px-2 py-1 rounded-md text-[8px] font-black transition-all ${filter === 'ALL' ? 'bg-white/10 text-white/60' : 'text-white/20 hover:text-white/40'}`}
                    >
                        LISTADO
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
                {/* ── SECCIÓN "PRÓXIMO EVENTO CRÍTICO" (MÁS INTELIGENTE) ── */}
                <div className="mb-6">
                    <div className="flex items-center gap-2 mb-3">
                        <Target size={12} className="text-neon-cyan" />
                        <span className="text-[10px] font-black text-white/60 tracking-widest uppercase">Target Macro Prioritario</span>
                    </div>

                    <div className="flex flex-col gap-3">
                        {/* ── DRIVER ACTUAL (RECIENTE) ── */}
                        {processedEvents.find(e => e.isRecentCritical || e.isLive) && (
                            <motion.div 
                                initial={{ opacity: 0, scale: 0.98 }}
                                animate={{ opacity: 1, scale: 1 }}
                                className="bg-amber-500/5 border border-amber-500/20 rounded-2xl p-4 relative overflow-hidden group border-l-amber-500 border-l-2"
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-2 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20">
                                        <div className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-ping" />
                                        <span className="text-[8px] font-black text-amber-500 tracking-widest uppercase">DRIVER ACTUAL / RECIENTE</span>
                                    </div>
                                    <span className="text-[9px] font-mono text-white/30 uppercase">{processedEvents.find(e => e.isRecentCritical || e.isLive)?.country}</span>
                                </div>
                                <h3 className="text-sm font-black text-white leading-tight">
                                    {processedEvents.find(e => e.isRecentCritical || e.isLive)?.title}
                                </h3>
                                <div className="mt-2 flex items-center justify-between text-[10px]">
                                    <div className="flex items-center gap-1.5 text-amber-500/60 font-mono">
                                        <History size={10} />
                                        <span>{processedEvents.find(e => e.isRecentCritical || e.isLive)?.timeLabel}</span>
                                    </div>
                                    <span className="text-white/20 font-bold uppercase text-[8px]">En proceso de absorción volumétrica</span>
                                </div>
                            </motion.div>
                        )}

                        {/* ── PRÓXIMA AMENAZA (FUTURO) ── */}
                        {processedEvents.filter(e => !e.isActualPast && e.impact === 'High').length > 0 && (
                            <motion.div 
                                initial={{ opacity: 0, scale: 0.98 }}
                                animate={{ opacity: 1, scale: 1 }}
                                className="bg-neon-red/5 border border-neon-red/20 rounded-2xl p-4 relative overflow-hidden group border-l-neon-red border-l-2"
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-2 px-2 py-0.5 rounded-full bg-neon-red/10 border border-neon-red/20">
                                        <div className="h-1.5 w-1.5 rounded-full bg-neon-red animate-pulse" />
                                        <span className="text-[8px] font-black text-neon-red tracking-widest uppercase">PRÓXIMA AMENAZA</span>
                                    </div>
                                    <span className="text-[9px] font-mono text-white/30 uppercase">{processedEvents.filter(e => !e.isActualPast && e.impact === 'High')[0].country}</span>
                                </div>
                                <h3 className="text-sm font-black text-white leading-tight">
                                    {processedEvents.filter(e => !e.isActualPast && e.impact === 'High')[0].title}
                                </h3>
                                <div className="mt-2 flex items-center justify-between text-[10px]">
                                    <div className="flex items-center gap-1.5 text-neon-red/60 font-mono font-bold">
                                        <Timer size={10} />
                                        <span>{processedEvents.filter(e => !e.isActualPast && e.impact === 'High')[0].timeLabel}</span>
                                    </div>
                                    <div className="flex items-center gap-1 text-white/40 font-mono">
                                        <span>F: {processedEvents.filter(e => !e.isActualPast && e.impact === 'High')[0].forecast || 'TBD'}</span>
                                    </div>
                                </div>
                            </motion.div>
                        )}

                        {!processedEvents.find(e => (e.isRecentCritical || e.isLive)) && processedEvents.filter(e => !e.isActualPast && e.impact === 'High').length === 0 && (
                            <div className="bg-white/5 border border-dashed border-white/10 rounded-2xl p-8 flex flex-col items-center justify-center opacity-40">
                                <ShieldAlert size={24} className="mb-2" />
                                <p className="text-[10px] font-mono uppercase tracking-widest">No se detectan amenazas críticas próximas</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* ── SECCIÓN "RADAR DE FLUJO" (LISTADO DINÁMICO) ── */}
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Zap size={12} className="text-amber-500" />
                            <span className="text-[10px] font-black text-white/60 tracking-widest uppercase">Radar de Flujo Macro</span>
                        </div>
                        <span className="text-[8px] font-mono text-white/20 uppercase tracking-tighter">Total: {relevantList.length}</span>
                    </div>

                    <div className="space-y-2">
                        <AnimatePresence mode="popLayout">
                            {relevantList.length === 0 ? (
                                <div className="py-12 flex flex-col items-center justify-center opacity-20 gap-3">
                                    <Activity size={32} className="animate-pulse" />
                                    <span className="text-[9px] font-mono tracking-widest uppercase">Sincronizando cronograma...</span>
                                </div>
                            ) : (
                                relevantList.map((event, idx) => (
                                    <motion.div
                                        key={`${event.title}-${event.date}-${idx}`}
                                        layout
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: idx * 0.03 }}
                                        className={`flex items-center gap-3 p-3 rounded-xl border transition-all hover:bg-white/[0.03] group ${event.isPast ? 'opacity-30 border-transparent' : 'bg-black/20 border-white/5'}`}
                                    >
                                        <div className="flex-shrink-0 w-10 flex flex-col items-center justify-center">
                                            <span className="text-[9px] font-black text-white/40 mb-1">{event.country}</span>
                                            <div className={`w-full h-1 rounded-full ${event.impact === 'High' ? 'bg-neon-red shadow-[0_0_5px_rgba(255,0,60,0.5)]' : event.impact === 'Medium' ? 'bg-amber-500' : 'bg-white/10'}`} />
                                        </div>

                                        <div className="flex-1 min-w-0 flex flex-col justify-center">
                                            <h4 className="text-[10.5px] font-bold text-white/80 truncate group-hover:text-white transition-colors uppercase tracking-tight">
                                                {event.title}
                                            </h4>
                                            <div className="flex items-center gap-2 mt-0.5">
                                                <span className={`text-[8px] font-black px-1 rounded-sm uppercase ${event.impact === 'High' ? 'text-neon-red/80' : 'text-white/30'}`}>
                                                    {event.impact}
                                                </span>
                                                <span className="h-0.5 w-0.5 rounded-full bg-white/10" />
                                                <span className="text-[8px] font-mono text-white/20">
                                                    {event.rawDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                </span>
                                            </div>
                                        </div>

                                        <div className="text-right flex flex-col items-end gap-1">
                                            <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-md ${!event.isPast && event.impact === 'High' ? 'bg-neon-red/10 text-neon-red' : 'text-white/30 font-bold'}`}>
                                                {!event.isPast && <Clock size={10} />}
                                                <span className="text-[10px] font-mono font-black whitespace-nowrap tabular-nums">
                                                    {event.timeLabel}
                                                </span>
                                            </div>
                                        </div>
                                    </motion.div>
                                ))
                            )}
                        </AnimatePresence>
                    </div>
                </div>
            </div>

            {/* ── ADVISORY FOOTER ── */}
            <div className="p-3 bg-neon-cyan/5 border-t border-white/5 flex items-center gap-3">
                <div className="flex-shrink-0 text-neon-cyan animate-pulse">
                    <Activity size={14} />
                </div>
                <div className="flex-1">
                    <p className="text-[9px] text-white/60 leading-tight font-medium">
                        <span className="text-neon-cyan font-black uppercase tracking-tighter mr-1">Filtrado Neural:</span> 
                        Eventos detectados por el motor de Slingshot. Se recomienda neutralidad ±60m en impactos rojos.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default memo(MacroCalendar);

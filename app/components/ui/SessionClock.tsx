'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Zap, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useTelemetryStore, SessionData, SessionInfo } from '../../store/telemetryStore';

// ─── Helpers ─────────────────────────────────────────────────────────────────

const SESSION_META: Record<string, { label: string; flag: string; color: string; glow: string; startUTC: number; endUTC: number }> = {
    asia: { label: 'Asia', flag: '🌏', color: 'text-orange-400', glow: 'rgba(251,146,60,0.4)', startUTC: 0, endUTC: 6 },
    london: { label: 'Londres', flag: '🏦', color: 'text-blue-400', glow: 'rgba(96,165,250,0.4)', startUTC: 7, endUTC: 15 },
    ny: { label: 'Nueva York', flag: '🗽', color: 'text-purple-400', glow: 'rgba(192,132,252,0.4)', startUTC: 13, endUTC: 20 },
};

const SESSION_DISPLAY: Record<string, { label: string; color: string; bg: string }> = {
    ASIA: { label: 'ASIA', color: 'text-orange-400', bg: 'bg-orange-400/10 border-orange-400/30' },
    LONDON_KILLZONE: { label: 'LONDON KILLZONE', color: 'text-blue-300', bg: 'bg-blue-400/15 border-blue-400/40' },
    LONDON: { label: 'LONDON', color: 'text-blue-400', bg: 'bg-blue-400/10 border-blue-400/20' },
    NY_KILLZONE: { label: 'NY KILLZONE', color: 'text-purple-300', bg: 'bg-purple-400/15 border-purple-400/40' },
    NEW_YORK: { label: 'NUEVA YORK', color: 'text-purple-400', bg: 'bg-purple-400/10 border-purple-400/20' },
    OFF_HOURS: { label: 'OFF HOURS', color: 'text-white/30', bg: 'bg-white/[0.03] border-white/10' },
};

const STATUS_STYLE: Record<string, string> = {
    ACTIVE: 'text-neon-green',
    CLOSED: 'text-white/30',
    PENDING: 'text-white/50',
};

function fmt(n: number | null, decimals = 0) {
    if (n == null) return '—';
    return '$' + n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatSessionTimes(startUTC: number, endUTC: number) {
    const formatTime = (hour: number) => hour.toString().padStart(2, '0') + ':00';

    // Calcular dinámicamente el horario en Chile a partir del UTC actual
    const dStart = new Date();
    dStart.setUTCHours(startUTC, 0, 0, 0);
    const dEnd = new Date();
    dEnd.setUTCHours(endUTC, 0, 0, 0);

    const fmtChile = new Intl.DateTimeFormat('es-CL', { timeZone: 'America/Santiago', hour: '2-digit', minute: '2-digit', hour12: false });
    return `${formatTime(startUTC)}-${formatTime(endUTC)} UTC | ${fmtChile.format(dStart)}-${fmtChile.format(dEnd)} CL`;
}

function SweepBadge({ swept, label }: { swept: boolean; label: string }) {
    if (!swept) return null;
    return (
        <span className="inline-flex items-center gap-1 text-[9px] font-bold text-neon-red bg-neon-red/10 border border-neon-red/30 px-1.5 py-0.5 rounded-full">
            <Zap size={8} />⚡ {label}
        </span>
    );
}

function SessionRow({ id, info }: { id: string; info: SessionInfo }) {
    const meta = SESSION_META[id];
    return (
        <div className={`grid grid-cols-[1fr_auto_auto_auto] items-center gap-3 py-2 px-3 rounded-lg border transition-colors ${info.status === 'ACTIVE' ? 'bg-white/[0.04] border-white/10' : 'bg-transparent border-transparent'}`}>
            {/* Sesión */}
            <div className="flex items-center gap-2">
                <span className="text-sm">{meta.flag}</span>
                <div className="flex flex-col">
                    <div className="flex items-baseline gap-1.5">
                        <p className={`text-[10px] font-bold ${meta.color} leading-none`}>{meta.label}</p>
                        <p className={`text-[8px] font-semibold ${STATUS_STYLE[info.status]}`}>{info.status}</p>
                    </div>
                    <p className="text-[8.5px] text-white/40 mt-0.5 leading-tight font-mono tracking-tighter">
                        {formatSessionTimes(meta.startUTC, meta.endUTC)}
                    </p>
                </div>
            </div>

            {/* HIGH */}
            <div className="text-right">
                <p className="text-[9px] text-white/30 font-bold tracking-wider mb-0.5">HIGH</p>
                <p className="text-[11px] font-bold text-neon-green/80 font-mono">{fmt(info.high, 0)}</p>
                <SweepBadge swept={info.swept_high} label="H" />
            </div>

            {/* LOW */}
            <div className="text-right">
                <p className="text-[9px] text-white/30 font-bold tracking-wider mb-0.5">LOW</p>
                <p className="text-[11px] font-bold text-neon-red/80 font-mono">{fmt(info.low, 0)}</p>
                <SweepBadge swept={info.swept_low} label="L" />
            </div>

            {/* Status dot */}
            <div className="flex justify-end">
                {info.status === 'ACTIVE' ? (
                    <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ backgroundColor: SESSION_META[id].glow }} />
                        <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: SESSION_META[id].glow }} />
                    </span>
                ) : (
                    <span className="h-2 w-2 rounded-full bg-white/10" />
                )}
            </div>
        </div>
    );
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function SessionClock() {
    const sessionData = useTelemetryStore(s => s.sessionData);
    const [tick, setTick] = useState(0);

    // Reloj local que actualiza cada segundo para mantener la hora viva
    useEffect(() => {
        const timer = setInterval(() => setTick(t => t + 1), 1000);
        return () => clearInterval(timer);
    }, []);

    const nowUtc = new Date();
    const utcStr = nowUtc.toUTCString().slice(17, 22) + ' UTC';
    const chileStr = nowUtc.toLocaleTimeString('es-CL', { timeZone: 'America/Santiago', hour: '2-digit', minute: '2-digit', hour12: false }) + ' Chile';

    const session = sessionData?.current_session ?? 'OFF_HOURS';
    const isKz = sessionData?.is_killzone ?? false;
    const disp = SESSION_DISPLAY[session] ?? SESSION_DISPLAY['OFF_HOURS'];

    return (
        <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl flex flex-col relative">
            <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none" />

            {/* Header */}
            <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                <div className="flex items-center gap-2.5">
                    <Clock size={15} className="text-neon-cyan" />
                    <h2 className="text-xs font-bold text-white/90 tracking-widest">SESIONES DE MERCADO</h2>
                </div>
                <div className="text-right">
                    <p className="text-[10px] font-mono text-white/50">{utcStr}</p>
                    <p className="text-[10px] font-mono text-white/30">{chileStr}</p>
                </div>
            </div>

            {/* Sesión activa */}
            <div className="px-4 pt-3 pb-2">
                <div className={`flex items-center justify-between px-3 py-2 rounded-xl border ${disp.bg}`}>
                    <div className="flex items-center gap-2">
                        {isKz && (
                            <motion.div
                                animate={{ scale: [1, 1.2, 1], opacity: [1, 0.6, 1] }}
                                transition={{ repeat: Infinity, duration: 1.2 }}
                            >
                                <Zap size={13} className="text-yellow-400" />
                            </motion.div>
                        )}
                        <span className={`text-[11px] font-black tracking-widest ${disp.color}`}>
                            {disp.label}
                        </span>
                    </div>
                    {isKz && (
                        <span className="text-[9px] font-bold text-yellow-400 bg-yellow-400/10 border border-yellow-400/30 px-2 py-0.5 rounded-full tracking-wider">
                            KILLZONE ACTIVA
                        </span>
                    )}
                </div>
            </div>

            {/* Tabla de sesiones */}
            <div className="px-2 pb-2 flex flex-col gap-0.5">
                {sessionData ? (
                    Object.entries(sessionData.sessions).map(([id, info]) => (
                        <SessionRow key={id} id={id} info={info as SessionInfo} />
                    ))
                ) : (
                    <div className="text-center text-white/20 text-[10px] italic py-4">Esperando datos de sesión...</div>
                )}
            </div>

            {/* PDH / PDL */}
            <div className="border-t border-white/5 mx-4 mb-3 pt-3">
                <p className="text-[9px] font-bold text-white/30 tracking-[0.2em] mb-2">NIVELES DEL DÍA ANTERIOR</p>
                <div className="grid grid-cols-2 gap-2">
                    <div className="bg-neon-green/5 border border-neon-green/20 rounded-lg p-2">
                        <div className="flex items-center gap-1 mb-1">
                            <TrendingUp size={10} className="text-neon-green/70" />
                            <span className="text-[9px] font-bold text-neon-green/60 tracking-wider">PDH</span>
                            {sessionData?.pdh_swept && <span className="text-[8px] text-neon-red font-bold ml-auto">⚡ BARRIDO</span>}
                        </div>
                        <p className="text-[12px] font-black text-neon-green/90 font-mono">{fmt(sessionData?.pdh ?? null, 0)}</p>
                        <p className="text-[8px] text-neon-green/30 mt-0.5">Objetivo alcista</p>
                    </div>
                    <div className="bg-neon-red/5 border border-neon-red/20 rounded-lg p-2">
                        <div className="flex items-center gap-1 mb-1">
                            <TrendingDown size={10} className="text-neon-red/70" />
                            <span className="text-[9px] font-bold text-neon-red/60 tracking-wider">PDL</span>
                            {sessionData?.pdl_swept && <span className="text-[8px] text-neon-red font-bold ml-auto">⚡ BARRIDO</span>}
                        </div>
                        <p className="text-[12px] font-black text-neon-red/90 font-mono">{fmt(sessionData?.pdl ?? null, 0)}</p>
                        <p className="text-[8px] text-neon-red/30 mt-0.5">Objetivo bajista</p>
                    </div>
                </div>
            </div>

            {/* Leyenda Educativa */}
            <div className="px-4 pb-3">
                <div className="bg-white/[0.02] border border-white/5 rounded-lg p-2.5 text-[9px] text-white/40 leading-snug">
                    <p className="font-bold text-white/60 mb-1.5 border-b border-white/5 pb-1 flex items-center gap-1">
                        <span className="text-neon-cyan">ℹ️</span> Tácticas Institucionales (SMC/ICT)
                    </p>
                    <ul className="grid grid-cols-1 gap-1.5">
                        <li><span className="text-white/60 font-bold">HIGH / LOW:</span> Puntos que el mercado es magnetizado a tocar.</li>
                        <li><span className="text-neon-cyan font-bold">PDH / PDL:</span> (Previous Daily High/Low) Niveles mayores del día anterior. Obran como barreras.</li>
                        <li><span className="text-yellow-400 font-bold">⚡ KILLZONE:</span> Ventana de alta volatilidad donde inyectan liquidez.</li>
                        <li><span className="text-neon-red font-bold">⚡ BARRIDO (Sweep):</span> Trampa. El precio rompe el H/L para "cazar" stop-losses y atrapar traders.</li>
                    </ul>
                </div>
            </div>
        </div>
    );
}

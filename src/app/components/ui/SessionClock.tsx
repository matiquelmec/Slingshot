'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Clock, Zap, TrendingUp, TrendingDown, Activity } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';
import { SessionInfo } from '../../types/signal';
import { formatCurrency } from '../../utils/formatters';

// ─── Helpers ─────────────────────────────────────────────────────────────────

const SESSION_META: Record<string, { label: string; flag: string; color: string; glow: string }> = {
    asia: { label: 'Asia (Tokio)', flag: '🌏', color: 'text-orange-400', glow: 'rgba(251,146,60,0.5)' },
    london: { label: 'Londres', flag: '🏦', color: 'text-blue-400', glow: 'rgba(96,165,250,0.5)' },
    ny: { label: 'Nueva York', flag: '🗽', color: 'text-purple-400', glow: 'rgba(192,132,252,0.5)' },
};

const SESSION_DISPLAY: Record<string, { label: string; color: string; bg: string }> = {
    ASIA: { label: 'ASIA RANGE', color: 'text-orange-300', bg: 'bg-orange-400/10 border-orange-400/30' },
    LONDON_KILLZONE: { label: 'LONDON OPEN (KZ)', color: 'text-blue-300', bg: 'bg-blue-400/15 border-blue-400/40' },
    LONDON: { label: 'LONDON SESSION', color: 'text-blue-300', bg: 'bg-blue-400/10 border-blue-400/25' },
    NY_KILLZONE: { label: 'NY OPEN (KZ)', color: 'text-purple-300', bg: 'bg-purple-400/15 border-purple-400/40' },
    LONDON_NY_OVERLAP: { label: 'POWER OVERLAP ⚡', color: 'text-indigo-200', bg: 'bg-indigo-500/20 border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.2)]' },
    NY_SILVER_BULLET_PM: { label: 'SILVER BULLET PM 🏹', color: 'text-yellow-300', bg: 'bg-yellow-400/15 border-yellow-400/40 shadow-[0_0_15px_rgba(250,204,21,0.2)]' },
    FRANKFURT_OPEN: { label: 'FRANKFURT PRE-OPEN', color: 'text-slate-200', bg: 'bg-slate-400/15 border-slate-400/30' },
    NEW_YORK: { label: 'NY SESSION (RTH)', color: 'text-purple-300', bg: 'bg-purple-400/10 border-purple-400/25' },
    OFF_HOURS: { label: 'OFF HOURS (TRANSICIÓN)', color: 'text-slate-300', bg: 'bg-white/[0.04] border-white/15' },
};

const STATUS_STYLE: Record<string, string> = {
    ACTIVE: 'text-neon-green',
    CLOSED: 'text-slate-400',
    PENDING: 'text-amber-300/80',
};

function getHourInTz(date: Date, timeZone: string): number {
    const str = new Intl.DateTimeFormat('en-US', { timeZone, hour: 'numeric', hour12: false }).format(date);
    const parsed = parseInt(str, 10);
    return parsed === 24 ? 0 : parsed;
}

function classifyClientLiveSession(nowUtc: Date) {
    const tokHour = getHourInTz(nowUtc, 'Asia/Tokyo');
    const lonHour = getHourInTz(nowUtc, 'Europe/London');
    const nyHour = getHourInTz(nowUtc, 'America/New_York');
    const fraHour = getHourInTz(nowUtc, 'Europe/Berlin');

    let current_session = 'OFF_HOURS';
    let is_killzone = false;
    let is_overlap = false;
    let is_silver_bullet = false;

    if (tokHour >= 9 && tokHour < 15) {
        current_session = 'ASIA';
    } else if (lonHour >= 8 && lonHour < 16 && nyHour < 8) {
        current_session = 'LONDON';
    } else if (nyHour >= 8 && nyHour < 16) {
        current_session = 'NEW_YORK';
    }

    if (lonHour >= 8 && lonHour < 11) {
        current_session = 'LONDON_KILLZONE';
        is_killzone = true;
    }
    if (nyHour >= 8 && nyHour < 11) {
        current_session = lonHour >= 8 ? 'LONDON_NY_OVERLAP' : 'NY_KILLZONE';
        is_killzone = true;
        is_overlap = lonHour >= 8;
    }
    if ((nyHour >= 10 && nyHour < 11) || (nyHour >= 14 && nyHour < 15)) {
        is_silver_bullet = true;
        if (nyHour >= 14) {
            current_session = 'NY_SILVER_BULLET_PM';
            is_killzone = true;
        }
    }
    if (fraHour >= 7 && fraHour < 8) {
        current_session = 'FRANKFURT_OPEN';
        is_killzone = true;
    }

    return { current_session, is_killzone, is_overlap, is_silver_bullet };
}

function formatSessionTimes(startUTC: number, endUTC: number) {
    if (startUTC === undefined || endUTC === undefined) return '...UTC | ...CL';

    const normalizedStartUtc = ((startUTC % 24) + 24) % 24;
    const normalizedEndUtc = ((endUTC % 24) + 24) % 24;

    const formatTime = (hour: number) => hour.toString().padStart(2, '0') + ':00';

    const dStart = new Date();
    dStart.setUTCHours(normalizedStartUtc, 0, 0, 0);
    const dEnd = new Date();
    dEnd.setUTCHours(normalizedEndUtc, 0, 0, 0);

    const fmtChile = new Intl.DateTimeFormat('es-CL', {
        timeZone: 'America/Santiago',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    });
    return `${formatTime(normalizedStartUtc)}-${formatTime(normalizedEndUtc)} UTC | ${fmtChile.format(dStart)}-${fmtChile.format(dEnd)} CL`;
}

function SweepBadge({ swept, label }: { swept?: boolean; label: string }) {
    if (!swept) return null;
    return (
        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-neon-red bg-neon-red/15 border border-neon-red/40 px-1.5 py-0.5 rounded-full mt-0.5">
            <Zap size={9} />⚡ {label}
        </span>
    );
}

function SessionRow({
    id,
    info,
}: {
    id: string;
    info: SessionInfo & { prev_high?: number | null; prev_low?: number | null };
}) {
    const meta = SESSION_META[id] ?? SESSION_META.ny;
    const isPending = info.status === 'PENDING';
    const isClosed = info.status === 'CLOSED';

    const showPrev = info.high == null && (isPending || isClosed) && info.prev_high != null;
    const displayHigh = info.high ?? (showPrev ? info.prev_high! : null);
    const displayLow = info.low ?? (showPrev ? info.prev_low! : null);

    return (
        <div
            className={`grid grid-cols-[1fr_auto_auto_auto] items-center gap-3 py-2 px-3 rounded-lg border transition-colors ${
                info.status === 'ACTIVE'
                    ? 'bg-white/[0.06] border-white/15'
                    : 'bg-transparent border-transparent'
            }`}
        >
            {/* Sesión */}
            <div className="flex items-center gap-2">
                <span className="text-sm">{meta.flag}</span>
                <div className="flex flex-col">
                    <div className="flex items-baseline gap-2">
                        <p className={`text-xs font-bold ${meta.color} leading-none`}>{meta.label}</p>
                        <p className={`text-[10px] font-semibold ${STATUS_STYLE[info.status] ?? 'text-slate-400'}`}>
                            {info.status}
                        </p>
                    </div>
                    <p className="text-[10px] text-slate-300 mt-1 leading-tight font-mono tracking-tight">
                        {formatSessionTimes(info.start_utc, info.end_utc)}
                    </p>
                </div>
            </div>

            {/* HIGH */}
            <div className="text-right">
                <p className="text-[10px] text-slate-400 font-bold tracking-wider mb-0.5">HIGH</p>
                <p className={`text-xs font-bold font-mono ${showPrev ? 'text-slate-400' : 'text-neon-green'}`}>
                    {formatCurrency(displayHigh)}
                </p>
                {showPrev && <p className="text-[9px] text-slate-400 tracking-wider">prev</p>}
                <SweepBadge swept={info.swept_high} label="H" />
            </div>

            {/* LOW */}
            <div className="text-right">
                <p className="text-[10px] text-slate-400 font-bold tracking-wider mb-0.5">LOW</p>
                <p className={`text-xs font-bold font-mono ${showPrev ? 'text-slate-400' : 'text-neon-red'}`}>
                    {formatCurrency(displayLow)}
                </p>
                {showPrev && <p className="text-[9px] text-slate-400 tracking-wider">prev</p>}
                <SweepBadge swept={info.swept_low} label="L" />
            </div>

            {/* Status dot */}
            <div className="flex justify-end">
                {info.status === 'ACTIVE' ? (
                    <span className="relative flex h-2.5 w-2.5">
                        <span
                            className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                            style={{ backgroundColor: meta.glow }}
                        />
                        <span
                            className="relative inline-flex rounded-full h-2.5 w-2.5"
                            style={{ backgroundColor: meta.glow }}
                        />
                    </span>
                ) : (
                    <span className="h-2 w-2 rounded-full bg-white/20" />
                )}
            </div>
        </div>
    );
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function SessionClock() {
    const sessionData = useTelemetryStore((s) => s.sessionData);
    const activeSymbol = useTelemetryStore((s) => s.activeSymbol);
    const [, setTick] = useState(0);

    useEffect(() => {
        const timer = setInterval(() => setTick((t) => t + 1), 1000);
        return () => clearInterval(timer);
    }, []);

    const nowUtc = new Date();
    const utcStr = nowUtc.toUTCString().slice(17, 22) + ' UTC';
    const chileStr =
        nowUtc.toLocaleTimeString('es-CL', {
            timeZone: 'America/Santiago',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false,
        }) + ' CL';
    const nyStr = nowUtc.toLocaleTimeString('en-US', {
        timeZone: 'America/New_York',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    });
    const lonStr = nowUtc.toLocaleTimeString('en-GB', {
        timeZone: 'Europe/London',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    });

    // Clasificación en tiempo real (evita congelamiento cuando el backend no emite ticks nuevos)
    const liveCls = classifyClientLiveSession(nowUtc);
    const session = liveCls.current_session;
    const isKz = liveCls.is_killzone;
    const isOverlap = liveCls.is_overlap;
    const isSilverBullet = liveCls.is_silver_bullet;
    const disp = SESSION_DISPLAY[session] ?? SESSION_DISPLAY.OFF_HOURS;

    const isMatchingAsset =
        Boolean(sessionData?.sessions) &&
        (!sessionData?.asset || sessionData.asset.toUpperCase() === activeSymbol.toUpperCase());

    return (
        <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl flex flex-col relative">
            <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none" />

            {/* Header */}
            <div className="p-4 border-b border-white/10 flex items-center justify-between bg-white/[0.01]">
                <div className="flex items-center gap-2">
                    <div className="relative">
                        <Clock size={16} className="text-neon-cyan" />
                        <motion.div
                            animate={{ opacity: [0.4, 1, 0.4] }}
                            transition={{ repeat: Infinity, duration: 2 }}
                            className="absolute -top-1 -right-1 w-1.5 h-1.5 bg-neon-cyan rounded-full shadow-[0_0_5px_rgba(0,255,255,0.8)]"
                        />
                    </div>
                    <div className="flex flex-col">
                        <div className="flex items-center gap-2">
                            <h2 className="text-xs font-bold text-white tracking-widest leading-none">
                                SESIONES DE MERCADO
                            </h2>
                            <span className="text-[10px] font-mono font-bold text-neon-cyan bg-neon-cyan/10 border border-neon-cyan/30 px-1.5 py-0.5 rounded">
                                {activeSymbol}
                            </span>
                        </div>
                        <span className="text-[10px] font-semibold text-slate-300 mt-1 flex items-center gap-1 uppercase">
                            <span className="w-1.5 h-1.5 bg-neon-cyan rounded-full animate-pulse" />
                            SOP-134 Real-Time Wall Clock
                        </span>
                    </div>
                </div>
                <div className="text-right flex flex-col items-end">
                    <div className="flex gap-2 items-center mb-1">
                        <span className="text-[10px] font-mono font-bold text-slate-200 tracking-tight uppercase px-1.5 py-0.5 rounded border border-white/15 bg-white/[0.04]">
                            🗽 {nyStr} NY
                        </span>
                        <span className="text-[10px] font-mono font-bold text-slate-200 tracking-tight uppercase px-1.5 py-0.5 rounded border border-white/15 bg-white/[0.04]">
                            🏦 {lonStr} LON
                        </span>
                    </div>
                    <div className="flex gap-2 items-baseline">
                        <p className="text-xs font-mono font-bold text-slate-200">{utcStr}</p>
                        <p className="text-xs font-mono font-bold text-neon-cyan">{chileStr}</p>
                    </div>
                </div>
            </div>

            {/* Sesión activa */}
            <div className="px-4 pt-4 pb-2">
                <div className={`flex items-center justify-between px-4 py-2 rounded-xl border ${disp.bg}`}>
                    <div className="flex items-center gap-2">
                        {(isKz || isSilverBullet || isOverlap) && (
                            <motion.div
                                animate={{ scale: [1, 1.2, 1], opacity: [1, 0.6, 1] }}
                                transition={{ repeat: Infinity, duration: 1.2 }}
                            >
                                <Zap size={14} className={isSilverBullet ? 'text-yellow-300' : 'text-neon-cyan'} />
                            </motion.div>
                        )}
                        <span className={`text-xs font-black tracking-widest ${disp.color}`}>{disp.label}</span>
                    </div>
                    {isSilverBullet && (
                        <span className="text-[10px] font-bold text-yellow-300 bg-yellow-400/15 border border-yellow-400/40 px-2 py-0.5 rounded-full tracking-wider">
                            SILVER BULLET 🏹
                        </span>
                    )}
                    {isOverlap && !isSilverBullet && (
                        <span className="text-[10px] font-bold text-indigo-200 bg-indigo-400/15 border border-indigo-400/40 px-2 py-0.5 rounded-full tracking-wider">
                            POWER OVERLAP ⚡
                        </span>
                    )}
                    {isKz && !isSilverBullet && !isOverlap && (
                        <span className="text-[10px] font-bold text-blue-300 bg-blue-400/15 border border-blue-400/40 px-2 py-0.5 rounded-full tracking-wider">
                            KILLZONE ACTIVA
                        </span>
                    )}
                </div>
            </div>

            {/* Tabla de sesiones */}
            <div className="px-2 pb-2 flex flex-col gap-1">
                {isMatchingAsset &&
                sessionData?.sessions &&
                typeof sessionData.sessions === 'object' &&
                Object.keys(sessionData.sessions).length > 0 ? (
                    Object.entries(sessionData.sessions).map(([id, info]) => (
                        <SessionRow key={id} id={id} info={info as any} />
                    ))
                ) : (
                    <div className="flex flex-col items-center justify-center py-8">
                        <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ repeat: Infinity, duration: 4, ease: 'linear' }}
                            className="mb-2"
                        >
                            <Activity size={20} className="text-neon-cyan" />
                        </motion.div>
                        <p className="text-xs font-bold tracking-widest text-neon-cyan animate-pulse">
                            SINCRONIZANDO {activeSymbol}...
                        </p>
                        <p className="text-[10px] text-slate-300 mt-1 uppercase">
                            Hidratando niveles intradiarios y PDH/PDL
                        </p>
                    </div>
                )}
            </div>

            {/* PDH / PDL */}
            <div className="border-t border-white/10 mx-4 mb-4 pt-4">
                <p className="text-[10px] font-bold text-slate-300 tracking-widest mb-2">
                    NIVELES DEL DÍA ANTERIOR ({activeSymbol})
                </p>
                <div className="grid grid-cols-2 gap-2">
                    <div className="bg-neon-green/10 border border-neon-green/30 rounded-lg p-2">
                        <div className="flex items-center gap-1 mb-1">
                            <TrendingUp size={12} className="text-neon-green" />
                            <span className="text-[10px] font-bold text-neon-green tracking-wider">PDH</span>
                            {isMatchingAsset && sessionData?.pdh_swept && (
                                <span className="text-[10px] text-neon-red font-bold ml-auto">⚡ BARRIDO</span>
                            )}
                        </div>
                        <p className="text-xs font-black text-neon-green font-mono">
                            {formatCurrency(isMatchingAsset ? (sessionData?.pdh ?? null) : null)}
                        </p>
                        <p className="text-[10px] text-slate-300 mt-0.5">Liquidez superior</p>
                    </div>
                    <div className="bg-neon-red/10 border border-neon-red/30 rounded-lg p-2">
                        <div className="flex items-center gap-1 mb-1">
                            <TrendingDown size={12} className="text-neon-red" />
                            <span className="text-[10px] font-bold text-neon-red tracking-wider">PDL</span>
                            {isMatchingAsset && sessionData?.pdl_swept && (
                                <span className="text-[10px] text-neon-red font-bold ml-auto">⚡ BARRIDO</span>
                            )}
                        </div>
                        <p className="text-xs font-black text-neon-red font-mono">
                            {formatCurrency(isMatchingAsset ? (sessionData?.pdl ?? null) : null)}
                        </p>
                        <p className="text-[10px] text-slate-300 mt-0.5">Liquidez inferior</p>
                    </div>
                </div>
            </div>

            {/* Leyenda Educativa */}
            <div className="px-4 pb-4">
                <div className="bg-white/[0.03] border border-white/10 rounded-lg p-2 text-[10px] text-slate-300 leading-snug">
                    <p className="font-bold text-white mb-1.5 border-b border-white/10 pb-1 flex items-center gap-1">
                        <span className="text-neon-cyan">ℹ️</span> Tácticas Institucionales (SMC/ICT)
                    </p>
                    <ul className="grid grid-cols-1 gap-1">
                        <li>
                            <span className="text-white font-bold">HIGH / LOW:</span> Extremos de liquidez por sesión.
                        </li>
                        <li>
                            <span className="text-neon-cyan font-bold">PDH / PDL:</span> Máximo y mínimo de la jornada previa.
                        </li>
                        <li>
                            <span className="text-yellow-300 font-bold">⚡ KILLZONE:</span> Ventana de inyección de volumen institucional.
                        </li>
                        <li>
                            <span className="text-neon-red font-bold">⚡ BARRIDO (Sweep):</span> Toma de liquidez sobre H/L o PDH/PDL.
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    );
}

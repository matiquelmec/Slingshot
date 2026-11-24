'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, Lock, RefreshCw, ShieldAlert } from 'lucide-react';
import { getApiBaseUrl } from '../../utils/apiUrl';

export interface ForwardTrackerSummary {
    parameter_freeze_date: string;
    configured_base_risk_pct: number;
    live_trades_count: number;
    win_rate_pct: number;
    realized_profit_factor: number;
    realized_total_net_r: number;
    realized_expectancy_r: number;
    realized_std_r: number;
    realized_ci95_low_r: number;
    realized_ci95_high_r: number;
    mean_entry_slippage_bps: number;
    total_fees_and_funding_r: number;
    benchmark_expectancy_r: number;
    implementation_shortfall_r: number;
    drift_z_score: number;
    drift_status: 'IN_LINE' | 'SAMPLE_BUILDING' | 'WARNING_DRIFT' | 'CRITICAL_DEGRADATION' | string;
    recommended_risk_action: string;
}

export interface ForwardTrackerResponse {
    frozen_mode: boolean;
    summary: ForwardTrackerSummary;
    policy_audit_log?: Array<{
        created_at: string;
        drift_status: string;
        drift_z_score: number;
        recommended_action: string;
        executed_action: string;
    }>;
}

export function getDriftBadgeStyle(status: string): {
    label: string;
    classes: string;
    Icon: typeof CheckCircle2;
} {
    switch (status) {
        case 'IN_LINE':
            return {
                label: 'EN LÍNEA (OOS)',
                classes: 'bg-neon-green/15 text-neon-green border-neon-green/40',
                Icon: CheckCircle2,
            };
        case 'WARNING_DRIFT':
            return {
                label: 'ALERTA DERIVA (-1.5σ)',
                classes: 'bg-amber-500/15 text-amber-300 border-amber-400/40',
                Icon: AlertTriangle,
            };
        case 'CRITICAL_DEGRADATION':
            return {
                label: 'DEGRADACIÓN CRÍTICA (-2.0σ)',
                classes: 'bg-neon-red/15 text-neon-red border-neon-red/40',
                Icon: ShieldAlert,
            };
        default:
            return {
                label: 'CONSTRUYENDO MUESTRA',
                classes: 'bg-neon-cyan/15 text-neon-cyan border-neon-cyan/40',
                Icon: Activity,
            };
    }
}

export default function ForwardTestAuditCard() {
    const [data, setData] = useState<ForwardTrackerResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    const fetchAudit = useCallback(async () => {
        setLoading(true);
        setError(false);
        try {
            const baseUrl = getApiBaseUrl();
            const res = await fetch(`${baseUrl}/api/v1/analytics/forward-tracker`, { cache: 'no-store' });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = (await res.json()) as ForwardTrackerResponse;
            if (json && json.summary) {
                setData(json);
            }
        } catch {
            setError(true);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAudit();
    }, [fetchAudit]);

    if (loading && !data) {
        return (
            <div className="p-4 rounded-xl bg-[#050B14]/80 border border-white/10 animate-pulse flex items-center justify-between">
                <span className="text-xs font-mono text-slate-300">Cargando auditoría Out-of-Sample (SOP-146)...</span>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="p-4 rounded-xl bg-[#050B14]/80 border border-white/10 flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-mono text-slate-300">
                    Auditoría Forward-Test pendiente de sincronización con FastAPI.
                </span>
                <button
                    type="button"
                    onClick={fetchAudit}
                    className="min-h-[44px] px-3 rounded-lg bg-white/5 hover:bg-white/10 border border-white/15 text-xs font-mono text-neon-cyan flex items-center gap-2 cursor-pointer"
                >
                    <RefreshCw size={14} />
                    <span>Reintentar</span>
                </button>
            </div>
        );
    }

    const { summary, frozen_mode } = data;
    const badge = getDriftBadgeStyle(summary.drift_status);
    const BadgeIcon = badge.Icon;
    const samplePct = Math.min(100, Math.round((summary.live_trades_count / 20) * 100));

    return (
        <section
            aria-label="Auditoría Científica Forward-Test Out-of-Sample"
            className="p-4 rounded-2xl bg-[#050B14]/85 backdrop-blur-xl border border-white/10 shadow-2xl flex flex-col gap-4"
        >
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/5 border border-white/15 text-[11px] font-mono font-bold text-slate-100">
                        <Lock size={12} className="text-neon-cyan" />
                        <span>{frozen_mode ? 'SOP-147 FROZEN OOS' : 'ADAPTIVE'}</span>
                    </span>
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] font-mono font-bold ${badge.classes}`}>
                        <BadgeIcon size={12} />
                        <span>{badge.label}</span>
                    </span>
                    <span className="text-xs font-mono text-slate-300">
                        Corte: <strong className="text-white">{summary.parameter_freeze_date}</strong>
                    </span>
                </div>

                <button
                    type="button"
                    onClick={fetchAudit}
                    aria-label="Actualizar auditoría Forward-Test"
                    className="min-h-[44px] px-3 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/15 text-xs font-mono text-slate-200 flex items-center gap-2 transition-all cursor-pointer"
                >
                    <RefreshCw size={13} className={loading ? 'animate-spin text-neon-cyan' : 'text-neon-cyan'} />
                    <span>Actualizar</span>
                </button>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 md:gap-4">
                <div className="p-3 rounded-xl bg-black/40 border border-white/10">
                    <p className="text-[11px] font-mono text-slate-400">MUESTRA OOS</p>
                    <p className="text-lg font-black font-mono text-white">
                        {summary.live_trades_count}{' '}
                        <span className="text-xs font-normal text-slate-400">/ 20 mín. ({samplePct}%)</span>
                    </p>
                    <p className="text-[11px] font-mono text-slate-300">Win Rate: {summary.win_rate_pct.toFixed(1)}%</p>
                </div>

                <div className="p-3 rounded-xl bg-black/40 border border-white/10">
                    <p className="text-[11px] font-mono text-slate-400">EXPECTATIVA REAL (E[R])</p>
                    <p className={`text-lg font-black font-mono ${summary.realized_expectancy_r >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
                        {summary.realized_expectancy_r >= 0 ? '+' : ''}
                        {summary.realized_expectancy_r.toFixed(3)} R
                    </p>
                    <p className="text-[11px] font-mono text-slate-300">
                        Benchmark SOP-119: +{summary.benchmark_expectancy_r.toFixed(3)} R
                    </p>
                </div>

                <div className="p-3 rounded-xl bg-black/40 border border-white/10">
                    <p className="text-[11px] font-mono text-slate-400">IMPLEMENTATION SHORTFALL</p>
                    <p className="text-lg font-black font-mono text-white">
                        {summary.implementation_shortfall_r >= 0 ? '+' : ''}
                        {summary.implementation_shortfall_r.toFixed(3)} R
                    </p>
                    <p className="text-[11px] font-mono text-slate-300">
                        Slippage: {summary.mean_entry_slippage_bps.toFixed(2)} bps
                    </p>
                </div>

                <div className="p-3 rounded-xl bg-black/40 border border-white/10">
                    <p className="text-[11px] font-mono text-slate-400">DERIVA ESTADÍSTICA (Z-SCORE)</p>
                    <p className={`text-lg font-black font-mono ${summary.drift_z_score <= -1.5 ? 'text-amber-300' : 'text-neon-cyan'}`}>
                        {summary.drift_z_score >= 0 ? '+' : ''}
                        {summary.drift_z_score.toFixed(2)} σ
                    </p>
                    <p className="text-[11px] font-mono text-slate-300 truncate">
                        Política: {summary.recommended_risk_action}
                    </p>
                </div>
            </div>
        </section>
    );
}

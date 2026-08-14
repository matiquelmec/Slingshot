// app/components/signals/FtmoShieldWidget.tsx
'use client';

import React from 'react';
import { AccountProfileConfig } from '../../types/signal';

interface FtmoShieldWidgetProps {
    config: AccountProfileConfig;
    currentProfitUsd?: number;
    dailyLossUsd?: number;
}

export const FtmoShieldWidget: React.FC<FtmoShieldWidgetProps> = ({
    config,
    currentProfitUsd = 0,
    dailyLossUsd = 0,
}) => {
    if (!config.isFtmo) return null;

    const targetUsd = config.targetProfitUsd || (config.accountSize * 0.10);
    const progressPct = Math.min(100, Math.max(0, (currentProfitUsd / targetUsd) * 100));

    const maxDailyLoss = config.maxDailyLossUsd || (config.accountSize * 0.05);
    const dailyLossPct = Math.min(100, (Math.abs(dailyLossUsd) / maxDailyLoss) * 100);
    const remainingDailyLossUsd = Math.max(0, maxDailyLoss - Math.abs(dailyLossUsd));

    return (
        <div className="flex flex-col gap-2 bg-gradient-to-r from-emerald-950/30 via-black/50 to-purple-950/30 border border-neon-green/20 rounded-xl p-3 shadow-md">
            {/* Cabecera del Widget */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="flex h-2 w-2 relative">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neon-green opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-neon-green"></span>
                    </span>
                    <span className="text-[10px] font-mono font-black text-neon-green uppercase tracking-wider">
                        🛡️ ESCUDO DE PROTECCIÓN FTMO &bull; {config.name}
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[9px] font-mono text-white/50 bg-white/5 px-2 py-0.5 rounded border border-white/10">
                        Kill-Switch Diario: <strong className="text-neon-green">ACTIVO (Máx 2 SLs)</strong>
                    </span>
                </div>
            </div>

            {/* Dos Barras de Progreso / Seguridad */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {/* 1. Meta del Challenge (+10% / +5%) */}
                {config.targetProfitUsd && (
                    <div className="flex flex-col gap-1 bg-black/40 border border-white/5 rounded-lg p-2">
                        <div className="flex items-center justify-between text-[9px] font-mono">
                            <span className="text-white/60">🎯 Avance hacia Aprobación ({config.phase === 'PHASE_1' ? 'Paso 1' : 'Paso 2'})</span>
                            <span className="font-bold text-neon-green">
                                ${currentProfitUsd.toLocaleString('en-US')} / ${targetUsd.toLocaleString('en-US')} USD ({progressPct.toFixed(1)}%)
                            </span>
                        </div>
                        <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-teal-500 to-neon-green rounded-full transition-all duration-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]"
                                style={{ width: `${progressPct}%` }}
                            />
                        </div>
                    </div>
                )}

                {/* 2. Margen de Pérdida Diaria Disponible (-5% Max) */}
                <div className="flex flex-col gap-1 bg-black/40 border border-white/5 rounded-lg p-2">
                    <div className="flex items-center justify-between text-[9px] font-mono">
                        <span className="text-white/60">🚨 Margen de Pérdida Diaria Disponible</span>
                        <span className={`font-bold ${dailyLossPct > 50 ? 'text-amber-400' : 'text-neon-cyan'}`}>
                            ${remainingDailyLossUsd.toLocaleString('en-US')} USD restantes
                        </span>
                    </div>
                    <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                        <div
                            className={`h-full rounded-full transition-all duration-500 ${
                                dailyLossPct > 60 ? 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]' : 'bg-neon-cyan shadow-[0_0_10px_rgba(6,182,212,0.5)]'
                            }`}
                            style={{ width: `${Math.max(5, 100 - dailyLossPct)}%` }}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
};

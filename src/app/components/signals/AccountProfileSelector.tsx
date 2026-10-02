// app/components/signals/AccountProfileSelector.tsx
'use client';

import React from 'react';
import { AccountProfileType, FtmoPhase, AccountProfileConfig } from '../../types/signal';

export interface AccountProfileState {
    profile: AccountProfileType;
    phase: FtmoPhase;
    riskOverridePct?: number;
}

interface AccountProfileSelectorProps {
    currentProfile: AccountProfileType;
    currentPhase: FtmoPhase;
    onProfileChange: (profile: AccountProfileType) => void;
    onPhaseChange: (phase: FtmoPhase) => void;
}

export const PROFILES_CONFIG: Record<AccountProfileType, (phase: FtmoPhase) => AccountProfileConfig> = {
    PERSONAL_250K: () => ({
        id: 'PERSONAL_250K',
        name: 'Cuenta Personal $250k',
        accountSize: 250000,
        riskPct: 1.5,
        riskUsd: 3750,
        platform: 'BITUNIX',
        isFtmo: false,
    }),
    FTMO_100K: (phase) => ({
        id: 'FTMO_100K',
        name: 'FTMO Challenge $100k',
        accountSize: 100000,
        riskPct: phase === 'PHASE_1' ? 0.75 : phase === 'PHASE_2' ? 0.50 : 0.75,
        riskUsd: phase === 'PHASE_1' ? 750 : phase === 'PHASE_2' ? 500 : 750,
        platform: 'MT5',
        isFtmo: true,
        phase,
        targetProfitPct: phase === 'PHASE_1' ? 10.0 : phase === 'PHASE_2' ? 5.0 : undefined,
        targetProfitUsd: phase === 'PHASE_1' ? 10000 : phase === 'PHASE_2' ? 5000 : undefined,
        maxDailyLossPct: 5.0,
        maxDailyLossUsd: 5000,
        maxTotalLossPct: 10.0,
        maxTotalLossUsd: 10000,
    }),
    FTMO_200K: (phase) => ({
        id: 'FTMO_200K',
        name: 'FTMO Challenge $200k',
        accountSize: 200000,
        riskPct: phase === 'PHASE_1' ? 0.75 : phase === 'PHASE_2' ? 0.50 : 0.75,
        riskUsd: phase === 'PHASE_1' ? 1500 : phase === 'PHASE_2' ? 1000 : 1500,
        platform: 'MT5',
        isFtmo: true,
        phase,
        targetProfitPct: phase === 'PHASE_1' ? 10.0 : phase === 'PHASE_2' ? 5.0 : undefined,
        targetProfitUsd: phase === 'PHASE_1' ? 20000 : phase === 'PHASE_2' ? 10000 : undefined,
        maxDailyLossPct: 5.0,
        maxDailyLossUsd: 10000,
        maxTotalLossPct: 10.0,
        maxTotalLossUsd: 20000,
    }),
    CUSTOM: () => ({
        id: 'CUSTOM',
        name: 'Personalizado',
        accountSize: 100000,
        riskPct: 1.0,
        riskUsd: 1000,
        platform: 'MT5',
        isFtmo: false,
    }),
};

export const AccountProfileSelector: React.FC<AccountProfileSelectorProps> = ({
    currentProfile,
    currentPhase,
    onProfileChange,
    onPhaseChange,
}) => {
    const activeConfig = PROFILES_CONFIG[currentProfile](currentPhase);

    return (
        <div className="flex flex-col gap-2.5 bg-black/60 border border-white/10 rounded-xl p-3 shadow-lg backdrop-blur-md">
            {/* Fila Superior: Selector de Cuenta */}
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono font-black uppercase text-white/50 tracking-wider">
                        💼 PERFIL DE OPERATIVA:
                    </span>
                    <div className="flex items-center gap-1 bg-white/5 p-1 rounded-lg border border-white/10">
                        <button
                            onClick={() => onProfileChange('PERSONAL_250K')}
                            className={`px-2.5 py-1 rounded-md text-[10px] font-mono font-bold transition-all ${
                                currentProfile === 'PERSONAL_250K'
                                    ? 'bg-neon-cyan text-black shadow-[0_0_12px_rgba(6,182,212,0.5)] font-black'
                                    : 'text-white/60 hover:text-white hover:bg-white/5'
                            }`}
                        >
                            🔵 Personal $250k
                        </button>
                        <button
                            onClick={() => onProfileChange('FTMO_100K')}
                            className={`px-2.5 py-1 rounded-md text-[10px] font-mono font-bold transition-all ${
                                currentProfile === 'FTMO_100K'
                                    ? 'bg-neon-green text-black shadow-[0_0_12px_rgba(165,243,180,0.5)] font-black'
                                    : 'text-white/60 hover:text-white hover:bg-white/5'
                            }`}
                        >
                            🟢 FTMO $100k
                        </button>
                        <button
                            onClick={() => onProfileChange('FTMO_200K')}
                            className={`px-2.5 py-1 rounded-md text-[10px] font-mono font-bold transition-all ${
                                currentProfile === 'FTMO_200K'
                                    ? 'bg-purple-500 text-white shadow-[0_0_12px_rgba(168,85,247,0.5)] font-black'
                                    : 'text-white/60 hover:text-white hover:bg-white/5'
                            }`}
                        >
                            🟣 FTMO $200k
                        </button>
                    </div>
                </div>

                {/* Si es FTMO, mostrar Selector de Fase */}
                {activeConfig.isFtmo && (
                    <div className="flex items-center gap-1.5">
                        <span className="text-[9px] font-mono text-white/40 uppercase">Fase:</span>
                        <div className="flex items-center gap-1 bg-white/5 p-0.5 rounded-lg border border-white/10">
                            <button
                                onClick={() => onPhaseChange('PHASE_1')}
                                className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold transition-all ${
                                    currentPhase === 'PHASE_1'
                                        ? 'bg-neon-green/20 text-neon-green border border-neon-green/40'
                                        : 'text-white/40 hover:text-white'
                                }`}
                            >
                                Paso 1 (+10%)
                            </button>
                            <button
                                onClick={() => onPhaseChange('PHASE_2')}
                                className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold transition-all ${
                                    currentPhase === 'PHASE_2'
                                        ? 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/40'
                                        : 'text-white/40 hover:text-white'
                                }`}
                            >
                                Paso 2 (+5%)
                            </button>
                            <button
                                onClick={() => onPhaseChange('FUNDED')}
                                className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold transition-all ${
                                    currentPhase === 'FUNDED'
                                        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                                        : 'text-white/40 hover:text-white'
                                }`}
                            >
                                💎 Fondeada
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* Fila Inferior: Métricas Clave del Perfil */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t border-white/5">
                <div className="flex flex-col bg-white/[0.02] border border-white/5 rounded-lg px-2.5 py-1.5">
                    <span className="text-[8px] font-mono text-white/40 uppercase">Capital Base</span>
                    <span className="text-[11px] font-mono font-black text-white">
                        ${activeConfig.accountSize.toLocaleString('en-US')} USD
                    </span>
                </div>
                <div className="flex flex-col bg-white/[0.02] border border-white/5 rounded-lg px-2.5 py-1.5">
                    <span className="text-[8px] font-mono text-white/40 uppercase">Riesgo Fijo / Trade</span>
                    <span className="text-[11px] font-mono font-black text-neon-cyan">
                        {activeConfig.riskPct}% (${activeConfig.riskUsd.toLocaleString('en-US')} USD)
                    </span>
                </div>
                <div className="flex flex-col bg-white/[0.02] border border-white/5 rounded-lg px-2.5 py-1.5">
                    <span className="text-[8px] font-mono text-white/40 uppercase">
                        {activeConfig.isFtmo ? 'Objetivo de Fase' : 'Plataforma'}
                    </span>
                    <span className="text-[11px] font-mono font-black text-neon-green">
                        {activeConfig.isFtmo
                            ? `+${activeConfig.targetProfitPct}% (+$${activeConfig.targetProfitUsd?.toLocaleString('en-US')} USD)`
                            : 'Bitunix Futures 20x'}
                    </span>
                </div>
                <div className="flex flex-col bg-white/[0.02] border border-white/5 rounded-lg px-2.5 py-1.5">
                    <span className="text-[8px] font-mono text-white/40 uppercase">
                        {activeConfig.isFtmo ? 'Pérdida Diaria Máx' : 'Margen Asignado'}
                    </span>
                    <span className={`text-[11px] font-mono font-black ${activeConfig.isFtmo ? 'text-red-400' : 'text-amber-400'}`}>
                        {activeConfig.isFtmo
                            ? `-${activeConfig.maxDailyLossPct}% (-$${activeConfig.maxDailyLossUsd?.toLocaleString('en-US')} USD)`
                            : '$12,500 USD (5%)'}
                    </span>
                </div>
            </div>
        </div>
    );
};

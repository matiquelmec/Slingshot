'use client';

import React from 'react';
import { Network, BarChart3, Radar, BrainCircuit, Clock } from 'lucide-react';
import { MLProjection, SessionData, TacticalDecision } from '../../types/signal';

interface DiagnosticGridProps {
    tacticalDecision: TacticalDecision | null;
    activeTimeframe: string;
    mlProjection: MLProjection | null;
    sessionData: SessionData | null;
}

const DiagnosticGridModule: React.FC<DiagnosticGridProps> = ({
    tacticalDecision, activeTimeframe, mlProjection, sessionData
}) => {

    // SMC Data extraída del payload táctico
    const smc = tacticalDecision?.smc || { order_blocks: { bullish: [], bearish: [] }, fvgs: { bullish: [], bearish: [] } };
    const bullOBs = smc.order_blocks?.bullish?.length || 0;
    const bearOBs = smc.order_blocks?.bearish?.length || 0;
    const activeFVGs = (smc.fvgs?.bullish?.length || 0) + (smc.fvgs?.bearish?.length || 0);
    
    // RVOL (Volume Institucional)
    const rvol = tacticalDecision?.diagnostic?.volume || 1.0;
    const isHighVolume = rvol >= 1.5;

    const getMlColor = () => {
        if (mlProjection?.direction === 'ALCISTA') return 'text-neon-green';
        if (mlProjection?.direction === 'BAJISTA') return 'text-neon-red';
        return 'text-white/40';
    };

    return (
        <div className="flex-none grid grid-cols-5 gap-4 p-4 border-b border-white/5 bg-gradient-to-b from-white/[0.02] to-transparent">
            {/* Module A: Structure & Regime */}
            <div className="col-span-1 flex flex-col justify-between border-r border-white/5 pr-4">
                <div className="flex items-center gap-2 mb-2">
                    <Network size={12} className="text-white/40" />
                    <span className="text-[9px] font-bold tracking-widest text-white/40 uppercase">Estructura & Régimen</span>
                </div>
                <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-1 rounded border border-white/10 bg-white/5 text-[10px] font-bold tracking-widest text-white/80">
                        {tacticalDecision?.regime || 'CALIBRATING'}
                    </span>
                    <span className="px-2 py-1 rounded border border-blue-500/20 bg-blue-500/10 text-[10px] font-bold tracking-widest text-blue-400">
                        {activeTimeframe}
                    </span>
                </div>
                <div className="flex flex-col gap-1 text-[10px] font-mono">
                    <div className="flex items-center justify-between">
                        <span className="text-white/40">RESIST:</span>
                        <span className="text-green-400/80">${tacticalDecision?.nearest_resistance?.toLocaleString(undefined, { minimumFractionDigits: 2 }) || '---'}</span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span className="text-white/40">SUPPORT:</span>
                        <span className="text-red-400/80">${tacticalDecision?.nearest_support?.toLocaleString(undefined, { minimumFractionDigits: 2 }) || '---'}</span>
                    </div>
                </div>
            </div>
            {/* Module B: Perfil de Liquidez (SMC) */}
            <div className="col-span-1 flex flex-col justify-between border-r border-white/5 pr-4 pl-2">
                <div className="flex items-center gap-2 mb-2">
                    <BarChart3 size={12} className="text-white/40" />
                    <span className="text-[9px] font-bold tracking-widest text-white/40 uppercase">Perfil de Liquidez</span>
                </div>
                <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-between text-[10px] font-mono">
                        <span className="text-white/50">ORDER BLOCKS:</span>
                        <div className="flex gap-1.5">
                            <span className="text-neon-green font-bold">{bullOBs}</span>
                            <span className="text-white/20">/</span>
                            <span className="text-neon-red font-bold">{bearOBs}</span>
                        </div>
                    </div>
                    <div className="flex items-center justify-between text-[10px] font-mono">
                        <span className="text-white/50">ACTIVE FVGs:</span>
                        <span className="text-yellow-400 font-bold">{activeFVGs}</span>
                    </div>
                </div>
            </div>


            {/* Module C: Volumen Institucional (RVOL) */}
            <div className="col-span-1 flex flex-col justify-between border-r border-white/5 pr-4 pl-2">
                <div className="flex items-center gap-2 mb-2">
                    <Radar size={12} className="text-white/40" />
                    <span className="text-[9px] font-bold tracking-widest text-white/40 uppercase">Esfuerzo Institucional</span>
                </div>
                <div className="flex items-center gap-3">
                    <div className="relative flex h-8 w-8 items-center justify-center">
                        {isHighVolume && (
                            <>
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neon-green opacity-20" />
                                <span className="absolute inline-flex h-6 w-6 rounded-full border-2 border-neon-green/50 animate-pulse" />
                            </>
                        )}
                        <div className={`relative inline-flex rounded-full h-3 w-3 ${isHighVolume ? 'bg-neon-green shadow-[0_0_10px_rgba(0,255,65,1)]' : 'bg-white/10'}`} />
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] font-bold tracking-widest text-white/60">RVOL (RELATIVE VOL)</span>
                        <span className={`text-[11px] font-black ${isHighVolume ? 'text-neon-green' : 'text-white/30'}`}>
                            {rvol.toFixed(2)}x {isHighVolume ? 'ALTO' : 'NORMAL'}
                        </span>
                    </div>
                </div>
            </div>

            {/* Module D: HTF BIAS (Portero Institucional) */}
            <div className="col-span-1 flex flex-col justify-between border-r border-white/5 pr-4 pl-2">
                <div className="flex items-center gap-2 mb-2">
                    <Radar size={12} className="text-white/40" />
                    <span className="text-[9px] font-bold tracking-widest text-white/40 uppercase">Sesgo Institucional (HTF)</span>
                </div>
                <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between mb-1">
                        <span className={`text-[11px] font-black tracking-tighter ${
                            tacticalDecision?.htf_bias?.direction === 'BULLISH' ? 'text-neon-green' : 
                            tacticalDecision?.htf_bias?.direction === 'BEARISH' ? 'text-neon-red' : 'text-white/40'
                        }`}>
                            {tacticalDecision?.htf_bias?.direction || 'ANALIZANDO...'}
                        </span>
                        <span className="text-[9px] font-mono text-white/30">H4+H1</span>
                    </div>
                    <div className="text-[8px] leading-tight text-white/50 italic opacity-80 line-clamp-2">
                         {tacticalDecision?.htf_bias?.reason || "Esperando confirmación de temporalidades mayores..."}
                    </div>
                </div>
            </div>

            {/* Module E: AI & Environment */}
            <div className="col-span-1 flex flex-col justify-between pl-2">
                <div className="flex items-center gap-2 mb-2">
                    <BrainCircuit size={12} className="text-white/40" />
                    <span className="text-[9px] font-bold tracking-widest text-white/40 uppercase">ML Inferencia</span>
                </div>
                <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between text-[10px] font-mono bg-white/[0.02] border border-white/5 rounded px-2 py-1">
                        <span className="text-white/50 text-[9px]">PROJECTION:</span>
                        <span className={`font-bold ${getMlColor()}`}>{mlProjection?.direction} {(mlProjection?.probability || 0).toFixed(0)}%</span>
                    </div>
                    <div className="flex items-center justify-between text-[10px] font-mono bg-white/[0.02] border border-white/5 rounded px-2 py-1">
                        <span className="flex items-center gap-1 text-white/50"><Clock size={10} /> SESSION:</span>
                        <span className="text-white/80 font-bold truncate">{sessionData?.current_session || '---'}</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

// Utilizamos memo para que JAMÁS se redibuje por el live price
export default React.memo(DiagnosticGridModule);

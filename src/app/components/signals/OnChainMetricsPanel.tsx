'use client';

import React from 'react';
import { Activity, TrendingUp, TrendingDown } from 'lucide-react';
import { OnChainMetrics } from '../../types/signal';

interface OnChainMetricsPanelProps {
    metrics: OnChainMetrics | null;
}

const OnChainMetricsPanel: React.FC<OnChainMetricsPanelProps> = ({ metrics }) => {
    if (!metrics) {
        return (
            <div className="h-full flex items-center justify-center py-4">
                 <div className="text-[10px] text-white/20 font-mono animate-pulse">
                    LOADING ON-CHAIN DATA...
                </div>
            </div>
        );
    }

    const { oi_delta_pct, funding_rate, whale_alerts_count, onchain_bias } = metrics;
    
    return (
        <div className="h-full flex flex-col justify-center py-2 space-y-3">
            {/* Sentiment Header */}
            <div className="flex items-center justify-between">
                <span className="text-[10px] text-white/40 font-bold tracking-widest uppercase flex items-center gap-1.5">
                    <Activity size={12} className="text-neon-cyan" />
                    On-Chain Bias
                </span>
                <span className={`text-[10px] font-black px-2 py-0.5 rounded border ${
                    onchain_bias === 'BULLISH_ACCUMULATION' ? 'bg-neon-green/10 text-neon-green border-neon-green/20' :
                    onchain_bias === 'BEARISH_WARNING' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                    'bg-white/5 text-white/60 border-white/10'
                }`}>
                    {onchain_bias.replace(/_/g, ' ')}
                </span>
            </div>

            {/* Metrics Row */}
            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                    <div className="text-[9px] text-white/30 uppercase tracking-tighter">Open Interest Δ</div>
                    <div className={`text-sm font-mono font-bold flex items-center gap-1 ${oi_delta_pct > 0 ? 'text-neon-green' : oi_delta_pct < 0 ? 'text-red-400' : 'text-white/20'}`}>
                        {metrics.is_spot_only ? (
                            <span className="text-[10px] tracking-tight text-white/30">SPOT ASSET</span>
                        ) : (
                            <>
                                {oi_delta_pct > 0 ? <TrendingUp size={12} /> : oi_delta_pct < 0 ? <TrendingDown size={12} /> : <Activity size={12} className="animate-pulse" />}
                                {oi_delta_pct !== 0 ? (
                                    <>{oi_delta_pct > 0 ? '+' : ''}{oi_delta_pct.toFixed(6)}%</>
                                ) : (
                                    <span className="text-[10px] tracking-tight">CALIBRANDO</span>
                                )}
                            </>
                        )}
                    </div>
                </div>
                <div className="space-y-1">
                    <div className="text-[9px] text-white/30 uppercase tracking-tighter">Funding Rate</div>
                    <div className="text-sm font-mono font-bold text-white/80">
                        {metrics.is_spot_only ? (
                            <span className="text-[10px] tracking-tight text-white/20 uppercase font-bold">No-Derivatives</span>
                        ) : (
                            <>{funding_rate.toFixed(4)}%</>
                        )}
                    </div>
                </div>
            </div>

            {/* Whale Info */}
            <div className={`p-2 rounded-lg border transition-all duration-300 ${
                whale_alerts_count > 0 ? 'bg-yellow-500/10 border-yellow-500/20' : 'bg-white/5 border-white/5'
            }`}>
                <div className="flex items-center justify-between">
                    <span className="text-[9px] text-white/40 uppercase">Whale Activity (24h)</span>
                    <span className={`text-[11px] font-bold ${whale_alerts_count > 0 ? 'text-yellow-400' : 'text-white/60'}`}>
                        {whale_alerts_count} ALERTS
                    </span>
                </div>
                {metrics.last_whale_alert && (
                    <div className="mt-1 text-[9px] text-white/60 leading-tight">
                        Last: <span className="text-white font-bold">${(metrics.last_whale_alert.amount / 1_000_000).toFixed(1)}M</span> to {metrics.last_whale_alert.to}
                    </div>
                )}
            </div>
        </div>
    );
};

export default OnChainMetricsPanel;

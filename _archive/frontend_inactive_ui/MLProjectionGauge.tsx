'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Activity } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';

export default function MLProjectionGauge() {
    const { mlProjection, activeTimeframe } = useTelemetryStore();

    return (
        <div className="h-36 bg-gradient-to-br from-[#050B14] to-black backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl flex flex-col justify-between p-5 relative overflow-hidden">
            <div className={`absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(${mlProjection.direction === 'ALCISTA' ? '0,255,65' : mlProjection.direction === 'BAJISTA' ? '255,0,60' : '100,100,100'},0.1),transparent_50%)] pointer-events-none transition-colors duration-1000`} />

            <div className="flex justify-between items-start z-10">
                <p className="text-[10px] text-white/50 tracking-[0.2em] font-bold uppercase">Proyección IA (XGBoost)</p>
                <Activity size={14} className={`${mlProjection.direction === 'ALCISTA' ? 'text-neon-green' : mlProjection.direction === 'BAJISTA' ? 'text-neon-red' : 'text-gray-400'} opacity-50`} />
            </div>

            <div className="z-10">
                <div className="flex items-baseline gap-3">
                    <span className={`text-4xl font-black ${mlProjection.direction === 'ALCISTA' ? 'text-neon-green drop-shadow-[0_0_15px_rgba(0,255,65,0.5)]' : mlProjection.direction === 'BAJISTA' ? 'text-neon-red drop-shadow-[0_0_15px_rgba(255,0,60,0.5)]' : 'text-white/50'} tracking-tighter`}>
                        {mlProjection.probability}%
                    </span>
                    <div className="flex flex-col">
                        <span className={`text-xs ${mlProjection.direction === 'ALCISTA' ? 'text-neon-green/80' : mlProjection.direction === 'BAJISTA' ? 'text-neon-red/80' : 'text-white/40'} font-semibold tracking-wider uppercase`}>
                            {mlProjection.direction} ({activeTimeframe})
                        </span>
                        {mlProjection.reason && (
                            <span className="text-[9px] text-white/40 mt-1 max-w-[200px] leading-tight break-words">
                                {mlProjection.reason}
                            </span>
                        )}
                    </div>
                </div>
                <div className="h-2 w-full bg-black rounded-full mt-4 overflow-hidden border border-white/5">
                    <motion.div
                        animate={{ width: `${mlProjection.probability}%` }}
                        transition={{ duration: 1.5, ease: [0.16, 1, 0.3, 1] }}
                        className={`h-full bg-gradient-to-r ${mlProjection.direction === 'ALCISTA' ? 'from-green-600 to-neon-green shadow-[0_0_15px_rgba(0,255,65,0.8)]' : mlProjection.direction === 'BAJISTA' ? 'from-red-600 to-neon-red shadow-[0_0_15px_rgba(255,0,60,0.8)]' : 'from-gray-600 to-gray-400'} relative`}
                    >
                        <div className="absolute top-0 right-0 bottom-0 w-4 bg-white/30 rounded-full blur-[2px]" />
                    </motion.div>
                </div>
            </div>
        </div>
    );
}

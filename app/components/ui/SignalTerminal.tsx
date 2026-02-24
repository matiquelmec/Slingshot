'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Terminal, ChevronRight, Activity, TrendingUp, TrendingDown, Clock, ShieldCheck } from 'lucide-react';
import { useTelemetryStore, Signal } from '../../store/telemetryStore';
import SignalDiagnostic from './SignalDiagnostic';

export default function SignalTerminal() {
    const signalHistory = useTelemetryStore(s => s.signalHistory);
    const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);

    return (
        <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl flex flex-col overflow-hidden relative min-h-[300px] flex-1">
            <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none" />

            <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                <div className="flex items-center gap-2.5">
                    <Terminal size={15} className="text-neon-cyan" />
                    <h2 className="text-xs font-bold text-white/90 tracking-widest uppercase">Signal Terminal v2.0</h2>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[10px] text-white/30 font-mono tracking-tighter">CONEXIÓN DIRECTA</span>
                    <div className="h-1.5 w-1.5 rounded-full bg-neon-green animate-pulse" />
                </div>
            </div>

            <div className="p-2 flex flex-col gap-1 overflow-y-auto max-h-[400px] custom-scrollbar">
                <AnimatePresence initial={false}>
                    {signalHistory.length === 0 ? (
                        <div className="p-6 text-center">
                            <Activity size={24} className="text-white/10 mx-auto mb-2" />
                            <p className="text-[10px] text-white/20 italic">No se han detectado señales en la sesión actual...</p>
                        </div>
                    ) : (
                        signalHistory.map((signal) => (
                            <motion.div
                                key={signal.id}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                onClick={() => setSelectedSignal(signal)}
                                className="group relative flex flex-col gap-1 p-3 rounded-xl hover:bg-white/[0.03] cursor-pointer transition-colors border border-transparent hover:border-white/5"
                            >
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <div className={`px-2 py-0.5 rounded text-[10px] font-black tracking-tighter ${signal.type === 'LONG' ? 'bg-neon-green/20 text-neon-green border border-neon-green/30' :
                                            signal.type === 'SHORT' ? 'bg-neon-red/20 text-neon-red border border-neon-red/30' :
                                                'bg-white/10 text-white/60 border border-white/20'
                                            }`}>
                                            {signal.type}
                                        </div>
                                        <span className="text-[11px] font-black text-white/90 font-mono tracking-tight">
                                            ${signal.price.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        {signal.confluence_score && (
                                            <div className={`flex items-center gap-1.5 px-1.5 py-0.5 rounded-md bg-white/5 border border-white/5`}>
                                                <div className={`h-1 w-1 rounded-full ${signal.confluence_score > 75 ? 'bg-neon-green shadow-[0_0_5px_rgba(0,255,65,0.8)]' : 'bg-yellow-500 shadow-[0_0_5px_rgba(234,179,8,0.8)]'}`} />
                                                <span className={`text-[9px] font-bold ${signal.confluence_score > 75 ? 'text-neon-green' : 'text-white/60'}`}>
                                                    {signal.confluence_score}%
                                                </span>
                                            </div>
                                        )}
                                        <span className="text-[9px] text-white/30 font-mono">
                                            {signal.timestamp}
                                        </span>
                                    </div>
                                </div>

                                <div className="flex items-center gap-2 text-[10px] ml-1">
                                    <ChevronRight size={10} className="text-neon-cyan/50" />
                                    <span className="text-white/40 uppercase tracking-wider">{signal.strategy}</span>
                                    <span className="text-white/20">•</span>
                                    <span className="text-neon-cyan/70 font-bold">{signal.symbol}</span>
                                    <span className="text-white/20">•</span>
                                    <span className="text-white/40">{signal.timeframe}</span>
                                </div>
                            </motion.div>
                        ))
                    )}
                </AnimatePresence>
            </div>

            {/* Terminal Footer */}
            <div className="mt-auto p-3 border-t border-white/5 bg-black/20">
                <div className="flex items-center gap-2 text-[9px] text-white/40 font-mono">
                    <Clock size={10} />
                    <span className="tracking-tight uppercase">Esperando próxima oportunidad neural...</span>
                </div>
            </div>

            {/* Interactive Diagnostic Modal */}
            <AnimatePresence>
                {selectedSignal && (
                    <SignalDiagnostic
                        signal={selectedSignal}
                        onClose={() => setSelectedSignal(null)}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}

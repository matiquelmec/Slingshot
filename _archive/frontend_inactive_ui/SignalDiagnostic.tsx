'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle2, AlertTriangle, Info, Zap, Brain, ShieldCheck } from 'lucide-react';
import { Signal } from '../../store/telemetryStore';

interface SignalDiagnosticProps {
    signal: Signal;
    onClose: () => void;
}

export default function SignalDiagnostic({ signal, onClose }: SignalDiagnosticProps) {
    const score = signal.confluence_score || 0;
    const confluences = signal.confluences || [];

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
        >
            <div className="w-full max-w-2xl bg-[#0A0F1A] border border-white/10 rounded-3xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,1)] relative">
                {/* Header Neon Background */}
                <div className={`absolute top-0 inset-x-0 h-1 ${score > 75 ? 'bg-neon-green' : score > 50 ? 'bg-yellow-500' : 'bg-neon-red'} shadow-[0_0_15px_rgba(0,255,65,0.5)]`} />

                {/* Header */}
                <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
                    <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${signal.type === 'LONG' ? 'bg-green-500/10 text-neon-green' : 'bg-red-500/10 text-neon-red'}`}>
                            <Zap size={20} />
                        </div>
                        <div>
                            <h3 className="text-xl font-bold tracking-tight">Análisis Neural v2.0</h3>
                            <p className="text-[10px] text-white/40 uppercase tracking-widest">{signal.symbol} • {signal.timeframe} • {signal.timestamp}</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-full transition-colors">
                        <X size={20} className="text-white/40" />
                    </button>
                </div>

                <div className="p-8 grid grid-cols-1 md:grid-cols-2 gap-8 max-h-[70vh] overflow-y-auto custom-scrollbar">

                    {/* Left Side: Score & Reasoning */}
                    <div className="flex flex-col gap-6">
                        <div className="relative h-48 w-48 mx-auto flex items-center justify-center">
                            <svg className="w-full h-full transform -rotate-90">
                                <circle
                                    cx="96" cy="96" r="80"
                                    stroke="currentColor" strokeWidth="8"
                                    fill="transparent" className="text-white/5"
                                />
                                <motion.circle
                                    cx="96" cy="96" r="80"
                                    stroke="currentColor" strokeWidth="8"
                                    fill="transparent"
                                    strokeDasharray={502.6}
                                    initial={{ strokeDashoffset: 502.6 }}
                                    animate={{ strokeDashoffset: 502.6 - (502.6 * score) / 100 }}
                                    transition={{ duration: 1.5, ease: "easeOut" }}
                                    className={`${score > 75 ? 'text-neon-green' : score > 50 ? 'text-yellow-500' : 'text-neon-red'} drop-shadow-[0_0_15px_rgba(0,255,65,0.3)]`}
                                />
                            </svg>
                            <div className="absolute inset-0 flex flex-col items-center justify-center">
                                <span className="text-5xl font-black tracking-tighter">{score}%</span>
                                <span className="text-[10px] text-white/40 uppercase font-bold tracking-[0.2em]">Convicción</span>
                            </div>
                        </div>

                        <div className="bg-white/[0.03] rounded-2xl p-5 border border-white/5">
                            <div className="flex items-center gap-2 mb-3">
                                <Brain size={16} className="text-neon-cyan" />
                                <span className="text-xs font-bold text-neon-cyan uppercase tracking-wider">Razonamiento Neural</span>
                            </div>
                            <p className="text-xs leading-relaxed text-white/70 italic">
                                "{signal.reasoning || "Analizando confluencias de mercado para determinar robustez de la señal..."}"
                            </p>
                        </div>
                    </div>

                    {/* Right Side: Confluence Checklist */}
                    <div className="flex flex-col gap-4">
                        <h4 className="text-xs font-bold text-white/40 uppercase tracking-[0.2em] mb-2 flex items-center gap-2">
                            <ShieldCheck size={14} /> Mapa de Confluencia
                        </h4>

                        <div className="space-y-3">
                            {confluences.length > 0 ? confluences.map((conf, idx) => (
                                <motion.div
                                    key={idx}
                                    initial={{ x: 20, opacity: 0 }}
                                    animate={{ x: 0, opacity: 1 }}
                                    transition={{ delay: idx * 0.1 }}
                                    className="group flex items-start gap-4 p-3 rounded-xl hover:bg-white/[0.03] transition-all border border-transparent hover:border-white/5"
                                >
                                    {conf.status === 'CONFIRMADO' ? (
                                        <CheckCircle2 size={18} className="text-neon-green mt-0.5 flex-shrink-0" />
                                    ) : conf.status === 'DIVERGENTE' || conf.status === 'PRECABER' ? (
                                        <AlertTriangle size={18} className="text-neon-red mt-0.5 flex-shrink-0" />
                                    ) : (
                                        <Info size={18} className="text-yellow-500/80 mt-0.5 flex-shrink-0" />
                                    )}
                                    <div>
                                        <p className="text-sm font-semibold text-white/90 leading-none group-hover:text-white transition-colors">
                                            {conf.factor}
                                        </p>
                                        <p className="text-[10px] text-white/30 mt-1 uppercase tracking-wider group-hover:text-white/50 transition-colors">
                                            {conf.detail}
                                        </p>
                                    </div>
                                </motion.div>
                            )) : (
                                <div className="p-8 text-center bg-white/[0.02] rounded-2xl border border-dashed border-white/5">
                                    <p className="text-xs text-white/20">Cargando diagnóstico institucional...</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Footer Analysis Tooltip */}
                <div className="p-4 bg-white/[0.02] border-t border-white/5 text-center">
                    <p className="text-[9px] text-white/20 uppercase tracking-[0.3em] font-medium">
                        Algoritmo Slingshot • Nivel Institucional • Precisión Basada en 24 Factores Neurales
                    </p>
                </div>
            </div>
        </motion.div>
    );
}

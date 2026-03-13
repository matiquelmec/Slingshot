'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Activity, ShieldCheck, Cpu } from 'lucide-react';
import ActiveAssetsMonitor from '../../components/radar/ActiveAssetsMonitor';
import RadarFeed from '../../components/radar/RadarFeed';

export default function RadarPage() {
    return (
        <div className="h-full w-full flex flex-col gap-6 p-6 overflow-y-auto custom-scrollbar">
            {/* Header / Stats Summary */}
            <div className="flex flex-col md:flex-row gap-6 items-stretch">
                <motion.div 
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="flex-1 bg-gradient-to-br from-[#0A121E] to-[#050B14] border border-white/5 rounded-3xl p-6 shadow-2xl relative overflow-hidden"
                >
                    <div className="absolute top-0 right-0 p-8 opacity-5">
                        <Activity size={120} />
                    </div>
                    <div className="relative z-10">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-2 bg-neon-cyan/20 rounded-xl border border-neon-cyan/30">
                                <Cpu size={20} className="text-neon-cyan" />
                            </div>
                            <h1 className="text-2xl font-black text-white tracking-tight">Radar Center</h1>
                        </div>
                        <p className="text-white/50 text-sm max-w-md leading-relaxed">
                            Monitoreo cuántico en tiempo real. Los activos listados aquí están siendo procesados 
                            por el <span className="text-neon-cyan font-bold">Slingshot Master Engine</span> de forma continua.
                        </p>
                    </div>
                </motion.div>

                <motion.div 
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="w-full md:w-80 bg-neon-cyan/5 border border-neon-cyan/10 rounded-3xl p-6 flex flex-col justify-center items-center text-center gap-3"
                >
                    <div className="p-3 bg-neon-green/20 rounded-full border border-neon-green/30">
                        <ShieldCheck size={32} className="text-neon-green" />
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-white uppercase tracking-widest">Sincronización OK</h3>
                        <p className="text-[10px] text-white/40 font-mono mt-1">LATENCIA: 14ms | MASTER NODE: v3.2</p>
                    </div>
                </motion.div>
            </div>

            {/* Asset Monitor (Core of Radar) */}
            <motion.section
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
            >
                <ActiveAssetsMonitor />
            </motion.section>

            {/* Signal Feed / Terminal Integration */}
            <div className="grid grid-cols-1 gap-6">
                <motion.section
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="bg-[#050B14]/40 border border-white/5 rounded-3xl overflow-hidden"
                >
                    <div className="p-6 border-b border-white/5 flex items-center justify-between">
                        <h2 className="text-sm font-bold text-white uppercase tracking-widest flex items-center gap-2">
                            <Activity size={16} className="text-neon-red" />
                            Feed de Señales Activas
                        </h2>
                    </div>
                    <div className="h-[500px]">
                        <RadarFeed />
                    </div>
                </motion.section>
            </div>
        </div>
    );
}

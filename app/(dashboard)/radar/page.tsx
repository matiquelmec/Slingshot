'use client';

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';
import { Radio, ShieldCheck, Activity } from 'lucide-react';

const RadarFeed = dynamic(() => import('../../components/radar/RadarFeed'), { ssr: false });
const ActiveAssetsMonitor = dynamic(() => import('../../components/radar/ActiveAssetsMonitor'), { ssr: false });

export default function RadarPage() {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    if (!mounted) return null;

    return (
        <div className="h-full w-full flex flex-col p-6 overflow-hidden bg-transparent">
            {/* Header Section */}
            <header className="flex items-center justify-between mb-8">
                <div className="flex flex-col">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-neon-cyan/10 border border-neon-cyan/30 rounded-lg">
                            <Radio size={20} className="text-neon-cyan animate-pulse" />
                        </div>
                        <h2 className="text-2xl font-black text-white tracking-[0.2em] drop-shadow-[0_0_10px_rgba(0,229,255,0.4)]">
                            RADAR CENTER
                        </h2>
                    </div>
                    <p className="text-[10px] text-white/40 mt-1 tracking-[0.3em] font-bold uppercase pl-1">
                        Monitoreo Adaptativo Multi-Activo v2.0
                    </p>
                </div>

                <div className="flex gap-4">
                    <div className="flex items-center gap-3 bg-black/40 backdrop-blur-md px-4 py-2 rounded-xl border border-white/5">
                        <ShieldCheck size={16} className="text-neon-green" />
                        <span className="text-[10px] font-bold text-white/60 tracking-wider">MALLA DE VIGILANCIA ACTIVA</span>
                    </div>
                    <div className="flex items-center gap-3 bg-neon-cyan/5 px-4 py-2 rounded-xl border border-neon-cyan/20">
                        <Activity size={16} className="text-neon-cyan" />
                        <span className="text-[10px] font-bold text-neon-cyan tracking-wider uppercase">Analizando 24/7</span>
                    </div>
                </div>
            </header>

            {/* Main Content Layout */}
            <div className="flex-1 grid grid-cols-12 gap-6 overflow-hidden">
                {/* Left Side: Active Assets Status */}
                <motion.section
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="col-span-12 lg:col-span-4 flex flex-col min-h-0"
                >
                    <ActiveAssetsMonitor />
                </motion.section>

                {/* Right Side: Global Signal Feed */}
                <motion.section
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 }}
                    className="col-span-12 lg:col-span-8 flex flex-col min-h-0"
                >
                    <RadarFeed />
                </motion.section>
            </div>
        </div>
    );
}

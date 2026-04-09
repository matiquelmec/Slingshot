'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Newspaper, Flame, Droplets, Zap, ExternalLink, BrainCircuit } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';

export default function NewsTerminal() {
    const { news, setNews } = useTelemetryStore();

    React.useEffect(() => {
        // Cargar historial de noticias al montar (REST fallback)
        const fetchNewsHistory = async () => {
            try {
                const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
                const res = await fetch(`${BASE_URL}/api/v1/news`);
                if (res.ok) {
                    const data = await res.json();
                    if (Array.isArray(data) && data.length > 0) {
                        setNews(data);
                    }
                }
            } catch (e) {
                console.warn("NewsTerminal: No se pudo cargar el historial de noticias.");
            }
        };

        if (news.length === 0) {
            fetchNewsHistory();
        }
    }, [news.length, setNews]);

    const getSentimentStyles = (sentiment: string) => {
        switch (sentiment) {
            case 'BULLISH':
                return {
                    icon: <Flame size={14} className="text-neon-green" />,
                    bg: 'bg-neon-green/10',
                    border: 'border-neon-green/30',
                    glow: 'shadow-[0_0_15px_rgba(0,255,65,0.2)]',
                    text: 'text-neon-green'
                };
            case 'BEARISH':
                return {
                    icon: <Droplets size={14} className="text-neon-red rotate-180" />,
                    bg: 'bg-neon-red/10',
                    border: 'border-neon-red/30',
                    glow: 'shadow-[0_0_15px_rgba(255,0,60,0.2)]',
                    text: 'text-neon-red'
                };
            default:
                return {
                    icon: <Zap size={14} className="text-white/40" />,
                    bg: 'bg-white/5',
                    border: 'border-white/10',
                    glow: '',
                    text: 'text-white/60'
                };
        }
    };

    return (
        <div className="flex flex-col h-full overflow-hidden">
            <div className="p-4 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-neon-purple/20 via-transparent to-transparent">
                <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded-lg bg-neon-purple/10 border border-neon-purple/20 shadow-[0_0_15px_rgba(191,0,255,0.1)]">
                        <Newspaper size={14} className="text-neon-purple" />
                    </div>
                    <div>
                        <h2 className="text-[10px] font-black text-white tracking-[0.2em] drop-shadow-[0_0_8px_rgba(191,0,255,0.4)]">RADAR DE NOTICIAS IA</h2>
                        <div className="h-0.5 w-8 bg-neon-purple/50 rounded-full mt-0.5" />
                    </div>
                </div>
                <div className="flex items-center gap-2 px-2 py-1 rounded-full bg-black/40 border border-white/5 shadow-inner">
                    <div className="relative">
                        <div className="h-1.5 w-1.5 rounded-full bg-neon-purple animate-ping absolute" />
                        <div className="h-1.5 w-1.5 rounded-full bg-neon-purple shadow-[0_0_5px_rgba(191,0,255,1)] relative" />
                    </div>
                    <span className="text-[9px] text-white/70 font-mono font-bold tracking-tighter">OLLAMA ACTIVE</span>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
                <AnimatePresence initial={false}>
                    {news.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center opacity-30 gap-3">
                            <BrainCircuit size={32} className="animate-pulse" />
                            <p className="text-[10px] font-mono tracking-widest text-center">ESCANEANDO REDES NEURALES COGNITIVAS...</p>
                        </div>
                    ) : (
                        news.map((item, idx) => {
                            const style = getSentimentStyles(item.sentiment);
                            return (
                                <motion.div
                                    key={`news-${item.timestamp}-${idx}`}
                                    initial={{ opacity: 0, x: 20, scale: 0.95 }}
                                    animate={{ opacity: 1, x: 0, scale: 1 }}
                                    transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                                    className={`p-3 rounded-xl border ${style.bg} ${style.border} ${style.glow} group relative overflow-hidden`}
                                >
                                    <div className="flex items-start gap-3 relative z-10">
                                        <div className="mt-1">{style.icon}</div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex justify-between items-start mb-1 gap-2">
                                                <span className={`text-[9px] font-black tracking-widest uppercase ${style.text}`}>
                                                    {item.sentiment} ({Math.round(item.score * 100)}%)
                                                </span>
                                                <span className="text-[8px] text-white/20 font-mono">
                                                    {new Date(item.timestamp).toLocaleTimeString()}
                                                </span>
                                            </div>
                                            <h3 className="text-[11px] font-bold text-white/90 leading-tight mb-2 group-hover:text-white transition-colors">
                                                {item.title}
                                            </h3>
                                            <div className="bg-black/40 rounded-lg p-2 border border-white/5">
                                                <p className="text-[9.5px] text-white/60 leading-relaxed italic pr-4">
                                                    <span className="text-neon-purple font-bold">INSIGHT IA:</span> {item.impact}
                                                </p>
                                            </div>
                                            <div className="mt-2 flex items-center justify-between">
                                                <span className="text-[9px] text-white/20 font-bold tracking-widest uppercase">{item.source}</span>
                                                <a 
                                                    href={item.url} 
                                                    target="_blank" 
                                                    rel="noopener noreferrer"
                                                    className="opacity-0 group-hover:opacity-100 transition-all flex items-center gap-1.5 px-2 py-1 rounded-md bg-white/5 border border-white/10 text-[8px] font-bold text-white/50 hover:text-white hover:bg-white/10 hover:border-white/20"
                                                >
                                                    EXPLORAR <ExternalLink size={8} />
                                                </a>
                                            </div>
                                        </div>
                                    </div>
                                    {/* Subtle background glow effect on sentiment color */}
                                    <div className={`absolute -right-4 -bottom-4 w-12 h-12 rounded-full opacity-10 filter blur-xl ${style.text === 'text-neon-green' ? 'bg-neon-green' : style.text === 'text-neon-red' ? 'bg-neon-red' : 'bg-white'}`} />
                                </motion.div>
                            );
                        })
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}

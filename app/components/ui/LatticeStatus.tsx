'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTelemetryStore } from '../../store/telemetryStore';
import { Shield, Zap, AlertCircle, RefreshCw, Terminal, X, Globe } from 'lucide-react';
import { getApiBaseUrl } from '../../utils/apiUrl';

export default function LatticeStatus() {
    const { tacticalDecision, isConnected, connectionStatus, connectionMode, activeSymbol, latestPrice } = useTelemetryStore();
    const d = tacticalDecision;
    const isStale = d.is_stale || connectionStatus === 'STALLED' || connectionStatus === 'DISCONNECTED' || !isConnected;

    // Sandbox panel states
    const [showPlayground, setShowPlayground] = useState(false);
    const [testAsset, setTestAsset] = useState(activeSymbol || 'BTCUSDT');
    const [testDir, setTestDir] = useState<'LONG' | 'SHORT'>('LONG');
    const [testPrice, setTestPrice] = useState<number>(latestPrice || 50000.0);
    const [isInjecting, setIsInjecting] = useState(false);

    // Sync test fields when store values change
    React.useEffect(() => {
        if (activeSymbol) setTestAsset(activeSymbol);
    }, [activeSymbol]);

    React.useEffect(() => {
        if (latestPrice) setTestPrice(latestPrice);
    }, [latestPrice]);

    const handleInjectSignal = async () => {
        setIsInjecting(true);
        try {
            const api_key = 'SLINGSHOT_INTERNAL_V6';
            const BASE_URL = getApiBaseUrl();
            const endpoint = `${BASE_URL}/api/v1/inject-test-signal?api_key=${api_key}&symbol=${testAsset}&direction=${testDir}&price=${testPrice}`;
            
            const res = await fetch(endpoint, { method: 'POST' });
            if (res.ok) {
                const result = await res.json();
                console.log("Injected signal:", result);
                alert(`Señal inyectada con éxito para ${testAsset} (${testDir})`);
                setShowPlayground(false);
            } else {
                const err = await res.json();
                alert(`Error al inyectar señal: ${err.detail || res.statusText}`);
            }
        } catch (e) {
            console.error("Failed to inject test signal:", e);
            alert("Error de red al conectar con el backend.");
        } finally {
            setIsInjecting(false);
        }
    };

    return (
        <div className="flex items-center gap-4 px-6 h-14 bg-[#050B14]/80 backdrop-blur-md border-b border-white/5 relative z-50">
            {/* 1. Brand / Mode */}
            <div className="flex items-center gap-2.5">
                <div className="relative">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-cyan to-blue-600 flex items-center justify-center shadow-[0_0_15px_rgba(0,229,255,0.3)]">
                        <Zap size={16} className="text-white fill-white" />
                    </div>
                </div>
                <div>
                    <h1 className="text-[10px] font-black tracking-[0.3em] text-white/90">SLINGSHOT</h1>
                    <p className="text-[8px] font-bold text-neon-cyan/60 tracking-widest">GEN 1 PLATINUM</p>
                </div>
            </div>

            <div className="h-6 w-px bg-white/5 mx-2" />

            {/* 2. System Status Badge */}
            <AnimatePresence mode="wait">
                <motion.div 
                    key={isStale ? 'stale' : d.strategy}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    className={`px-3 py-1.5 rounded-full border flex items-center gap-2 ${
                        connectionStatus === 'DISCONNECTED' 
                        ? 'bg-neon-red/10 border-neon-red/30 text-neon-red shadow-[0_0_10px_rgba(255,0,0,0.2)]' 
                        : connectionStatus === 'STALLED'
                        ? 'bg-yellow-400/10 border-yellow-400/30 text-yellow-400 shadow-[0_0_10px_rgba(250,204,21,0.2)]'
                        : d.strategy?.includes('STANDBY') 
                        ? 'bg-white/10 border-white/30 text-white/80' 
                        : 'bg-neon-green/10 border-neon-green/30 text-neon-green shadow-[0_0_10px_rgba(0,255,0,0.1)]'
                    }`}
                >
                    {connectionStatus === 'DISCONNECTED' ? <AlertCircle size={12} className="animate-pulse" /> : connectionStatus === 'STALLED' ? <RefreshCw size={12} className="animate-spin" /> : <Shield size={12} />}
                    <span className="text-[9px] font-black tracking-widest uppercase">
                        {connectionStatus === 'DISCONNECTED' ? 'DISCONNECTED' : connectionStatus === 'STALLED' ? 'DATA LAG (STALLED)' : d.strategy?.includes('STANDBY') ? 'STANDBY' : 'OPERATIONAL'}
                    </span>
                </motion.div>
            </AnimatePresence>

            <div className="h-6 w-px bg-white/5 mx-2" />

            {/* System Load / Inference Latency (SIGMA) */}
            <div className="flex flex-col">
                <span className="text-[7px] font-bold text-white/30 tracking-[0.2em] uppercase">SYSTEM LOAD</span>
                <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-mono font-bold ${d.inference_latency && d.inference_latency > 50 ? 'text-neon-red' : 'text-neon-green'}`}>
                        {d.inference_latency || '32'}ms
                    </span>
                    <div className="flex gap-0.5 items-end h-3">
                        {[0.4, 0.6, 0.3, 0.8, 0.5].map((h, i) => (
                            <motion.div 
                                key={i}
                                className="w-[2px] bg-neon-green/40 rounded-full"
                                animate={{ height: [`${h*100}%`, `${(1-h)*100}%`, `${h*100}%`] }}
                                transition={{ duration: 1, repeat: Infinity, delay: i * 0.1 }}
                            />
                        ))}
                    </div>
                </div>
            </div>


            {/* 2.5 Ghost Sentinel Macro Banner (v17.1) */}
            {(() => {
                const ghost = useTelemetryStore.getState().ghostData;
                if (!ghost) return null;
                const fgVal = ghost.fear_greed_value ?? 50;
                const fgLabel = ghost.fear_greed_label ?? 'Neutral';
                const btcd = ghost.btc_dominance ? Number(ghost.btc_dominance).toFixed(1) : '56.9';
                const bias = ghost.macro_bias ?? 'NEUTRAL';
                
                const fgColor = fgVal < 30 ? 'text-neon-red bg-neon-red/10 border-neon-red/30' : fgVal > 70 ? 'text-neon-green bg-neon-green/10 border-neon-green/30' : 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30';
                const biasColor = bias === 'BLOCK_LONGS' ? 'text-orange-400 border-orange-400/30 bg-orange-400/10' : bias === 'BULLISH' ? 'text-neon-green border-neon-green/30 bg-neon-green/10' : bias === 'BEARISH' ? 'text-neon-red border-neon-red/30 bg-neon-red/10' : 'text-white/60 border-white/10 bg-white/5';
                
                return (
                    <div className="flex items-center gap-3">
                        {/* Fear & Greed */}
                        <div className={`px-2.5 py-1 rounded-lg border flex items-center gap-1.5 font-mono text-[9px] font-black ${fgColor}`}>
                            <span>🧠 F&G: {fgVal}</span>
                            <span className="text-[8px] opacity-80">({fgLabel})</span>
                        </div>
                        {/* BTC Dominance */}
                        <div className="px-2.5 py-1 rounded-lg border border-white/10 bg-white/5 font-mono text-[9px] font-black text-white/80 flex items-center gap-1">
                            <span className="text-neon-cyan">₿</span>
                            <span>DOM: {btcd}%</span>
                        </div>
                        {/* Macro Bias */}
                        <div className={`px-2.5 py-1 rounded-lg border font-mono text-[9px] font-black tracking-widest uppercase ${biasColor}`}>
                            <span>🛡️ {bias}</span>
                        </div>
                    </div>
                );
            })()}

            <div className="flex-1" />

            {/* 3. Global Stats */}
            <div className="flex items-center gap-6">
                {/* Absorción Global */}
                <div className="flex flex-col items-end">
                    <span className="text-[7px] font-bold text-white/30 tracking-widest">LATTICE ABSORPTION</span>
                    <div className="flex items-center gap-1.5">
                        <span className={`text-[11px] font-mono font-black ${d.diagnostic?.is_absorption_elite ? 'text-yellow-400 animate-pulse' : 'text-white/80'}`}>
                            {d.diagnostic?.absorption_score?.toFixed(2) || '0.00'}
                        </span>
                        <div className="w-12 h-1 bg-white/5 rounded-full overflow-hidden">
                            <motion.div 
                                className={`h-full ${d.diagnostic?.is_absorption_elite ? 'bg-yellow-400 shadow-[0_0_8px_yellow]' : 'bg-neon-cyan'}`}
                                initial={{ width: 0 }}
                                animate={{ width: `${Math.min((d.diagnostic?.absorption_score || 0) * 20, 100)}%` }}
                            />
                        </div>
                    </div>
                </div>

                {/* GGUF Platinum Sync (SIGMA) */}
                <div className="flex flex-col items-end">
                    <span className="text-[7px] font-bold text-white/30 tracking-widest uppercase">GGUF PLATINUM SYNC</span>
                    <div className="flex items-center gap-2 px-3 py-1 bg-neon-cyan/10 border border-neon-cyan/30 rounded-lg shadow-[0_0_10px_rgba(0,229,255,0.1)]">
                        <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-neon-cyan animate-pulse' : 'bg-neon-red'}`} />
                        <span className="text-[9px] font-black text-neon-cyan/80 font-mono tracking-tighter">
                            {d.gguf_sync_score ? (d.gguf_sync_score * 100).toFixed(1) : '98.5'}%
                        </span>
                    </div>
                </div>

                {/* Connection Mode Badge */}
                <div className="flex flex-col items-end">
                    <span className="text-[7px] font-bold text-white/30 tracking-widest uppercase">FEED CHANNEL</span>
                    <div className={`flex items-center gap-1.5 px-3 py-1 border rounded-lg font-mono text-[9px] font-black tracking-widest uppercase transition-all ${
                        connectionMode === 'FALLBACK'
                        ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400 shadow-[0_0_10px_rgba(250,204,21,0.1)]'
                        : connectionStatus === 'DISCONNECTED'
                        ? 'bg-red-500/10 border-red-500/30 text-red-400'
                        : 'bg-green-500/10 border-green-500/30 text-green-400 shadow-[0_0_10px_rgba(34,197,94,0.1)]'
                    }`}>
                        <Globe size={10} className={connectionMode === 'FALLBACK' ? 'animate-pulse' : ''} />
                        {connectionMode === 'FALLBACK' ? 'BITUNIX FALLBACK' : connectionStatus === 'DISCONNECTED' ? 'OFFLINE' : 'BINANCE FUTURES WS'}
                    </div>
                </div>

                {/* Sandbox Playground Button */}
                <button
                    onClick={() => setShowPlayground(!showPlayground)}
                    className={`px-3 py-2 border rounded-lg text-[9px] font-black uppercase tracking-widest flex items-center gap-1.5 transition-all ${
                        showPlayground 
                        ? 'bg-neon-cyan text-black border-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.3)]' 
                        : 'bg-white/5 border-white/10 text-white/60 hover:text-neon-cyan hover:border-neon-cyan/50 hover:bg-neon-cyan/5'
                    }`}
                >
                    <Terminal size={10} />
                    SANDBOX
                </button>
            </div>

            {/* Sandbox Playground Modal */}
            <AnimatePresence>
                {showPlayground && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="absolute top-16 right-6 w-80 bg-[#070e1a]/95 backdrop-blur-xl border border-white/10 rounded-xl p-4 shadow-[0_10px_30px_rgba(0,0,0,0.6)] z-50 flex flex-col gap-3"
                    >
                        <div className="flex items-center justify-between border-b border-white/5 pb-2">
                            <span className="text-[10px] font-black text-white tracking-wider flex items-center gap-1.5"><Terminal size={12} className="text-neon-cyan" /> DEV SANDBOX INJECTOR</span>
                            <button onClick={() => setShowPlayground(false)} className="text-white/40 hover:text-white"><X size={12} /></button>
                        </div>
                        
                        <div className="flex flex-col gap-3 text-[10px]">
                            {/* Asset select */}
                            <div className="flex flex-col gap-1">
                                <label className="text-white/40 font-bold tracking-wider">ACTIVO</label>
                                <select 
                                    id="sandbox-asset-select"
                                    name="sandboxAsset"
                                    value={testAsset} 
                                    onChange={(e) => setTestAsset(e.target.value)}
                                    className="bg-black/50 border border-white/10 rounded px-2.5 py-1.5 text-white font-mono outline-none focus:border-neon-cyan/50"
                                >
                                    <option value="BTCUSDT">BTCUSDT</option>
                                    <option value="ETHUSDT">ETHUSDT</option>
                                    <option value="SOLUSDT">SOLUSDT</option>
                                    <option value="XRPUSDT">XRPUSDT</option>
                                    <option value="PAXGUSDT">PAXGUSDT</option>
                                    <option value="XAGUSDT">XAGUSDT</option>
                                </select>
                            </div>

                            {/* Direction select */}
                            <div className="flex flex-col gap-1">
                                <label className="text-white/40 font-bold tracking-wider">DIRECCIÓN</label>
                                <div className="grid grid-cols-2 gap-2">
                                    <button 
                                        type="button"
                                        onClick={() => setTestDir('LONG')}
                                        className={`py-1.5 rounded font-black text-center transition-all outline-none ${testDir === 'LONG' ? 'bg-green-500/20 border border-green-500/50 text-green-400 shadow-[0_0_8px_rgba(34,197,94,0.1)]' : 'bg-white/5 border border-white/10 text-white/50 hover:bg-white/10'}`}
                                    >
                                        LONG
                                    </button>
                                    <button 
                                        type="button"
                                        onClick={() => setTestDir('SHORT')}
                                        className={`py-1.5 rounded font-black text-center transition-all outline-none ${testDir === 'SHORT' ? 'bg-red-500/20 border border-red-500/50 text-red-400 shadow-[0_0_8px_rgba(239,68,68,0.1)]' : 'bg-white/5 border border-white/10 text-white/50 hover:bg-white/10'}`}
                                    >
                                        SHORT
                                    </button>
                                </div>
                            </div>

                            {/* Price */}
                            <div className="flex flex-col gap-1">
                                <label className="text-white/40 font-bold tracking-wider">PRECIO DE REFERENCIA</label>
                                <input 
                                    id="sandbox-price-input"
                                    name="sandboxPrice"
                                    type="number" 
                                    value={testPrice} 
                                    onChange={(e) => setTestPrice(Number(e.target.value))}
                                    className="bg-black/50 border border-white/10 rounded px-2.5 py-1.5 text-white font-mono outline-none focus:border-neon-cyan/50"
                                />
                            </div>

                            <button
                                onClick={handleInjectSignal}
                                disabled={isInjecting}
                                className="mt-2 py-2 bg-gradient-to-r from-neon-cyan to-blue-600 hover:from-neon-cyan/80 hover:to-blue-600/80 text-white font-black rounded text-[10px] tracking-widest uppercase transition-all shadow-[0_0_15px_rgba(0,229,255,0.2)] disabled:opacity-50"
                            >
                                {isInjecting ? 'INYECTANDO...' : 'INYECTAR EN MEMORIA'}
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Stale Guard Overlay - Conditional inside the component for better UX */}
            {isStale && (
                <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="absolute inset-x-0 -bottom-1 h-0.5 bg-neon-red shadow-[0_0_10px_red]"
                />
            )}
        </div>
    );
}

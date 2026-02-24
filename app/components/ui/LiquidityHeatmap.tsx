'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Layers, ArrowDown, ArrowUp, Zap } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';

export default function LiquidityHeatmap() {
    const { liquidityHeatmap, latestPrice } = useTelemetryStore();

    if (!liquidityHeatmap || (!liquidityHeatmap.bids.length && !liquidityHeatmap.asks.length)) {
        return (
            <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl p-4 flex flex-col items-center justify-center min-h-[150px]">
                <Layers size={20} className="text-white/10 mb-2" />
                <p className="text-[10px] text-white/20 italic">Escaneando liquidez profunda (Order Book)...</p>
            </div>
        );
    }

    // Calcular volúmenes máximos para hacer las barras relativas
    const maxBidVol = Math.max(...liquidityHeatmap.bids.map(b => b.volume), 0.0001);
    const maxAskVol = Math.max(...liquidityHeatmap.asks.map(a => a.volume), 0.0001);

    // AI summary logic
    const totalBidVol = liquidityHeatmap.bids.reduce((acc, b) => acc + b.volume, 0);
    const totalAskVol = liquidityHeatmap.asks.reduce((acc, a) => acc + a.volume, 0);
    const totalVol = totalBidVol + totalAskVol;

    let summaryTitle = "Balance Neutro";
    let summaryColor = "text-white/50";
    let summaryBg = "bg-white/5 border-white/10";
    let iconColor = "text-white/40";
    let insights: string[] = ["Distribución de órdenes estable a corto plazo."];

    if (totalVol > 0) {
        const bidPct = (totalBidVol / totalVol) * 100;
        const askPct = (totalAskVol / totalVol) * 100;

        insights = [];

        if (askPct > 65) {
            summaryTitle = "Pared de Venta (Heavy Asks)";
            summaryColor = "text-neon-red";
            summaryBg = "bg-neon-red/10 border-neon-red/20";
            iconColor = "text-neon-red/70";
            insights.push(`${askPct.toFixed(0)}% del volumen está esperando vender.`);
            insights.push("Cuidado: Riesgo de rechazo al alza.");
            if (totalAskVol > 10) insights.push("Posible 'Spoofing' institucional actuando como barrera.");
        } else if (askPct > 55) {
            summaryTitle = "Presión de Venta Moderada";
            summaryColor = "text-red-400";
            summaryBg = "bg-red-400/10 border-red-400/20";
            iconColor = "text-red-400/70";
            insights.push(`${askPct.toFixed(0)}% de sesgo vendedor en el nivel actual.`);
            insights.push("Resistencia dinámica activa.");
        } else if (bidPct > 65) {
            summaryTitle = "Fuerte Soporte (Heavy Bids)";
            summaryColor = "text-neon-green";
            summaryBg = "bg-neon-green/10 border-neon-green/20";
            iconColor = "text-neon-green/70";
            insights.push(`${bidPct.toFixed(0)}% del volumen está esperando comprar.`);
            insights.push("Colchón de liquidez protege contra caídas bruscas.");
            if (totalBidVol > 10) insights.push("Posible acumulación institucional en esta zona.");
        } else if (bidPct > 55) {
            summaryTitle = "Interés Comprador Moderado";
            summaryColor = "text-green-400";
            summaryBg = "bg-green-400/10 border-green-400/20";
            iconColor = "text-green-400/70";
            insights.push(`${bidPct.toFixed(0)}% de sesgo comprador cercano.`);
            insights.push("Posible zona de pivot para un rebote.");
        } else {
            insights.push(`Equilibrio (Bids: ${bidPct.toFixed(0)}% / Asks: ${askPct.toFixed(0)}%).`);
            insights.push("Esperando que flujos de caja rompan la liquidez hacia un lado.");
        }
    }

    return (
        <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl flex flex-col overflow-hidden relative min-h-[220px] pb-1">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(0,229,255,0.03),transparent)] pointer-events-none" />

            {/* Encabezado */}
            <div className="p-3 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                <div className="flex items-center gap-2">
                    <Layers size={14} className="text-neon-cyan" />
                    <h2 className="text-[10px] font-bold text-white/90 tracking-widest uppercase shadow-neon-cyan/20">Mapa de Liquidez</h2>
                </div>
                <div className="flex gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-neon-red shadow-[0_0_8px_rgba(255,0,60,0.8)] animate-pulse" />
                    <div className="h-1.5 w-1.5 rounded-full bg-neon-green shadow-[0_0_8px_rgba(0,255,65,0.8)] animate-pulse" />
                </div>
            </div>

            <div className="flex-1 p-3 flex flex-col gap-2 overflow-y-auto custom-scrollbar">

                {/* Zonas de Venta (Asks) - Ordenadas de mayor a menor precio */}
                <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-1 mb-1">
                        <ArrowDown size={10} className="text-neon-red/60" />
                        <span className="text-[8px] font-bold text-neon-red/50 tracking-wider">PRESIÓN VENDEDORA</span>
                    </div>
                    {[...liquidityHeatmap.asks].sort((a, b) => b.price - a.price).map((ask, idx) => {
                        const widthPct = Math.min((ask.volume / maxAskVol) * 100, 100);
                        const distPct = latestPrice ? ((ask.price - latestPrice) / latestPrice * 100).toFixed(2) : null;

                        return (
                            <div key={`ask-${idx}`} className="relative h-6 group">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${widthPct}%` }}
                                    transition={{ duration: 0.3, ease: 'easeOut' }}
                                    className="absolute right-0 inset-y-0 bg-gradient-to-l from-neon-red/20 to-transparent rounded-l-md border-r border-neon-red/40"
                                />
                                <div className="absolute inset-0 flex items-center justify-between px-2">
                                    <span className="text-[10px] text-white/70 font-mono z-10">{ask.volume.toFixed(2)} Vol</span>
                                    <div className="flex items-center gap-2 z-10">
                                        {distPct && <span className="text-[8px] text-neon-red/50">+{distPct}%</span>}
                                        <span className="text-[11px] font-bold text-neon-red font-mono">${ask.price.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}</span>
                                    </div>
                                </div>
                            </div>
                        )
                    })}
                </div>

                {/* Separador Precio Actual */}
                <div className="py-1 border-y border-white/5 flex items-center justify-center my-1 bg-white/[0.02]">
                    <span className="text-[9px] text-white/40 tracking-[0.2em]">{latestPrice ? `$${latestPrice.toLocaleString()}` : 'SPREAD'}</span>
                </div>

                {/* Zonas de Compra (Bids) - Ordenadas de mayor a menor precio */}
                <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-1 mb-1 justify-end">
                        <span className="text-[8px] font-bold text-neon-green/50 tracking-wider">SOPORTE COMPRADOR</span>
                        <ArrowUp size={10} className="text-neon-green/60" />
                    </div>
                    {[...liquidityHeatmap.bids].sort((a, b) => b.price - a.price).map((bid, idx) => {
                        const widthPct = Math.min((bid.volume / maxBidVol) * 100, 100);
                        const distPct = latestPrice ? ((latestPrice - bid.price) / latestPrice * 100).toFixed(2) : null;

                        return (
                            <div key={`bid-${idx}`} className="relative h-6 group">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${widthPct}%` }}
                                    transition={{ duration: 0.3, ease: 'easeOut' }}
                                    className="absolute left-0 inset-y-0 bg-gradient-to-r from-neon-green/20 to-transparent rounded-r-md border-l border-neon-green/40"
                                />
                                <div className="absolute inset-0 flex items-center justify-between px-2">
                                    <div className="flex items-center gap-2 z-10">
                                        <span className="text-[11px] font-bold text-neon-green font-mono">${bid.price.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}</span>
                                        {distPct && <span className="text-[8px] text-neon-green/50">-{distPct}%</span>}
                                    </div>
                                    <span className="text-[10px] text-white/70 font-mono z-10">{bid.volume.toFixed(2)} Vol</span>
                                </div>
                            </div>
                        )
                    })}
                </div>

            </div>

            {/* AI Summary Footer */}
            <div className="px-3 pb-2 mt-auto">
                <div className={`p-2 rounded-lg border flex flex-col gap-1.5 ${summaryBg}`}>
                    <div className="flex items-center gap-2 border-b border-black/10 pb-1 mb-0.5">
                        <Zap size={12} className={`flex-shrink-0 ${iconColor} animate-pulse`} />
                        <span className={`text-[10px] font-black tracking-widest uppercase ${summaryColor}`}>
                            {summaryTitle}
                        </span>
                    </div>
                    <ul className="flex flex-col gap-0.5">
                        {insights.map((insight, i) => (
                            <li key={i} className="flex items-start gap-1.5">
                                <span className={`text-[8px] mt-0.5 ${summaryColor}`}>•</span>
                                <span className="text-[9.5px] text-white/70 leading-tight">{insight}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
        </div>
    );
}

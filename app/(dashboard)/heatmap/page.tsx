'use client';

import React from 'react';
import dynamic from 'next/dynamic';

const LiquidityHeatmap = dynamic(() => import('../../components/ui/LiquidityHeatmap'), { ssr: false });

export default function HeatmapPage() {
    return (
        <div className="h-full w-full flex flex-col pt-2">
            <h2 className="text-xl font-black text-white tracking-widest mb-4 px-2">LIQUIDITY HEATMAP & ORDERBOOK</h2>
            <div className="flex-1 w-full relative min-h-0 bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl overflow-hidden">
                <LiquidityHeatmap />
            </div>
        </div>
    );
}

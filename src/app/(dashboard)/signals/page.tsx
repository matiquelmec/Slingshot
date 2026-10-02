'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import { Network } from 'lucide-react';

const SignalTerminal = dynamic(() => import('../../components/signals/SignalTerminal'), { ssr: false });

export default function SignalsPage() {
    return (
        <div className="h-full w-full flex flex-col p-4 overflow-hidden">
            <h2 className="text-xl font-black text-white tracking-widest mb-4 flex items-center gap-3">
                <Network className="text-neon-cyan" /> 
                SIGNAL TERMINAL <span className="text-white/20 font-light">|</span> <span className="text-neon-cyan/50 text-sm">HFT ORDER FLOW</span>
            </h2>
            <div className="flex-1 min-h-0 relative">
                <SignalTerminal />
            </div>
        </div>
    );
}

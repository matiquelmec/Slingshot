'use client';

import React from 'react';
import dynamic from 'next/dynamic';

const SignalTerminal = dynamic(() => import('../../components/signals/SignalTerminal'), { ssr: false });

export default function SignalsPage() {
    return (
        <div className="h-full w-full flex flex-col pt-2">
            <h2 className="text-xl font-black text-white tracking-widest mb-4 px-2">SIGNAL TERMINAL (ORDER FLOW INFERENCIA)</h2>
            <div className="flex-1 w-full relative">
                <SignalTerminal />
            </div>
        </div>
    );
}

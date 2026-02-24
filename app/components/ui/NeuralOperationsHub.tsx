'use client';

import React from 'react';
import MacroRadar from './MacroRadar';
import SignalTerminal from './SignalTerminal';
import MLProjectionGauge from './MLProjectionGauge';

export default function NeuralOperationsHub() {
    return (
        <div className="flex flex-col gap-5 h-full overflow-hidden min-h-0 pr-1 custom-scrollbar">
            {/* Macro Intelligence Section */}
            <div className="flex-shrink-0">
                <MacroRadar />
            </div>

            {/* AI Projection Gauge */}
            <div className="flex-shrink-0">
                <MLProjectionGauge />
            </div>

            {/* Signal & Operations Section */}
            <div className="flex-1 min-h-0 flex flex-col">
                <SignalTerminal />
            </div>
        </div>
    );
}

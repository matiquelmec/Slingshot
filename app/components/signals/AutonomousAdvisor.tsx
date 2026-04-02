'use client';

import React, { useEffect, useState } from 'react';
import { BrainCircuit } from 'lucide-react';

function TypewriterText({ text, speed = 30 }: { text: string; speed?: number }) {
    const [displayedText, setDisplayedText] = useState('');

    useEffect(() => {
        if (!text) {
            setDisplayedText('');
            return;
        }

        setDisplayedText((current) => {
            if (!text.startsWith(current)) return '';
            return current;
        });

        let timeoutId: NodeJS.Timeout;

        const tick = () => {
            setDisplayedText((current) => {
                if (current.length < text.length) {
                    timeoutId = setTimeout(tick, speed);
                    return text.slice(0, current.length + 1);
                }
                return current;
            });
        };

        timeoutId = setTimeout(tick, speed);
        return () => clearTimeout(timeoutId);
    }, [text, speed]);

    return (
        <div className="flex flex-col relative">
            <span className="whitespace-pre-wrap">
                {displayedText}
                <span className="animate-pulse bg-white/50 w-1.5 h-2.5 inline-block ml-0.5 align-middle" />
            </span>
        </div>
    );
}

interface AutonomousAdvisorProps {
    advisorLog: string | null;
    strategy: string | null;
}

const AutonomousAdvisor: React.FC<AutonomousAdvisorProps> = ({ advisorLog, strategy }) => {
    return (
        <div className="flex-none bg-black/60 border-t border-b border-white/5 px-4 py-2 flex flex-col justify-center text-[10px] font-mono tracking-widest min-h-[40px]">
            <div className="flex items-center gap-2 mb-1">
                <BrainCircuit size={10} className="text-neon-cyan/80 animate-pulse" />
                <span className="text-neon-cyan font-bold">AUTONOMOUS ADVISOR (LLM):</span>
                {strategy && (
                    <span className="text-white/30 text-[8px] border border-white/10 px-1 rounded">
                        ALGO: {strategy}
                    </span>
                )}
            </div>
            <div className="text-white/70 leading-relaxed italic ml-4 border-l border-white/10 pl-2">
                {advisorLog ? (
                    <div className="flex flex-col gap-1">
                         <TypewriterText 
                            text={typeof advisorLog === 'string' ? advisorLog : (advisorLog as any)?.content ?? 'Analizando...'} 
                            speed={30} 
                        />
                        {(advisorLog as any)?.updated_at && (
                            <span className="text-[8px] text-white/20 not-italic uppercase tracking-widest mt-1">
                                AUDIT CAPTURED: {new Date((advisorLog as any).updated_at).toLocaleTimeString('en-US', { hour12: false })}
                            </span>
                        )}
                    </div>
                ) : (
                    <span className="text-white/30 animate-pulse">Awaiting candle close for tactical AI briefing...</span>
                )}
            </div>
        </div>
    );
};

export default React.memo(AutonomousAdvisor);

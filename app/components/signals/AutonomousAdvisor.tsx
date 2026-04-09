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
    // Parsear advisorLog si es un string JSON para extraer verdict, logic y threat
    let parsedAdvisor: any = null;
    let displayText = typeof advisorLog === 'string' ? advisorLog : (advisorLog as any)?.content ?? 'Analizando...';
    
    if (typeof displayText === 'string' && displayText.startsWith('{')) {
        try {
            parsedAdvisor = JSON.parse(displayText);
            displayText = parsedAdvisor.logic || displayText;
        } catch (e) {
            // Ignorar y usar texto crudo
        }
    } else if (typeof advisorLog === 'object' && advisorLog !== null && 'verdict' in advisorLog) {
        parsedAdvisor = advisorLog;
        displayText = parsedAdvisor.logic || 'Analizando...';
    }

    // Colores por threat
    const threatColors: Record<string, string> = {
        'LOW': 'text-green-400 border-green-500/30 bg-green-500/10',
        'MEDIUM': 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10',
        'HIGH': 'text-red-400 border-red-500/30 bg-red-500/10'
    };

    const verdictColors: Record<string, string> = {
        'GO': 'bg-green-500/10 text-green-400 border-green-500/30',
        'AVOID': 'bg-red-500/10 text-red-400 border-red-500/30',
        'SIDEWAYS': 'bg-yellow-500/10 text-yellow-500 border-yellow-500/30'
    };

    return (
        <div className="flex-none bg-black/60 border-t border-b border-white/5 px-4 py-2 flex flex-col justify-center text-[10px] font-mono tracking-widest min-h-[40px]">
            <div className="flex items-center gap-2 mb-1">
                <BrainCircuit size={10} className="text-neon-cyan/80 animate-pulse" />
                <span className="text-neon-cyan font-bold">AUTONOMOUS ADVISOR:</span>
                {strategy && (
                    <span className="text-white/30 text-[8px] border border-white/10 px-1 rounded">
                        ALGO: {strategy}
                    </span>
                )}
            </div>
            
            <div className="text-white/70 leading-relaxed italic ml-4 border-l border-white/10 pl-2 flex flex-col gap-1">
                {advisorLog ? (
                    <>
                        {parsedAdvisor ? (
                            <div className="flex items-center gap-2 flex-wrap mb-1 mt-1">
                                <span className={`px-1.5 py-0.5 rounded text-[8px] border font-bold ${verdictColors[parsedAdvisor.verdict] || 'bg-white/5 border-white/20'}`}>
                                    {parsedAdvisor.verdict || 'UNKNOWN'}
                                </span>
                                {parsedAdvisor.threat && (
                                    <span className={`px-1.5 py-0.5 rounded text-[8px] border uppercase ${threatColors[parsedAdvisor.threat] || 'border-white/20 text-white/50'}`}>
                                        THREAT {parsedAdvisor.threat}
                                    </span>
                                )}
                                <div className="text-[10px] not-italic text-neon-cyan/90 ml-1">
                                    <TypewriterText text={`> ${displayText}`} speed={20} />
                                </div>
                            </div>
                        ) : (
                             <TypewriterText text={displayText} speed={30} />
                        )}

                        {(advisorLog as any)?.updated_at && (
                            <span className="text-[8px] text-white/20 not-italic uppercase tracking-widest mt-1">
                                AUDIT: {new Date((advisorLog as any).updated_at).toLocaleTimeString('en-US', { hour12: false })}
                            </span>
                        )}
                    </>
                ) : (
                    <span className="text-white/30 animate-pulse">Awaiting candle close for tactical AI briefing...</span>
                )}
            </div>
        </div>
    );
};

export default React.memo(AutonomousAdvisor);

import { TelemetryState, CandleData, NeuralLog } from './types';
import { Signal, OnChainMetrics, NewsItem, LiquidationCluster } from '../../types/signal';
import { mergeSignals } from './storage';

// 🛡️ [INSTITUTIONAL ISOLATION] Utilidad de limpieza y comparación de símbolos
const cleanSymbol = (s: string) => s ? s.replace(/[\s\/]/g, '').toUpperCase() : '';

const isSameSymbol = (s1: string, s2: string) => {
    if (!s1 || !s2) return false;
    return cleanSymbol(s1) === cleanSymbol(s2);
};

export const handleWsMessage = (
    event: MessageEvent, 
    set: (fn: (state: TelemetryState) => any | Partial<TelemetryState>) => void, 
    get: () => TelemetryState,
    context: { connectionId: string, lastMsgTimestamp: number, staleGuardActive: boolean }
) => {
    const currentId = get().activeConnectionId;
    if (context.connectionId !== currentId) return;

    const now = Date.now();
    const gapMs = now - context.lastMsgTimestamp;
    context.lastMsgTimestamp = now;

    if (gapMs > 60_000 && !context.staleGuardActive) {
        context.staleGuardActive = true;
        console.warn(`[STALE GUARD] Gap de ${(gapMs / 1000).toFixed(0)}s detectado. Purgando mensajes obsoletos...`);
        set((state) => ({
            neuralLogs: [{
                id: Math.random().toString(36).substring(7),
                timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                type: 'SYSTEM',
                message: '[SYSTEM] Stale messages purged. Syncing to HEAD...'
            }, ...state.neuralLogs].slice(0, 5),
            tacticalDecision: { ...state.tacticalDecision, is_stale: true }
        }));
    }

    let data: any;
    try {
        data = JSON.parse(event.data);

        if (context.staleGuardActive) {
            if (data.type === 'history' || data.type === 'ghost_update' || data.type === 'radar_update') {
                context.staleGuardActive = false;
            } else {
                return;
            }
        }

        switch (data.type) {
            case 'history':
                const sortedCandles = data.data.map((item: any) => ({
                    time: Number(item.data.timestamp),
                    open: Number(item.data.open),
                    high: Number(item.data.high),
                    low: Number(item.data.low),
                    close: Number(item.data.close),
                    volume: Number(item.data.volume),
                    bullish_div: item.data.bullish_div,
                    bearish_div: item.data.bearish_div
                })).sort((a: any, b: any) => a.time - b.time);

                const lastPrice = sortedCandles.length > 0 ? Number(sortedCandles[sortedCandles.length - 1].close) : null;
                set((state) => ({
                    candles: sortedCandles,
                    latestPrice: lastPrice,
                    latestPrices: { ...state.latestPrices, [state.activeSymbol]: lastPrice }
                }));
                break;

            case 'candle':
                const newCandle: CandleData = {
                    time: data.data.timestamp,
                    open: data.data.open,
                    high: data.data.high,
                    low: data.data.low,
                    close: data.data.close,
                    volume: data.data.volume,
                    bullish_div: data.data.bullish_div,
                    bearish_div: data.data.bearish_div
                };

                set((state) => {
                    const currentCandles = [...state.candles];
                    const lastIdx = currentCandles.length - 1;
                    if (lastIdx >= 0) {
                        const lastTime = Number(currentCandles[lastIdx].time);
                        const newTime = Number(newCandle.time);
                        if (newTime < lastTime) return state;
                        if (lastTime === newTime) {
                            currentCandles[lastIdx] = newCandle;
                        } else {
                            currentCandles.push(newCandle);
                            if (currentCandles.length > 1000) currentCandles.shift();
                        }
                    } else {
                        currentCandles.push(newCandle);
                    }

                    return {
                        candles: currentCandles,
                        latestPrice: Number(newCandle.close),
                        latestPrices: { ...state.latestPrices, [state.activeSymbol]: Number(newCandle.close) }
                    };
                });
                break;

            case 'neural_pulse':
                set((state) => {
                    const pulseData = data.data || {};
                    const logObj = pulseData.log || {};
                    const newLog: NeuralLog = {
                        id: Math.random().toString(36).substring(7),
                        timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                        type: logObj.type || 'SYSTEM',
                        message: logObj.message || 'Heartbeat neural recibido.'
                    };
                    return {
                        mlProjection: pulseData.ml_projection || state.mlProjection,
                        liquidityHeatmap: pulseData.liquidity_heatmap || state.liquidityHeatmap,
                        neuralLogs: [newLog, ...state.neuralLogs].slice(0, 10)
                    };
                });
                break;

            case 'tactical_update':
                const d = data.data;
                if (!d) break;
                set((state) => {
                    const incomingSignals: Signal[] = d.signals ?? [];
                    const activeSignalsOnly = incomingSignals.filter(s => s.status === 'ACTIVE');
                    const { data: newHistoryData, ids: newHistoryIds } = activeSignalsOnly.length > 0
                        ? mergeSignals(state.signalHistory, state.signalIds, activeSignalsOnly)
                        : { data: state.signalHistory, ids: state.signalIds };
                    
                    const updatedAdvisorLogs = { ...state.advisorLogs };
                    if (d.advisor_log) updatedAdvisorLogs[d.asset] = d.advisor_log;

                    return {
                        isCalibrating: false,
                        tacticalDecision: {
                            ...state.tacticalDecision,
                            asset: d.asset,
                            regime: d.market_regime ?? 'UNKNOWN',
                            strategy: d.active_strategy ?? 'STANDBY',
                            reasoning: `Régimen: ${d.market_regime}. Soportes mapeados.`,
                            current_price: d.current_price ?? null,
                            signal_history: incomingSignals,
                            ...d
                        },
                        advisorLogs: updatedAdvisorLogs,
                        htfBias: d.htf_bias ?? state.htfBias,
                        latestPrice: isSameSymbol(d.asset, state.activeSymbol) ? (d.current_price ?? state.latestPrice) : state.latestPrice,
                        latestPrices: { ...state.latestPrices, [d.asset]: d.current_price ?? (state.latestPrices[d.asset] || null) },
                        signalHistory: newHistoryData,
                        signalIds: newHistoryIds,
                    };
                });
                break;

            case 'signal_auditor_update':
                const sig = data.data as Signal;
                if (!sig.asset || !sig.price || sig.price <= 0) return;
                const id = sig.id || `${sig.timestamp}-${sig.asset}`;
                set((state) => {
                    const status = sig.status || '';
                    const newAuditedData = { ...state.auditedSignals, [id]: sig };
                    const newAuditedIds = state.auditedSignals[id] ? state.auditedIds : [id, ...state.auditedIds].slice(0, 100); 

                    let newHistory = { data: state.signalHistory, ids: state.signalIds };
                    if (['ACTIVE', 'FILLED', 'SHIELD_ACTIVATED'].includes(status)) {
                        const currentPrice = state.latestPrices[sig.asset] || (sig.asset === state.activeSymbol ? state.latestPrice : null);
                        const deviation = currentPrice ? Math.abs(sig.price - currentPrice) / currentPrice : 0;
                        if (deviation < 0.15 || !currentPrice) {
                            newHistory = mergeSignals(state.signalHistory, state.signalIds, [sig]);
                        }
                    }
                    return { auditedSignals: newAuditedData, auditedIds: newAuditedIds, signalHistory: newHistory.data, signalIds: newHistory.ids };
                });
                break;

            case 'advisor_update':
                const advice = data.data;
                if (!advice) break;
                set((state) => {
                    if (advice.asset && !isSameSymbol(advice.asset, state.activeSymbol)) return state;
                    return {
                        advisorLogs: { ...state.advisorLogs, [advice.asset || state.activeSymbol]: advice }
                    };
                });
                break;

            case 'execution_update':
                const execSig = data.data as Signal;
                set((state) => {
                    const currentPrice = state.latestPrices[execSig.asset] || state.latestPrice;
                    const deviation = currentPrice ? Math.abs(execSig.price - currentPrice) / currentPrice : 0;
                    if (deviation > 0.25 && currentPrice) return state;
                    const { data: nHistory, ids: nIds } = mergeSignals(state.signalHistory, state.signalIds, [execSig]);
                    return { signalHistory: nHistory, signalIds: nIds };
                });
                break;

            case 'radar_update':
                const summary = data.data as any[];
                set((state) => {
                    const newSummary = { ...state.marketSummary };
                    const newPrices = { ...state.latestPrices };
                    let newLatestPrice = state.latestPrice;

                    summary.forEach(s => {
                        const asset = s.asset;
                        newSummary[asset] = s;
                        if (s.price) {
                            newPrices[asset] = s.price;
                            if (asset === state.activeSymbol) {
                                newLatestPrice = s.price;
                            }
                        }
                    });
                    return { 
                        marketSummary: newSummary, 
                        latestPrices: newPrices,
                        latestPrice: newLatestPrice
                    };
                });
                break;

            case 'session_update':
                set((state) => {
                    // 🛡️ [STRUCTURE GUARD] El mensaje puede venir envuelto en .data (WS) o directo (REST/Fallback)
                    const payload = data.data?.sessions ? data.data : (data.sessions ? data : null);
                    
                    if (!payload || !payload.sessions) {
                        // Evitar ruido excesivo si es un mensaje de control vacío
                        if (data.data) console.warn(`[TELEMETRY] ⚠️ Sesión incompleta recibida para ${data.data.asset || 'unknown'}`);
                        return state;
                    }

                    const dataAsset = payload.asset;
                    
                    // 🛡️ [ISOLATION GUARD] Ignorar si el mensaje no coincide con el símbolo activo
                    if (dataAsset && !isSameSymbol(dataAsset, state.activeSymbol)) {
                        return state;
                    }
                    
                    // 🚀 [PLATINUM SYNC] Reemplazo total para evitar fragmentación
                    return { 
                        sessionData: { 
                            ...payload,
                            asset: dataAsset || state.activeSymbol
                        } as any 
                    };
                });
                break;

            case 'smc_data':
                set((state) => {
                    const dataAsset = data.data.asset;
                    if (dataAsset && !isSameSymbol(dataAsset, state.activeSymbol)) return state;
                    
                    return { smcData: data.data };
                });
                set((state) => {
                    const newLog: NeuralLog = {
                        id: Math.random().toString(36).substring(7),
                        timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                        type: 'SENSOR',
                        message: `[SMC] Estructura actualizada. OBs: ${data.data.order_blocks.bullish.length} Bull / ${data.data.order_blocks.bearish.length} Bear.`
                    };
                    return { neuralLogs: [newLog, ...state.neuralLogs].slice(0, 3) };
                });
                break;

            case 'ghost_update':
                const g = data.data || {};
                set((state) => {
                    const activeSym = state.activeSymbol;
                    const newState: any = { ghostData: { ...g, symbol: g.symbol || activeSym } };
                    if (g.symbol === activeSym && g.oi_delta_pct !== undefined) {
                        newState.onchainMetrics = {
                            symbol: g.symbol,
                            oi_delta_pct: Number(g.oi_delta_pct),
                            funding_rate: Number(g.funding_rate),
                            onchain_bias: g.onchain_bias,
                            whale_alerts_count: g.whale_alerts_count || 0,
                            ts: g.last_updated || Date.now() / 1000
                        };
                    }
                    const biasIcons: Record<string, string> = {
                        BULLISH: '🟢', BEARISH: '🔴', NEUTRAL: '⚪',
                        BLOCK_LONGS: '🟠', BLOCK_SHORTS: '🟤', CONFLICTED: '🟡'
                    };
                    const icon = biasIcons[g.macro_bias] ?? '⚪';
                    const fund = g.funding_rate != null ? Number(g.funding_rate).toFixed(4) : "0.0000";
                    const newLog: NeuralLog = {
                        id: Math.random().toString(36).substring(7),
                        timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                        type: g.block_longs || g.block_shorts ? 'ALERT' : 'SENSOR',
                        message: `[GHOST] ${icon} F&G=${g.fear_greed_value ?? '?'} (${g.fear_greed_label ?? 'N/A'}) | BTCD=${g.btc_dominance ?? '?'}% | Fund=${fund}% | Bias=${g.macro_bias ?? 'N/A'}`
                    };
                    newState.neuralLogs = [newLog, ...state.neuralLogs].slice(0, 5);
                    return newState;
                });
                break;

            case 'news_update':
                const newsItem = data.data as NewsItem;
                set((state) => {
                    const idx = state.news.findIndex(n => n.id === newsItem.id);
                    if (idx !== -1) {
                        const updated = [...state.news];
                        updated[idx] = newsItem;
                        return { news: updated };
                    }
                    return { news: [newsItem, ...state.news].slice(0, 15) };
                });
                break;

            case 'liquidation_update':
                set({ liquidations: data.data as LiquidationCluster[] } as any);
                break;

            case 'onchain_update':
                const metrics = data.data as OnChainMetrics;
                if (metrics && metrics.symbol === get().activeSymbol) {
                    set({ onchainMetrics: metrics } as any);
                }
                break;
            
            case 'htf_bias_update':
                const incomingSymbol = data.data?.symbol?.toUpperCase();
                const currentSymbol = get().activeSymbol?.toUpperCase();
                
                console.log(`🌐 [TELEMETRY] HTF Update received for ${incomingSymbol}. Active: ${currentSymbol}`);

                if (data.data && incomingSymbol === currentSymbol) {
                    set((state) => {
                        const updatedBias = {
                            ...(state.htfBias || {}),
                            ...data.data,
                            is_analyzing: false
                        };
                        
                        return {
                            htfBias: updatedBias,
                            // Sincronizar en todos los formatos posibles para compatibilidad
                            tacticalDecision: {
                                ...state.tacticalDecision,
                                htf_bias: updatedBias,
                                htfBias: updatedBias
                            }
                        };
                    });
                }
                break;
        }
    } catch (err) {
        console.error("❌ [WS-HANDLER] Critical error:", err);
    }
};

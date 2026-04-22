import { create } from 'zustand';
import { Signal, NeuralLog, KeyLevel, TacticalDecision, SessionData, SMCDataPayload, GhostData, HTFBias, NewsItem, LiquidationCluster, EconomicEvent, OnChainMetrics } from '../types/signal';


export interface CandleData {
    time: number | string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    bullish_div?: boolean; // 🎯 Divergencia Matemática Oculta
    bearish_div?: boolean; // 🎯 Divergencia Matemática Oculta
}

export type Timeframe = '1m' | '3m' | '5m' | '15m' | '30m' | '1h' | '2h' | '4h' | '8h' | '1d' | '1w' | '1M';

// Las interfaces NeuralLog, KeyLevel, TacticalDecision, SessionInfo, SessionData, OrderBlockData, SMCDataPayload y GhostData 
// han sido movidas a ../types/signal.ts para centralizar la lógica de tipos.

export const MASTER_WATCHLIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT"];

interface TelemetryState {
    advisorLogs: Record<string, any>; // 🧠 Mapeo de análisis por activo (v5.7.155 Master Gold)
    isConnected: boolean;
    isCalibrating: boolean;
    activeSymbol: string;
    activeTimeframe: Timeframe;
    candles: CandleData[];
    latestPrice: number | null;
    latestPrices: Record<string, number | null>; // 🚀 Mapa de precios por activo (v5.7.155 Master Gold)
    mlProjection: { direction: 'ALCISTA' | 'BAJISTA' | 'NEUTRAL' | 'ANALIZANDO' | 'CALIBRANDO' | 'ERROR', probability: number, reason?: string };
    liquidityHeatmap: { bids: { price: number, volume: number }[], asks: { price: number, volume: number }[] } | null;
    neuralLogs: NeuralLog[];
    tacticalDecision: TacticalDecision;
    smcData: SMCDataPayload | null;
    sessionData: SessionData | null;
    ghostData: GhostData | null;
    htfBias: HTFBias | null;
    news: NewsItem[];
    liquidations: LiquidationCluster[];
    marketSummary: Record<string, { asset: string, price: number | null, regime: string, strategy: string, bias: string, trend: number }>;
    economicEvents: EconomicEvent[];
    onchainMetrics: OnChainMetrics | null;
    signalHistory: Record<string, Signal>; // 🏹 O(1) Map para búsqueda instantánea (v5.4)
    signalIds: string[];                    // 📜 Índice ordenado para renderizado
    auditedSignals: Record<string, Signal>; // 🏹 O(1) Map para auditoría (v5.4)
    auditedIds: string[];                   // 📜 Índice ordenado para auditoría
    activeConnectionId: string | null;
    viewMode: 'SYMBOL' | 'GLOBAL';          // 🛰️ Modo de vista global (v8.4)
    connect: (symbol: string, timeframe?: Timeframe) => void;
    disconnect: () => void;
    setTimeframe: (tf: Timeframe) => void;
    setNews: (news: NewsItem[]) => void;
    setViewMode: (mode: 'SYMBOL' | 'GLOBAL') => void;
    hydrateSignals: (signals: Signal[]) => void;
    fetchEconomicEvents: () => Promise<void>;
    clearSignalHistory: () => void;
}

export const useTelemetryStore = create<TelemetryState>((set, get) => {
    let ws: WebSocket | null = null;
    let retryCount = 0;
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;
    const MAX_RETRIES = 5;

    // Cargar historial de señales desde localStorage al iniciar
    const _loadSignalHistory = (): { data: Record<string, Signal>, ids: string[] } => {
        try {
            const raw = localStorage.getItem('slingshot_signal_history_v2');
            if (!raw) return { data: {}, ids: [] };
            const parsed = JSON.parse(raw);
            const data = parsed.data || {};
            const ids = parsed.ids || [];

            // Helper to ensure timezone-naive strings are parsed as UTC
            const getUtcTime = (ts: string) => {
                if (ts.includes('Z') || ts.includes('+')) return new Date(ts).getTime();
                return new Date(ts.replace(' ', 'T') + 'Z').getTime();
            };

            const now = Date.now();
            const validIds = ids.filter((id: string) => {
                const s = data[id];
                if (!s) return false;
                const age = now - getUtcTime(s.timestamp);
                return age < 2 * 60 * 60 * 1000; // 2 horas max caching
            });

            const validData: Record<string, Signal> = {};
            validIds.forEach((id: string) => {
                validData[id] = data[id];
            });

            return { data: validData, ids: validIds };
        } catch {
            return { data: {}, ids: [] };
        }
    };

    const _saveSignalHistory = (data: Record<string, Signal>, ids: string[]) => {
        try {
            localStorage.setItem('slingshot_signal_history_v2', JSON.stringify({ data, ids }));
        } catch { /* quota exceeded — ignorar */ }
    };

    const _mergeSignals = (prevData: Record<string, Signal>, prevIds: string[], incoming: Signal[]): { data: Record<string, Signal>, ids: string[] } => {
        let newData = { ...prevData };
        let newIds = [...prevIds];
        let hasChanged = false;

        incoming.forEach(sig => {
            const id = sig.id || `${sig.timestamp}-${sig.asset}`;
            
            if (!sig.asset || !sig.price || sig.price <= 0) return;

            // Si es nueva señal o el estado cambió, marcamos como cambiado
            if (!newData[id] || JSON.stringify(newData[id]) !== JSON.stringify({ ...sig, id })) {
                if (!newData[id]) {
                    newIds.unshift(id);
                }
                newData[id] = { ...sig, id };
                hasChanged = true;
            }
        });

        if (!hasChanged) return { data: prevData, ids: prevIds };

        // Garbage collector (2 horas)
        const now = Date.now();
        const getUtcTime = (ts: string) => {
            if (ts.includes('Z') || ts.includes('+')) return new Date(ts).getTime();
            return new Date(ts.replace(' ', 'T') + 'Z').getTime();
        };

        const finalIds = newIds.filter(id => {
            const s = newData[id];
            return s && (now - getUtcTime(s.timestamp) < 2 * 60 * 60 * 1000);
        }).slice(0, 100);

        // Si después del garbage collector los IDs cambiaron, regenerar el mapa
        if (finalIds.length !== newIds.length) {
            const finalData: Record<string, Signal> = {};
            finalIds.forEach(id => { finalData[id] = newData[id]; });
            _saveSignalHistory(finalData, finalIds);
            return { data: finalData, ids: finalIds };
        }

        _saveSignalHistory(newData, newIds);
        return { data: newData, ids: newIds };
    };

    const doConnect = async (symbol: string, timeframe: Timeframe, isRetry = false) => {
        const connectionId = Math.random().toString(36).substring(7);

        // Clean up existing connection and pending retries
        if (ws) {
            ws.onclose = null; // Cierra la puerta al bucle de reconexión zombie del antiguo socket
            ws.onerror = null;
            ws.onmessage = null;
            ws.close(1000); // 1000 = Normal Closure
            ws = null;
        }
        if (retryTimeout) {
            clearTimeout(retryTimeout);
            retryTimeout = null;
        }

        if (!isRetry) {
            retryCount = 0; // Reset counter on fresh connect
            set({
                activeSymbol: symbol,
                activeTimeframe: timeframe,
                activeConnectionId: connectionId,
                candles: [],
                isConnected: false,
                isCalibrating: true,
                smcData: null,
                sessionData: null,
                latestPrice: null,
                liquidityHeatmap: null,
                // advisorLogs: {},  <-- REMOVED: Mantener caché entre símbolos para hidratación instantánea v5.7.155 Master Gold
                mlProjection: { direction: 'NEUTRAL', probability: 50, reason: "Aguardando conexión de telemetría..." },
                tacticalDecision: {
                    regime: "ANALIZANDO NUEVO RIESGO...",
                    strategy: "STANDBY",
                    reasoning: `Sincronizando telemetría para ${symbol}.`,
                    current_price: null,
                    nearest_support: null,
                    nearest_resistance: null,
                    signals: [],
                    key_levels: { resistances: [], supports: [] }
                },
                htfBias: null,
                ghostData: null, // Restablecer al desconectar
                auditedSignals: {}, 
                auditedIds: []
            });

            // 🚀 Hidratación REST asíncrona: evita que el Frontend parpadee en "Sincronizando..." 
            // mientras espera el ciclo 1s-3s (Fast Path) del primer ghost_update por WebSocket.
            const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
            fetch(`${BASE_URL}/api/v1/ghost`)
                .then(res => res.json())
                .then(data => {
                    const currentId = get().activeConnectionId;
                    if (connectionId === currentId && data.ghost) {
                        set({ ghostData: { ...data.ghost, symbol } });
                    }
                }).catch(err => console.error("Ghost hydration failed", err));

        } else {
            // Si es un reintento, mantenemos el ID pero lo registramos como activo
            set({ activeConnectionId: connectionId });
        }

        // ✅ JWT Auth v6.0.1: URL dinámica y Security Key interna para fetch
        const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
        const BASE_WS = process.env.NEXT_PUBLIC_API_WS_URL ?? 'ws://localhost:8000';
        const SECURITY_KEY = 'SLINGSHOT_INTERNAL_V6'; // 🔐 Sigma Security v6.0

        try {
            const tokenRes = await fetch(`${BASE_URL}/api/v1/auth/token?api_key=${SECURITY_KEY}`);
            const tokenData = await tokenRes.json();
            
            if (!tokenData.token) {
                throw new Error("No token returned");
            }
            
            // Verificar si la conexión sigue siendo la activa después del delay del fetch
            const currentId = get().activeConnectionId;
            if (connectionId !== currentId) {
                return;
            }
            
            ws = new WebSocket(`${BASE_WS}/api/v1/stream/${symbol}?interval=${timeframe}&token=${tokenData.token}`);
            
            ws.onopen = () => {
                set({ isConnected: true });
            };
        } catch (error) {
            console.error("[AUTH] Fallo al hacer fetch del JWT para el WS:", error);
            if (retryCount < MAX_RETRIES) {
                const delayMs = Math.pow(2, retryCount) * 2000;
                retryCount++;
                console.warn(`[WS Auth] Reintento ${retryCount}/${MAX_RETRIES} en ${delayMs / 1000}s...`);
                retryTimeout = setTimeout(() => {
                    doConnect(get().activeSymbol, get().activeTimeframe, true);
                }, delayMs);
            }
            return;
        }

        // 🔴 STALE GUARD v5.7.155 Master Gold: Track last message time for zombie tab detection
        let lastMsgTimestamp = Date.now();
        let staleGuardActive = false;

        ws.onmessage = (event) => {
            const currentId = get().activeConnectionId;
            if (connectionId !== currentId) {
                return;
            }

            // 🔴 STALE GUARD: Si hubo un gap > 60s (PC suspendida), descartar mensajes viejos
            // hasta que llegue un 'history' fresco que resincronice el estado
            const now = Date.now();
            const gapMs = now - lastMsgTimestamp;
            lastMsgTimestamp = now;

            if (gapMs > 60_000 && !staleGuardActive) {
                staleGuardActive = true;
                console.warn(`[STALE GUARD] Gap de ${(gapMs / 1000).toFixed(0)}s detectado. Purgando mensajes obsoletos...`);
                set((state) => ({
                    neuralLogs: [{
                        id: Math.random().toString(36).substring(7),
                        timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                        type: 'SYSTEM' as const,
                        message: '[SYSTEM] Stale messages purged. Syncing to HEAD...'
                    }, ...state.neuralLogs].slice(0, 5),
                    tacticalDecision: { ...state.tacticalDecision, is_stale: true }
                }));
            }

            // Si el stale guard está activo, solo dejamos pasar 'history' (resync completo)
            // y mensajes de tipo estado global. Los ticks individuales viejos se descartan.
            let data: any;
            try {
                data = JSON.parse(event.data);

                if (staleGuardActive) {
                    // Solo aceptar history (resync) o mensajes de estado que traigan snapshot completo
                    if (data.type === 'history' || data.type === 'ghost_update' || data.type === 'radar_update') {
                        staleGuardActive = false; // Resync completado
                    } else {
                        return; // Descartar mensajes stale silenciosamente
                    }
                }

                if (data.type === 'history') {
                    // Carga ultrasónica de datos históricos (Batch Processing)
                    const rawItems = data.data.map((item: any) => ({
                        time: Number(item.data.timestamp),
                        open: Number(item.data.open),
                        high: Number(item.data.high),
                        low: Number(item.data.low),
                        close: Number(item.data.close),
                        volume: Number(item.data.volume),
                        bullish_div: item.data.bullish_div,
                        bearish_div: item.data.bearish_div
                    }));

                    // 🛡️ Blindaje de duplicados y orden
                    const uniqueCandlesMap = new Map();
                    rawItems.forEach((c: any) => uniqueCandlesMap.set(c.time, c));
                    const sortedCandles = Array.from(uniqueCandlesMap.values()).sort((a, b) => (a.time as number) - (b.time as number));

                    const lastPrice = sortedCandles.length > 0 ? Number(sortedCandles[sortedCandles.length - 1].close) : null;
                    set((state) => ({
                        candles: sortedCandles,
                        latestPrice: lastPrice,
                        latestPrices: {
                            ...state.latestPrices,
                            [get().activeSymbol]: lastPrice
                        }
                    }));
                } else if (data.type === 'candle') {
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

                            // Protección Monotónica: Ignorar si el timestamp retrocede (evita bug de lightweight-charts)
                            if (newTime < lastTime) return state;

                            if (lastTime === newTime) {
                                currentCandles[lastIdx] = newCandle; // Update ongoing candle
                            } else {
                                currentCandles.push(newCandle); // New candle
                                if (currentCandles.length > 1000) currentCandles.shift();
                            }
                        } else {
                            currentCandles.push(newCandle); // Primera vela
                        }

                        return {
                            candles: currentCandles,
                            latestPrice: Number(newCandle.close),
                            latestPrices: {
                                ...state.latestPrices,
                                [state.activeSymbol]: Number(newCandle.close)
                            }
                        };
                    });
                } else if (data.type === 'neural_pulse') {
                    // Update del Fast Path (Tiempo Real Inter-Vela)
                    set((state) => {
                        const pulseData = data.data || {};
                        const logObj = pulseData.log || {};
                        
                        const newLog: NeuralLog = {
                            id: Math.random().toString(36).substring(7),
                            timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                            type: logObj.type || 'SYSTEM',
                            message: logObj.message || 'Heartbeat neural recibido.'
                        };
                        const updatedLogs = [newLog, ...state.neuralLogs].slice(0, 10); 

                        return {
                            mlProjection: pulseData.ml_projection || state.mlProjection,
                            liquidityHeatmap: pulseData.liquidity_heatmap || state.liquidityHeatmap,
                            neuralLogs: updatedLogs
                        };
                    });
                } else if (data.type === 'tactical_update') {
                    const d = data.data;
                    if (!d) return;
                    
                    const incomingSignals: Signal[] = d.signals ?? [];
                    const isElite = MASTER_WATCHLIST.includes(d.asset);

                    set((state) => {
                        // Protocolo v5.7.15: Una Sola Señal Maestra (El Mejor Cuadro)
                        // [v8.2.0] Eliminamos las restricciones rígidas (RR>2.0, Score>70). 
                        // El Gatekeeper del backend ya filtró la señal según el activo. Si es ACTIVE, es válida.
                        const activeSignalsOnly = incomingSignals.filter(s => s.status === 'ACTIVE');
                        
                        // OMEGA: Anti-Repetición en la UI (Top 1 por Asset en la cola visual)
                        const { data: newHistoryData, ids: newHistoryIds } = activeSignalsOnly.length > 0
                            ? _mergeSignals(state.signalHistory, state.signalIds, activeSignalsOnly)
                            : { data: state.signalHistory, ids: state.signalIds };
                        
                        // Si es Elite, forzamos actualización de advisor inmediata
                        const updatedAdvisorLogs = { ...state.advisorLogs };
                        if (d.advisor_log) {
                            updatedAdvisorLogs[d.asset] = d.advisor_log;
                        }

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
                                ...d // Spread remaining data
                            },
                            advisorLogs: updatedAdvisorLogs,
                            htfBias: d.htf_bias ?? state.htfBias,
                            latestPrice: d.asset === state.activeSymbol ? (d.current_price ?? state.latestPrice) : state.latestPrice,
                            latestPrices: {
                                ...state.latestPrices,
                                [d.asset]: d.current_price ?? (state.latestPrices[d.asset] || null)
                            },
                            signalHistory: newHistoryData,
                            signalIds: newHistoryIds,
                        };
                    });
                } else if (data.type === 'signal_auditor_update') {
                    // Evento específico inyectado en WS desde v3.3 (Audit Mode)
                    const sig = data.data as Signal;
                    
                    // [GATEKEEPER v8.3.0] Validation of signal integrity
                    if (!sig.asset || !sig.price || sig.price <= 0) {
                        console.warn(`[TELEMETRY] Skipping malformed/contaminated signal:`, sig);
                        return;
                    }

                    const id = sig.id || `${sig.timestamp}-${sig.asset}`;

                    set((state) => {
                        const status = sig.status || '';
                        
                        // 1. Sincronizar Radar (Acepta TODO: Aprobadas y Bloqueadas)
                        const newAuditedData = { ...state.auditedSignals, [id]: sig };
                        const newAuditedIds = state.auditedSignals[id] ? state.auditedIds : [id, ...state.auditedIds].slice(0, 100); 

                        // 2. Sincronizar OMEGA (Solo Aprobadas/Ejecución)
                        let newHistory = { data: state.signalHistory, ids: state.signalIds };
                        
                        // [v8.3.0] PURE ACTIVE FILTER: Solo permitimos señales ACTIVE si coinciden con el activo
                        // y tienen un precio coherente (anti-pollution)
                        if (['ACTIVE', 'FILLED', 'SHIELD_ACTIVATED'].includes(status)) {
                            const currentPrice = state.latestPrices[sig.asset] || (sig.asset === state.activeSymbol ? state.latestPrice : null);
                            const sigPrice = sig.price || 0;
                            const deviation = currentPrice ? Math.abs(sigPrice - currentPrice) / currentPrice : 0;
                            
                            // 15% threshold for gatekeeping (matched with backend gatekeeper.py)
                            if (deviation < 0.15 || !currentPrice) {
                                newHistory = _mergeSignals(state.signalHistory, state.signalIds, [sig]);
                            } else {
                                console.warn(`[POLLUTION ALERT] Reverting signal ${id} on ${sig.asset} | Sig: ${sigPrice} vs Market: ${currentPrice} | Dev: ${(deviation*100).toFixed(1)}%`);
                            }
                        }

                        return { 
                            auditedSignals: newAuditedData,
                            auditedIds: newAuditedIds,
                            signalHistory: newHistory.data,
                            signalIds: newHistory.ids
                        };
                    });
                } else if (data.type === 'advisor_update') {
                    const advice = data.data;
                    if (!advice) return;
                    
                    set((state) => {
                        const asset = advice?.asset || state.activeSymbol; 
                        return {
                            advisorLogs: {
                                ...state.advisorLogs,
                                [asset]: advice
                            }
                        };
                    });
                } else if (data.type === 'execution_update') {
                    // 🛡️ OMEGA Live Synchronization
                    const sig = data.data as Signal;
                    set((state) => {
                        const currentPrice = state.latestPrices[sig.asset] || state.latestPrice;
                        const sigPrice = sig.price || 0;
                        const deviation = currentPrice ? Math.abs(sigPrice - currentPrice) / currentPrice : 0;

                        if (deviation > 0.25 && currentPrice) {
                            console.warn(`[EXECUTION POLLUTION] Blocked state update for ${sig.asset} due to incoherent price: ${sigPrice}`);
                            return state;
                        }

                        const { data: newHistoryData, ids: newHistoryIds } = _mergeSignals(state.signalHistory, state.signalIds, [sig]);
                        return {
                            signalHistory: newHistoryData,
                            signalIds: newHistoryIds
                        };
                    });
                } else if (data.type === 'radar_update') {
                    // Update del Status de todos los radares (Broadcasters persistentes)
                    const summary = data.data as any[];
                    set((state) => {
                        const newSummary = { ...state.marketSummary };
                        const newPrices = { ...state.latestPrices };
                        summary.forEach(s => {
                            newSummary[s.asset] = s;
                            if (s.price) newPrices[s.asset] = s.price;
                        });
                        return { 
                            marketSummary: newSummary,
                            latestPrices: newPrices
                        };
                    });
                } else if (data.type === 'session_update') {
                    set((state) => ({ 
                        sessionData: { ...(state.sessionData || {}), ...data.data } as any
                    }));
                } else if (data.type === 'smc_data') {
                    set({ smcData: data.data });
                    set((state) => {
                        const newLog: NeuralLog = {
                            id: Math.random().toString(36).substring(7),
                            timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                            type: 'SENSOR',
                            message: `[SMC] Estructura actualizada. OBs: ${data.data.order_blocks.bullish.length} Bull / ${data.data.order_blocks.bearish.length} Bear. FVGs: ${data.data.fvgs.bullish.length + data.data.fvgs.bearish.length}.`
                        };
                        return { neuralLogs: [newLog, ...state.neuralLogs].slice(0, 3) };
                    });
                } else if (data.type === 'ghost_update') {
                    const g = data.data || {};
                    const activeSym = get().activeSymbol;
                    
                    // [v8.5.7] Macro Radar es GLOBAL: Actualizar siempre con la última telemetría macro disponible
                    set({ ghostData: { ...g, symbol: g.symbol || activeSym } });
                    set((state) => {
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
                        return { neuralLogs: [newLog, ...state.neuralLogs].slice(0, 5) };
                    });
                } else if (data.type === 'drift_alert') {
                    const drift = data.data || {};
                    set((state) => {
                        const levelIcon = drift.drift_level === 'SEVERE' ? '🚨' : '⚠️';
                        const psi = drift.psi_max != null ? Number(drift.psi_max).toFixed(3) : "0.000";
                        const acc = drift.rolling_accuracy != null ? (Number(drift.rolling_accuracy) * 100).toFixed(1) : "0.0";
                        const newLog: NeuralLog = {
                            id: Math.random().toString(36).substring(7),
                            timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
                            type: 'ALERT',
                            message: `[DRIFT] ${levelIcon} ${drift.drift_level}: PSI=${psi} | Acc=${acc}% | ${drift.recommendation ?? 'Analizando...'}`
                        };
                        return { neuralLogs: [newLog, ...state.neuralLogs].slice(0, 5) };
                    });
                } else if (data.type === 'news_update') {
                    const newsItem = data.data as NewsItem;
                    set((state) => {
                        // Anti-duplicados (por ID o título estricto)
                        const exists = state.news.some(n => 
                            n.id === newsItem.id || 
                            n.title === newsItem.title
                        );
                        if (exists) return state; // Ignorar si ya existe
                        
                        return { news: [newsItem, ...state.news].slice(0, 15) }; // Mantener un feed denso y corporativo (max 15)
                    });
                } else if (data.type === 'liquidation_update') {
                    set({ liquidations: data.data as LiquidationCluster[] });
                } else if (data.type === 'onchain_update') {
                    const metrics = data.data as OnChainMetrics;
                    if (metrics && metrics.symbol === get().activeSymbol) {
                        set({ onchainMetrics: metrics });
                    }
                }
            } catch (err) {
                console.error("❌ [WS-HANDLER] Critical error:", {
                    error: err instanceof Error ? err.message : err,
                    stack: err instanceof Error ? err.stack : null,
                    messageType: data?.type,
                    payload: data?.data
                });
            }
        };


        ws.onclose = (event) => {
            set({ isConnected: false });
            // ✅ FIX: Reconexión automática con exponential backoff
            // No reconectar si fue un cierre intencional (código 1000) o excedimos reintentos
            if (event.code !== 1000 && retryCount < MAX_RETRIES) {
                const delayMs = Math.pow(2, retryCount) * 2000; // 2s, 4s, 8s, 16s, 32s
                retryCount++;
                const { activeSymbol, activeTimeframe } = get();
                console.warn(`[WS] Conexión perdida. Reintento ${retryCount}/${MAX_RETRIES} en ${delayMs / 1000}s...`);
                retryTimeout = setTimeout(() => {
                    doConnect(activeSymbol, activeTimeframe, true);
                }, delayMs);
            }
        };

        ws.onerror = () => {
            set({ isConnected: false });
            // El evento 'close' se dispara inmediatamente después, que maneja el retry
        };
    };

    return {
        advisorLogs: {},
        isConnected: false,
        isCalibrating: true,

        activeSymbol: 'BTCUSDT',
        activeTimeframe: '15m',
        candles: [],
        latestPrice: null,
        latestPrices: {},
        mlProjection: { direction: 'CALIBRANDO', probability: 0 },
        neuralLogs: [],
        tacticalDecision: {
            regime: "DESCUBRIENDO...",
            strategy: "STANDBY",
            reasoning: "Inicializando motores de inferencia.",
            current_price: null,
            nearest_support: null,
            nearest_resistance: null,
            signals: [],
            key_levels: { resistances: [], supports: [] }
        },
        smcData: null,
        sessionData: null,
        ghostData: null,
        htfBias: null,
        news: [],
        liquidations: [],
        economicEvents: [],
        marketSummary: {},
        liquidityHeatmap: null,
        ...(() => {
            const initialSignals = typeof window !== 'undefined' ? _loadSignalHistory() : { data: {}, ids: [] };
            return {
                signalHistory: initialSignals.data,
                signalIds: initialSignals.ids
            };
        })(),
        auditedSignals: {},
        auditedIds: [],
        activeConnectionId: null,
        onchainMetrics: null,
        viewMode: 'SYMBOL',

        hydrateSignals: (signals: Signal[]) => {
            set((state) => {
                const { data, ids } = _mergeSignals(state.signalHistory, state.signalIds, signals);
                return { 
                    signalHistory: data, 
                    signalIds: ids 
                };
            });
        },

        connect: (symbol: string, timeframe?: Timeframe) => {
            const tf = timeframe ?? get().activeTimeframe;
            if (typeof window !== 'undefined') {
                localStorage.setItem('slingshot_symbol', symbol);
                localStorage.setItem('slingshot_timeframe', tf);
            }
            doConnect(symbol, tf);
        },

        setTimeframe: (tf: Timeframe) => {
            const symbol = get().activeSymbol;
            if (typeof window !== 'undefined') {
                localStorage.setItem('slingshot_timeframe', tf);
            }
            doConnect(symbol, tf);
        },

        disconnect: () => {
            if (ws) {
                ws.close();
                ws = null;
            }
        },

        setNews: (newsItems: NewsItem[]) => {
            set({ news: newsItems.slice(0, 15) }); // Mantener el límite visual de 15 noticias corporativas
        },

        setViewMode: (mode: 'SYMBOL' | 'GLOBAL') => {
            set({ viewMode: mode });
        },

        fetchEconomicEvents: async () => {
            try {
                const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
                const res = await fetch(`${BASE_URL}/api/v1/calendar`);
                if (res.ok) {
                    const data = await res.json();
                    
                    // Handle different API response formats (Direct Array or Wrapped)
                    let events: EconomicEvent[] = [];
                    if (Array.isArray(data)) {
                        events = data;
                    } else if (data && Array.isArray(data.value)) {
                        events = data.value;
                    } else if (data && Array.isArray(data.data)) {
                        events = data.data;
                    }

                    if (events.length > 0 || Array.isArray(data)) {
                        set({ economicEvents: events });
                    }
                }
            } catch (e) {
                console.error("Failed to fetch economic events:", e);
            }
        },

        clearSignalHistory: () => {
            localStorage.removeItem('slingshot_signal_history_v2');
            set({
                signalHistory: {},
                signalIds: [],
                auditedSignals: {},
                auditedIds: []
            });
            console.log("🧹 Signal history and localStorage cleared.");
        }
    };
});

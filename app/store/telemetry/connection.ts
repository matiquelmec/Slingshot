import { TelemetryState, Timeframe } from './types';
import { handleWsMessage } from './handlers';
import { MAX_RETRIES } from './constants';
import { getApiBaseUrl, getWsBaseUrl } from '../../utils/apiUrl';

export const createConnectionManager = (set: any, get: any) => {
    let ws: WebSocket | null = null;
    let retryCount = 0;
    let retryTimeout: any = null;
    let watchdogInterval: any = null;

    const doConnect = async (symbol: string, timeframe: Timeframe, isRetry = false) => {
        const connectionId = Math.random().toString(36).substring(7);

        if (ws) {
            ws.onclose = null;
            ws.onerror = null;
            ws.onmessage = null;
            try { ws.close(1000); } catch (e) {}
            ws = null;
        }
        if (retryTimeout) clearTimeout(retryTimeout);
        if (watchdogInterval) clearInterval(watchdogInterval);

        const BASE_URL = getApiBaseUrl();
        const BASE_WS = getWsBaseUrl();
        const clean = symbol.replace(/[\s\/]/g, '').toUpperCase();

        if (!isRetry) {
            retryCount = 0;
            set((state: any) => ({
                activeSymbol: symbol,
                activeTimeframe: timeframe,
                activeConnectionId: connectionId,
                isConnected: false,
                connectionStatus: 'CONNECTING',
                isCalibrating: true,
                mlProjection: { direction: 'NEUTRAL', probability: 50, reason: `Sincronizando ${symbol}...` },
                tacticalDecision: {
                    ...state.tacticalDecision,
                    regime: "SINCRONIZANDO...",
                    strategy: "STANDBY",
                    reasoning: `Cargando telemetría de alta velocidad para ${symbol} (${timeframe}).`,
                },
            }));
        } else {
            set({ activeConnectionId: connectionId });
        }

        // 🚀 [REST FAST HYDRATION] Carga inmediata de todos los módulos
        const fetchInitialData = async () => {
            try {
                // 1. Ghost & Macro
                fetch(`${BASE_URL}/api/v1/ghost`)
                    .then(r => r.json())
                    .then(data => { if (data?.ghost) set({ ghostData: data.ghost }); })
                    .catch(() => {});

                // 2. [FAST DIAGNOSTIC] Retina Técnica, SMC, Niveles, Sesiones, Velas y Heatmap
                const diagRes = await fetch(`${BASE_URL}/api/v1/diagnostic/${clean}?timeframe=${timeframe}`);
                if (diagRes.ok) {
                    const diag = await diagRes.json();
                    if (diag && !diag.error) {
                        const newCandles = Array.isArray(diag.candles) && diag.candles.length > 0 ? diag.candles : [];
                        const latestCandlePrice = newCandles.length > 0 ? Number(newCandles[newCandles.length - 1].close) : null;
                        
                        set((state: any) => ({
                            isCalibrating: false,
                            isConnected: true, // Gráfico desbloqueado de inmediato
                            connectionStatus: 'CONNECTED',
                            ...(newCandles.length > 0 ? {
                                candles: newCandles,
                                latestPrice: latestCandlePrice ?? state.latestPrice,
                                latestPrices: { ...state.latestPrices, [clean]: latestCandlePrice ?? state.latestPrices[clean] }
                            } : {}),
                            tacticalDecision: diag.tactical ? {
                                ...state.tacticalDecision,
                                asset: clean,
                                regime: diag.tactical.market_regime ?? 'UNKNOWN',
                                strategy: diag.tactical.active_strategy ?? 'STANDBY',
                                reasoning: `Régimen: ${diag.tactical.market_regime || 'NEUTRAL'}. Soportes mapeados.`,
                                current_price: diag.tactical.current_price ?? latestCandlePrice ?? state.latestPrice,
                                signal_history: diag.tactical.signals ?? [],
                                ...diag.tactical
                            } : state.tacticalDecision,
                            smcData: diag.smc ?? state.smcData,
                            sessionData: diag.sessions ? {
                                ...diag.sessions,
                                asset: clean
                            } : state.sessionData,
                            mlProjection: diag.ml_projection ?? state.mlProjection,
                            htfBias: diag.htf_bias ?? state.htfBias,
                            ...(diag.liquidity_heatmap ? { liquidityHeatmap: diag.liquidity_heatmap } : {})
                        }));
                    }
                }

                // 3. Liquidaciones
                fetch(`${BASE_URL}/api/v1/liquidations/${clean}`)
                    .then(r => r.json())
                    .then(data => {
                        if (Array.isArray(data) && data.length > 0) {
                            set({ liquidations: data });
                        }
                    })
                    .catch(() => {});

                // 4. Heatmap dedicado si no venía en diagnostic
                if (!get().liquidityHeatmap) {
                    fetch(`${BASE_URL}/api/v1/heatmap/${clean}`)
                        .then(r => r.json())
                        .then(data => {
                            if (data && (data.bids || data.hot_bids)) {
                                set({ liquidityHeatmap: data });
                            }
                        })
                        .catch(() => {});
                }

                // 5. Radar Market States
                fetch(`${BASE_URL}/api/v1/market-states`)
                    .then(r => r.json())
                    .then(statesData => {
                        if (Array.isArray(statesData)) {
                            const newSummary: Record<string, any> = {};
                            const newPrices: Record<string, number | null> = {};
                            statesData.forEach((s: any) => {
                                const asset = s.asset;
                                newSummary[asset] = s;
                                const p = s.price ?? s.current_price ?? s.close ?? s.latest_price;
                                if (p) newPrices[asset] = Number(p);
                            });
                            set((state: any) => ({ 
                                marketSummary: { ...state.marketSummary, ...newSummary },
                                latestPrices: { ...state.latestPrices, ...newPrices },
                                latestPrice: newPrices[clean] ?? state.latestPrice
                            }));
                        }
                    })
                    .catch(() => {});

                // 6. Noticias y Calendario
                if (get().news.length === 0) {
                    fetch(`${BASE_URL}/api/v1/news`)
                        .then(res => res.json())
                        .then(data => { if (Array.isArray(data)) set({ news: data.slice(0, 15) }); })
                        .catch(() => {});
                }
                if (get().economicEvents.length === 0) {
                    get().fetchEconomicEvents();
                }

            } catch (err) {
                console.warn('[TELEMETRY] ⚠️ Error en hidratación inicial:', err);
            }
        };

        // Ejecutar carga REST inicial
        await fetchInitialData();

        // ── Iniciar bucle continuo REST (1.5s) como columna vertebral ──
        let pollCycle = 0;
        const startRestPolling = () => {
            if (watchdogInterval) clearInterval(watchdogInterval);
            watchdogInterval = setInterval(async () => {
                if (connectionId !== get().activeConnectionId) return;
                pollCycle++;
                try {
                    const pollRes = await fetch(`${BASE_URL}/api/v1/diagnostic/${clean}?timeframe=${timeframe}`);
                    if (pollRes.ok) {
                        const diag = await pollRes.json();
                        if (diag && !diag.error) {
                            const newCandles = Array.isArray(diag.candles) && diag.candles.length > 0 ? diag.candles : null;
                            const latestCandlePrice = newCandles && newCandles.length > 0 ? Number(newCandles[newCandles.length - 1].close) : null;
                            
                            set((state: any) => ({
                                isCalibrating: false,
                                isConnected: true,
                                connectionStatus: 'CONNECTED',
                                ...(newCandles ? {
                                    candles: newCandles,
                                    latestPrice: latestCandlePrice ?? state.latestPrice,
                                    latestPrices: { ...state.latestPrices, [clean]: latestCandlePrice ?? state.latestPrices[clean] }
                                } : {}),
                                tacticalDecision: diag.tactical ? {
                                    ...state.tacticalDecision,
                                    asset: clean,
                                    regime: diag.tactical.market_regime ?? state.tacticalDecision.regime,
                                    strategy: diag.tactical.active_strategy ?? state.tacticalDecision.strategy,
                                    current_price: diag.tactical.current_price ?? latestCandlePrice ?? state.latestPrice,
                                    ...diag.tactical
                                } : state.tacticalDecision,
                                smcData: diag.smc ?? state.smcData,
                                sessionData: diag.sessions ? { ...diag.sessions, asset: clean } : state.sessionData,
                                mlProjection: diag.ml_projection ?? state.mlProjection,
                                htfBias: diag.htf_bias ?? state.htfBias,
                                ...(diag.liquidity_heatmap ? { liquidityHeatmap: diag.liquidity_heatmap } : {})
                            }));
                        }
                    }

                    // Cada 4 ciclos (~6s): actualizar liquidaciones y ghost
                    if (pollCycle % 4 === 0) {
                        fetch(`${BASE_URL}/api/v1/liquidations/${clean}`)
                            .then(r => r.json())
                            .then(data => { if (Array.isArray(data) && data.length > 0) set({ liquidations: data }); })
                            .catch(() => {});

                        fetch(`${BASE_URL}/api/v1/ghost`)
                            .then(r => r.json())
                            .then(data => { if (data?.ghost) set({ ghostData: data.ghost }); })
                            .catch(() => {});
                    }
                } catch (e) {}
            }, 1500);
        };

        // Si no hay WebSocket configurado (HTTPS / Vercel), operar exclusivamente en REST Ultra-Fast
        if (!BASE_WS || !BASE_WS.startsWith('ws')) {
            console.log("🌐 [TELEMETRY] Modo Ultra-Fast REST Polling activo (Vercel HTTPS).");
            set({ isConnected: true, connectionStatus: 'CONNECTED', connectionMode: 'REST' });
            startRestPolling();
            return;
        }

        // Si hay WebSocket disponible (ej: localhost o proxy WSS), intentar conexión WS
        const SECURITY_KEY = process.env.NEXT_PUBLIC_SECURITY_KEY ?? 'SLINGSHOT_INTERNAL_V6';
        try {
            const tokenRes = await fetch(`${BASE_URL}/api/v1/auth/token?api_key=${SECURITY_KEY}`);
            const tokenData = await tokenRes.json();
            if (!tokenData.token) throw new Error("No token");

            if (connectionId !== get().activeConnectionId) return;

            ws = new WebSocket(`${BASE_WS}/api/v1/stream/${symbol}?interval=${timeframe}&token=${tokenData.token}`);
            let lastMsgTimestamp = Date.now();
            let context = { connectionId, lastMsgTimestamp, staleGuardActive: false };

            ws.onopen = () => {
                set({ isConnected: true, connectionStatus: 'CONNECTED', connectionMode: 'WS' });
            };

            ws.onmessage = (e) => handleWsMessage(e, set, get, context);

            ws.onclose = (event) => {
                console.warn("[WS] Desconectado, activando respaldo continuo REST.");
                startRestPolling();
            };

            ws.onerror = () => {
                console.warn("[WS] Error de socket, asegurando telemetría REST.");
                startRestPolling();
            };

        } catch (error) {
            console.warn("[WS] No disponible, operando en REST continuo:", error);
            startRestPolling();
        }
    };

    return {
        doConnect,
        disconnect: () => {
            if (ws) {
                ws.onclose = null;
                ws.onerror = null;
                ws.onmessage = null;
                try { ws.close(); } catch (e) {}
                ws = null;
            }
            if (watchdogInterval) {
                clearInterval(watchdogInterval);
                watchdogInterval = null;
            }
        }
    };
};

import { TelemetryState, Timeframe } from './types';
import { handleWsMessage } from './handlers';
import { MAX_RETRIES } from './constants';
import { getApiBaseUrl, getWsBaseUrl } from '../../utils/apiUrl';

export const createConnectionManager = (set: any, get: any) => {
    let ws: WebSocket | null = null;
    let retryCount = 0;
    let retryTimeout: any = null;
    let watchdogInterval: any = null;

    const doConnect = async (rawSymbol: string, timeframe: Timeframe, isRetry = false) => {
        const connectionId = Math.random().toString(36).substring(7);
        const symbol = rawSymbol === 'PAXGUSDT' ? 'XAUUSDT' : rawSymbol;

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
                activeSymbol: clean,
                activeTimeframe: timeframe,
                activeConnectionId: connectionId,
                isConnected: state.isConnected,
                connectionStatus: state.isConnected ? 'CONNECTED' : 'CONNECTING',
                isCalibrating: !state.marketSummary?.[clean],
                mlProjection: state.mlProjection?.direction && state.mlProjection.direction !== 'CALIBRANDO'
                    ? state.mlProjection
                    : { direction: 'NEUTRAL', probability: 50, reason: `Sincronizando ${clean}...` },
                tacticalDecision: {
                    ...state.tacticalDecision,
                    regime: state.marketSummary?.[clean]?.regime || "SINCRONIZANDO...",
                    strategy: state.marketSummary?.[clean]?.strategy || "STANDBY",
                    reasoning: `Cargando telemetría institucional para ${clean} (${timeframe}).`,
                },
            }));
        } else {
            set({ activeConnectionId: connectionId });
        }

        const hydrateMarketStates = async () => {
            try {
                const res = await fetch(`${BASE_URL}/api/v1/market-states`);
                if (!res.ok) return;
                const statesData = await res.json();
                if (Array.isArray(statesData) && statesData.length > 0) {
                    const newSummary: Record<string, any> = {};
                    const newPrices: Record<string, number | null> = {};
                    statesData.forEach((s: any) => {
                        const asset = s.asset;
                        if (!asset) return;
                        newSummary[asset] = s;
                        const p = s.price ?? s.current_price ?? s.close ?? s.latest_price;
                        if (p && Number(p) > 0) {
                            newPrices[asset] = Number(p);
                        }
                    });
                    const activeState = newSummary[clean];
                    set((state: any) => ({
                        isConnected: true,
                        isCalibrating: false,
                        connectionStatus: 'CONNECTED',
                        marketSummary: { ...state.marketSummary, ...newSummary },
                        latestPrices: { ...state.latestPrices, ...newPrices },
                        latestPrice: newPrices[clean] ?? state.latestPrice,
                        ...(activeState?.session_state && !state.sessionData ? {
                            sessionData: { ...activeState.session_state, asset: clean }
                        } : {}),
                        ...(activeState && (!state.tacticalDecision?.current_price) ? {
                            tacticalDecision: {
                                ...state.tacticalDecision,
                                asset: clean,
                                regime: activeState.regime || state.tacticalDecision?.regime || 'ACTIVE',
                                strategy: activeState.strategy || state.tacticalDecision?.strategy || 'SMC INSTITUTIONAL',
                                current_price: newPrices[clean] ?? state.latestPrice,
                            }
                        } : {})
                    }));
                }
            } catch (e) {}
        };

        const hydrateDiagnostic = async () => {
            try {
                const diagRes = await fetch(`${BASE_URL}/api/v1/diagnostic/${clean}?timeframe=${timeframe}`);
                if (!diagRes.ok) return;
                const diag = await diagRes.json();
                if (diag && !diag.error) {
                    const newCandles = Array.isArray(diag.candles) && diag.candles.length > 0 ? diag.candles : [];
                    const latestCandlePrice = newCandles.length > 0 ? Number(newCandles[newCandles.length - 1].close) : null;

                    set((state: any) => ({
                        isCalibrating: false,
                        isConnected: true,
                        connectionStatus: 'CONNECTED',
                        ...(newCandles.length > 0 ? {
                            candles: newCandles,
                            latestPrice: latestCandlePrice ?? state.latestPrice,
                            latestPrices: { ...state.latestPrices, [clean]: latestCandlePrice ?? state.latestPrices[clean] }
                        } : {}),
                        tacticalDecision: diag.tactical ? {
                            ...state.tacticalDecision,
                            asset: clean,
                            regime: diag.tactical.market_regime ?? state.tacticalDecision?.regime ?? 'ACTIVE',
                            strategy: diag.tactical.active_strategy ?? state.tacticalDecision?.strategy ?? 'SMC INSTITUTIONAL',
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
                        advisorLogs: diag.advisor_log ? { ...state.advisorLogs, [clean]: diag.advisor_log } : state.advisorLogs,
                        htfBias: diag.htf_bias ?? state.htfBias,
                        ...(diag.liquidity_heatmap ? { liquidityHeatmap: diag.liquidity_heatmap } : {})
                    }));
                }
            } catch (e) {}
        };

        // 🚀 [PARALLEL REST FAST HYDRATION] Carga simultánea sin bloqueo en serie
        const fetchInitialData = async () => {
            try {
                await Promise.allSettled([
                    hydrateMarketStates(),
                    hydrateDiagnostic(),
                    fetch(`${BASE_URL}/api/v1/ghost`)
                        .then(r => r.json())
                        .then(data => { if (data?.ghost) set({ ghostData: data.ghost }); })
                        .catch(() => {}),
                    fetch(`${BASE_URL}/api/v1/liquidations/${clean}`)
                        .then(r => r.json())
                        .then(data => {
                            if (Array.isArray(data) && data.length > 0) {
                                set({ liquidations: data });
                            }
                        })
                        .catch(() => {})
                ]);

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
                console.warn('[TELEMETRY] Error en hidratación inicial:', err);
            }
        };

        // ── Iniciar bucle continuo REST (1.5s) como columna vertebral ──
        let pollCycle = 0;
        const startRestPolling = () => {
            if (watchdogInterval) clearInterval(watchdogInterval);
            watchdogInterval = setInterval(async () => {
                if (connectionId !== get().activeConnectionId) return;
                pollCycle++;
                try {
                    await hydrateDiagnostic();

                    // Cada 2 ciclos (~3s) o si el resumen de mercado está vacío: sincronizar los 13 activos
                    if (pollCycle % 2 === 0 || Object.keys(get().marketSummary || {}).length === 0) {
                        await hydrateMarketStates();
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

        // Arrancar el polling de respaldo inmediatamente y disparar la hidratación paralela
        startRestPolling();
        await fetchInitialData();

        // Si no hay WebSocket configurado (HTTPS / Vercel), operar exclusivamente en REST Ultra-Fast
        if (!BASE_WS || !BASE_WS.startsWith('ws')) {
            set({ isConnected: true, connectionStatus: 'CONNECTED', connectionMode: 'REST' });
            return;
        }

        // Si hay WebSocket disponible, conectar WS manteniendo el respaldo REST
        const SECURITY_KEY = process.env.NEXT_PUBLIC_SECURITY_KEY ?? 'SLINGSHOT_INTERNAL_V6';
        try {
            const tokenRes = await fetch(`${BASE_URL}/api/v1/auth/token?api_key=${SECURITY_KEY}`);
            const tokenData = await tokenRes.json();
            if (!tokenData.token) throw new Error("No token");

            if (connectionId !== get().activeConnectionId) return;

            ws = new WebSocket(`${BASE_WS}/api/v1/stream/${clean}?interval=${timeframe}&token=${tokenData.token}`);
            const lastMsgTimestamp = Date.now();
            const context = { connectionId, lastMsgTimestamp, staleGuardActive: false };

            ws.onopen = () => {
                set({ isConnected: true, connectionStatus: 'CONNECTED', connectionMode: 'WS' });
            };

            ws.onmessage = (e) => handleWsMessage(e, set, get, context);

            ws.onclose = () => {
                startRestPolling();
            };

            ws.onerror = () => {
                startRestPolling();
            };

        } catch (error) {
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

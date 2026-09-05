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
            ws.close(1000);
            ws = null;
        }
        if (retryTimeout) clearTimeout(retryTimeout);
        if (watchdogInterval) clearInterval(watchdogInterval);

        const BASE_URL = getApiBaseUrl();
        const BASE_WS = getWsBaseUrl();

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

            // Rest Hydration
            // 🚀 [PLATINUM HYDRATION] Carga inmediata vía REST para evitar delay de WS
            const fetchInitialData = async () => {
                try {
                    const clean = symbol.replace(/[\s\/]/g, '').toUpperCase();
                    
                    // 1. Ghost & Macro
                    const ghostRes = await fetch(`${BASE_URL}/api/v1/ghost`);
                    if (ghostRes.ok) {
                        const ghostData = await ghostRes.json();
                        if (ghostData.ghost) set({ ghostState: ghostData.ghost });
                        if (ghostData.macro) set({ macroContext: ghostData.macro });
                    }

                    // 2. [NEW] Sessions Recovery Path
                    const sessionRes = await fetch(`${BASE_URL}/api/v1/sessions/${clean}`);
                    if (sessionRes.ok) {
                        const sessionData = await sessionRes.json();
                        if (sessionData && sessionData.data) {
                            console.log(`[TELEMETRY] 📥 Hidratación REST exitosa para ${clean}`);
                            set({ sessionData: sessionData.data });
                        }
                    }

                    // 3. [NEW] Radar Market States Recovery Path
                    const statesRes = await fetch(`${BASE_URL}/api/v1/market-states`);
                    if (statesRes.ok) {
                        const statesData = await statesRes.json();
                        if (Array.isArray(statesData)) {
                            const newSummary: Record<string, any> = {};
                            const newPrices: Record<string, number | null> = {};
                            statesData.forEach((s: any) => {
                                const asset = s.asset;
                                newSummary[asset] = s;
                                const p = s.price ?? s.current_price ?? s.close ?? s.latest_price;
                                if (p) {
                                    newPrices[asset] = Number(p);
                                }
                            });
                            set((state: any) => ({ 
                                marketSummary: { ...state.marketSummary, ...newSummary },
                                latestPrices: { ...state.latestPrices, ...newPrices },
                                latestPrice: newPrices[clean] ?? state.latestPrice
                            }));
                        }
                    }
                } catch (err) {
                    console.warn('[TELEMETRY] ⚠️ Error en hidratación inicial:', err);
                }
            };

            fetchInitialData();

            if (get().news.length === 0) {
                fetch(`${BASE_URL}/api/v1/news`)
                    .then(res => res.json())
                    .then(data => {
                        if (Array.isArray(data)) set({ news: data.slice(0, 15) });
                    }).catch(e => console.warn("🌐 [TELEMETRY] News fetch failed:", e));
            }

            if (get().economicEvents.length === 0) {
                get().fetchEconomicEvents();
            }
        } else {
            set({ activeConnectionId: connectionId });
        }

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
                set({ isConnected: true, connectionStatus: 'CONNECTED' });
                watchdogInterval = setInterval(() => {
                    const gap = Date.now() - context.lastMsgTimestamp;
                    if (gap > 15_000) set({ connectionStatus: 'DISCONNECTED' });
                    else if (gap > 5_000) set({ connectionStatus: 'STALLED' });
                    else set({ connectionStatus: 'CONNECTED' });
                }, 1000);
            };

            ws.onmessage = (e) => handleWsMessage(e, set, get, context);

            ws.onclose = (event) => {
                set({ isConnected: false });
                if (event.code !== 1000 && retryCount < MAX_RETRIES) {
                    const delay = Math.pow(2, retryCount) * 2000;
                    retryCount++;
                    retryTimeout = setTimeout(() => doConnect(get().activeSymbol, get().activeTimeframe, true), delay);
                }
            };

            ws.onerror = () => set({ isConnected: false });

        } catch (error) {
            console.error("[AUTH] WS connection failed:", error);
            if (retryCount < MAX_RETRIES) {
                const delay = Math.pow(2, retryCount) * 2000;
                retryCount++;
                retryTimeout = setTimeout(() => doConnect(get().activeSymbol, get().activeTimeframe, true), delay);
            }
        }
    };

    return {
        doConnect,
        disconnect: () => {
            if (ws) {
                ws.onclose = null;
                ws.close();
                ws = null;
            }
        }
    };
};

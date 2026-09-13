import { create } from 'zustand';
import { TelemetryState, Timeframe } from './types';
import { initialState } from './initialState';
import { mergeSignals } from './storage';
import { createConnectionManager } from './connection';
import { Signal, NewsItem } from '../../types/signal';
import { getApiBaseUrl } from '../../utils/apiUrl';

export const useTelemetryStore = create<TelemetryState>((set, get) => {
    const connectionManager = createConnectionManager(set, get);

    return {
        ...initialState,

        connect: (symbol: string, timeframe?: Timeframe) => {
            const tf = timeframe ?? get().activeTimeframe;
            if (typeof window !== 'undefined') {
                localStorage.setItem('slingshot_symbol', symbol);
                localStorage.setItem('slingshot_timeframe', tf);
            }
            connectionManager.doConnect(symbol, tf);
        },

        disconnect: () => {
            connectionManager.disconnect();
        },

        setTimeframe: (tf: Timeframe) => {
            const symbol = get().activeSymbol;
            if (typeof window !== 'undefined') {
                localStorage.setItem('slingshot_timeframe', tf);
            }
            connectionManager.doConnect(symbol, tf);
        },

        setNews: (newsItems: NewsItem[]) => {
            set({ news: newsItems.slice(0, 15) });
        },

        setViewMode: (mode: 'SYMBOL' | 'GLOBAL') => {
            set({ viewMode: mode });
        },

        hydrateSignals: (signals: Signal[]) => {
            set((state) => {
                const { data, ids } = mergeSignals(state.signalHistory, state.signalIds, signals);
                return { signalHistory: data, signalIds: ids };
            });
        },

        fetchEconomicEvents: async (retries = 3) => {
            const BASE_URL = getApiBaseUrl();
            const endpoint = `${BASE_URL}/api/v1/calendar`;
            
            for (let attempt = 1; attempt <= retries; attempt++) {
                try {
                    const res = await fetch(endpoint);
                    if (!res.ok) {
                        throw new Error(`HTTP ${res.status} - ${res.statusText}`);
                    }
                    
                    const data = await res.json();
                    let events = Array.isArray(data) ? data : (data.value || data.data || []);
                    if (events && events.length > 0) {
                        set({ economicEvents: events });
                    }
                    return; // Éxito, salir del loop
                } catch (e: any) {
                    if (attempt < retries) {
                        // Backoff exponencial: 1s, 2s...
                        await new Promise(r => setTimeout(r, attempt * 1000));
                    } else {
                        console.warn("🌐 [TELEMETRY] Calendario económico no disponible temporalmente:", e.message || e);
                    }
                }
            }
        },

        clearSignalHistory: () => {
            if (typeof window !== 'undefined') {
                localStorage.removeItem('slingshot_signal_history_v2');
            }
            set({ signalHistory: {}, signalIds: [] });
        }
    };
});

export * from './types';

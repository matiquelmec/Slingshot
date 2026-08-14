import { create } from 'zustand';
import { TelemetryState, Timeframe } from './types';
import { initialState } from './initialState';
import { mergeSignals } from './storage';
import { createConnectionManager } from './connection';
import { Signal, NewsItem } from '../../types/signal';

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

        fetchEconomicEvents: async () => {
            try {
                const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
                const endpoint = `${BASE_URL.replace(/\/$/, '')}/api/v1/calendar`;
                
                const res = await fetch(endpoint);
                if (!res.ok) {
                    throw new Error(`HTTP Error: ${res.status} - ${res.statusText}`);
                }
                
                const data = await res.json();
                let events = Array.isArray(data) ? data : (data.value || data.data || []);
                if (events && events.length > 0) {
                    set({ economicEvents: events });
                }
            } catch (e: any) {
                console.error("🌐 [TELEMETRY] Failed to fetch economic events:", e.message || e);
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

import { TelemetryState } from './types';
import { loadSignalHistory } from './storage';

const initialSignals = loadSignalHistory();

export const initialState: Omit<TelemetryState, 'connect' | 'disconnect' | 'setTimeframe' | 'setNews' | 'setViewMode' | 'hydrateSignals' | 'fetchEconomicEvents' | 'clearSignalHistory'> = {
    advisorLogs: {},
    isConnected: false,
    connectionStatus: 'DISCONNECTED',
    connectionMode: 'WS',
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
    signalHistory: initialSignals.data,
    signalIds: initialSignals.ids,
    auditedSignals: {},
    auditedIds: [],
    activeConnectionId: null,
    onchainMetrics: null,
    viewMode: 'SYMBOL',
};
